"""
DafelHub Monitor Command
Enterprise monitoring, metrics collection, and observability platform.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.layout import Layout
from rich.live import Live
from rich.tree import Tree
from rich.columns import Columns
import time
import asyncio
import json

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)
console = Console()

app = typer.Typer(help="Monitor services, metrics, and system health")


class MetricType(str, Enum):
    """Types of metrics to collect"""
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    RESOURCE_USAGE = "resource_usage"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MonitoringEngine(LoggerMixin):
    """
    Enterprise monitoring and observability engine
    """
    
    def __init__(self):
        self.metrics_store: Dict[str, List[Dict[str, Any]]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.dashboards: Dict[str, Dict[str, Any]] = {}
        
    def collect_metrics(self, service: str, metric_type: MetricType) -> Dict[str, Any]:
        """
        Collect metrics for a specific service
        """
        self.logger.info(f"Collecting {metric_type.value} metrics for {service}")
        
        # Mock metric data based on type
        if metric_type == MetricType.PERFORMANCE:
            return {
                "cpu_usage": 45.2,
                "memory_usage": 62.8,
                "disk_usage": 34.1,
                "network_io": 128.4
            }
        elif metric_type == MetricType.AVAILABILITY:
            return {
                "uptime": 99.95,
                "downtime_minutes": 3.6,
                "health_check_success_rate": 99.8
            }
        elif metric_type == MetricType.ERROR_RATE:
            return {
                "error_rate": 0.12,
                "5xx_errors": 8,
                "4xx_errors": 24,
                "total_requests": 10542
            }
        elif metric_type == MetricType.THROUGHPUT:
            return {
                "requests_per_second": 142.5,
                "requests_per_minute": 8550,
                "peak_rps": 289.7
            }
        elif metric_type == MetricType.LATENCY:
            return {
                "avg_response_time": 85.2,
                "p95_response_time": 156.8,
                "p99_response_time": 234.5
            }
        else:
            return {
                "custom_metric_1": 42.0,
                "custom_metric_2": 3.14,
                "timestamp": datetime.now().isoformat()
            }
    
    def generate_alerts(self, service: str, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate alerts based on metric thresholds
        """
        alerts = []
        
        # CPU usage alert
        if metrics.get("cpu_usage", 0) > 80:
            alerts.append({
                "id": f"cpu-{service}-{int(time.time())}",
                "service": service,
                "severity": AlertSeverity.HIGH.value,
                "message": f"High CPU usage: {metrics['cpu_usage']}%",
                "timestamp": datetime.now().isoformat(),
                "threshold": 80
            })
        
        # Error rate alert  
        if metrics.get("error_rate", 0) > 1.0:
            alerts.append({
                "id": f"error-{service}-{int(time.time())}",
                "service": service,
                "severity": AlertSeverity.CRITICAL.value,
                "message": f"High error rate: {metrics['error_rate']}%",
                "timestamp": datetime.now().isoformat(),
                "threshold": 1.0
            })
        
        # Response time alert
        if metrics.get("p95_response_time", 0) > 200:
            alerts.append({
                "id": f"latency-{service}-{int(time.time())}",
                "service": service,
                "severity": AlertSeverity.MEDIUM.value,
                "message": f"High latency: {metrics['p95_response_time']}ms",
                "timestamp": datetime.now().isoformat(),
                "threshold": 200
            })
        
        return alerts
    
    def create_dashboard(self, name: str, services: List[str]) -> Dict[str, Any]:
        """
        Create a monitoring dashboard
        """
        dashboard = {
            "name": name,
            "services": services,
            "created": datetime.now().isoformat(),
            "widgets": [
                {
                    "type": "metrics_table",
                    "title": "Service Overview",
                    "services": services
                },
                {
                    "type": "alert_panel", 
                    "title": "Active Alerts",
                    "severity_filter": ["critical", "high"]
                },
                {
                    "type": "performance_chart",
                    "title": "Performance Trends",
                    "time_range": "1h"
                }
            ]
        }
        
        self.dashboards[name] = dashboard
        return dashboard


@app.command()
def dashboard(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Dashboard name"),
    services: Optional[str] = typer.Option(None, "--services", "-s", help="Comma-separated list of services"),
    refresh: int = typer.Option(5, "--refresh", "-r", help="Refresh interval in seconds"),
    save: bool = typer.Option(False, "--save", help="Save dashboard configuration")
) -> None:
    """
    Display real-time monitoring dashboard
    """
    if not name:
        name = "main-dashboard"
    
    service_list = services.split(",") if services else ["api-service", "worker-service", "auth-service"]
    
    console.print(f"[bold blue]Monitoring Dashboard:[/bold blue] {name}")
    console.print(f"[dim]Services: {', '.join(service_list)} | Refresh: {refresh}s[/dim]\n")
    
    monitoring = MonitoringEngine()
    
    # Create dashboard layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )
    
    try:
        with Live(layout, refresh_per_second=1/refresh, screen=True) as live:
            while True:
                # Header
                header_table = Table.grid()
                header_table.add_column()
                header_table.add_row(
                    f"[bold]DafelHub Monitoring Dashboard[/bold] - {name}",
                )
                header_table.add_row(
                    f"[dim]Last updated: {datetime.now().strftime('%H:%M:%S')} | "
                    f"Services: {len(service_list)} | Auto-refresh: {refresh}s[/dim]"
                )
                layout["header"].update(Panel(header_table, border_style="blue"))
                
                # Collect current metrics
                all_metrics = {}
                for service in service_list:
                    all_metrics[service] = monitoring.collect_metrics(service, MetricType.PERFORMANCE)
                
                # Left panel - Service metrics
                metrics_table = Table(title="Service Metrics")
                metrics_table.add_column("Service", style="cyan")
                metrics_table.add_column("CPU %", style="yellow")
                metrics_table.add_column("Memory %", style="green")
                metrics_table.add_column("Status", style="bold")
                
                for service, metrics in all_metrics.items():
                    cpu = metrics.get("cpu_usage", 0)
                    memory = metrics.get("memory_usage", 0)
                    
                    # Determine status color
                    if cpu > 80 or memory > 90:
                        status = "[red]CRITICAL[/red]"
                    elif cpu > 60 or memory > 75:
                        status = "[yellow]WARNING[/yellow]"
                    else:
                        status = "[green]HEALTHY[/green]"
                    
                    metrics_table.add_row(
                        service,
                        f"{cpu:.1f}",
                        f"{memory:.1f}",
                        status
                    )
                
                layout["left"].update(Panel(metrics_table, title="System Overview"))
                
                # Right panel - Alerts and logs
                alerts = []
                for service, metrics in all_metrics.items():
                    service_alerts = monitoring.generate_alerts(service, metrics)
                    alerts.extend(service_alerts)
                
                if alerts:
                    alert_table = Table(title="Active Alerts")
                    alert_table.add_column("Service", style="cyan")
                    alert_table.add_column("Severity", style="bold")
                    alert_table.add_column("Message", style="white")
                    
                    for alert in alerts[-5:]:  # Show last 5 alerts
                        severity_color = {
                            "critical": "red",
                            "high": "orange1", 
                            "medium": "yellow",
                            "low": "green"
                        }.get(alert["severity"], "white")
                        
                        alert_table.add_row(
                            alert["service"],
                            f"[{severity_color}]{alert['severity'].upper()}[/{severity_color}]",
                            alert["message"]
                        )
                    
                    layout["right"].update(Panel(alert_table, title="Alerts", border_style="red"))
                else:
                    layout["right"].update(Panel(
                        "[green]No active alerts[/green]\n\n[dim]All services operating normally[/dim]",
                        title="System Status",
                        border_style="green"
                    ))
                
                # Footer
                footer_table = Table.grid()
                footer_table.add_column()
                footer_table.add_row("[dim]Press Ctrl+C to exit | Commands: dafelhub monitor service <name> | dafelhub monitor alerts[/dim]")
                layout["footer"].update(footer_table)
                
                time.sleep(refresh)
                
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped[/dim]")
        
        if save:
            dashboard_config = monitoring.create_dashboard(name, service_list)
            config_path = Path(f"{name}-dashboard.json")
            with open(config_path, 'w') as f:
                json.dump(dashboard_config, f, indent=2)
            console.print(f"[green]Dashboard configuration saved to {config_path}[/green]")


@app.command()
def service(
    name: str = typer.Argument(..., help="Service name to monitor"),
    metric_type: MetricType = typer.Option(
        MetricType.PERFORMANCE,
        "--type",
        "-t",
        help="Type of metrics to display"
    ),
    duration: int = typer.Option(60, "--duration", "-d", help="Monitoring duration in seconds"),
    threshold_alerts: bool = typer.Option(True, "--alerts/--no-alerts", help="Enable threshold alerts")
) -> None:
    """
    Monitor specific service metrics in detail
    """
    console.print(f"[bold blue]Monitoring service:[/bold blue] {name}")
    console.print(f"[dim]Metric type: {metric_type.value} | Duration: {duration}s[/dim]\n")
    
    monitoring = MonitoringEngine()
    start_time = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        monitor_task = progress.add_task("Collecting metrics...", total=duration)
        
        try:
            while time.time() - start_time < duration:
                elapsed = time.time() - start_time
                progress.update(monitor_task, completed=elapsed)
                
                # Collect metrics
                metrics = monitoring.collect_metrics(name, metric_type)
                
                # Display current metrics
                current_table = Table(title=f"{name} - {metric_type.value.title()} Metrics")
                current_table.add_column("Metric", style="cyan")
                current_table.add_column("Value", style="green")
                current_table.add_column("Status", style="bold")
                
                for metric_name, value in metrics.items():
                    # Determine status based on metric type and value
                    if isinstance(value, (int, float)):
                        if metric_type == MetricType.PERFORMANCE:
                            if "usage" in metric_name.lower() and value > 80:
                                status = "[red]HIGH[/red]"
                            elif "usage" in metric_name.lower() and value > 60:
                                status = "[yellow]MODERATE[/yellow]"
                            else:
                                status = "[green]NORMAL[/green]"
                        else:
                            status = "[green]OK[/green]"
                        
                        current_table.add_row(
                            metric_name.replace("_", " ").title(),
                            f"{value:.1f}" if isinstance(value, float) else str(value),
                            status
                        )
                    else:
                        current_table.add_row(
                            metric_name.replace("_", " ").title(),
                            str(value),
                            "[green]OK[/green]"
                        )
                
                console.clear()
                console.print(f"[bold blue]Monitoring:[/bold blue] {name} ({metric_type.value})")
                console.print(f"[dim]Elapsed: {elapsed:.1f}s / {duration}s[/dim]\n")
                console.print(current_table)
                
                # Generate and show alerts if enabled
                if threshold_alerts:
                    alerts = monitoring.generate_alerts(name, metrics)
                    if alerts:
                        console.print("\n[bold red]ALERTS:[/bold red]")
                        for alert in alerts:
                            severity_color = {
                                "critical": "red",
                                "high": "orange1",
                                "medium": "yellow"
                            }.get(alert["severity"], "white")
                            console.print(f"[{severity_color}]• {alert['message']}[/{severity_color}]")
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            console.print("\n[dim]Monitoring stopped by user[/dim]")
    
    console.print(Panel(
        f"[green]✓[/green] Monitoring session completed for '{name}'\n"
        f"[dim]Duration: {duration}s[/dim]\n\n"
        f"[bold]View historical data:[/bold]\n"
        f"dafelhub monitor history {name}\n"
        f"dafelhub monitor dashboard --services {name}",
        title="[bold green]Monitoring Complete[/bold green]",
        border_style="green"
    ))


@app.command()
def alerts(
    severity: Optional[AlertSeverity] = typer.Option(None, "--severity", "-s", help="Filter by alert severity"),
    service: Optional[str] = typer.Option(None, "--service", help="Filter by service name"),
    last_hours: int = typer.Option(24, "--hours", help="Show alerts from last N hours")
) -> None:
    """
    Display system alerts and notifications
    """
    console.print("[bold blue]System Alerts[/bold blue]")
    
    # Mock alert data
    mock_alerts = [
        {
            "id": "alert-001",
            "service": "api-service",
            "severity": "critical",
            "message": "Service unresponsive for 5 minutes",
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "resolved": False
        },
        {
            "id": "alert-002", 
            "service": "worker-service",
            "severity": "high",
            "message": "High memory usage detected (89%)",
            "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
            "resolved": False
        },
        {
            "id": "alert-003",
            "service": "auth-service", 
            "severity": "medium",
            "message": "Response time above threshold (250ms)",
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "resolved": True
        },
        {
            "id": "alert-004",
            "service": "api-service",
            "severity": "low",
            "message": "SSL certificate expires in 30 days",
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "resolved": False
        }
    ]
    
    # Filter alerts
    filtered_alerts = mock_alerts
    
    if severity:
        filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity.value]
    
    if service:
        filtered_alerts = [a for a in filtered_alerts if a["service"] == service]
    
    # Filter by time
    cutoff_time = datetime.now() - timedelta(hours=last_hours)
    filtered_alerts = [
        a for a in filtered_alerts 
        if datetime.fromisoformat(a["timestamp"]) > cutoff_time
    ]
    
    if not filtered_alerts:
        console.print(Panel(
            "[green]No alerts found matching the criteria[/green]\n\n"
            "[dim]All systems operating normally[/dim]",
            title="Alert Status",
            border_style="green"
        ))
        return
    
    # Group alerts by severity
    alert_groups = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": []
    }
    
    for alert in filtered_alerts:
        alert_groups[alert["severity"]].append(alert)
    
    # Display alerts by severity
    for severity_level, alerts in alert_groups.items():
        if not alerts:
            continue
            
        severity_color = {
            "critical": "red",
            "high": "orange1",
            "medium": "yellow", 
            "low": "blue"
        }.get(severity_level, "white")
        
        console.print(f"\n[bold {severity_color}]{severity_level.upper()} ALERTS ({len(alerts)})[/bold {severity_color}]")
        
        alert_table = Table()
        alert_table.add_column("Service", style="cyan")
        alert_table.add_column("Message", style="white")
        alert_table.add_column("Time", style="dim")
        alert_table.add_column("Status", style="bold")
        
        for alert in alerts:
            timestamp = datetime.fromisoformat(alert["timestamp"])
            time_ago = datetime.now() - timestamp
            
            if time_ago.total_seconds() < 3600:
                time_str = f"{int(time_ago.total_seconds() / 60)}m ago"
            else:
                time_str = f"{int(time_ago.total_seconds() / 3600)}h ago"
            
            status = "[green]RESOLVED[/green]" if alert["resolved"] else "[red]ACTIVE[/red]"
            
            alert_table.add_row(
                alert["service"],
                alert["message"],
                time_str,
                status
            )
        
        console.print(alert_table)
    
    # Show summary
    total_active = len([a for a in filtered_alerts if not a["resolved"]])
    console.print(f"\n[dim]Total alerts: {len(filtered_alerts)} | Active: {total_active} | "
                 f"Resolved: {len(filtered_alerts) - total_active}[/dim]")


@app.command() 
def metrics(
    service: str = typer.Argument(..., help="Service name"),
    metric_types: Optional[str] = typer.Option(
        None,
        "--types",
        "-t", 
        help="Comma-separated metric types (performance,availability,latency,etc.)"
    ),
    format_output: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, csv)"
    ),
    time_range: str = typer.Option(
        "1h", 
        "--range",
        "-r",
        help="Time range (1h, 6h, 24h, 7d)"
    )
) -> None:
    """
    Display detailed metrics for a service
    """
    console.print(f"[bold blue]Metrics for service:[/bold blue] {service}")
    console.print(f"[dim]Time range: {time_range} | Format: {format_output}[/dim]\n")
    
    monitoring = MonitoringEngine()
    
    # Parse metric types
    if metric_types:
        types_to_collect = [MetricType(t.strip()) for t in metric_types.split(",")]
    else:
        types_to_collect = [MetricType.PERFORMANCE, MetricType.AVAILABILITY, MetricType.LATENCY]
    
    # Collect all requested metrics
    all_metrics = {}
    for metric_type in types_to_collect:
        all_metrics[metric_type.value] = monitoring.collect_metrics(service, metric_type)
    
    if format_output == "json":
        # JSON output
        output = {
            "service": service,
            "timestamp": datetime.now().isoformat(),
            "time_range": time_range,
            "metrics": all_metrics
        }
        console.print_json(data=output)
        
    elif format_output == "csv":
        # CSV output
        console.print("metric_type,metric_name,value")
        for metric_type, metrics in all_metrics.items():
            for metric_name, value in metrics.items():
                console.print(f"{metric_type},{metric_name},{value}")
                
    else:
        # Table output (default)
        for metric_type, metrics in all_metrics.items():
            metric_table = Table(title=f"{service} - {metric_type.title()} Metrics")
            metric_table.add_column("Metric", style="cyan")
            metric_table.add_column("Current Value", style="green")
            metric_table.add_column("Threshold", style="yellow")
            metric_table.add_column("Status", style="bold")
            
            for metric_name, value in metrics.items():
                # Define thresholds based on metric type
                if metric_type == "performance":
                    threshold = 80 if "usage" in metric_name else "N/A"
                    if isinstance(threshold, (int, float)) and isinstance(value, (int, float)):
                        status = "[red]HIGH[/red]" if value > threshold else "[green]OK[/green]"
                    else:
                        status = "[green]OK[/green]"
                else:
                    threshold = "N/A"
                    status = "[green]OK[/green]"
                
                metric_table.add_row(
                    metric_name.replace("_", " ").title(),
                    str(value) + ("%" if "usage" in metric_name or "rate" in metric_name else ""),
                    str(threshold) + ("%" if isinstance(threshold, (int, float)) and "usage" in metric_name else ""),
                    status
                )
            
            console.print(metric_table)
            console.print()  # Add spacing between tables


@app.command()
def history(
    service: str = typer.Argument(..., help="Service name"),
    hours: int = typer.Option(24, "--hours", "-h", help="Hours of history to display"),
    metric_type: Optional[MetricType] = typer.Option(None, "--type", "-t", help="Specific metric type")
) -> None:
    """
    Show historical metrics and trends for a service
    """
    console.print(f"[bold blue]Historical metrics for:[/bold blue] {service}")
    console.print(f"[dim]Last {hours} hours[/dim]\n")
    
    # Mock historical data
    historical_data = []
    base_time = datetime.now()
    
    for i in range(hours):
        timestamp = base_time - timedelta(hours=i)
        historical_data.append({
            "timestamp": timestamp.strftime("%H:%M"),
            "cpu_usage": 45 + (i % 20) - 10,
            "memory_usage": 60 + (i % 15) - 7,
            "response_time": 80 + (i % 30) - 15,
            "error_rate": max(0, 0.1 + (i % 5) * 0.02)
        })
    
    historical_data.reverse()  # Show chronological order
    
    # Create trend table
    trend_table = Table(title=f"Metrics Trend - Last {hours} Hours")
    trend_table.add_column("Time", style="dim")
    trend_table.add_column("CPU %", style="yellow")
    trend_table.add_column("Memory %", style="green")
    trend_table.add_column("Response Time (ms)", style="blue")
    trend_table.add_column("Error Rate %", style="red")
    
    # Show recent data points (last 10)
    recent_data = historical_data[-10:] if len(historical_data) > 10 else historical_data
    
    for data_point in recent_data:
        trend_table.add_row(
            data_point["timestamp"],
            f"{data_point['cpu_usage']:.1f}",
            f"{data_point['memory_usage']:.1f}",
            f"{data_point['response_time']:.1f}",
            f"{data_point['error_rate']:.2f}"
        )
    
    console.print(trend_table)
    
    # Show summary statistics
    console.print("\n[bold]Summary Statistics:[/bold]")
    
    summary_table = Table()
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Average", style="green")
    summary_table.add_column("Peak", style="yellow")
    summary_table.add_column("Minimum", style="blue")
    
    # Calculate stats
    cpu_values = [d["cpu_usage"] for d in historical_data]
    memory_values = [d["memory_usage"] for d in historical_data]
    response_values = [d["response_time"] for d in historical_data]
    error_values = [d["error_rate"] for d in historical_data]
    
    summary_table.add_row(
        "CPU Usage (%)",
        f"{sum(cpu_values)/len(cpu_values):.1f}",
        f"{max(cpu_values):.1f}",
        f"{min(cpu_values):.1f}"
    )
    summary_table.add_row(
        "Memory Usage (%)",
        f"{sum(memory_values)/len(memory_values):.1f}",
        f"{max(memory_values):.1f}",
        f"{min(memory_values):.1f}"
    )
    summary_table.add_row(
        "Response Time (ms)",
        f"{sum(response_values)/len(response_values):.1f}",
        f"{max(response_values):.1f}",
        f"{min(response_values):.1f}"
    )
    summary_table.add_row(
        "Error Rate (%)",
        f"{sum(error_values)/len(error_values):.2f}",
        f"{max(error_values):.2f}",
        f"{min(error_values):.2f}"
    )
    
    console.print(summary_table)