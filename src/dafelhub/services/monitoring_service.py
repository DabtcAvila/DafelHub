"""
DafelHub Monitoring Service
Enterprise-grade monitoring and observability system with metrics, alerting, and analytics.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Callable, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque

import psutil
from pydantic import BaseModel, Field, field_validator

from dafelhub.core.config import settings
from dafelhub.core.logging import LoggerMixin


class MetricType(str, Enum):
    """Metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: datetime
    value: Union[int, float]
    labels: Dict[str, str]


class Metric(BaseModel):
    """Metric definition"""
    name: str
    metric_type: MetricType
    description: str = ""
    unit: str = ""
    labels: Dict[str, str] = Field(default_factory=dict)
    help_text: str = ""


class AlertRule(BaseModel):
    """Alert rule definition"""
    id: str
    name: str
    description: str
    metric_name: str
    condition: str  # e.g., "> 0.8", "< 100", "!= 0"
    threshold: Union[int, float]
    severity: AlertSeverity
    duration: int = 60  # seconds to wait before firing
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    is_active: bool = True
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: str) -> str:
        """Validate condition format"""
        allowed_ops = ['>', '<', '>=', '<=', '==', '!=']
        if not any(op in v for op in allowed_ops):
            raise ValueError(f"Condition must contain one of: {', '.join(allowed_ops)}")
        return v


class Alert(BaseModel):
    """Active alert"""
    id: str
    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    metric_name: str
    current_value: Union[int, float]
    threshold: Union[int, float]
    started_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


class HealthCheck(BaseModel):
    """Health check definition"""
    id: str
    name: str
    description: str
    check_type: str  # http, tcp, command, custom
    target: str  # URL, host:port, command, etc.
    interval: int = 30  # seconds
    timeout: int = 10  # seconds
    retries: int = 3
    expected_status: Optional[int] = None
    expected_content: Optional[str] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    is_active: bool = True


class HealthCheckResult(BaseModel):
    """Health check result"""
    check_id: str
    status: HealthStatus
    response_time: float
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    
    
class SystemMetrics(BaseModel):
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    disk_io: Dict[str, int]
    process_count: int
    load_average: List[float]
    uptime_seconds: float
    timestamp: datetime


class MonitoringServiceError(Exception):
    """Base exception for monitoring service errors"""
    pass


class MetricNotFoundError(MonitoringServiceError):
    """Raised when metric is not found"""
    pass


class AlertRuleError(MonitoringServiceError):
    """Raised when alert rule operations fail"""
    pass


class MonitoringService(LoggerMixin):
    """
    Enterprise monitoring and observability system
    
    Features:
    - Metrics collection and storage
    - Real-time alerting system
    - Health check monitoring
    - System resource monitoring
    - Performance analytics
    - Custom dashboards support
    - Integration with external systems
    """
    
    def __init__(
        self,
        metrics_retention_days: int = 30,
        alert_check_interval: int = 10,
        health_check_interval: int = 30,
        enable_system_monitoring: bool = True
    ):
        """
        Initialize monitoring service
        
        Args:
            metrics_retention_days: Days to retain metrics data
            alert_check_interval: Alert evaluation interval in seconds
            health_check_interval: Health check interval in seconds
            enable_system_monitoring: Enable system resource monitoring
        """
        self.metrics_retention_days = metrics_retention_days
        self.alert_check_interval = alert_check_interval
        self.health_check_interval = health_check_interval
        self.enable_system_monitoring = enable_system_monitoring
        
        # Metrics storage
        self._metrics: Dict[str, Metric] = {}
        self._metric_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._metric_locks: Dict[str, asyncio.Lock] = {}
        
        # Alerting
        self._alert_rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        
        # Health checks
        self._health_checks: Dict[str, HealthCheck] = {}
        self._health_results: Dict[str, HealthCheckResult] = {}
        
        # Background tasks
        self._monitoring_tasks: List[asyncio.Task] = []
        self._running = False
        
        # Callbacks
        self._metric_callbacks: List[Callable] = []
        self._alert_callbacks: List[Callable] = []
        self._health_callbacks: List[Callable] = []
        
        self.logger.info(
            "MonitoringService initialized",
            extra={
                "metrics_retention_days": metrics_retention_days,
                "alert_check_interval": alert_check_interval,
                "health_check_interval": health_check_interval,
                "enable_system_monitoring": enable_system_monitoring
            }
        )
    
    async def start(self) -> None:
        """Start monitoring service background tasks"""
        if self._running:
            return
        
        self._running = True
        
        # Start background monitoring tasks
        if self.enable_system_monitoring:
            task = asyncio.create_task(self._system_monitoring_loop())
            self._monitoring_tasks.append(task)
        
        task = asyncio.create_task(self._alert_evaluation_loop())
        self._monitoring_tasks.append(task)
        
        task = asyncio.create_task(self._health_check_loop())
        self._monitoring_tasks.append(task)
        
        task = asyncio.create_task(self._cleanup_loop())
        self._monitoring_tasks.append(task)
        
        self.logger.info("MonitoringService started")
    
    async def stop(self) -> None:
        """Stop monitoring service"""
        self._running = False
        
        # Cancel background tasks
        for task in self._monitoring_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
        
        self._monitoring_tasks.clear()
        self.logger.info("MonitoringService stopped")
    
    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        unit: str = "",
        labels: Optional[Dict[str, str]] = None,
        help_text: str = ""
    ) -> None:
        """
        Register a new metric
        
        Args:
            name: Metric name
            metric_type: Type of metric
            description: Metric description
            unit: Metric unit
            labels: Default labels
            help_text: Help text for metric
        """
        metric = Metric(
            name=name,
            metric_type=metric_type,
            description=description,
            unit=unit,
            labels=labels or {},
            help_text=help_text
        )
        
        self._metrics[name] = metric
        self._metric_locks[name] = asyncio.Lock()
        
        self.logger.info(
            "Metric registered",
            extra={
                "metric_name": name,
                "metric_type": metric_type.value,
                "description": description
            }
        )
    
    async def record_metric(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record a metric value
        
        Args:
            name: Metric name
            value: Metric value
            labels: Additional labels
            timestamp: Timestamp (defaults to now)
        """
        if name not in self._metrics:
            raise MetricNotFoundError(f"Metric {name} not found")
        
        timestamp = timestamp or datetime.now(timezone.utc)
        labels = labels or {}
        
        # Merge with default labels
        merged_labels = {**self._metrics[name].labels, **labels}
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=merged_labels
        )
        
        async with self._metric_locks[name]:
            self._metric_data[name].append(point)
        
        # Trigger callbacks
        for callback in self._metric_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(name, point)
                else:
                    callback(name, point)
            except Exception as e:
                self.logger.warning(f"Metric callback error: {e}")
        
        self.logger.debug(
            "Metric recorded",
            extra={
                "metric_name": name,
                "value": value,
                "labels": merged_labels
            }
        )
    
    def increment_counter(
        self,
        name: str,
        amount: Union[int, float] = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric
        
        Args:
            name: Counter name
            amount: Amount to increment
            labels: Additional labels
        """
        asyncio.create_task(self.record_metric(name, amount, labels))
    
    def set_gauge(
        self,
        name: str,
        value: Union[int, float],
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Set a gauge metric value
        
        Args:
            name: Gauge name
            value: Gauge value
            labels: Additional labels
        """
        asyncio.create_task(self.record_metric(name, value, labels))
    
    def time_operation(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """
        Context manager to time operations
        
        Args:
            metric_name: Timer metric name
            labels: Additional labels
        
        Usage:
            async with monitoring.time_operation("api_request_duration", {"endpoint": "/users"}):
                await some_operation()
        """
        
        class TimerContext:
            def __init__(self, service: 'MonitoringService', name: str, labels: Optional[Dict[str, str]]):
                self.service = service
                self.name = name
                self.labels = labels or {}
                self.start_time = None
            
            async def __aenter__(self):
                self.start_time = time.time()
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.start_time:
                    duration = time.time() - self.start_time
                    await self.service.record_metric(self.name, duration, self.labels)
        
        return TimerContext(self, metric_name, labels)
    
    async def add_alert_rule(self, rule: AlertRule) -> None:
        """
        Add alert rule
        
        Args:
            rule: Alert rule definition
        """
        # Validate metric exists
        if rule.metric_name not in self._metrics:
            raise AlertRuleError(f"Metric {rule.metric_name} not found")
        
        self._alert_rules[rule.id] = rule
        
        self.logger.info(
            "Alert rule added",
            extra={
                "rule_id": rule.id,
                "rule_name": rule.name,
                "metric_name": rule.metric_name,
                "condition": rule.condition,
                "threshold": rule.threshold,
                "severity": rule.severity.value
            }
        )
    
    async def remove_alert_rule(self, rule_id: str) -> bool:
        """
        Remove alert rule
        
        Args:
            rule_id: Alert rule ID
            
        Returns:
            True if removed successfully
        """
        if rule_id not in self._alert_rules:
            return False
        
        del self._alert_rules[rule_id]
        
        # Resolve any active alerts for this rule
        alerts_to_resolve = [
            alert for alert in self._active_alerts.values()
            if alert.rule_id == rule_id
        ]
        
        for alert in alerts_to_resolve:
            await self._resolve_alert(alert.id)
        
        self.logger.info("Alert rule removed", extra={"rule_id": rule_id})
        return True
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an alert
        
        Args:
            alert_id: Alert ID
            acknowledged_by: User who acknowledged the alert
            
        Returns:
            True if acknowledged successfully
        """
        if alert_id not in self._active_alerts:
            return False
        
        alert = self._active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = acknowledged_by
        
        self.logger.info(
            "Alert acknowledged",
            extra={
                "alert_id": alert_id,
                "acknowledged_by": acknowledged_by
            }
        )
        
        return True
    
    async def add_health_check(self, health_check: HealthCheck) -> None:
        """
        Add health check
        
        Args:
            health_check: Health check definition
        """
        self._health_checks[health_check.id] = health_check
        
        self.logger.info(
            "Health check added",
            extra={
                "check_id": health_check.id,
                "check_name": health_check.name,
                "check_type": health_check.check_type,
                "target": health_check.target,
                "interval": health_check.interval
            }
        )
    
    async def remove_health_check(self, check_id: str) -> bool:
        """
        Remove health check
        
        Args:
            check_id: Health check ID
            
        Returns:
            True if removed successfully
        """
        if check_id not in self._health_checks:
            return False
        
        del self._health_checks[check_id]
        
        if check_id in self._health_results:
            del self._health_results[check_id]
        
        self.logger.info("Health check removed", extra={"check_id": check_id})
        return True
    
    async def get_metric_data(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> List[MetricPoint]:
        """
        Get metric data points
        
        Args:
            name: Metric name
            start_time: Start time filter
            end_time: End time filter
            labels: Label filters
            
        Returns:
            List of metric data points
        """
        if name not in self._metric_data:
            return []
        
        async with self._metric_locks[name]:
            data = list(self._metric_data[name])
        
        # Apply time filters
        if start_time:
            data = [p for p in data if p.timestamp >= start_time]
        
        if end_time:
            data = [p for p in data if p.timestamp <= end_time]
        
        # Apply label filters
        if labels:
            data = [
                p for p in data
                if all(p.labels.get(k) == v for k, v in labels.items())
            ]
        
        return data
    
    async def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        metric_name: Optional[str] = None
    ) -> List[Alert]:
        """
        Get active alerts
        
        Args:
            severity: Filter by severity
            metric_name: Filter by metric name
            
        Returns:
            List of active alerts
        """
        alerts = list(self._active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if metric_name:
            alerts = [a for a in alerts if a.metric_name == metric_name]
        
        # Sort by severity and start time
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.INFO: 2,
            AlertSeverity.DEBUG: 3
        }
        
        alerts.sort(key=lambda a: (severity_order[a.severity], a.started_at))
        
        return alerts
    
    async def get_health_status(self) -> Dict[str, HealthCheckResult]:
        """
        Get current health check results
        
        Returns:
            Dictionary of health check results
        """
        return dict(self._health_results)
    
    async def get_system_metrics(self) -> SystemMetrics:
        """
        Get current system metrics
        
        Returns:
            System metrics snapshot
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            disk_io = psutil.disk_io_counters()
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                network_io={
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                disk_io={
                    "read_bytes": disk_io.read_bytes,
                    "write_bytes": disk_io.write_bytes,
                    "read_count": disk_io.read_count,
                    "write_count": disk_io.write_count
                } if disk_io else {},
                process_count=len(psutil.pids()),
                load_average=list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0],
                uptime_seconds=time.time() - psutil.boot_time(),
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            self.logger.error(f"Failed to get system metrics: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                network_io={},
                disk_io={},
                process_count=0,
                load_average=[0.0, 0.0, 0.0],
                uptime_seconds=0.0,
                timestamp=datetime.now(timezone.utc)
            )
    
    def add_metric_callback(self, callback: Callable) -> None:
        """
        Add metric callback
        
        Args:
            callback: Callback function
        """
        self._metric_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable) -> None:
        """
        Add alert callback
        
        Args:
            callback: Callback function
        """
        self._alert_callbacks.append(callback)
    
    def add_health_callback(self, callback: Callable) -> None:
        """
        Add health check callback
        
        Args:
            callback: Callback function
        """
        self._health_callbacks.append(callback)
    
    async def _system_monitoring_loop(self) -> None:
        """Background task for system monitoring"""
        while self._running:
            try:
                metrics = await self.get_system_metrics()
                
                # Record system metrics
                await self.record_metric("system_cpu_percent", metrics.cpu_percent)
                await self.record_metric("system_memory_percent", metrics.memory_percent)
                await self.record_metric("system_disk_percent", metrics.disk_percent)
                await self.record_metric("system_process_count", metrics.process_count)
                await self.record_metric("system_uptime_seconds", metrics.uptime_seconds)
                
                if metrics.load_average:
                    await self.record_metric("system_load_1min", metrics.load_average[0])
                    await self.record_metric("system_load_5min", metrics.load_average[1])
                    await self.record_metric("system_load_15min", metrics.load_average[2])
                
                for key, value in metrics.network_io.items():
                    await self.record_metric(f"system_network_{key}", value)
                
                for key, value in metrics.disk_io.items():
                    await self.record_metric(f"system_disk_{key}", value)
                
            except Exception as e:
                self.logger.error(f"System monitoring error: {e}", exc_info=True)
            
            await asyncio.sleep(30)  # Collect system metrics every 30 seconds
    
    async def _alert_evaluation_loop(self) -> None:
        """Background task for alert evaluation"""
        while self._running:
            try:
                for rule in self._alert_rules.values():
                    if not rule.is_active:
                        continue
                    
                    await self._evaluate_alert_rule(rule)
                
            except Exception as e:
                self.logger.error(f"Alert evaluation error: {e}", exc_info=True)
            
            await asyncio.sleep(self.alert_check_interval)
    
    async def _evaluate_alert_rule(self, rule: AlertRule) -> None:
        """Evaluate a single alert rule"""
        try:
            # Get recent metric data
            recent_data = await self.get_metric_data(
                rule.metric_name,
                start_time=datetime.now(timezone.utc) - timedelta(seconds=rule.duration)
            )
            
            if not recent_data:
                return
            
            # Get latest value
            latest_point = max(recent_data, key=lambda p: p.timestamp)
            current_value = latest_point.value
            
            # Evaluate condition
            condition_met = self._evaluate_condition(
                current_value,
                rule.condition,
                rule.threshold
            )
            
            alert_id = f"{rule.id}_{rule.metric_name}"
            
            if condition_met:
                # Check if alert already exists
                if alert_id not in self._active_alerts:
                    # Create new alert
                    alert = Alert(
                        id=alert_id,
                        rule_id=rule.id,
                        name=rule.name,
                        description=rule.description,
                        severity=rule.severity,
                        status=AlertStatus.ACTIVE,
                        metric_name=rule.metric_name,
                        current_value=current_value,
                        threshold=rule.threshold,
                        started_at=datetime.now(timezone.utc),
                        labels={**rule.labels, **latest_point.labels},
                        annotations=rule.annotations
                    )
                    
                    self._active_alerts[alert_id] = alert
                    self._alert_history.append(alert)
                    
                    # Trigger callbacks
                    for callback in self._alert_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback("alert_fired", alert)
                            else:
                                callback("alert_fired", alert)
                        except Exception as e:
                            self.logger.warning(f"Alert callback error: {e}")
                    
                    self.logger.warning(
                        "Alert fired",
                        extra={
                            "alert_id": alert_id,
                            "rule_name": rule.name,
                            "metric_name": rule.metric_name,
                            "current_value": current_value,
                            "threshold": rule.threshold,
                            "severity": rule.severity.value
                        }
                    )
            else:
                # Resolve alert if it exists
                if alert_id in self._active_alerts:
                    await self._resolve_alert(alert_id)
                    
        except Exception as e:
            self.logger.error(f"Alert rule evaluation error for {rule.id}: {e}")
    
    def _evaluate_condition(
        self,
        value: Union[int, float],
        condition: str,
        threshold: Union[int, float]
    ) -> bool:
        """Evaluate alert condition"""
        if ">" in condition:
            if ">=" in condition:
                return value >= threshold
            else:
                return value > threshold
        elif "<" in condition:
            if "<=" in condition:
                return value <= threshold
            else:
                return value < threshold
        elif "==" in condition:
            return value == threshold
        elif "!=" in condition:
            return value != threshold
        else:
            return False
    
    async def _resolve_alert(self, alert_id: str) -> None:
        """Resolve an active alert"""
        if alert_id not in self._active_alerts:
            return
        
        alert = self._active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(timezone.utc)
        
        # Move to history
        del self._active_alerts[alert_id]
        
        # Trigger callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback("alert_resolved", alert)
                else:
                    callback("alert_resolved", alert)
            except Exception as e:
                self.logger.warning(f"Alert callback error: {e}")
        
        self.logger.info(
            "Alert resolved",
            extra={
                "alert_id": alert_id,
                "rule_name": alert.name
            }
        )
    
    async def _health_check_loop(self) -> None:
        """Background task for health checks"""
        while self._running:
            try:
                # Run health checks
                for check in self._health_checks.values():
                    if not check.is_active:
                        continue
                    
                    asyncio.create_task(self._run_health_check(check))
                
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}", exc_info=True)
            
            await asyncio.sleep(self.health_check_interval)
    
    async def _run_health_check(self, check: HealthCheck) -> None:
        """Run a single health check"""
        start_time = time.time()
        
        try:
            if check.check_type == "http":
                result = await self._http_health_check(check)
            elif check.check_type == "tcp":
                result = await self._tcp_health_check(check)
            elif check.check_type == "command":
                result = await self._command_health_check(check)
            else:
                result = HealthCheckResult(
                    check_id=check.id,
                    status=HealthStatus.UNKNOWN,
                    response_time=0.0,
                    message=f"Unknown check type: {check.check_type}",
                    timestamp=datetime.now(timezone.utc)
                )
        
        except Exception as e:
            result = HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=time.time() - start_time,
                message=f"Health check error: {str(e)}",
                timestamp=datetime.now(timezone.utc)
            )
        
        self._health_results[check.id] = result
        
        # Trigger callbacks
        for callback in self._health_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(check, result)
                else:
                    callback(check, result)
            except Exception as e:
                self.logger.warning(f"Health callback error: {e}")
        
        # Record health check metric
        status_value = 1 if result.status == HealthStatus.HEALTHY else 0
        await self.record_metric(
            "health_check_status",
            status_value,
            {"check_id": check.id, "check_name": check.name}
        )
        
        await self.record_metric(
            "health_check_response_time",
            result.response_time,
            {"check_id": check.id, "check_name": check.name}
        )
    
    async def _http_health_check(self, check: HealthCheck) -> HealthCheckResult:
        """Perform HTTP health check"""
        import aiohttp
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    check.target,
                    timeout=aiohttp.ClientTimeout(total=check.timeout)
                ) as response:
                    response_time = time.time() - start_time
                    content = await response.text()
                    
                    # Check status
                    if check.expected_status and response.status != check.expected_status:
                        return HealthCheckResult(
                            check_id=check.id,
                            status=HealthStatus.CRITICAL,
                            response_time=response_time,
                            message=f"Expected status {check.expected_status}, got {response.status}",
                            details={"status_code": response.status, "content": content[:500]},
                            timestamp=datetime.now(timezone.utc)
                        )
                    
                    # Check content
                    if check.expected_content and check.expected_content not in content:
                        return HealthCheckResult(
                            check_id=check.id,
                            status=HealthStatus.WARNING,
                            response_time=response_time,
                            message="Expected content not found",
                            details={"content": content[:500]},
                            timestamp=datetime.now(timezone.utc)
                        )
                    
                    return HealthCheckResult(
                        check_id=check.id,
                        status=HealthStatus.HEALTHY,
                        response_time=response_time,
                        message="HTTP check passed",
                        details={"status_code": response.status},
                        timestamp=datetime.now(timezone.utc)
                    )
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=check.timeout,
                message="Health check timeout",
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=time.time() - start_time,
                message=f"HTTP check failed: {str(e)}",
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _tcp_health_check(self, check: HealthCheck) -> HealthCheckResult:
        """Perform TCP health check"""
        start_time = time.time()
        
        try:
            # Parse host:port
            if ':' in check.target:
                host, port_str = check.target.split(':')
                port = int(port_str)
            else:
                host = check.target
                port = 80
            
            # Test connection
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=check.timeout)
            
            writer.close()
            await writer.wait_closed()
            
            response_time = time.time() - start_time
            
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                message="TCP connection successful",
                timestamp=datetime.now(timezone.utc)
            )
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=check.timeout,
                message="TCP connection timeout",
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=time.time() - start_time,
                message=f"TCP check failed: {str(e)}",
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _command_health_check(self, check: HealthCheck) -> HealthCheckResult:
        """Perform command health check"""
        start_time = time.time()
        
        try:
            process = await asyncio.create_subprocess_shell(
                check.target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=check.timeout
            )
            
            response_time = time.time() - start_time
            
            if process.returncode == 0:
                status = HealthStatus.HEALTHY
                message = "Command executed successfully"
            else:
                status = HealthStatus.CRITICAL
                message = f"Command failed with exit code {process.returncode}"
            
            return HealthCheckResult(
                check_id=check.id,
                status=status,
                response_time=response_time,
                message=message,
                details={
                    "exit_code": process.returncode,
                    "stdout": stdout.decode()[:500],
                    "stderr": stderr.decode()[:500]
                },
                timestamp=datetime.now(timezone.utc)
            )
        
        except asyncio.TimeoutError:
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=check.timeout,
                message="Command execution timeout",
                timestamp=datetime.now(timezone.utc)
            )
        except Exception as e:
            return HealthCheckResult(
                check_id=check.id,
                status=HealthStatus.CRITICAL,
                response_time=time.time() - start_time,
                message=f"Command check failed: {str(e)}",
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _cleanup_loop(self) -> None:
        """Background task for data cleanup"""
        while self._running:
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.metrics_retention_days)
                
                # Clean up old metric data
                for metric_name in self._metric_data:
                    async with self._metric_locks[metric_name]:
                        data = self._metric_data[metric_name]
                        # Remove old points
                        while data and data[0].timestamp < cutoff_time:
                            data.popleft()
                
                # Clean up old alert history
                self._alert_history = [
                    alert for alert in self._alert_history
                    if alert.started_at > cutoff_time
                ]
                
                self.logger.info("Monitoring data cleanup completed")
                
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}", exc_info=True)
            
            # Run cleanup once per day
            await asyncio.sleep(24 * 60 * 60)