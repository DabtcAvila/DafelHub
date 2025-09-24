"""
DafelHub Enterprise Database Health Monitor
Real-time database health monitoring and alerting system
Integrated with SecurityAgent audit trail and connection manager

Features:
- Real-time performance monitoring
- Health checks with automatic remediation
- Connection pool monitoring
- Query performance tracking
- Resource usage monitoring
- Alerting and notification system
- Historical trend analysis
- Predictive health scoring

TODO: [DB-007] Implement real-time health monitoring - @DatabaseAgent - 2024-09-24
TODO: [DB-008] Add predictive health scoring - @DatabaseAgent - 2024-09-24
TODO: [DB-009] Integrate alerting system - @DatabaseAgent - 2024-09-24
"""

import asyncio
import time
import threading
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Set, Union
import json
import statistics
from collections import deque
import psutil
import weakref

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings
from dafelhub.core.enterprise_vault import get_enterprise_vault_manager
from dafelhub.security.audit_trail import get_persistent_audit_trail
from dafelhub.database.connection_manager import get_connection_manager, ConnectionPriority
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool


logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    EXCELLENT = "excellent"      # 90-100%
    GOOD = "good"               # 70-89%
    WARNING = "warning"         # 50-69%
    CRITICAL = "critical"       # 20-49%
    FAILED = "failed"          # 0-19%


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(Enum):
    """Types of metrics being monitored"""
    CONNECTION = "connection"
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    QUERY = "query"
    AVAILABILITY = "availability"
    SECURITY = "security"


@dataclass
class HealthMetric:
    """Health metric data point"""
    metric_name: str
    metric_type: MetricType
    value: Union[int, float, bool, str]
    unit: str
    timestamp: datetime
    pool_id: Optional[str] = None
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_numeric(self) -> bool:
        """Check if metric value is numeric"""
        return isinstance(self.value, (int, float))
    
    def get_status(self) -> HealthStatus:
        """Get health status based on thresholds"""
        if not self.is_numeric:
            return HealthStatus.GOOD if self.value else HealthStatus.FAILED
        
        value = float(self.value)
        
        if self.threshold_critical is not None and value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.threshold_warning is not None and value >= self.threshold_warning:
            return HealthStatus.WARNING
        else:
            return HealthStatus.GOOD


@dataclass
class HealthAlert:
    """Health alert"""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    metric_name: str
    current_value: Union[int, float, str]
    threshold: Optional[float]
    pool_id: Optional[str]
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'alert_id': self.alert_id,
            'severity': self.severity.value,
            'title': self.title,
            'message': self.message,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'pool_id': self.pool_id,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class PoolHealthSummary:
    """Pool health summary"""
    pool_id: str
    overall_status: HealthStatus
    score: float
    metrics: Dict[str, HealthMetric]
    active_alerts: List[HealthAlert]
    last_check: datetime
    uptime: float
    availability_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'pool_id': self.pool_id,
            'overall_status': self.overall_status.value,
            'score': self.score,
            'metrics_count': len(self.metrics),
            'active_alerts': len(self.active_alerts),
            'last_check': self.last_check.isoformat(),
            'uptime': self.uptime,
            'availability_percent': self.availability_percent
        }


class DatabaseHealthMonitor(LoggerMixin):
    """
    Enterprise Database Health Monitor
    
    Comprehensive monitoring system with:
    - Real-time performance metrics collection
    - Connection pool health monitoring
    - Query performance analysis
    - Resource usage tracking
    - Automated alerting and remediation
    - Historical trend analysis
    - Predictive health scoring
    - Integration with audit trail
    """
    
    def __init__(self, vault_manager=None, audit_trail=None):
        super().__init__()
        
        # Core dependencies
        self.vault = vault_manager or get_enterprise_vault_manager()
        self.audit = audit_trail or get_persistent_audit_trail()
        self.connection_manager = get_connection_manager()
        
        # Monitoring state
        self._monitoring_active = False
        self._monitor_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        
        # Metrics storage (in-memory with limited history)
        self._metrics_history: Dict[str, deque] = {}
        self._current_metrics: Dict[str, HealthMetric] = {}
        self._pool_summaries: Dict[str, PoolHealthSummary] = {}
        
        # Alerting
        self._active_alerts: Dict[str, HealthAlert] = {}
        self._alert_handlers: List[Callable[[HealthAlert], None]] = []
        self._alert_cooldowns: Dict[str, datetime] = {}
        
        # Configuration
        self.check_interval = 30.0  # seconds
        self.metrics_history_limit = 1440  # 24 hours at 1-minute intervals
        self.alert_cooldown_duration = 300.0  # 5 minutes
        self.availability_window = 3600.0  # 1 hour window
        
        # Metric thresholds
        self._metric_thresholds = {
            'connection_pool_utilization': {'warning': 0.8, 'critical': 0.95},
            'query_response_time_avg': {'warning': 5.0, 'critical': 10.0},  # seconds
            'failed_queries_rate': {'warning': 0.05, 'critical': 0.1},      # 5%, 10%
            'cpu_usage_percent': {'warning': 80.0, 'critical': 95.0},
            'memory_usage_percent': {'warning': 85.0, 'critical': 95.0},
            'disk_usage_percent': {'warning': 85.0, 'critical': 95.0},
            'connection_errors_rate': {'warning': 0.02, 'critical': 0.05},   # 2%, 5%
            'deadlock_rate': {'warning': 0.01, 'critical': 0.05},            # 1%, 5%
        }
        
        # Performance tracking
        self._performance_stats = {
            'total_checks': 0,
            'failed_checks': 0,
            'alerts_generated': 0,
            'alerts_resolved': 0,
            'avg_check_duration': 0.0
        }
        
        self.logger.info("Database Health Monitor initialized")
    
    async def start_monitoring(self, pool_ids: Optional[List[str]] = None) -> None:
        """Start comprehensive health monitoring"""
        
        if self._monitoring_active:
            self.logger.warning("Health monitoring is already active")
            return
        
        try:
            # Get pool IDs to monitor
            if pool_ids is None:
                # Monitor all available pools
                manager_status = await self.connection_manager.get_global_status()
                pool_ids = list(self.connection_manager._pools.keys())
            
            if not pool_ids:
                self.logger.warning("No connection pools available to monitor")
                return
            
            self._monitoring_active = True
            self._shutdown_event.clear()
            
            # Start monitoring tasks for each pool
            for pool_id in pool_ids:
                task = asyncio.create_task(self._monitor_pool_health(pool_id))
                self._monitor_tasks[pool_id] = task
                self.logger.info(f"Started health monitoring for pool: {pool_id}")
            
            # Start global monitoring tasks
            self._monitor_tasks['system'] = asyncio.create_task(self._monitor_system_health())
            self._monitor_tasks['alerts'] = asyncio.create_task(self._alert_management_loop())
            self._monitor_tasks['cleanup'] = asyncio.create_task(self._cleanup_loop())
            
            # Audit monitoring start
            self.audit.add_entry(
                'database_health_monitoring_started',
                {
                    'monitored_pools': pool_ids,
                    'check_interval': self.check_interval,
                    'metrics_configured': len(self._metric_thresholds)
                }
            )
            
            self.logger.info("Database Health Monitor started successfully", extra={
                "monitored_pools": len(pool_ids),
                "check_interval": self.check_interval
            })
            
        except Exception as e:
            self._monitoring_active = False
            self.logger.error(f"Failed to start health monitoring: {e}")
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring gracefully"""
        
        if not self._monitoring_active:
            return
        
        self.logger.info("Stopping Database Health Monitor")
        
        try:
            # Signal shutdown
            self._monitoring_active = False
            self._shutdown_event.set()
            
            # Cancel all monitoring tasks
            for task_name, task in self._monitor_tasks.items():
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=5.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        self.logger.warning(f"Task {task_name} did not shut down gracefully")
            
            self._monitor_tasks.clear()
            
            # Audit monitoring stop
            self.audit.add_entry(
                'database_health_monitoring_stopped',
                {
                    'performance_stats': self._performance_stats,
                    'active_alerts': len(self._active_alerts)
                }
            )
            
            self.logger.info("Database Health Monitor stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping health monitoring: {e}")
    
    async def get_health_summary(self, pool_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        
        if pool_id:
            # Get specific pool summary
            if pool_id in self._pool_summaries:
                summary = self._pool_summaries[pool_id]
                return {
                    'pool': summary.to_dict(),
                    'recent_metrics': self._get_recent_metrics(pool_id),
                    'alerts': [alert.to_dict() for alert in summary.active_alerts]
                }
            else:
                return {'error': f'Pool not found: {pool_id}'}
        
        # Get global summary
        overall_status = self._calculate_overall_health()
        
        return {
            'monitoring_active': self._monitoring_active,
            'overall_health': overall_status.value,
            'overall_score': self._calculate_overall_score(),
            'monitored_pools': len(self._pool_summaries),
            'active_alerts': len(self._active_alerts),
            'critical_alerts': len([a for a in self._active_alerts.values() if a.severity == AlertSeverity.CRITICAL]),
            'pools': {
                pool_id: summary.to_dict() 
                for pool_id, summary in self._pool_summaries.items()
            },
            'performance_stats': self._performance_stats,
            'last_check': max([
                summary.last_check for summary in self._pool_summaries.values()
            ], default=datetime.now()).isoformat()
        }
    
    async def get_performance_trends(
        self, 
        pool_id: str, 
        metric_name: str, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get performance trend analysis"""
        
        if pool_id not in self._metrics_history:
            return {'error': f'No metrics history for pool: {pool_id}'}
        
        history_key = f"{pool_id}:{metric_name}"
        if history_key not in self._metrics_history:
            return {'error': f'No history for metric: {metric_name}'}
        
        # Get recent data points
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self._metrics_history[history_key]
            if m.timestamp >= cutoff_time and m.is_numeric
        ]
        
        if not recent_metrics:
            return {'error': 'No recent data available'}
        
        values = [float(m.value) for m in recent_metrics]
        timestamps = [m.timestamp.isoformat() for m in recent_metrics]
        
        # Calculate trends
        trend_analysis = {
            'metric_name': metric_name,
            'pool_id': pool_id,
            'time_window_hours': hours,
            'data_points': len(values),
            'statistics': {
                'min': min(values),
                'max': max(values),
                'avg': statistics.mean(values),
                'median': statistics.median(values),
                'std_dev': statistics.stdev(values) if len(values) > 1 else 0.0
            },
            'trend': self._calculate_trend(values),
            'data': list(zip(timestamps, values))
        }
        
        return trend_analysis
    
    def add_alert_handler(self, handler: Callable[[HealthAlert], None]) -> None:
        """Add custom alert handler"""
        self._alert_handlers.append(handler)
        self.logger.info("Alert handler added")
    
    async def test_connectivity(self, pool_id: str) -> Dict[str, Any]:
        """Test database connectivity for specific pool"""
        
        try:
            start_time = time.time()
            
            # Get connection and test
            async with self.connection_manager.get_connection(
                pool_id,
                priority=ConnectionPriority.HIGH,
                timeout=10.0
            ) as conn:
                # Basic connectivity test
                result = await conn.fetchrow("SELECT 1 as test, NOW() as timestamp")
                
                response_time = time.time() - start_time
                
                return {
                    'pool_id': pool_id,
                    'connected': True,
                    'response_time': response_time,
                    'server_time': result['timestamp'].isoformat(),
                    'test_timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            response_time = time.time() - start_time
            
            return {
                'pool_id': pool_id,
                'connected': False,
                'error': str(e),
                'response_time': response_time,
                'test_timestamp': datetime.now().isoformat()
            }
    
    # Private monitoring methods
    
    async def _monitor_pool_health(self, pool_id: str) -> None:
        """Monitor individual pool health"""
        
        while self._monitoring_active and not self._shutdown_event.is_set():
            try:
                start_check = time.time()
                
                # Collect pool metrics
                metrics = await self._collect_pool_metrics(pool_id)
                
                # Update metrics history
                for metric_name, metric in metrics.items():
                    self._update_metric_history(pool_id, metric_name, metric)
                    self._current_metrics[f"{pool_id}:{metric_name}"] = metric
                
                # Check for alerts
                await self._check_metric_alerts(pool_id, metrics)
                
                # Update pool summary
                self._update_pool_summary(pool_id, metrics)
                
                # Update performance stats
                check_duration = time.time() - start_check
                self._performance_stats['total_checks'] += 1
                self._performance_stats['avg_check_duration'] = (
                    (self._performance_stats['avg_check_duration'] * 
                     (self._performance_stats['total_checks'] - 1) + check_duration) /
                    self._performance_stats['total_checks']
                )
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._performance_stats['failed_checks'] += 1
                self.logger.error(f"Error monitoring pool {pool_id}: {e}")
                await asyncio.sleep(min(self.check_interval, 60))  # Reduce frequency on error
    
    async def _collect_pool_metrics(self, pool_id: str) -> Dict[str, HealthMetric]:
        """Collect comprehensive metrics for a pool"""
        
        metrics = {}
        timestamp = datetime.now()
        
        try:
            # Get pool status
            pool_status = await self.connection_manager.get_pool_status(pool_id)
            
            if 'error' in pool_status:
                # Pool not available
                metrics['availability'] = HealthMetric(
                    metric_name='availability',
                    metric_type=MetricType.AVAILABILITY,
                    value=False,
                    unit='boolean',
                    timestamp=timestamp,
                    pool_id=pool_id
                )
                return metrics
            
            # Connection pool metrics
            current_stats = pool_status.get('current_stats', {})
            
            # Pool utilization
            utilization = current_stats.get('utilization_percent', 0) / 100.0
            metrics['connection_pool_utilization'] = HealthMetric(
                metric_name='connection_pool_utilization',
                metric_type=MetricType.CONNECTION,
                value=utilization,
                unit='ratio',
                timestamp=timestamp,
                pool_id=pool_id,
                threshold_warning=self._metric_thresholds['connection_pool_utilization']['warning'],
                threshold_critical=self._metric_thresholds['connection_pool_utilization']['critical']
            )
            
            # Active connections
            metrics['active_connections'] = HealthMetric(
                metric_name='active_connections',
                metric_type=MetricType.CONNECTION,
                value=current_stats.get('active_connections', 0),
                unit='count',
                timestamp=timestamp,
                pool_id=pool_id
            )
            
            # Idle connections
            metrics['idle_connections'] = HealthMetric(
                metric_name='idle_connections',
                metric_type=MetricType.CONNECTION,
                value=current_stats.get('idle_connections', 0),
                unit='count',
                timestamp=timestamp,
                pool_id=pool_id
            )
            
            # Query performance metrics
            pool_metrics = pool_status.get('metrics', {})
            
            # Average query time
            avg_query_time = pool_metrics.get('avg_query_time', 0)
            metrics['query_response_time_avg'] = HealthMetric(
                metric_name='query_response_time_avg',
                metric_type=MetricType.PERFORMANCE,
                value=avg_query_time,
                unit='seconds',
                timestamp=timestamp,
                pool_id=pool_id,
                threshold_warning=self._metric_thresholds['query_response_time_avg']['warning'],
                threshold_critical=self._metric_thresholds['query_response_time_avg']['critical']
            )
            
            # Failed queries rate
            total_queries = pool_metrics.get('total_queries', 0)
            failed_queries = pool_metrics.get('failed_queries', 0)
            failed_rate = (failed_queries / max(total_queries, 1))
            
            metrics['failed_queries_rate'] = HealthMetric(
                metric_name='failed_queries_rate',
                metric_type=MetricType.PERFORMANCE,
                value=failed_rate,
                unit='ratio',
                timestamp=timestamp,
                pool_id=pool_id,
                threshold_warning=self._metric_thresholds['failed_queries_rate']['warning'],
                threshold_critical=self._metric_thresholds['failed_queries_rate']['critical']
            )
            
            # Test connectivity and response time
            connectivity_test = await self.test_connectivity(pool_id)
            
            metrics['connectivity'] = HealthMetric(
                metric_name='connectivity',
                metric_type=MetricType.AVAILABILITY,
                value=connectivity_test.get('connected', False),
                unit='boolean',
                timestamp=timestamp,
                pool_id=pool_id
            )
            
            metrics['connection_response_time'] = HealthMetric(
                metric_name='connection_response_time',
                metric_type=MetricType.PERFORMANCE,
                value=connectivity_test.get('response_time', 0),
                unit='seconds',
                timestamp=timestamp,
                pool_id=pool_id,
                threshold_warning=2.0,  # 2 seconds
                threshold_critical=5.0   # 5 seconds
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics for pool {pool_id}: {e}")
            
            # Add error metric
            metrics['collection_error'] = HealthMetric(
                metric_name='collection_error',
                metric_type=MetricType.AVAILABILITY,
                value=False,
                unit='boolean',
                timestamp=timestamp,
                pool_id=pool_id,
                context={'error': str(e)}
            )
        
        return metrics
    
    async def _monitor_system_health(self) -> None:
        """Monitor system-wide health metrics"""
        
        while self._monitoring_active and not self._shutdown_event.is_set():
            try:
                timestamp = datetime.now()
                
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_metric = HealthMetric(
                    metric_name='cpu_usage_percent',
                    metric_type=MetricType.RESOURCE,
                    value=cpu_percent,
                    unit='percent',
                    timestamp=timestamp,
                    threshold_warning=self._metric_thresholds['cpu_usage_percent']['warning'],
                    threshold_critical=self._metric_thresholds['cpu_usage_percent']['critical']
                )
                
                self._current_metrics['system:cpu_usage_percent'] = cpu_metric
                self._update_metric_history('system', 'cpu_usage_percent', cpu_metric)
                
                # Memory usage
                memory = psutil.virtual_memory()
                memory_metric = HealthMetric(
                    metric_name='memory_usage_percent',
                    metric_type=MetricType.RESOURCE,
                    value=memory.percent,
                    unit='percent',
                    timestamp=timestamp,
                    threshold_warning=self._metric_thresholds['memory_usage_percent']['warning'],
                    threshold_critical=self._metric_thresholds['memory_usage_percent']['critical']
                )
                
                self._current_metrics['system:memory_usage_percent'] = memory_metric
                self._update_metric_history('system', 'memory_usage_percent', memory_metric)
                
                # Disk usage
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                disk_metric = HealthMetric(
                    metric_name='disk_usage_percent',
                    metric_type=MetricType.RESOURCE,
                    value=disk_percent,
                    unit='percent',
                    timestamp=timestamp,
                    threshold_warning=self._metric_thresholds['disk_usage_percent']['warning'],
                    threshold_critical=self._metric_thresholds['disk_usage_percent']['critical']
                )
                
                self._current_metrics['system:disk_usage_percent'] = disk_metric
                self._update_metric_history('system', 'disk_usage_percent', disk_metric)
                
                # Check system alerts
                system_metrics = {
                    'cpu_usage_percent': cpu_metric,
                    'memory_usage_percent': memory_metric,
                    'disk_usage_percent': disk_metric
                }
                
                await self._check_metric_alerts('system', system_metrics)
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error monitoring system health: {e}")
                await asyncio.sleep(60)
    
    async def _check_metric_alerts(self, pool_id: str, metrics: Dict[str, HealthMetric]) -> None:
        """Check metrics for alert conditions"""
        
        for metric_name, metric in metrics.items():
            try:
                status = metric.get_status()
                alert_key = f"{pool_id}:{metric_name}"
                
                # Check if we should create an alert
                should_alert = False
                severity = AlertSeverity.INFO
                
                if status == HealthStatus.CRITICAL:
                    should_alert = True
                    severity = AlertSeverity.CRITICAL
                elif status == HealthStatus.WARNING:
                    should_alert = True
                    severity = AlertSeverity.WARNING
                
                # Check cooldown
                if should_alert and alert_key in self._alert_cooldowns:
                    if (datetime.now() - self._alert_cooldowns[alert_key]).total_seconds() < self.alert_cooldown_duration:
                        continue  # Skip due to cooldown
                
                # Create alert if needed
                if should_alert and alert_key not in self._active_alerts:
                    alert = self._create_alert(metric, severity, pool_id)
                    self._active_alerts[alert_key] = alert
                    self._alert_cooldowns[alert_key] = datetime.now()
                    
                    # Trigger alert handlers
                    await self._trigger_alert(alert)
                    
                # Resolve alert if metric is back to normal
                elif not should_alert and alert_key in self._active_alerts:
                    alert = self._active_alerts[alert_key]
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    
                    # Remove from active alerts
                    del self._active_alerts[alert_key]
                    self._performance_stats['alerts_resolved'] += 1
                    
                    # Audit resolution
                    self.audit.add_entry(
                        'database_health_alert_resolved',
                        {
                            'alert': alert.to_dict(),
                            'resolution_time': (alert.resolved_at - alert.timestamp).total_seconds()
                        }
                    )
                    
            except Exception as e:
                self.logger.error(f"Error checking alerts for {pool_id}:{metric_name}: {e}")
    
    def _create_alert(self, metric: HealthMetric, severity: AlertSeverity, pool_id: str) -> HealthAlert:
        """Create health alert"""
        
        alert_id = f"alert_{int(time.time())}_{hash(f'{pool_id}:{metric.metric_name}')}"
        
        # Generate alert message
        if severity == AlertSeverity.CRITICAL:
            title = f"CRITICAL: {metric.metric_name} threshold exceeded"
            message = (f"Critical threshold exceeded for {metric.metric_name} in pool {pool_id}. "
                      f"Current value: {metric.value} {metric.unit}, "
                      f"Threshold: {metric.threshold_critical}")
        else:
            title = f"WARNING: {metric.metric_name} threshold exceeded"
            message = (f"Warning threshold exceeded for {metric.metric_name} in pool {pool_id}. "
                      f"Current value: {metric.value} {metric.unit}, "
                      f"Threshold: {metric.threshold_warning}")
        
        alert = HealthAlert(
            alert_id=alert_id,
            severity=severity,
            title=title,
            message=message,
            metric_name=metric.metric_name,
            current_value=metric.value,
            threshold=metric.threshold_critical if severity == AlertSeverity.CRITICAL else metric.threshold_warning,
            pool_id=pool_id,
            timestamp=datetime.now()
        )
        
        return alert
    
    async def _trigger_alert(self, alert: HealthAlert) -> None:
        """Trigger alert through all registered handlers"""
        
        try:
            # Update statistics
            self._performance_stats['alerts_generated'] += 1
            
            # Audit alert creation
            self.audit.add_entry(
                'database_health_alert_triggered',
                {
                    'alert': alert.to_dict(),
                    'handlers_count': len(self._alert_handlers)
                }
            )
            
            # Log alert
            log_level = 'critical' if alert.severity == AlertSeverity.CRITICAL else 'warning'
            self.logger.log(
                getattr(self.logger, log_level),
                f"Health Alert: {alert.title}",
                extra={
                    "alert_id": alert.alert_id,
                    "pool_id": alert.pool_id,
                    "metric": alert.metric_name,
                    "value": alert.current_value,
                    "threshold": alert.threshold
                }
            )
            
            # Trigger custom handlers
            for handler in self._alert_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(alert)
                    else:
                        handler(alert)
                except Exception as e:
                    self.logger.error(f"Alert handler failed: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error triggering alert: {e}")
    
    def _update_metric_history(self, pool_id: str, metric_name: str, metric: HealthMetric) -> None:
        """Update metric history with limited retention"""
        
        history_key = f"{pool_id}:{metric_name}"
        
        if history_key not in self._metrics_history:
            self._metrics_history[history_key] = deque(maxlen=self.metrics_history_limit)
        
        self._metrics_history[history_key].append(metric)
    
    def _update_pool_summary(self, pool_id: str, metrics: Dict[str, HealthMetric]) -> None:
        """Update pool health summary"""
        
        # Calculate overall health score
        health_scores = []
        for metric in metrics.values():
            status = metric.get_status()
            score_map = {
                HealthStatus.EXCELLENT: 100,
                HealthStatus.GOOD: 80,
                HealthStatus.WARNING: 60,
                HealthStatus.CRITICAL: 30,
                HealthStatus.FAILED: 0
            }
            health_scores.append(score_map.get(status, 50))
        
        overall_score = statistics.mean(health_scores) if health_scores else 0
        overall_status = self._score_to_status(overall_score)
        
        # Get active alerts for this pool
        pool_alerts = [
            alert for alert in self._active_alerts.values()
            if alert.pool_id == pool_id
        ]
        
        # Calculate uptime and availability
        uptime = 0.0
        availability = 100.0
        
        # Get connectivity history for availability calculation
        connectivity_key = f"{pool_id}:connectivity"
        if connectivity_key in self._metrics_history:
            recent_connectivity = [
                m for m in self._metrics_history[connectivity_key]
                if (datetime.now() - m.timestamp).total_seconds() <= self.availability_window
            ]
            
            if recent_connectivity:
                connected_count = sum(1 for m in recent_connectivity if m.value)
                availability = (connected_count / len(recent_connectivity)) * 100
        
        # Create summary
        summary = PoolHealthSummary(
            pool_id=pool_id,
            overall_status=overall_status,
            score=overall_score,
            metrics=metrics,
            active_alerts=pool_alerts,
            last_check=datetime.now(),
            uptime=uptime,
            availability_percent=availability
        )
        
        self._pool_summaries[pool_id] = summary
    
    def _score_to_status(self, score: float) -> HealthStatus:
        """Convert numeric score to health status"""
        if score >= 90:
            return HealthStatus.EXCELLENT
        elif score >= 70:
            return HealthStatus.GOOD
        elif score >= 50:
            return HealthStatus.WARNING
        elif score >= 20:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.FAILED
    
    def _calculate_overall_health(self) -> HealthStatus:
        """Calculate overall system health"""
        if not self._pool_summaries:
            return HealthStatus.FAILED
        
        scores = [summary.score for summary in self._pool_summaries.values()]
        overall_score = statistics.mean(scores)
        
        return self._score_to_status(overall_score)
    
    def _calculate_overall_score(self) -> float:
        """Calculate overall health score"""
        if not self._pool_summaries:
            return 0.0
        
        scores = [summary.score for summary in self._pool_summaries.values()]
        return statistics.mean(scores)
    
    def _get_recent_metrics(self, pool_id: str, hours: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """Get recent metrics for a pool"""
        
        recent_metrics = {}
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        for history_key, history in self._metrics_history.items():
            if history_key.startswith(f"{pool_id}:"):
                metric_name = history_key.split(":", 1)[1]
                recent_data = [
                    {
                        'timestamp': m.timestamp.isoformat(),
                        'value': m.value,
                        'unit': m.unit,
                        'status': m.get_status().value
                    }
                    for m in history
                    if m.timestamp >= cutoff_time
                ]
                
                if recent_data:
                    recent_metrics[metric_name] = recent_data
        
        return recent_metrics
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values"""
        if len(values) < 2:
            return "stable"
        
        # Simple linear trend calculation
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        try:
            slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
            
            if slope > 0.1:
                return "increasing"
            elif slope < -0.1:
                return "decreasing"
            else:
                return "stable"
        except ZeroDivisionError:
            return "stable"
    
    async def _alert_management_loop(self) -> None:
        """Background alert management"""
        
        while self._monitoring_active and not self._shutdown_event.is_set():
            try:
                # Clean up old cooldowns
                current_time = datetime.now()
                expired_cooldowns = [
                    key for key, cooldown_time in self._alert_cooldowns.items()
                    if (current_time - cooldown_time).total_seconds() > self.alert_cooldown_duration * 2
                ]
                
                for key in expired_cooldowns:
                    del self._alert_cooldowns[key]
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in alert management loop: {e}")
                await asyncio.sleep(30)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup of old data"""
        
        while self._monitoring_active and not self._shutdown_event.is_set():
            try:
                # Cleanup is handled by deque maxlen, but we can add more cleanup here
                current_time = datetime.now()
                
                # Log cleanup statistics
                total_metrics = sum(len(history) for history in self._metrics_history.values())
                
                self.logger.debug(f"Health monitor cleanup: {total_metrics} total metrics in history")
                
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)


# Global singleton instance
_health_monitor: Optional[DatabaseHealthMonitor] = None
_monitor_lock = threading.Lock()


def get_health_monitor() -> DatabaseHealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    
    with _monitor_lock:
        if _health_monitor is None:
            _health_monitor = DatabaseHealthMonitor()
        return _health_monitor