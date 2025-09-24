"""
Performance Profiler
Advanced profiling utilities with execution timing, memory tracking, and performance analysis
@module dafelhub.monitoring.profiler
"""

import time
import threading
import asyncio
import functools
import cProfile
import pstats
import traceback
import psutil
import gc
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Union, Tuple, ContextManager
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from pathlib import Path
import json
import io

from .logger import Logger, LogContext, get_logger
from .metrics_collector import MetricsCollector, get_metrics_collector


@dataclass
class PerformanceSnapshot:
    """Performance metrics snapshot"""
    timestamp: float
    cpu_percent: float
    memory_rss: int  # MB
    memory_vms: int  # MB
    memory_percent: float
    thread_count: int
    open_files: int
    network_connections: int


@dataclass
class ProfileResult:
    """Profiling result with detailed metrics"""
    name: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    error: Optional[str] = None
    memory_delta: Optional[int] = None  # MB
    cpu_time: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    snapshots: List[PerformanceSnapshot] = None
    call_stats: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['snapshots'] = [asdict(snap) for snap in (self.snapshots or [])]
        return data


class ProfilerStats:
    """Collect and analyze profiling statistics"""
    
    def __init__(self, max_results: int = 1000):
        self.max_results = max_results
        self.results: deque = deque(maxlen=max_results)
        self.stats_by_name: Dict[str, List[ProfileResult]] = defaultdict(list)
        self.lock = threading.Lock()
    
    def add_result(self, result: ProfileResult):
        """Add profiling result"""
        with self.lock:
            self.results.append(result)
            self.stats_by_name[result.name].append(result)
            
            # Keep only recent results per name
            if len(self.stats_by_name[result.name]) > 100:
                self.stats_by_name[result.name] = self.stats_by_name[result.name][-100:]
    
    def get_summary(self, name: str = None) -> Dict[str, Any]:
        """Get performance summary statistics"""
        with self.lock:
            if name:
                results = self.stats_by_name.get(name, [])
            else:
                results = list(self.results)
        
        if not results:
            return {"error": "No profiling data available"}
        
        durations = [r.duration for r in results if r.success]
        memory_deltas = [r.memory_delta for r in results if r.memory_delta is not None]
        
        summary = {
            "name": name or "all",
            "total_calls": len(results),
            "successful_calls": len([r for r in results if r.success]),
            "failed_calls": len([r for r in results if not r.success]),
            "success_rate": len([r for r in results if r.success]) / len(results) * 100 if results else 0
        }
        
        if durations:
            summary.update({
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "p50_duration": sorted(durations)[len(durations)//2] if durations else 0,
                "p95_duration": sorted(durations)[int(len(durations)*0.95)] if durations else 0,
                "p99_duration": sorted(durations)[int(len(durations)*0.99)] if durations else 0
            })
        
        if memory_deltas:
            summary.update({
                "avg_memory_delta": sum(memory_deltas) / len(memory_deltas),
                "max_memory_delta": max(memory_deltas),
                "min_memory_delta": min(memory_deltas)
            })
        
        return summary
    
    def get_slowest_operations(self, limit: int = 10) -> List[ProfileResult]:
        """Get slowest operations"""
        with self.lock:
            successful_results = [r for r in self.results if r.success]
            return sorted(successful_results, key=lambda x: x.duration, reverse=True)[:limit]
    
    def get_memory_intensive_operations(self, limit: int = 10) -> List[ProfileResult]:
        """Get most memory intensive operations"""
        with self.lock:
            memory_results = [r for r in self.results if r.memory_delta is not None]
            return sorted(memory_results, key=lambda x: x.memory_delta or 0, reverse=True)[:limit]


class PerformanceProfiler:
    """
    Advanced Performance Profiler
    
    Features:
    - Function and method profiling with decorators
    - Context manager for code block profiling
    - Async/await support
    - Memory usage tracking
    - CPU profiling with call statistics
    - Real-time performance monitoring
    - Statistical analysis and reporting
    - Integration with logging and metrics
    """
    
    _instance: Optional['PerformanceProfiler'] = None
    _lock = threading.Lock()
    
    def __init__(self,
                 logger: Optional[Logger] = None,
                 metrics_collector: Optional[MetricsCollector] = None,
                 enable_memory_tracking: bool = True,
                 enable_cpu_profiling: bool = True,
                 snapshot_interval: float = 1.0):
        
        self.logger = logger or get_logger()
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.enable_memory_tracking = enable_memory_tracking
        self.enable_cpu_profiling = enable_cpu_profiling
        self.snapshot_interval = snapshot_interval
        
        self.stats = ProfilerStats()
        self.active_profiles: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
        # Register profiling metrics
        self._register_metrics()
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'PerformanceProfiler':
        """Get singleton instance with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance
    
    def _register_metrics(self):
        """Register profiling metrics with collector"""
        try:
            self.metrics_collector.register_metric(
                self.metrics_collector.__class__.get_metric("operations_total").__class__,
                "profile_operations_total",
                "Total profiled operations",
                ["operation", "status"]
            )
            
            self.metrics_collector.register_metric(
                self.metrics_collector.__class__.get_metric("operation_duration_seconds").__class__,
                "profile_duration_seconds",
                "Profiled operation duration",
                ["operation"]
            )
            
            self.metrics_collector.register_metric(
                self.metrics_collector.__class__.get_metric("system_memory_bytes").__class__, 
                "profile_memory_usage_bytes",
                "Memory usage during profiling",
                ["operation"]
            )
        except Exception as e:
            self.logger.debug(f"Could not register profiling metrics: {e}")
    
    def _get_performance_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot"""
        try:
            process = psutil.Process()
            memory = process.memory_info()
            
            return PerformanceSnapshot(
                timestamp=time.time(),
                cpu_percent=process.cpu_percent(),
                memory_rss=round(memory.rss / 1024 / 1024, 2),  # MB
                memory_vms=round(memory.vms / 1024 / 1024, 2),  # MB
                memory_percent=round(process.memory_percent(), 2),
                thread_count=process.num_threads(),
                open_files=len(process.open_files()),
                network_connections=len(process.connections())
            )
        except Exception:
            return PerformanceSnapshot(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_rss=0,
                memory_vms=0,
                memory_percent=0.0,
                thread_count=0,
                open_files=0,
                network_connections=0
            )
    
    @contextmanager
    def profile_context(self, 
                       name: str,
                       context: Optional[Dict[str, Any]] = None,
                       take_snapshots: bool = True) -> ContextManager[ProfileResult]:
        """Context manager for profiling code blocks"""
        profile_id = f"{name}_{time.time()}_{threading.current_thread().ident}"
        start_time = time.time()
        start_snapshot = None
        snapshots = []
        profiler = None
        error = None
        
        # Start CPU profiling if enabled
        if self.enable_cpu_profiling:
            profiler = cProfile.Profile()
            profiler.enable()
        
        # Take initial snapshot
        if take_snapshots and self.enable_memory_tracking:
            start_snapshot = self._get_performance_snapshot()
            snapshots.append(start_snapshot)
        
        # Store active profile info
        with self.lock:
            self.active_profiles[profile_id] = {
                "name": name,
                "start_time": start_time,
                "context": context
            }
        
        # Start background snapshot collection
        snapshot_task = None
        if take_snapshots and self.enable_memory_tracking:
            snapshot_task = self._start_snapshot_collection(profile_id, snapshots)
        
        try:
            result = ProfileResult(
                name=name,
                start_time=start_time,
                end_time=0,
                duration=0,
                success=False,
                context=context
            )
            yield result
            
            # Mark as successful if no exception
            result.success = True
            
        except Exception as e:
            error = str(e)
            result.success = False
            result.error = error
            raise
            
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Stop CPU profiling
            call_stats = None
            if profiler:
                profiler.disable()
                call_stats = self._extract_call_stats(profiler)
            
            # Stop snapshot collection
            if snapshot_task:
                snapshot_task.cancel()
            
            # Take final snapshot
            if take_snapshots and self.enable_memory_tracking:
                end_snapshot = self._get_performance_snapshot()
                snapshots.append(end_snapshot)
            
            # Calculate memory delta
            memory_delta = None
            if start_snapshot and len(snapshots) > 1:
                memory_delta = snapshots[-1].memory_rss - start_snapshot.memory_rss
            
            # Update result
            result.end_time = end_time
            result.duration = duration
            result.memory_delta = memory_delta
            result.snapshots = snapshots if take_snapshots else None
            result.call_stats = call_stats
            
            # Store result
            self.stats.add_result(result)
            
            # Clean up active profile
            with self.lock:
                self.active_profiles.pop(profile_id, None)
            
            # Log result
            log_context = LogContext(
                operation=name,
                duration=duration,
                status="success" if result.success else "failure",
                component="profiler"
            )
            if context:
                for key, value in context.items():
                    if hasattr(log_context, key):
                        setattr(log_context, key, value)
            
            if result.success:
                self.logger.debug(f"Profile complete: {name}", log_context)
            else:
                self.logger.error(f"Profile failed: {name}", log_context)
            
            # Record metrics
            self._record_metrics(result)
    
    async def _start_snapshot_collection(self, profile_id: str, snapshots: List[PerformanceSnapshot]):
        """Start background snapshot collection"""
        try:
            while profile_id in self.active_profiles:
                await asyncio.sleep(self.snapshot_interval)
                if profile_id in self.active_profiles:  # Check again after sleep
                    snapshot = self._get_performance_snapshot()
                    snapshots.append(snapshot)
        except asyncio.CancelledError:
            pass
    
    def _extract_call_stats(self, profiler: cProfile.Profile) -> Dict[str, Any]:
        """Extract call statistics from profiler"""
        try:
            stats_buffer = io.StringIO()
            stats = pstats.Stats(profiler, stream=stats_buffer)
            stats.sort_stats('cumulative')
            
            # Get top functions by cumulative time
            stats_data = []
            for func, (cc, nc, tt, ct, callers) in stats.stats.items():
                filename, line_num, func_name = func
                stats_data.append({
                    "function": f"{filename}:{line_num}({func_name})",
                    "call_count": cc,
                    "total_time": tt,
                    "cumulative_time": ct,
                    "per_call": ct / cc if cc > 0 else 0
                })
            
            # Sort by cumulative time and return top 20
            stats_data.sort(key=lambda x: x["cumulative_time"], reverse=True)
            
            return {
                "top_functions": stats_data[:20],
                "total_functions": len(stats_data),
                "total_calls": sum(item["call_count"] for item in stats_data)
            }
        except Exception as e:
            return {"error": f"Failed to extract call stats: {e}"}
    
    def _record_metrics(self, result: ProfileResult):
        """Record profiling metrics"""
        try:
            # Record operation count
            self.metrics_collector.inc_counter(
                "profile_operations_total",
                {"operation": result.name, "status": "success" if result.success else "failure"}
            )
            
            # Record duration
            if result.success:
                self.metrics_collector.observe_histogram(
                    "profile_duration_seconds",
                    {"operation": result.name},
                    result.duration
                )
            
            # Record memory usage
            if result.memory_delta is not None:
                self.metrics_collector.observe_histogram(
                    "profile_memory_usage_bytes", 
                    {"operation": result.name},
                    abs(result.memory_delta) * 1024 * 1024  # Convert MB to bytes
                )
        except Exception:
            pass  # Ignore metrics recording errors
    
    def profile_function(self,
                        name: Optional[str] = None,
                        take_snapshots: bool = True,
                        context: Optional[Dict[str, Any]] = None):
        """Decorator for profiling functions"""
        def decorator(func: Callable):
            profile_name = name or f"{func.__module__}.{func.__qualname__}"
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    with self.profile_context(profile_name, context, take_snapshots):
                        return await func(*args, **kwargs)
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.profile_context(profile_name, context, take_snapshots):
                        return func(*args, **kwargs)
                return sync_wrapper
        
        return decorator
    
    async def profile_async(self,
                           name: str,
                           coro_func: Callable,
                           context: Optional[Dict[str, Any]] = None,
                           take_snapshots: bool = True,
                           *args, **kwargs):
        """Profile async function execution"""
        with self.profile_context(name, context, take_snapshots) as result:
            return await coro_func(*args, **kwargs)
    
    def profile_sync(self,
                    name: str, 
                    func: Callable,
                    context: Optional[Dict[str, Any]] = None,
                    take_snapshots: bool = True,
                    *args, **kwargs):
        """Profile sync function execution"""
        with self.profile_context(name, context, take_snapshots) as result:
            return func(*args, **kwargs)
    
    def get_stats_summary(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get profiling statistics summary"""
        return self.stats.get_summary(name)
    
    def get_slowest_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest operations"""
        results = self.stats.get_slowest_operations(limit)
        return [result.to_dict() for result in results]
    
    def get_memory_intensive_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most memory intensive operations"""
        results = self.stats.get_memory_intensive_operations(limit)
        return [result.to_dict() for result in results]
    
    def get_active_profiles(self) -> List[Dict[str, Any]]:
        """Get currently active profiles"""
        with self.lock:
            current_time = time.time()
            active = []
            for profile_id, info in self.active_profiles.items():
                active.append({
                    "id": profile_id,
                    "name": info["name"],
                    "duration": current_time - info["start_time"],
                    "context": info.get("context")
                })
            return active
    
    def export_stats(self, format: str = "json") -> str:
        """Export profiling statistics"""
        data = {
            "timestamp": time.time(),
            "summary": self.get_stats_summary(),
            "slowest_operations": self.get_slowest_operations(20),
            "memory_intensive_operations": self.get_memory_intensive_operations(20),
            "active_profiles": self.get_active_profiles()
        }
        
        if format.lower() == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            return str(data)
    
    def clear_stats(self):
        """Clear all profiling statistics"""
        self.stats = ProfilerStats()
        with self.lock:
            self.active_profiles.clear()
    
    def benchmark(self,
                 name: str,
                 func: Callable,
                 iterations: int = 100,
                 warmup: int = 10,
                 context: Optional[Dict[str, Any]] = None,
                 *args, **kwargs) -> Dict[str, Any]:
        """Benchmark a function with multiple iterations"""
        
        # Warmup iterations
        for _ in range(warmup):
            try:
                func(*args, **kwargs)
            except Exception:
                pass
        
        # Force garbage collection
        gc.collect()
        
        results = []
        start_total = time.time()
        
        for i in range(iterations):
            with self.profile_context(f"{name}_benchmark_{i}", context, take_snapshots=False) as result:
                func(*args, **kwargs)
            results.append(result)
        
        end_total = time.time()
        
        # Calculate statistics
        durations = [r.duration for r in results if r.success]
        memory_deltas = [r.memory_delta for r in results if r.memory_delta is not None]
        
        benchmark_stats = {
            "name": name,
            "iterations": iterations,
            "warmup": warmup,
            "total_time": end_total - start_total,
            "successful_iterations": len(durations),
            "failed_iterations": iterations - len(durations)
        }
        
        if durations:
            durations.sort()
            benchmark_stats.update({
                "min_duration": min(durations),
                "max_duration": max(durations),
                "avg_duration": sum(durations) / len(durations),
                "median_duration": durations[len(durations)//2],
                "p95_duration": durations[int(len(durations) * 0.95)],
                "p99_duration": durations[int(len(durations) * 0.99)],
                "ops_per_second": len(durations) / (end_total - start_total)
            })
        
        if memory_deltas:
            benchmark_stats.update({
                "avg_memory_delta": sum(memory_deltas) / len(memory_deltas),
                "max_memory_delta": max(memory_deltas),
                "min_memory_delta": min(memory_deltas)
            })
        
        return benchmark_stats


# Global profiler instance
_global_profiler: Optional[PerformanceProfiler] = None


def get_profiler(**kwargs) -> PerformanceProfiler:
    """Get global profiler instance"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler.get_instance(**kwargs)
    return _global_profiler


# Convenience decorators
def profile(name: Optional[str] = None, 
           take_snapshots: bool = True,
           context: Optional[Dict[str, Any]] = None):
    """Decorator for profiling functions"""
    return get_profiler().profile_function(name, take_snapshots, context)


@contextmanager
def profile_block(name: str, 
                 context: Optional[Dict[str, Any]] = None,
                 take_snapshots: bool = True):
    """Context manager for profiling code blocks"""
    with get_profiler().profile_context(name, context, take_snapshots):
        yield