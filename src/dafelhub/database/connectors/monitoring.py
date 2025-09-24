"""
Real-time PostgreSQL Monitoring and Statistics Dashboard
Enterprise monitoring capabilities for PostgreSQL connectors
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from collections import defaultdict, deque
import weakref
from enum import Enum

from dafelhub.core.logging import get_logger, LoggerMixin


logger = get_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


@dataclass
class PerformanceAlert:
    """Performance monitoring alert"""
    id: str
    level: AlertLevel
    title: str
    description: str
    connection_id: str
    metric: str
    threshold: float
    current_value: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class ConnectionHealth:
    """Connection health metrics"""
    connection_id: str
    status: str
    uptime: float
    last_activity: Optional[datetime]
    query_success_rate: float
    avg_response_time: float
    active_connections: int
    max_connections: int
    pool_utilization: float
    alerts: List[PerformanceAlert] = field(default_factory=list)


@dataclass
class QueryPerformanceMetrics:
    """Detailed query performance metrics"""
    query_id: str
    sql_hash: str
    query_type: str
    execution_count: int
    total_execution_time: float
    avg_execution_time: float
    min_execution_time: float
    max_execution_time: float
    last_executed: datetime
    rows_examined_avg: float
    rows_returned_avg: float
    cache_hit_rate: float
    error_count: int
    error_rate: float


@dataclass
class SystemMetrics:
    """System-level metrics"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_io_read: float
    disk_io_write: float
    network_io_read: float
    network_io_write: float
    connection_count: int


class MonitoringCollector(LoggerMixin):
    """Collects and aggregates monitoring data"""
    
    def __init__(self, max_history: int = 1000, alert_retention_hours: int = 24):
        self.max_history = max_history
        self.alert_retention_hours = alert_retention_hours
        
        # Data storage
        self._connection_metrics: Dict[str, ConnectionHealth] = {}
        self._query_metrics: Dict[str, QueryPerformanceMetrics] = {}
        self._system_metrics: deque = deque(maxlen=max_history)
        self._alerts: List[PerformanceAlert] = []
        self._alert_rules: Dict[str, Dict] = {}
        
        # Aggregation data
        self._query_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._connection_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Weak references to connectors for live monitoring
        self._connectors: Set[weakref.ref] = set()
        
        self._setup_default_alert_rules()
    
    def register_connector(self, connector) -> None:
        """Register a connector for monitoring"""
        weak_connector = weakref.ref(connector, self._cleanup_connector_ref)
        self._connectors.add(weak_connector)
        self.logger.info(f"Registered connector for monitoring: {connector.id}")
    
    def _cleanup_connector_ref(self, ref: weakref.ref) -> None:
        """Clean up dead connector reference"""
        self._connectors.discard(ref)
    
    def _setup_default_alert_rules(self) -> None:
        """Setup default alerting rules"""
        self._alert_rules = {
            'high_query_time': {
                'metric': 'avg_execution_time',
                'threshold': 5.0,  # 5 seconds
                'level': AlertLevel.WARNING,
                'description': 'Average query execution time is high'
            },
            'low_success_rate': {
                'metric': 'query_success_rate',
                'threshold': 95.0,  # Below 95%
                'level': AlertLevel.ERROR,
                'comparison': 'less_than',
                'description': 'Query success rate is below threshold'
            },
            'high_pool_utilization': {
                'metric': 'pool_utilization',
                'threshold': 90.0,  # Above 90%
                'level': AlertLevel.WARNING,
                'description': 'Connection pool utilization is high'
            },
            'connection_errors': {
                'metric': 'connection_errors',
                'threshold': 10,  # More than 10 errors per minute
                'level': AlertLevel.CRITICAL,
                'description': 'High number of connection errors'
            }
        }
    
    async def collect_metrics(self) -> None:
        """Collect metrics from all registered connectors"""
        current_time = datetime.now()
        
        # Clean up dead references
        dead_refs = [ref for ref in self._connectors if ref() is None]
        for ref in dead_refs:
            self._connectors.discard(ref)
        
        # Collect from live connectors
        for connector_ref in list(self._connectors):
            connector = connector_ref()
            if connector is None:
                continue
            
            try:
                await self._collect_connector_metrics(connector, current_time)
            except Exception as e:
                self.logger.error(f"Error collecting metrics from connector {connector.id}",
                                extra_data={"error": str(e)})
        
        # Cleanup old alerts
        await self._cleanup_old_alerts()
    
    async def _collect_connector_metrics(self, connector, timestamp: datetime) -> None:
        """Collect metrics from a single connector"""
        try:
            # Get performance metrics
            perf_metrics = connector.get_performance_metrics()
            
            # Update connection health
            connection_health = ConnectionHealth(
                connection_id=connector.id,
                status=perf_metrics['status'],
                uptime=perf_metrics['uptime_seconds'],
                last_activity=datetime.fromisoformat(perf_metrics['last_activity']) 
                             if perf_metrics['last_activity'] else None,
                query_success_rate=perf_metrics['query_metrics']['success_rate'],
                avg_response_time=perf_metrics['query_metrics']['avg_execution_time'],
                active_connections=perf_metrics['pool_metrics']['current_size'],
                max_connections=perf_metrics['pool_metrics']['max_size'],
                pool_utilization=(perf_metrics['pool_metrics']['current_size'] / 
                                perf_metrics['pool_metrics']['max_size'] * 100) 
                               if perf_metrics['pool_metrics']['max_size'] > 0 else 0
            )
            
            self._connection_metrics[connector.id] = connection_health
            
            # Store historical data
            self._connection_history[connector.id].append({
                'timestamp': timestamp,
                'success_rate': connection_health.query_success_rate,
                'avg_response_time': connection_health.avg_response_time,
                'pool_utilization': connection_health.pool_utilization,
                'active_connections': connection_health.active_connections
            })
            
            # Update query metrics
            await self._update_query_metrics(connector, perf_metrics['query_metrics'])
            
            # Check for alerts
            await self._check_alerts(connector.id, connection_health)
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics from connector {connector.id}",
                            extra_data={"error": str(e)})
    
    async def _update_query_metrics(self, connector, query_metrics: Dict[str, Any]) -> None:
        """Update query performance metrics"""
        # This would typically analyze the query history from the connector
        # For now, we'll create aggregate metrics
        
        query_types = query_metrics.get('query_type_distribution', {})
        
        for query_type, stats in query_types.items():
            query_hash = f"{connector.id}_{query_type}"
            
            if query_hash not in self._query_metrics:
                self._query_metrics[query_hash] = QueryPerformanceMetrics(
                    query_id=query_hash,
                    sql_hash=query_hash,
                    query_type=query_type,
                    execution_count=0,
                    total_execution_time=0.0,
                    avg_execution_time=0.0,
                    min_execution_time=float('inf'),
                    max_execution_time=0.0,
                    last_executed=datetime.now(),
                    rows_examined_avg=0.0,
                    rows_returned_avg=0.0,
                    cache_hit_rate=0.0,
                    error_count=0,
                    error_rate=0.0
                )
            
            # Update metrics
            metric = self._query_metrics[query_hash]
            metric.execution_count = stats['count']
            metric.avg_execution_time = stats['avg_time']
            metric.total_execution_time = stats['total_time']
            metric.last_executed = datetime.now()
    
    async def _check_alerts(self, connection_id: str, health: ConnectionHealth) -> None:
        """Check for alert conditions"""
        current_time = datetime.now()
        
        for rule_name, rule in self._alert_rules.items():
            try:
                metric_value = getattr(health, rule['metric'], None)
                if metric_value is None:
                    continue
                
                threshold = rule['threshold']
                comparison = rule.get('comparison', 'greater_than')
                
                # Check condition
                triggered = False
                if comparison == 'greater_than' and metric_value > threshold:
                    triggered = True
                elif comparison == 'less_than' and metric_value < threshold:
                    triggered = True
                
                if triggered:
                    # Check if alert already exists
                    existing_alert = next(
                        (a for a in self._alerts 
                         if a.connection_id == connection_id 
                         and a.metric == rule['metric'] 
                         and not a.resolved),
                        None
                    )
                    
                    if not existing_alert:
                        alert = PerformanceAlert(
                            id=f"{connection_id}_{rule_name}_{int(time.time())}",
                            level=rule['level'],
                            title=f"{rule_name.replace('_', ' ').title()}",
                            description=rule['description'],
                            connection_id=connection_id,
                            metric=rule['metric'],
                            threshold=threshold,
                            current_value=metric_value,
                            timestamp=current_time
                        )
                        
                        self._alerts.append(alert)
                        health.alerts.append(alert)
                        
                        self.logger.warning(f"Alert triggered: {alert.title}",
                                          extra_data={
                                              "connection_id": connection_id,
                                              "metric": alert.metric,
                                              "threshold": threshold,
                                              "current_value": metric_value
                                          })
                else:
                    # Resolve existing alerts
                    for alert in self._alerts:
                        if (alert.connection_id == connection_id 
                            and alert.metric == rule['metric'] 
                            and not alert.resolved):
                            alert.resolved = True
                            alert.resolved_at = current_time
                            
                            self.logger.info(f"Alert resolved: {alert.title}",
                                           extra_data={"connection_id": connection_id})
            
            except Exception as e:
                self.logger.error(f"Error checking alert rule: {rule_name}",
                                extra_data={"error": str(e)})
    
    async def _cleanup_old_alerts(self) -> None:
        """Clean up old resolved alerts"""
        cutoff_time = datetime.now() - timedelta(hours=self.alert_retention_hours)
        
        self._alerts = [
            alert for alert in self._alerts
            if not alert.resolved or alert.resolved_at is None or alert.resolved_at > cutoff_time
        ]
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        current_time = datetime.now()
        
        # Connection overview
        connections = []
        for conn_id, health in self._connection_metrics.items():
            connections.append({
                'id': conn_id,
                'status': health.status,
                'uptime': health.uptime,
                'success_rate': health.query_success_rate,
                'avg_response_time': health.avg_response_time,
                'pool_utilization': health.pool_utilization,
                'active_alerts': len([a for a in health.alerts if not a.resolved])
            })
        
        # Top slow queries
        slow_queries = sorted(
            self._query_metrics.values(),
            key=lambda x: x.avg_execution_time,
            reverse=True
        )[:10]
        
        # Recent alerts
        recent_alerts = sorted(
            [a for a in self._alerts if not a.resolved],
            key=lambda x: x.timestamp,
            reverse=True
        )[:20]
        
        # System overview
        total_connections = sum(h.active_connections for h in self._connection_metrics.values())
        avg_success_rate = (
            sum(h.query_success_rate for h in self._connection_metrics.values()) /
            len(self._connection_metrics)
        ) if self._connection_metrics else 100.0
        
        critical_alerts = len([a for a in recent_alerts if a.level == AlertLevel.CRITICAL])
        
        return {
            'timestamp': current_time.isoformat(),
            'overview': {
                'total_connections': total_connections,
                'active_connections': len([h for h in self._connection_metrics.values() 
                                         if h.status == 'connected']),
                'avg_success_rate': avg_success_rate,
                'critical_alerts': critical_alerts,
                'total_queries': sum(q.execution_count for q in self._query_metrics.values())
            },
            'connections': connections,
            'slow_queries': [
                {
                    'query_type': q.query_type,
                    'avg_time': q.avg_execution_time,
                    'execution_count': q.execution_count,
                    'error_rate': q.error_rate
                }
                for q in slow_queries
            ],
            'alerts': [
                {
                    'id': a.id,
                    'level': a.level.value,
                    'title': a.title,
                    'description': a.description,
                    'connection_id': a.connection_id,
                    'timestamp': a.timestamp.isoformat(),
                    'current_value': a.current_value,
                    'threshold': a.threshold
                }
                for a in recent_alerts
            ],
            'historical_data': self._get_historical_trends()
        }
    
    def _get_historical_trends(self) -> Dict[str, Any]:
        """Get historical trend data for charting"""
        trends = {}
        
        for conn_id, history in self._connection_history.items():
            if not history:
                continue
            
            # Get last 50 data points
            recent_history = list(history)[-50:]
            
            trends[conn_id] = {
                'timestamps': [h['timestamp'].isoformat() for h in recent_history],
                'success_rates': [h['success_rate'] for h in recent_history],
                'response_times': [h['avg_response_time'] for h in recent_history],
                'pool_utilization': [h['pool_utilization'] for h in recent_history],
                'active_connections': [h['active_connections'] for h in recent_history]
            }
        
        return trends
    
    def get_connection_details(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed metrics for a specific connection"""
        if connection_id not in self._connection_metrics:
            return None
        
        health = self._connection_metrics[connection_id]
        history = list(self._connection_history[connection_id])
        
        # Query metrics for this connection
        connection_queries = {
            k: v for k, v in self._query_metrics.items() 
            if k.startswith(connection_id)
        }
        
        return {
            'connection': asdict(health),
            'query_metrics': [asdict(q) for q in connection_queries.values()],
            'historical_data': {
                'timestamps': [h['timestamp'].isoformat() for h in history],
                'success_rates': [h['success_rate'] for h in history],
                'response_times': [h['avg_response_time'] for h in history],
                'pool_utilization': [h['pool_utilization'] for h in history]
            },
            'alerts': [asdict(a) for a in health.alerts]
        }
    
    async def export_metrics(self, format: str = 'json', 
                           time_range: Optional[Tuple[datetime, datetime]] = None) -> str:
        """Export metrics in various formats"""
        data = self.get_dashboard_data()
        
        if format == 'json':
            return json.dumps(data, indent=2, default=str)
        
        elif format == 'prometheus':
            # Export in Prometheus format
            lines = []
            
            # Connection metrics
            for conn in data['connections']:
                lines.append(f'postgresql_connection_uptime{{connection="{conn["id"]}"}} {conn["uptime"]}')
                lines.append(f'postgresql_connection_success_rate{{connection="{conn["id"]}"}} {conn["success_rate"]}')
                lines.append(f'postgresql_connection_response_time{{connection="{conn["id"]}"}} {conn["avg_response_time"]}')
                lines.append(f'postgresql_connection_pool_utilization{{connection="{conn["id"]}"}} {conn["pool_utilization"]}')
            
            # Alert metrics
            for level in AlertLevel:
                count = len([a for a in data['alerts'] if a['level'] == level.value])
                lines.append(f'postgresql_alerts_total{{level="{level.value}"}} {count}')
            
            return '\n'.join(lines)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")


class MonitoringDashboard(LoggerMixin):
    """Real-time monitoring dashboard"""
    
    def __init__(self, collector: MonitoringCollector, update_interval: float = 10.0):
        self.collector = collector
        self.update_interval = update_interval
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the monitoring dashboard"""
        if self._running:
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("PostgreSQL monitoring dashboard started")
    
    async def stop(self) -> None:
        """Stop the monitoring dashboard"""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("PostgreSQL monitoring dashboard stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                await self.collector.collect_metrics()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in monitoring loop", extra_data={"error": str(e)})
                await asyncio.sleep(5)  # Short sleep on error
    
    def get_realtime_data(self) -> Dict[str, Any]:
        """Get real-time dashboard data"""
        return self.collector.get_dashboard_data()
    
    async def generate_report(self, connection_id: Optional[str] = None,
                             time_range: Optional[Tuple[datetime, datetime]] = None) -> str:
        """Generate performance report"""
        if connection_id:
            data = self.collector.get_connection_details(connection_id)
            if not data:
                return f"No data found for connection: {connection_id}"
            
            # Generate detailed connection report
            report = f"""
PostgreSQL Connection Performance Report
Connection ID: {connection_id}
Generated: {datetime.now().isoformat()}

CONNECTION HEALTH:
- Status: {data['connection']['status']}
- Uptime: {data['connection']['uptime']:.2f} seconds
- Success Rate: {data['connection']['query_success_rate']:.2f}%
- Average Response Time: {data['connection']['avg_response_time']:.3f}s
- Pool Utilization: {data['connection']['pool_utilization']:.1f}%

QUERY PERFORMANCE:
"""
            
            for query in data['query_metrics'][:10]:  # Top 10 queries
                report += f"""
- Query Type: {query['query_type']}
  Executions: {query['execution_count']}
  Avg Time: {query['avg_execution_time']:.3f}s
  Error Rate: {query['error_rate']:.2f}%
"""
            
            if data['alerts']:
                report += "\nACTIVE ALERTS:\n"
                for alert in data['alerts']:
                    if not alert['resolved']:
                        report += f"- {alert['title']}: {alert['description']}\n"
            
            return report
        
        else:
            # Generate system-wide report
            data = self.collector.get_dashboard_data()
            
            report = f"""
PostgreSQL System Performance Report
Generated: {datetime.now().isoformat()}

SYSTEM OVERVIEW:
- Total Connections: {data['overview']['total_connections']}
- Active Connections: {data['overview']['active_connections']}
- Average Success Rate: {data['overview']['avg_success_rate']:.2f}%
- Critical Alerts: {data['overview']['critical_alerts']}
- Total Queries: {data['overview']['total_queries']}

CONNECTION STATUS:
"""
            
            for conn in data['connections']:
                report += f"""
- {conn['id']}:
  Status: {conn['status']}
  Success Rate: {conn['success_rate']:.2f}%
  Avg Response: {conn['avg_response_time']:.3f}s
  Pool Usage: {conn['pool_utilization']:.1f}%
  Active Alerts: {conn['active_alerts']}
"""
            
            if data['slow_queries']:
                report += "\nSLOWEST QUERIES:\n"
                for query in data['slow_queries'][:5]:
                    report += f"- {query['query_type']}: {query['avg_time']:.3f}s (executed {query['execution_count']} times)\n"
            
            return report


# Global monitoring instances
_monitoring_collector: Optional[MonitoringCollector] = None
_monitoring_dashboard: Optional[MonitoringDashboard] = None


async def get_monitoring_collector() -> MonitoringCollector:
    """Get global monitoring collector instance"""
    global _monitoring_collector
    if _monitoring_collector is None:
        _monitoring_collector = MonitoringCollector()
    return _monitoring_collector


async def get_monitoring_dashboard() -> MonitoringDashboard:
    """Get global monitoring dashboard instance"""
    global _monitoring_dashboard, _monitoring_collector
    if _monitoring_dashboard is None:
        if _monitoring_collector is None:
            _monitoring_collector = MonitoringCollector()
        _monitoring_dashboard = MonitoringDashboard(_monitoring_collector)
    return _monitoring_dashboard


async def start_monitoring() -> None:
    """Start global monitoring"""
    dashboard = await get_monitoring_dashboard()
    await dashboard.start()


async def stop_monitoring() -> None:
    """Stop global monitoring"""
    if _monitoring_dashboard:
        await _monitoring_dashboard.stop()