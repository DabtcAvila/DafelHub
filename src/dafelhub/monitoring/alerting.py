"""
Alerting and Notification System
Enterprise-grade alerting with multiple notification channels and intelligent routing
@module dafelhub.monitoring.alerting
"""

import asyncio
import smtplib
import json
import time
import threading
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .logger import Logger, LogContext, get_logger
from .metrics_collector import MetricsCollector, get_metrics_collector


class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"
    INFO = "info"


class AlertStatus(Enum):
    """Alert status"""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


class NotificationChannel(Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    DISCORD = "discord"
    TEAMS = "teams"
    SMS = "sms"


@dataclass
class AlertRule:
    """Alert rule definition"""
    name: str
    description: str
    severity: AlertSeverity
    condition: str  # Expression to evaluate
    threshold: float
    duration: float = 60.0  # Duration in seconds
    labels: Dict[str, str] = None
    annotations: Dict[str, str] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}
        if self.annotations is None:
            self.annotations = {}


@dataclass
class Alert:
    """Alert instance"""
    id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    firing_time: float
    resolved_time: Optional[float] = None
    acknowledged_time: Optional[float] = None
    acknowledged_by: Optional[str] = None
    fingerprint: str = ""
    
    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self._generate_fingerprint()
    
    def _generate_fingerprint(self) -> str:
        """Generate unique fingerprint for alert"""
        content = f"{self.rule_name}:{self.title}:{sorted(self.labels.items())}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            **asdict(self),
            "severity": self.severity.value,
            "status": self.status.value,
            "firing_time": self.firing_time,
            "resolved_time": self.resolved_time,
            "acknowledged_time": self.acknowledged_time
        }


@dataclass 
class NotificationConfig:
    """Notification channel configuration"""
    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class AlertStorage:
    """SQLite-based alert storage"""
    
    def __init__(self, db_path: str = "alerts.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    labels TEXT NOT NULL,
                    annotations TEXT NOT NULL,
                    firing_time REAL NOT NULL,
                    resolved_time REAL,
                    acknowledged_time REAL,
                    acknowledged_by TEXT,
                    fingerprint TEXT NOT NULL,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON alerts(fingerprint)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)
            ''')
    
    def save_alert(self, alert: Alert):
        """Save alert to storage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO alerts 
                (id, rule_name, severity, status, title, message, labels, annotations,
                 firing_time, resolved_time, acknowledged_time, acknowledged_by, fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.id,
                alert.rule_name,
                alert.severity.value,
                alert.status.value,
                alert.title,
                alert.message,
                json.dumps(alert.labels),
                json.dumps(alert.annotations),
                alert.firing_time,
                alert.resolved_time,
                alert.acknowledged_time,
                alert.acknowledged_by,
                alert.fingerprint
            ))
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return self._get_alerts_by_status([AlertStatus.FIRING.value, AlertStatus.ACKNOWLEDGED.value])
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT * FROM alerts WHERE severity = ? ORDER BY firing_time DESC',
                (severity.value,)
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT * FROM alerts ORDER BY firing_time DESC LIMIT ?',
                (limit,)
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]
    
    def _get_alerts_by_status(self, statuses: List[str]) -> List[Alert]:
        """Get alerts by status"""
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ','.join(['?' for _ in statuses])
            cursor = conn.execute(
                f'SELECT * FROM alerts WHERE status IN ({placeholders}) ORDER BY firing_time DESC',
                statuses
            )
            return [self._row_to_alert(row) for row in cursor.fetchall()]
    
    def _row_to_alert(self, row) -> Alert:
        """Convert database row to Alert object"""
        return Alert(
            id=row[0],
            rule_name=row[1],
            severity=AlertSeverity(row[2]),
            status=AlertStatus(row[3]),
            title=row[4],
            message=row[5],
            labels=json.loads(row[6]),
            annotations=json.loads(row[7]),
            firing_time=row[8],
            resolved_time=row[9],
            acknowledged_time=row[10],
            acknowledged_by=row[11],
            fingerprint=row[12]
        )


class NotificationSender:
    """Handle sending notifications through various channels"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
    
    async def send_email(self, alert: Alert, config: Dict[str, Any], recipients: List[str]):
        """Send email notification"""
        try:
            smtp_host = config.get('smtp_host', 'localhost')
            smtp_port = config.get('smtp_port', 587)
            username = config.get('username')
            password = config.get('password')
            from_addr = config.get('from_addr', username)
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            
            # Email body
            body = f"""
Alert: {alert.title}

Severity: {alert.severity.value.upper()}
Status: {alert.status.value}
Time: {datetime.fromtimestamp(alert.firing_time).strftime('%Y-%m-%d %H:%M:%S')}

Description:
{alert.message}

Labels:
{json.dumps(alert.labels, indent=2)}

Rule: {alert.rule_name}
Alert ID: {alert.id}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if username and password:
                    server.starttls()
                    server.login(username, password)
                server.send_message(msg)
            
            self.logger.info(f"Email notification sent for alert {alert.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
    
    async def send_slack(self, alert: Alert, config: Dict[str, Any]):
        """Send Slack notification"""
        if not REQUESTS_AVAILABLE:
            self.logger.error("Requests library required for Slack notifications")
            return
        
        try:
            webhook_url = config.get('webhook_url')
            if not webhook_url:
                self.logger.error("Slack webhook URL not configured")
                return
            
            # Color based on severity
            color_map = {
                AlertSeverity.CRITICAL: "#FF0000",
                AlertSeverity.HIGH: "#FF8800", 
                AlertSeverity.MEDIUM: "#FFAA00",
                AlertSeverity.LOW: "#00AA00",
                AlertSeverity.INFO: "#0088AA"
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "#808080"),
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Status", "value": alert.status.value, "short": True},
                        {"title": "Rule", "value": alert.rule_name, "short": True},
                        {"title": "Time", "value": datetime.fromtimestamp(alert.firing_time).strftime('%Y-%m-%d %H:%M:%S'), "short": True}
                    ],
                    "footer": f"Alert ID: {alert.id}"
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info(f"Slack notification sent for alert {alert.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send Slack notification: {e}")
    
    async def send_webhook(self, alert: Alert, config: Dict[str, Any]):
        """Send generic webhook notification"""
        if not REQUESTS_AVAILABLE:
            self.logger.error("Requests library required for webhook notifications")
            return
        
        try:
            webhook_url = config.get('url')
            if not webhook_url:
                self.logger.error("Webhook URL not configured")
                return
            
            headers = config.get('headers', {})
            headers.setdefault('Content-Type', 'application/json')
            
            payload = {
                "alert": alert.to_dict(),
                "timestamp": time.time()
            }
            
            response = requests.post(
                webhook_url, 
                json=payload, 
                headers=headers,
                timeout=config.get('timeout', 10)
            )
            response.raise_for_status()
            
            self.logger.info(f"Webhook notification sent for alert {alert.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook notification: {e}")


class AlertEvaluator:
    """Evaluate alert rules against metrics"""
    
    def __init__(self, 
                 metrics_collector: MetricsCollector,
                 logger: Logger):
        self.metrics_collector = metrics_collector
        self.logger = logger
        self.rule_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
    
    def evaluate_rule(self, rule: AlertRule) -> Optional[Alert]:
        """Evaluate single alert rule"""
        if not rule.enabled:
            return None
        
        try:
            # Get current metric value
            metric_value = self._get_metric_value(rule.condition)
            if metric_value is None:
                return None
            
            # Check if threshold is breached
            is_firing = self._evaluate_condition(metric_value, rule.threshold, rule.condition)
            
            # Get rule state
            rule_state = self.rule_states[rule.name]
            currently_firing = rule_state.get('firing', False)
            first_breach_time = rule_state.get('first_breach_time', 0)
            
            current_time = time.time()
            
            if is_firing and not currently_firing:
                # Start of potential alert
                rule_state['firing'] = True
                rule_state['first_breach_time'] = current_time
                self.logger.debug(f"Alert rule {rule.name} threshold breached")
                return None
            
            elif is_firing and currently_firing:
                # Check if duration exceeded
                if current_time - first_breach_time >= rule.duration:
                    # Fire alert
                    alert_id = f"{rule.name}_{int(current_time)}"
                    
                    alert = Alert(
                        id=alert_id,
                        rule_name=rule.name,
                        severity=rule.severity,
                        status=AlertStatus.FIRING,
                        title=rule.description,
                        message=f"Metric value {metric_value:.2f} exceeds threshold {rule.threshold} for {rule.duration}s",
                        labels=rule.labels.copy(),
                        annotations=rule.annotations.copy(),
                        firing_time=current_time
                    )
                    
                    # Reset rule state
                    rule_state['firing'] = False
                    rule_state['first_breach_time'] = 0
                    
                    return alert
            
            elif not is_firing and currently_firing:
                # Threshold no longer breached
                rule_state['firing'] = False
                rule_state['first_breach_time'] = 0
                self.logger.debug(f"Alert rule {rule.name} threshold no longer breached")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error evaluating alert rule {rule.name}: {e}")
            return None
    
    def _get_metric_value(self, condition: str) -> Optional[float]:
        """Extract metric value from condition string"""
        try:
            # Simple parsing for conditions like "cpu_usage > 80"
            if '>' in condition:
                metric_name = condition.split('>')[0].strip()
            elif '<' in condition:
                metric_name = condition.split('<')[0].strip()
            elif '=' in condition:
                metric_name = condition.split('=')[0].strip()
            else:
                return None
            
            # Get metric samples
            samples = self.metrics_collector.get_all_samples()
            for sample in samples:
                if sample.name == metric_name:
                    return sample.value
            
            return None
            
        except Exception:
            return None
    
    def _evaluate_condition(self, value: float, threshold: float, condition: str) -> bool:
        """Evaluate if condition is met"""
        if '>' in condition:
            return value > threshold
        elif '<' in condition:
            return value < threshold
        elif '>=' in condition:
            return value >= threshold
        elif '<=' in condition:
            return value <= threshold
        elif '==' in condition:
            return abs(value - threshold) < 0.001  # Float comparison
        else:
            return value > threshold  # Default to greater than


class AlertManager:
    """
    Enterprise Alert Manager
    
    Features:
    - Flexible rule-based alerting
    - Multiple notification channels (email, Slack, webhooks)
    - Alert deduplication and grouping
    - Alert acknowledgment and silencing
    - Historical alert storage
    - Intelligent routing and escalation
    - Rate limiting and throttling
    """
    
    _instance: Optional['AlertManager'] = None
    _lock = threading.Lock()
    
    def __init__(self,
                 metrics_collector: Optional[MetricsCollector] = None,
                 logger: Optional[Logger] = None,
                 storage_path: str = "alerts.db",
                 evaluation_interval: float = 30.0):
        
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.logger = logger or get_logger()
        self.evaluation_interval = evaluation_interval
        
        # Components
        self.storage = AlertStorage(storage_path)
        self.evaluator = AlertEvaluator(self.metrics_collector, self.logger)
        self.sender = NotificationSender(self.logger)
        
        # Configuration
        self.rules: Dict[str, AlertRule] = {}
        self.notification_configs: Dict[str, NotificationConfig] = {}
        self.silences: Dict[str, float] = {}  # fingerprint -> silence_until
        
        # State
        self.active_alerts: Dict[str, Alert] = {}
        self.running = False
        self.evaluation_task = None
        
        # Default rules
        self._setup_default_rules()
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'AlertManager':
        """Get singleton instance with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance
    
    def _setup_default_rules(self):
        """Setup default alert rules"""
        
        # High CPU usage
        self.add_rule(AlertRule(
            name="high_cpu_usage",
            description="High CPU Usage Detected",
            severity=AlertSeverity.HIGH,
            condition="system_cpu_percent > 80",
            threshold=80.0,
            duration=300.0,  # 5 minutes
            labels={"component": "system", "resource": "cpu"},
            annotations={"summary": "CPU usage is above 80%"}
        ))
        
        # High memory usage
        self.add_rule(AlertRule(
            name="high_memory_usage", 
            description="High Memory Usage Detected",
            severity=AlertSeverity.HIGH,
            condition="system_memory_percent > 85",
            threshold=85.0,
            duration=300.0,
            labels={"component": "system", "resource": "memory"},
            annotations={"summary": "Memory usage is above 85%"}
        ))
        
        # High error rate
        self.add_rule(AlertRule(
            name="high_error_rate",
            description="High Error Rate Detected", 
            severity=AlertSeverity.CRITICAL,
            condition="errors_total > 10",
            threshold=10.0,
            duration=60.0,  # 1 minute
            labels={"component": "application", "type": "errors"},
            annotations={"summary": "Error rate is above threshold"}
        ))
        
        # Disk space low
        self.add_rule(AlertRule(
            name="disk_space_low",
            description="Low Disk Space Warning",
            severity=AlertSeverity.MEDIUM,
            condition="system_disk_usage_percent > 90",
            threshold=90.0,
            duration=600.0,  # 10 minutes
            labels={"component": "system", "resource": "disk"},
            annotations={"summary": "Disk space is above 90%"}
        ))
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule"""
        self.rules[rule.name] = rule
        self.logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove alert rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.logger.info(f"Removed alert rule: {rule_name}")
    
    def add_notification_config(self, name: str, config: NotificationConfig):
        """Add notification configuration"""
        self.notification_configs[name] = config
        self.logger.info(f"Added notification config: {name}")
    
    def configure_email(self, 
                       name: str = "default_email",
                       smtp_host: str = "localhost",
                       smtp_port: int = 587,
                       username: str = "",
                       password: str = "",
                       recipients: List[str] = None):
        """Configure email notifications"""
        config = NotificationConfig(
            channel=NotificationChannel.EMAIL,
            enabled=True,
            config={
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "username": username,
                "password": password,
                "from_addr": username,
                "recipients": recipients or []
            }
        )
        self.add_notification_config(name, config)
    
    def configure_slack(self,
                       name: str = "default_slack", 
                       webhook_url: str = ""):
        """Configure Slack notifications"""
        config = NotificationConfig(
            channel=NotificationChannel.SLACK,
            enabled=True,
            config={"webhook_url": webhook_url}
        )
        self.add_notification_config(name, config)
    
    def configure_webhook(self,
                         name: str = "default_webhook",
                         url: str = "",
                         headers: Dict[str, str] = None):
        """Configure webhook notifications"""
        config = NotificationConfig(
            channel=NotificationChannel.WEBHOOK,
            enabled=True,
            config={
                "url": url,
                "headers": headers or {},
                "timeout": 10
            }
        )
        self.add_notification_config(name, config)
    
    async def start(self):
        """Start alert evaluation and notification"""
        if self.running:
            return
        
        self.running = True
        self.logger.info("Starting alert manager")
        
        # Start evaluation loop
        self.evaluation_task = asyncio.create_task(self._evaluation_loop())
    
    async def stop(self):
        """Stop alert manager"""
        self.running = False
        if self.evaluation_task:
            self.evaluation_task.cancel()
            try:
                await self.evaluation_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped alert manager")
    
    async def _evaluation_loop(self):
        """Main alert evaluation loop"""
        while self.running:
            try:
                await self._evaluate_rules()
                await asyncio.sleep(self.evaluation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in alert evaluation loop: {e}")
                await asyncio.sleep(self.evaluation_interval)
    
    async def _evaluate_rules(self):
        """Evaluate all alert rules"""
        for rule in self.rules.values():
            try:
                alert = self.evaluator.evaluate_rule(rule)
                if alert:
                    await self._handle_alert(alert)
            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule.name}: {e}")
    
    async def _handle_alert(self, alert: Alert):
        """Handle new alert"""
        # Check if alert is silenced
        if self._is_silenced(alert):
            return
        
        # Check for duplicate
        existing_alert = self.active_alerts.get(alert.fingerprint)
        if existing_alert:
            return  # Already active
        
        # Store alert
        self.active_alerts[alert.fingerprint] = alert
        self.storage.save_alert(alert)
        
        # Log alert
        self.logger.warn(
            f"Alert fired: {alert.title}",
            LogContext(
                operation="alert_fired",
                component="alerting",
                correlation_id=alert.id
            )
        )
        
        # Send notifications
        await self._send_notifications(alert)
    
    def _is_silenced(self, alert: Alert) -> bool:
        """Check if alert is silenced"""
        silence_until = self.silences.get(alert.fingerprint, 0)
        return time.time() < silence_until
    
    async def _send_notifications(self, alert: Alert):
        """Send notifications for alert"""
        for name, config in self.notification_configs.items():
            if not config.enabled:
                continue
            
            try:
                if config.channel == NotificationChannel.EMAIL:
                    recipients = config.config.get('recipients', [])
                    if recipients:
                        await self.sender.send_email(alert, config.config, recipients)
                
                elif config.channel == NotificationChannel.SLACK:
                    await self.sender.send_slack(alert, config.config)
                
                elif config.channel == NotificationChannel.WEBHOOK:
                    await self.sender.send_webhook(alert, config.config)
                
            except Exception as e:
                self.logger.error(f"Failed to send notification via {name}: {e}")
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system"):
        """Acknowledge an alert"""
        for fingerprint, alert in self.active_alerts.items():
            if alert.id == alert_id:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_time = time.time()
                alert.acknowledged_by = acknowledged_by
                self.storage.save_alert(alert)
                
                self.logger.info(f"Alert acknowledged: {alert_id} by {acknowledged_by}")
                break
    
    def silence_alert(self, alert_id: str, duration_hours: float = 1.0):
        """Silence an alert for specified duration"""
        for fingerprint, alert in self.active_alerts.items():
            if alert.id == alert_id:
                silence_until = time.time() + (duration_hours * 3600)
                self.silences[fingerprint] = silence_until
                
                alert.status = AlertStatus.SILENCED
                self.storage.save_alert(alert)
                
                self.logger.info(f"Alert silenced: {alert_id} for {duration_hours} hours")
                break
    
    def resolve_alert(self, alert_id: str):
        """Manually resolve an alert"""
        for fingerprint, alert in self.active_alerts.items():
            if alert.id == alert_id:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_time = time.time()
                self.storage.save_alert(alert)
                
                # Remove from active alerts
                del self.active_alerts[fingerprint]
                
                self.logger.info(f"Alert resolved: {alert_id}")
                break
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        return self.storage.get_alert_history(limit)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get alerting statistics"""
        active_alerts = self.get_active_alerts()
        alert_history = self.get_alert_history(1000)  # Last 1000 alerts
        
        severity_counts = defaultdict(int)
        status_counts = defaultdict(int)
        
        for alert in alert_history:
            severity_counts[alert.severity.value] += 1
            status_counts[alert.status.value] += 1
        
        return {
            "active_alerts": len(active_alerts),
            "total_rules": len(self.rules),
            "notification_configs": len(self.notification_configs),
            "alerts_last_24h": len([
                a for a in alert_history 
                if a.firing_time > time.time() - 86400
            ]),
            "severity_distribution": dict(severity_counts),
            "status_distribution": dict(status_counts),
            "silenced_alerts": len(self.silences)
        }


# Global alert manager instance
_global_alert_manager: Optional[AlertManager] = None


def get_alert_manager(**kwargs) -> AlertManager:
    """Get global alert manager instance"""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager.get_instance(**kwargs)
    return _global_alert_manager