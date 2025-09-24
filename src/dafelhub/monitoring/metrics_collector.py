"""
Prometheus Metrics Collector
Enterprise-grade metrics collection with histograms, system monitoring, and custom metrics
@module dafelhub.monitoring.metrics_collector
"""

import time
import threading
import psutil
import socket
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import asyncio
from pathlib import Path


class MetricType(Enum):
    """Metric types compatible with Prometheus"""
    COUNTER = "counter"
    GAUGE = "gauge"  
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricDefinition:
    """Metric definition with metadata"""
    name: str
    help: str
    type: MetricType
    labels: List[str]
    unit: Optional[str] = None
    buckets: Optional[List[float]] = None
    quantiles: Optional[List[float]] = None


@dataclass
class MetricSample:
    """Individual metric sample"""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: float
    type: MetricType


class Counter:
    """Prometheus Counter metric - monotonically increasing"""
    
    def __init__(self, name: str, help: str, labels: List[str] = None):
        self.name = name
        self.help = help
        self.labels = labels or []
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def inc(self, labels: Dict[str, str] = None, value: float = 1.0):
        """Increment counter"""
        if value < 0:
            raise ValueError("Counter can only be incremented by non-negative values")
        
        label_key = self._get_label_key(labels or {})
        with self._lock:
            self._values[label_key] += value
    
    def get_value(self, labels: Dict[str, str] = None) -> float:
        """Get counter value"""
        label_key = self._get_label_key(labels or {})
        with self._lock:
            return self._values[label_key]
    
    def get_samples(self) -> List[MetricSample]:
        """Get all counter samples"""
        samples = []
        with self._lock:
            for label_key, value in self._values.items():
                labels = self._parse_label_key(label_key)
                samples.append(MetricSample(
                    name=self.name,
                    value=value,
                    labels=labels,
                    timestamp=time.time(),
                    type=MetricType.COUNTER
                ))
        return samples
    
    def _get_label_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dict to string key"""
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def _parse_label_key(self, label_key: str) -> Dict[str, str]:
        """Parse label key back to dict"""
        if not label_key:
            return {}
        return dict(item.split("=", 1) for item in label_key.split("|") if "=" in item)
    
    def reset(self):
        """Reset counter (for testing)"""
        with self._lock:
            self._values.clear()


class Gauge:
    """Prometheus Gauge metric - can go up and down"""
    
    def __init__(self, name: str, help: str, labels: List[str] = None):
        self.name = name
        self.help = help
        self.labels = labels or []
        self._values: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def set(self, labels: Dict[str, str] = None, value: float = 0.0):
        """Set gauge value"""
        label_key = self._get_label_key(labels or {})
        with self._lock:
            self._values[label_key] = value
    
    def inc(self, labels: Dict[str, str] = None, value: float = 1.0):
        """Increment gauge"""
        label_key = self._get_label_key(labels or {})
        with self._lock:
            self._values[label_key] += value
    
    def dec(self, labels: Dict[str, str] = None, value: float = 1.0):
        """Decrement gauge"""
        label_key = self._get_label_key(labels or {})
        with self._lock:
            self._values[label_key] -= value
    
    def get_value(self, labels: Dict[str, str] = None) -> float:
        """Get gauge value"""
        label_key = self._get_label_key(labels or {})
        with self._lock:
            return self._values[label_key]
    
    def get_samples(self) -> List[MetricSample]:
        """Get all gauge samples"""
        samples = []
        with self._lock:
            for label_key, value in self._values.items():
                labels = self._parse_label_key(label_key)
                samples.append(MetricSample(
                    name=self.name,
                    value=value,
                    labels=labels,
                    timestamp=time.time(),
                    type=MetricType.GAUGE
                ))
        return samples
    
    def _get_label_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dict to string key"""
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def _parse_label_key(self, label_key: str) -> Dict[str, str]:
        """Parse label key back to dict"""
        if not label_key:
            return {}
        return dict(item.split("=", 1) for item in label_key.split("|") if "=" in item)


class Histogram:
    """Prometheus Histogram metric - samples observations"""
    
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')]
    
    def __init__(self, name: str, help: str, labels: List[str] = None, buckets: List[float] = None):
        self.name = name
        self.help = help
        self.labels = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._buckets: Dict[str, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._counts: Dict[str, int] = defaultdict(int)
        self._sums: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def observe(self, labels: Dict[str, str] = None, value: float = 0.0):
        """Observe a value"""
        label_key = self._get_label_key(labels or {})
        with self._lock:
            self._counts[label_key] += 1
            self._sums[label_key] += value
            
            # Update buckets
            for bucket in self.buckets:
                if value <= bucket:
                    self._buckets[label_key][bucket] += 1
    
    def get_samples(self) -> List[MetricSample]:
        """Get all histogram samples"""
        samples = []
        with self._lock:
            for label_key in self._counts.keys():
                labels = self._parse_label_key(label_key)
                
                # Bucket samples
                for bucket, count in self._buckets[label_key].items():
                    bucket_labels = {**labels, "le": str(bucket) if bucket != float('inf') else "+Inf"}
                    samples.append(MetricSample(
                        name=f"{self.name}_bucket",
                        value=count,
                        labels=bucket_labels,
                        timestamp=time.time(),
                        type=MetricType.HISTOGRAM
                    ))
                
                # Count sample
                samples.append(MetricSample(
                    name=f"{self.name}_count",
                    value=self._counts[label_key],
                    labels=labels,
                    timestamp=time.time(),
                    type=MetricType.HISTOGRAM
                ))
                
                # Sum sample
                samples.append(MetricSample(
                    name=f"{self.name}_sum",
                    value=self._sums[label_key],
                    labels=labels,
                    timestamp=time.time(),
                    type=MetricType.HISTOGRAM
                ))
        
        return samples
    
    def _get_label_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dict to string key"""
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def _parse_label_key(self, label_key: str) -> Dict[str, str]:
        """Parse label key back to dict"""
        if not label_key:
            return {}
        return dict(item.split("=", 1) for item in label_key.split("|") if "=" in item)


class Summary:
    """Prometheus Summary metric - samples observations with quantiles"""
    
    DEFAULT_QUANTILES = [0.5, 0.9, 0.95, 0.99]
    
    def __init__(self, name: str, help: str, labels: List[str] = None, quantiles: List[float] = None, max_age: float = 600):
        self.name = name
        self.help = help
        self.labels = labels or []
        self.quantiles = quantiles or self.DEFAULT_QUANTILES
        self.max_age = max_age
        self._observations: Dict[str, deque] = defaultdict(lambda: deque())
        self._counts: Dict[str, int] = defaultdict(int)
        self._sums: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def observe(self, labels: Dict[str, str] = None, value: float = 0.0):
        """Observe a value"""
        label_key = self._get_label_key(labels or {})
        now = time.time()
        
        with self._lock:
            self._counts[label_key] += 1
            self._sums[label_key] += value
            self._observations[label_key].append((now, value))
            
            # Remove old observations
            cutoff = now - self.max_age
            while (self._observations[label_key] and 
                   self._observations[label_key][0][0] < cutoff):
                self._observations[label_key].popleft()
    
    def get_samples(self) -> List[MetricSample]:
        """Get all summary samples"""
        samples = []
        with self._lock:
            for label_key in self._counts.keys():
                labels = self._parse_label_key(label_key)
                observations = [obs[1] for obs in self._observations[label_key]]
                
                if observations:
                    observations.sort()
                    
                    # Quantile samples
                    for quantile in self.quantiles:
                        index = int(quantile * (len(observations) - 1))
                        value = observations[index] if observations else 0.0
                        quantile_labels = {**labels, "quantile": str(quantile)}
                        samples.append(MetricSample(
                            name=self.name,
                            value=value,
                            labels=quantile_labels,
                            timestamp=time.time(),
                            type=MetricType.SUMMARY
                        ))
                
                # Count sample
                samples.append(MetricSample(
                    name=f"{self.name}_count",
                    value=self._counts[label_key],
                    labels=labels,
                    timestamp=time.time(),
                    type=MetricType.SUMMARY
                ))
                
                # Sum sample
                samples.append(MetricSample(
                    name=f"{self.name}_sum",
                    value=self._sums[label_key],
                    labels=labels,
                    timestamp=time.time(),
                    type=MetricType.SUMMARY
                ))
        
        return samples
    
    def _get_label_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dict to string key"""
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def _parse_label_key(self, label_key: str) -> Dict[str, str]:
        """Parse label key back to dict"""
        if not label_key:
            return {}
        return dict(item.split("=", 1) for item in label_key.split("|") if "=" in item)


class MetricsCollector:
    """
    Enterprise Metrics Collector
    Prometheus-compatible metrics collection with histograms, system monitoring, and alerting
    
    Features:
    - Standard Prometheus metric types (Counter, Gauge, Histogram, Summary)
    - Real-time system resource monitoring (CPU, Memory, Disk, Network)
    - Custom metrics registration and collection
    - Thread-safe operations
    - Export formats (Prometheus, JSON, OpenMetrics)
    - Automatic system metrics collection
    - Performance profiling integration
    """
    
    _instance: Optional['MetricsCollector'] = None
    _lock = threading.Lock()
    
    def __init__(self, 
                 service_name: str = "dafelhub",
                 namespace: str = "",
                 collect_system_metrics: bool = True,
                 system_metrics_interval: float = 30.0):
        
        self.service_name = service_name
        self.namespace = namespace
        self.collect_system_metrics = collect_system_metrics
        self.system_metrics_interval = system_metrics_interval
        
        # Metric registry
        self.metrics: Dict[str, Union[Counter, Gauge, Histogram, Summary]] = {}
        self.metric_definitions: Dict[str, MetricDefinition] = {}
        
        # System information
        self.hostname = socket.gethostname()
        self.pid = psutil.Process().pid
        
        # Initialize built-in metrics
        self._initialize_builtin_metrics()
        
        # Start system metrics collection
        if self.collect_system_metrics:
            self._start_system_metrics_collection()
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'MetricsCollector':
        """Get singleton instance with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance
    
    def _initialize_builtin_metrics(self):
        """Initialize built-in application metrics"""
        # HTTP metrics
        self.register_metric(Counter, "http_requests_total", 
                           "Total HTTP requests", ["method", "status", "endpoint"])
        self.register_metric(Histogram, "http_request_duration_seconds",
                           "HTTP request duration", ["method", "endpoint"])
        
        # Database metrics  
        self.register_metric(Counter, "database_connections_total",
                           "Total database connections", ["database", "status"])
        self.register_metric(Gauge, "database_connections_active", 
                           "Active database connections", ["database"])
        self.register_metric(Histogram, "database_query_duration_seconds",
                           "Database query duration", ["database", "operation"])
        
        # Application metrics
        self.register_metric(Counter, "operations_total",
                           "Total operations", ["operation", "status"])
        self.register_metric(Histogram, "operation_duration_seconds", 
                           "Operation duration", ["operation"])
        self.register_metric(Gauge, "operations_active",
                           "Active operations", ["operation"])
        
        # Error metrics
        self.register_metric(Counter, "errors_total",
                           "Total errors", ["type", "component"])
        
        # System metrics
        if self.collect_system_metrics:
            self.register_metric(Gauge, "system_memory_bytes",
                               "System memory usage", ["type"])
            self.register_metric(Gauge, "system_cpu_percent", 
                               "System CPU usage", ["cpu"])
            self.register_metric(Gauge, "system_disk_bytes",
                               "System disk usage", ["device", "type"])
            self.register_metric(Gauge, "system_network_bytes",
                               "System network usage", ["interface", "direction"])
            self.register_metric(Gauge, "system_process_count",
                               "System process count", [])
            self.register_metric(Gauge, "system_uptime_seconds",
                               "System uptime", [])
    
    def register_metric(self, 
                       metric_class: type,
                       name: str, 
                       help: str, 
                       labels: List[str] = None,
                       **kwargs) -> Union[Counter, Gauge, Histogram, Summary]:
        """Register a new metric"""
        full_name = f"{self.namespace}_{name}" if self.namespace else name
        
        if full_name in self.metrics:
            return self.metrics[full_name]
        
        # Create metric instance
        if metric_class == Counter:
            metric = Counter(full_name, help, labels)
            metric_type = MetricType.COUNTER
        elif metric_class == Gauge:
            metric = Gauge(full_name, help, labels)
            metric_type = MetricType.GAUGE
        elif metric_class == Histogram:
            buckets = kwargs.get('buckets')
            metric = Histogram(full_name, help, labels, buckets)
            metric_type = MetricType.HISTOGRAM
        elif metric_class == Summary:
            quantiles = kwargs.get('quantiles')
            max_age = kwargs.get('max_age', 600)
            metric = Summary(full_name, help, labels, quantiles, max_age)
            metric_type = MetricType.SUMMARY
        else:
            raise ValueError(f"Unsupported metric type: {metric_class}")
        
        self.metrics[full_name] = metric
        self.metric_definitions[full_name] = MetricDefinition(
            name=full_name,
            help=help,
            type=metric_type,
            labels=labels or [],
            **kwargs
        )
        
        return metric
    
    def get_metric(self, name: str) -> Optional[Union[Counter, Gauge, Histogram, Summary]]:
        """Get metric by name"""
        full_name = f"{self.namespace}_{name}" if self.namespace else name
        return self.metrics.get(full_name)
    
    # Convenience methods for common operations
    
    def inc_counter(self, name: str, labels: Dict[str, str] = None, value: float = 1.0):
        """Increment counter metric"""
        metric = self.get_metric(name)
        if isinstance(metric, Counter):
            metric.inc(labels, value)
    
    def set_gauge(self, name: str, labels: Dict[str, str] = None, value: float = 0.0):
        """Set gauge metric value"""
        metric = self.get_metric(name)
        if isinstance(metric, Gauge):
            metric.set(labels, value)
    
    def observe_histogram(self, name: str, labels: Dict[str, str] = None, value: float = 0.0):
        """Observe histogram metric"""
        metric = self.get_metric(name)
        if isinstance(metric, Histogram):
            metric.observe(labels, value)
    
    def observe_summary(self, name: str, labels: Dict[str, str] = None, value: float = 0.0):
        """Observe summary metric"""
        metric = self.get_metric(name)
        if isinstance(metric, Summary):
            metric.observe(labels, value)
    
    # High-level metric recording methods
    
    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        labels = {"method": method, "endpoint": endpoint, "status": str(status)}
        self.inc_counter("http_requests_total", labels)
        self.observe_histogram("http_request_duration_seconds", 
                              {"method": method, "endpoint": endpoint}, duration)
    
    def record_database_operation(self, database: str, operation: str, 
                                 success: bool, duration: float):
        """Record database operation metrics"""
        status = "success" if success else "failure"
        self.inc_counter("database_connections_total", 
                        {"database": database, "status": status})
        self.observe_histogram("database_query_duration_seconds",
                             {"database": database, "operation": operation}, duration)
    
    def record_operation(self, operation: str, success: bool, duration: float):
        """Record general operation metrics"""
        status = "success" if success else "failure"
        self.inc_counter("operations_total", {"operation": operation, "status": status})
        self.observe_histogram("operation_duration_seconds", {"operation": operation}, duration)
    
    def record_error(self, error_type: str, component: str):
        """Record error metric"""
        self.inc_counter("errors_total", {"type": error_type, "component": component})
    
    def track_active_operation(self, operation: str, active: bool):
        """Track active operations"""
        metric = self.get_metric("operations_active")
        if isinstance(metric, Gauge):
            if active:
                metric.inc({"operation": operation})
            else:
                metric.dec({"operation": operation})
    
    def _start_system_metrics_collection(self):
        """Start background system metrics collection"""
        def collect_system_metrics():
            while True:
                try:
                    self._collect_system_metrics()
                except Exception:
                    pass  # Ignore system metrics collection errors
                time.sleep(self.system_metrics_interval)
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
    
    def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            # Memory metrics
            memory = psutil.virtual_memory()
            self.set_gauge("system_memory_bytes", {"type": "total"}, memory.total)
            self.set_gauge("system_memory_bytes", {"type": "available"}, memory.available)
            self.set_gauge("system_memory_bytes", {"type": "used"}, memory.used)
            self.set_gauge("system_memory_bytes", {"type": "free"}, memory.free)
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(percpu=True)
            for i, percent in enumerate(cpu_percent):
                self.set_gauge("system_cpu_percent", {"cpu": str(i)}, percent)
            self.set_gauge("system_cpu_percent", {"cpu": "total"}, psutil.cpu_percent())
            
            # Disk metrics
            for disk in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    device = disk.device.replace("/", "_").replace("\\", "_")
                    self.set_gauge("system_disk_bytes", {"device": device, "type": "total"}, usage.total)
                    self.set_gauge("system_disk_bytes", {"device": device, "type": "used"}, usage.used)
                    self.set_gauge("system_disk_bytes", {"device": device, "type": "free"}, usage.free)
                except:
                    continue
            
            # Network metrics
            net_io = psutil.net_io_counters(pernic=True)
            for interface, stats in net_io.items():
                self.set_gauge("system_network_bytes", 
                             {"interface": interface, "direction": "sent"}, stats.bytes_sent)
                self.set_gauge("system_network_bytes",
                             {"interface": interface, "direction": "recv"}, stats.bytes_recv)
            
            # Process metrics
            self.set_gauge("system_process_count", {}, len(psutil.pids()))
            
            # System uptime
            self.set_gauge("system_uptime_seconds", {}, time.time() - psutil.boot_time())
            
        except Exception:
            pass  # Ignore individual metric collection errors
    
    def get_all_samples(self) -> List[MetricSample]:
        """Get all metric samples"""
        samples = []
        for metric in self.metrics.values():
            samples.extend(metric.get_samples())
        return samples
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format"""
        output = []
        samples_by_name = defaultdict(list)
        
        # Group samples by metric name
        for sample in self.get_all_samples():
            samples_by_name[sample.name].append(sample)
        
        # Generate Prometheus format
        for metric_name, samples in samples_by_name.items():
            if not samples:
                continue
            
            # Get base metric name (without suffixes)
            base_name = metric_name.replace("_total", "").replace("_count", "").replace("_sum", "").replace("_bucket", "")
            
            # Add help and type comments
            if base_name in self.metric_definitions:
                definition = self.metric_definitions[base_name]
                output.append(f"# HELP {base_name} {definition.help}")
                output.append(f"# TYPE {base_name} {definition.type.value}")
            
            # Add samples
            for sample in samples:
                labels_str = ""
                if sample.labels:
                    label_pairs = [f'{k}="{v}"' for k, v in sample.labels.items()]
                    labels_str = "{" + ",".join(label_pairs) + "}"
                
                output.append(f"{sample.name}{labels_str} {sample.value}")
            
            output.append("")  # Empty line between metrics
        
        return "\n".join(output)
    
    def export_json(self) -> str:
        """Export metrics in JSON format"""
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "hostname": self.hostname,
            "pid": self.pid,
            "metrics": []
        }
        
        for sample in self.get_all_samples():
            data["metrics"].append({
                "name": sample.name,
                "value": sample.value,
                "labels": sample.labels,
                "timestamp": sample.timestamp,
                "type": sample.type.value
            })
        
        return json.dumps(data, indent=2)
    
    def export_openmetrics(self) -> str:
        """Export metrics in OpenMetrics format"""
        output = ["# OpenMetrics-Text 1.0.0"]
        
        samples_by_name = defaultdict(list)
        for sample in self.get_all_samples():
            samples_by_name[sample.name].append(sample)
        
        for metric_name, samples in samples_by_name.items():
            if not samples:
                continue
            
            base_name = metric_name.replace("_total", "").replace("_count", "").replace("_sum", "").replace("_bucket", "")
            
            if base_name in self.metric_definitions:
                definition = self.metric_definitions[base_name]
                output.append(f"# HELP {base_name} {definition.help}")
                output.append(f"# TYPE {base_name} {definition.type.value}")
                if definition.unit:
                    output.append(f"# UNIT {base_name} {definition.unit}")
            
            for sample in samples:
                labels_str = ""
                if sample.labels:
                    label_pairs = [f'{k}="{v}"' for k, v in sample.labels.items()]
                    labels_str = "{" + ",".join(label_pairs) + "}"
                
                timestamp_ms = int(sample.timestamp * 1000)
                output.append(f"{sample.name}{labels_str} {sample.value} {timestamp_ms}")
            
            output.append("")
        
        output.append("# EOF")
        return "\n".join(output)
    
    def get_metric_families(self) -> Dict[str, Dict]:
        """Get metric families for dashboard"""
        families = defaultdict(lambda: {
            "name": "",
            "help": "", 
            "type": "",
            "samples": []
        })
        
        for sample in self.get_all_samples():
            base_name = sample.name.replace("_total", "").replace("_count", "").replace("_sum", "").replace("_bucket", "")
            
            families[base_name]["name"] = base_name
            families[base_name]["samples"].append(sample)
            
            if base_name in self.metric_definitions:
                definition = self.metric_definitions[base_name]
                families[base_name]["help"] = definition.help
                families[base_name]["type"] = definition.type.value
        
        return dict(families)
    
    def reset_metrics(self):
        """Reset all metrics (for testing)"""
        for metric in self.metrics.values():
            if hasattr(metric, 'reset'):
                metric.reset()


# Global metrics collector instance
_global_collector: Optional[MetricsCollector] = None


def get_metrics_collector(**kwargs) -> MetricsCollector:
    """Get global metrics collector instance"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector.get_instance(**kwargs)
    return _global_collector