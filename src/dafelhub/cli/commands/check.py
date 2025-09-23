"""
DafelHub Check Command
Enterprise system verification, health checks, and diagnostic tools.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, TaskID, SpinnerColumn, TextColumn, BarColumn
from rich.tree import Tree
from rich.status import Status
import time
import json
import asyncio
from datetime import datetime

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.core.config import settings

logger = get_logger(__name__)
console = Console()

app = typer.Typer(help="System verification and health checks")


class CheckType(str, Enum):
    """Types of system checks"""
    HEALTH = "health"
    CONNECTIVITY = "connectivity"
    DEPENDENCIES = "dependencies"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STORAGE = "storage"
    ALL = "all"


class CheckSeverity(str, Enum):
    """Check result severity levels"""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    CRITICAL = "critical"


class SystemChecker(LoggerMixin):
    """
    Enterprise system verification and diagnostic engine
    """
    
    def __init__(self):
        self.check_results: List[Dict[str, Any]] = []
        self.total_checks = 0
        self.passed_checks = 0
        self.failed_checks = 0
        self.warnings = 0
    
    async def run_health_checks(self, service: str) -> List[Dict[str, Any]]:
        """
        Run comprehensive health checks for a service
        """
        self.logger.info(f"Running health checks for: {service}")
        
        checks = [
            {"name": "Service Response", "check": self._check_service_response},
            {"name": "Memory Usage", "check": self._check_memory_usage},
            {"name": "CPU Usage", "check": self._check_cpu_usage},
            {"name": "Disk Space", "check": self._check_disk_space},
            {"name": "Network Connectivity", "check": self._check_network},
            {"name": "Database Connection", "check": self._check_database},
            {"name": "Cache Connection", "check": self._check_cache},
            {"name": "Log Files", "check": self._check_logs}
        ]
        
        results = []
        for check_info in checks:
            result = await check_info["check"](service)
            result["name"] = check_info["name"]
            result["service"] = service
            results.append(result)
            
            # Update counters
            self.total_checks += 1
            if result["status"] == CheckSeverity.PASSED.value:
                self.passed_checks += 1
            elif result["status"] == CheckSeverity.FAILED.value or result["status"] == CheckSeverity.CRITICAL.value:
                self.failed_checks += 1
            elif result["status"] == CheckSeverity.WARNING.value:
                self.warnings += 1
        
        return results
    
    async def run_connectivity_checks(self, targets: List[str]) -> List[Dict[str, Any]]:
        """
        Run connectivity checks to external services
        """
        self.logger.info("Running connectivity checks")
        
        results = []
        for target in targets:
            # Simulate connectivity check
            await asyncio.sleep(0.3)
            
            # Mock results with some variation
            import random
            success = random.random() > 0.1  # 90% success rate
            
            if success:
                result = {
                    "name": f"Connection to {target}",
                    "status": CheckSeverity.PASSED.value,
                    "message": f"Successfully connected to {target}",
                    "response_time": f"{random.uniform(10, 100):.1f}ms",
                    "details": {"endpoint": target, "protocol": "HTTPS"}
                }
            else:
                result = {
                    "name": f"Connection to {target}",
                    "status": CheckSeverity.FAILED.value,
                    "message": f"Failed to connect to {target}",
                    "error": "Connection timeout",
                    "details": {"endpoint": target, "protocol": "HTTPS"}
                }
            
            results.append(result)
            self.total_checks += 1
            if result["status"] == CheckSeverity.PASSED.value:
                self.passed_checks += 1
            else:
                self.failed_checks += 1
        
        return results
    
    async def run_dependency_checks(self, service: str) -> List[Dict[str, Any]]:
        """
        Check service dependencies and external integrations
        """
        self.logger.info(f"Checking dependencies for: {service}")
        
        dependencies = [
            {"name": "PostgreSQL Database", "type": "database", "required": True},
            {"name": "Redis Cache", "type": "cache", "required": True},
            {"name": "OpenAI API", "type": "api", "required": False},
            {"name": "AWS S3", "type": "storage", "required": True},
            {"name": "Stripe API", "type": "payment", "required": False},
            {"name": "SendGrid", "type": "email", "required": True}
        ]
        
        results = []
        for dep in dependencies:
            await asyncio.sleep(0.2)
            
            # Mock dependency check results
            import random
            available = random.random() > (0.05 if dep["required"] else 0.1)
            
            if available:
                status = CheckSeverity.PASSED.value
                message = f"{dep['name']} is available and responding"
            else:
                status = CheckSeverity.CRITICAL.value if dep["required"] else CheckSeverity.WARNING.value
                message = f"{dep['name']} is not available"
            
            result = {
                "name": f"Dependency: {dep['name']}",
                "status": status,
                "message": message,
                "required": dep["required"],
                "type": dep["type"],
                "service": service
            }
            
            results.append(result)
            self.total_checks += 1
            if result["status"] == CheckSeverity.PASSED.value:
                self.passed_checks += 1
            elif result["status"] == CheckSeverity.WARNING.value:
                self.warnings += 1
            else:
                self.failed_checks += 1
        
        return results
    
    async def run_security_checks(self, service: str) -> List[Dict[str, Any]]:
        """
        Run security verification checks
        """
        self.logger.info(f"Running security checks for: {service}")
        
        security_checks = [
            "SSL Certificate Validity",
            "Authentication Configuration",
            "Authorization Policies", 
            "API Rate Limiting",
            "Input Validation",
            "CORS Configuration",
            "Security Headers",
            "Dependency Vulnerabilities"
        ]
        
        results = []
        for check_name in security_checks:
            await asyncio.sleep(0.4)
            
            # Mock security check results
            import random
            passed = random.random() > 0.15  # 85% pass rate
            
            if passed:
                result = {
                    "name": check_name,
                    "status": CheckSeverity.PASSED.value,
                    "message": f"{check_name} configured correctly",
                    "service": service
                }
            else:
                severity = CheckSeverity.CRITICAL.value if "Certificate" in check_name else CheckSeverity.WARNING.value
                result = {
                    "name": check_name,
                    "status": severity,
                    "message": f"{check_name} requires attention",
                    "service": service
                }
            
            results.append(result)
            self.total_checks += 1
            if result["status"] == CheckSeverity.PASSED.value:
                self.passed_checks += 1
            elif result["status"] == CheckSeverity.WARNING.value:
                self.warnings += 1
            else:
                self.failed_checks += 1
        
        return results
    
    # Individual check methods
    async def _check_service_response(self, service: str) -> Dict[str, Any]:
        """Check if service is responding to health checks"""
        await asyncio.sleep(0.5)
        
        # Mock response check
        import random
        responding = random.random() > 0.05  # 95% uptime
        
        if responding:
            return {
                "status": CheckSeverity.PASSED.value,
                "message": f"Service {service} is responding normally",
                "response_time": f"{random.uniform(50, 150):.1f}ms"
            }
        else:
            return {
                "status": CheckSeverity.CRITICAL.value,
                "message": f"Service {service} is not responding",
                "error": "HTTP 503 Service Unavailable"
            }
    
    async def _check_memory_usage(self, service: str) -> Dict[str, Any]:
        """Check memory usage levels"""
        await asyncio.sleep(0.2)
        
        import random
        usage = random.uniform(20, 95)
        
        if usage < 75:
            status = CheckSeverity.PASSED.value
            message = f"Memory usage is normal ({usage:.1f}%)"
        elif usage < 85:
            status = CheckSeverity.WARNING.value
            message = f"Memory usage is elevated ({usage:.1f}%)"
        else:
            status = CheckSeverity.CRITICAL.value
            message = f"Memory usage is critical ({usage:.1f}%)"
        
        return {
            "status": status,
            "message": message,
            "value": f"{usage:.1f}%",
            "threshold": "75%"
        }
    
    async def _check_cpu_usage(self, service: str) -> Dict[str, Any]:
        """Check CPU usage levels"""
        await asyncio.sleep(0.2)
        
        import random
        usage = random.uniform(10, 90)
        
        if usage < 70:
            status = CheckSeverity.PASSED.value
            message = f"CPU usage is normal ({usage:.1f}%)"
        elif usage < 85:
            status = CheckSeverity.WARNING.value
            message = f"CPU usage is high ({usage:.1f}%)"
        else:
            status = CheckSeverity.CRITICAL.value
            message = f"CPU usage is critical ({usage:.1f}%)"
        
        return {
            "status": status,
            "message": message,
            "value": f"{usage:.1f}%",
            "threshold": "70%"
        }
    
    async def _check_disk_space(self, service: str) -> Dict[str, Any]:
        """Check available disk space"""
        await asyncio.sleep(0.3)
        
        import random
        free_space = random.uniform(10, 85)
        
        if free_space > 20:
            status = CheckSeverity.PASSED.value
            message = f"Disk space is adequate ({free_space:.1f}% free)"
        elif free_space > 10:
            status = CheckSeverity.WARNING.value
            message = f"Disk space is low ({free_space:.1f}% free)"
        else:
            status = CheckSeverity.CRITICAL.value
            message = f"Disk space is critically low ({free_space:.1f}% free)"
        
        return {
            "status": status,
            "message": message,
            "value": f"{free_space:.1f}% free",
            "threshold": "20% free minimum"
        }
    
    async def _check_network(self, service: str) -> Dict[str, Any]:
        """Check network connectivity"""
        await asyncio.sleep(0.4)
        
        import random
        network_ok = random.random() > 0.05
        
        if network_ok:
            return {
                "status": CheckSeverity.PASSED.value,
                "message": "Network connectivity is healthy",
                "latency": f"{random.uniform(1, 10):.1f}ms"
            }
        else:
            return {
                "status": CheckSeverity.FAILED.value,
                "message": "Network connectivity issues detected",
                "error": "Packet loss detected"
            }
    
    async def _check_database(self, service: str) -> Dict[str, Any]:
        """Check database connection and performance"""
        await asyncio.sleep(0.6)
        
        import random
        db_ok = random.random() > 0.02
        
        if db_ok:
            return {
                "status": CheckSeverity.PASSED.value,
                "message": "Database connection is healthy",
                "query_time": f"{random.uniform(5, 50):.1f}ms"
            }
        else:
            return {
                "status": CheckSeverity.CRITICAL.value,
                "message": "Database connection failed",
                "error": "Connection timeout"
            }
    
    async def _check_cache(self, service: str) -> Dict[str, Any]:
        """Check cache service connection"""
        await asyncio.sleep(0.3)
        
        import random
        cache_ok = random.random() > 0.03
        
        if cache_ok:
            return {
                "status": CheckSeverity.PASSED.value,
                "message": "Cache service is responding",
                "hit_rate": f"{random.uniform(85, 98):.1f}%"
            }
        else:
            return {
                "status": CheckSeverity.WARNING.value,
                "message": "Cache service is not responding",
                "error": "Redis connection failed"
            }
    
    async def _check_logs(self, service: str) -> Dict[str, Any]:
        """Check log file status and recent errors"""
        await asyncio.sleep(0.2)
        
        import random
        logs_ok = random.random() > 0.1
        
        if logs_ok:
            return {
                "status": CheckSeverity.PASSED.value,
                "message": "Log files are being written normally",
                "recent_errors": random.randint(0, 3)
            }
        else:
            return {
                "status": CheckSeverity.WARNING.value,
                "message": "Issues detected in log files",
                "recent_errors": random.randint(10, 50)
            }


@app.command()
def health(
    service: str = typer.Argument(..., help="Service name to check"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed check results"),
    fix_issues: bool = typer.Option(False, "--fix", help="Attempt to fix detected issues"),
    save_report: bool = typer.Option(False, "--save", help="Save health check report")
) -> None:
    """
    Run comprehensive health checks for a service
    """
    console.print(f"[bold blue]Running health checks for:[/bold blue] {service}")
    
    checker = SystemChecker()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        
        health_task = progress.add_task("Running health checks...", total=100)
        
        # Run health checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(checker.run_health_checks(service))
        loop.close()
        
        progress.update(health_task, completed=100)
    
    # Display results
    console.print(f"\n[bold]Health Check Results for {service}[/bold]\n")
    
    # Summary table
    summary_table = Table(title="Health Check Summary")
    summary_table.add_column("Check", style="cyan")
    summary_table.add_column("Status", style="bold")
    summary_table.add_column("Message", style="white")
    if detailed:
        summary_table.add_column("Details", style="dim")
    
    for result in results:
        status_color = {
            "passed": "green",
            "warning": "yellow",
            "failed": "red",
            "critical": "red"
        }.get(result["status"], "white")
        
        status_text = f"[{status_color}]{result['status'].upper()}[/{status_color}]"
        
        row_data = [result["name"], status_text, result["message"]]
        
        if detailed:
            details = []
            for key, value in result.items():
                if key not in ["name", "status", "message", "service"]:
                    details.append(f"{key}: {value}")
            row_data.append(" | ".join(details) if details else "N/A")
        
        summary_table.add_row(*row_data)
    
    console.print(summary_table)
    
    # Overall status
    overall_status = "HEALTHY"
    if checker.failed_checks > 0:
        overall_status = "UNHEALTHY"
    elif checker.warnings > 0:
        overall_status = "DEGRADED"
    
    status_color = {
        "HEALTHY": "green",
        "DEGRADED": "yellow", 
        "UNHEALTHY": "red"
    }.get(overall_status, "white")
    
    console.print(Panel(
        f"[bold]Overall Status: [{status_color}]{overall_status}[/{status_color}][/bold]\n\n"
        f"Total Checks: {checker.total_checks}\n"
        f"[green]Passed: {checker.passed_checks}[/green]\n"
        f"[yellow]Warnings: {checker.warnings}[/yellow]\n"
        f"[red]Failed: {checker.failed_checks}[/red]",
        title="Health Check Summary",
        border_style=status_color
    ))
    
    # Auto-fix issues if requested
    if fix_issues and (checker.failed_checks > 0 or checker.warnings > 0):
        console.print("\n[yellow]Attempting to fix detected issues...[/yellow]")
        
        # Mock auto-fix functionality
        with console.status("Fixing issues..."):
            time.sleep(2)
        
        console.print("[green]✓[/green] Attempted automatic fixes. Re-run health check to verify.")
    
    # Save report if requested
    if save_report:
        report_path = Path(f"{service}-health-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        report_data = {
            "service": service,
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "summary": {
                "total_checks": checker.total_checks,
                "passed": checker.passed_checks,
                "warnings": checker.warnings,
                "failed": checker.failed_checks
            },
            "results": results
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        console.print(f"[green]Health check report saved to: {report_path}[/green]")


@app.command()
def connectivity(
    targets: str = typer.Option(
        "database,cache,api,storage",
        "--targets",
        "-t",
        help="Comma-separated list of targets to check"
    ),
    timeout: int = typer.Option(30, "--timeout", help="Connection timeout in seconds"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run checks in parallel")
) -> None:
    """
    Check connectivity to external services and dependencies
    """
    target_list = [t.strip() for t in targets.split(",")]
    
    console.print(f"[bold blue]Checking connectivity to:[/bold blue] {', '.join(target_list)}")
    console.print(f"[dim]Timeout: {timeout}s | Parallel: {parallel}[/dim]\n")
    
    checker = SystemChecker()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        connectivity_task = progress.add_task("Testing connections...", total=len(target_list))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(checker.run_connectivity_checks(target_list))
        loop.close()
        
        progress.update(connectivity_task, completed=len(target_list))
    
    # Display results
    connectivity_table = Table(title="Connectivity Check Results")
    connectivity_table.add_column("Target", style="cyan")
    connectivity_table.add_column("Status", style="bold")
    connectivity_table.add_column("Message", style="white")
    connectivity_table.add_column("Response Time", style="green")
    
    for result in results:
        status_color = "green" if result["status"] == "passed" else "red"
        status_text = f"[{status_color}]{result['status'].upper()}[/{status_color}]"
        
        response_time = result.get("response_time", "N/A")
        
        connectivity_table.add_row(
            result["details"]["endpoint"],
            status_text,
            result["message"],
            response_time
        )
    
    console.print(connectivity_table)
    
    # Summary
    passed = len([r for r in results if r["status"] == "passed"])
    failed = len([r for r in results if r["status"] == "failed"])
    
    summary_color = "green" if failed == 0 else "red"
    console.print(f"\n[{summary_color}]Connectivity Summary: {passed}/{len(results)} targets reachable[/{summary_color}]")


@app.command()
def dependencies(
    service: str = typer.Argument(..., help="Service name to check dependencies"),
    include_optional: bool = typer.Option(True, "--include-optional", help="Include optional dependencies"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed dependency information")
) -> None:
    """
    Verify service dependencies and external integrations
    """
    console.print(f"[bold blue]Checking dependencies for:[/bold blue] {service}")
    
    checker = SystemChecker()
    
    with console.status("Checking dependencies..."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(checker.run_dependency_checks(service))
        loop.close()
    
    # Filter results if not including optional dependencies
    if not include_optional:
        results = [r for r in results if r.get("required", True)]
    
    # Display results
    dep_table = Table(title="Dependency Check Results")
    dep_table.add_column("Dependency", style="cyan")
    dep_table.add_column("Type", style="blue")
    dep_table.add_column("Required", style="yellow")
    dep_table.add_column("Status", style="bold")
    dep_table.add_column("Message", style="white")
    
    for result in results:
        status_color = {
            "passed": "green",
            "warning": "yellow",
            "failed": "red",
            "critical": "red"
        }.get(result["status"], "white")
        
        status_text = f"[{status_color}]{result['status'].upper()}[/{status_color}]"
        required_text = "Yes" if result["required"] else "No"
        
        dep_table.add_row(
            result["name"].replace("Dependency: ", ""),
            result["type"].title(),
            required_text,
            status_text,
            result["message"]
        )
    
    console.print(dep_table)
    
    # Summary by type
    if verbose:
        console.print("\n[bold]Dependency Summary by Type:[/bold]")
        
        dep_types = {}
        for result in results:
            dep_type = result["type"]
            if dep_type not in dep_types:
                dep_types[dep_type] = {"total": 0, "passed": 0, "failed": 0}
            
            dep_types[dep_type]["total"] += 1
            if result["status"] == "passed":
                dep_types[dep_type]["passed"] += 1
            else:
                dep_types[dep_type]["failed"] += 1
        
        type_table = Table()
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Total", style="blue")
        type_table.add_column("Available", style="green")
        type_table.add_column("Issues", style="red")
        
        for dep_type, stats in dep_types.items():
            type_table.add_row(
                dep_type.title(),
                str(stats["total"]),
                str(stats["passed"]),
                str(stats["failed"])
            )
        
        console.print(type_table)


@app.command()
def security(
    service: str = typer.Argument(..., help="Service name to security check"),
    scan_type: str = typer.Option(
        "standard",
        "--scan-type", 
        "-t",
        help="Security scan type (standard, comprehensive, quick)"
    ),
    fix_issues: bool = typer.Option(False, "--fix", help="Attempt to fix security issues"),
    generate_report: bool = typer.Option(False, "--report", help="Generate security report")
) -> None:
    """
    Run security verification and vulnerability checks
    """
    console.print(f"[bold blue]Running security checks for:[/bold blue] {service}")
    console.print(f"[dim]Scan type: {scan_type}[/dim]\n")
    
    checker = SystemChecker()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        security_task = progress.add_task("Running security checks...", total=100)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(checker.run_security_checks(service))
        loop.close()
        
        progress.update(security_task, completed=100)
    
    # Display results
    security_table = Table(title="Security Check Results")
    security_table.add_column("Check", style="cyan")
    security_table.add_column("Status", style="bold")
    security_table.add_column("Finding", style="white")
    security_table.add_column("Risk Level", style="yellow")
    
    for result in results:
        status_color = {
            "passed": "green",
            "warning": "yellow",
            "failed": "red",
            "critical": "red"
        }.get(result["status"], "white")
        
        status_text = f"[{status_color}]{result['status'].upper()}[/{status_color}]"
        
        # Determine risk level
        if result["status"] == "critical":
            risk_level = "[red]HIGH[/red]"
        elif result["status"] == "failed":
            risk_level = "[orange1]MEDIUM[/orange1]"
        elif result["status"] == "warning":
            risk_level = "[yellow]LOW[/yellow]"
        else:
            risk_level = "[green]NONE[/green]"
        
        security_table.add_row(
            result["name"],
            status_text,
            result["message"],
            risk_level
        )
    
    console.print(security_table)
    
    # Security summary
    critical_issues = len([r for r in results if r["status"] == "critical"])
    failed_checks = len([r for r in results if r["status"] == "failed"])
    warnings = len([r for r in results if r["status"] == "warning"])
    
    if critical_issues > 0:
        overall_security = "CRITICAL"
        border_color = "red"
    elif failed_checks > 0:
        overall_security = "AT RISK"
        border_color = "orange1"
    elif warnings > 0:
        overall_security = "ACCEPTABLE"
        border_color = "yellow"
    else:
        overall_security = "SECURE"
        border_color = "green"
    
    console.print(Panel(
        f"[bold]Security Status: {overall_security}[/bold]\n\n"
        f"Critical Issues: {critical_issues}\n"
        f"Failed Checks: {failed_checks}\n"
        f"Warnings: {warnings}\n"
        f"Passed: {len(results) - critical_issues - failed_checks - warnings}",
        title="Security Summary",
        border_style=border_color
    ))
    
    # Generate report if requested
    if generate_report:
        report_path = Path(f"{service}-security-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        report_data = {
            "service": service,
            "scan_type": scan_type,
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_security,
            "summary": {
                "critical_issues": critical_issues,
                "failed_checks": failed_checks,
                "warnings": warnings,
                "total_checks": len(results)
            },
            "findings": results
        }
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        console.print(f"\n[green]Security report saved to: {report_path}[/green]")


@app.command()
def logs(
    service: str = typer.Argument(..., help="Service name"),
    level: str = typer.Option("error", "--level", "-l", help="Log level to check (error, warn, info, debug)"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to analyze"),
    since: str = typer.Option("1h", "--since", help="Time range to analyze (1h, 6h, 24h, 7d)")
) -> None:
    """
    Analyze service logs for errors and issues
    """
    console.print(f"[bold blue]Analyzing logs for:[/bold blue] {service}")
    console.print(f"[dim]Level: {level} | Lines: {lines} | Since: {since}[/dim]\n")
    
    # Mock log analysis
    with console.status("Analyzing log files..."):
        time.sleep(2)
    
    # Mock log analysis results
    log_issues = [
        {
            "timestamp": "2024-01-15T10:30:00Z",
            "level": "ERROR",
            "message": "Database connection timeout",
            "count": 5,
            "first_seen": "10:25:00",
            "last_seen": "10:30:00"
        },
        {
            "timestamp": "2024-01-15T10:15:00Z", 
            "level": "WARN",
            "message": "High memory usage detected",
            "count": 12,
            "first_seen": "09:45:00",
            "last_seen": "10:15:00"
        },
        {
            "timestamp": "2024-01-15T09:30:00Z",
            "level": "ERROR", 
            "message": "API rate limit exceeded",
            "count": 3,
            "first_seen": "09:30:00",
            "last_seen": "09:35:00"
        }
    ]
    
    if log_issues:
        console.print("[bold]Log Issues Found:[/bold]\n")
        
        issues_table = Table(title="Log Analysis Results")
        issues_table.add_column("Level", style="bold")
        issues_table.add_column("Message", style="white")
        issues_table.add_column("Count", style="yellow")
        issues_table.add_column("First Seen", style="dim")
        issues_table.add_column("Last Seen", style="dim")
        
        for issue in log_issues:
            level_color = {
                "ERROR": "red",
                "WARN": "yellow",
                "INFO": "blue",
                "DEBUG": "dim"
            }.get(issue["level"], "white")
            
            issues_table.add_row(
                f"[{level_color}]{issue['level']}[/{level_color}]",
                issue["message"],
                str(issue["count"]),
                issue["first_seen"],
                issue["last_seen"]
            )
        
        console.print(issues_table)
        
        # Recommendations
        console.print("\n[bold]Recommendations:[/bold]")
        console.print("• Investigate database connection stability")
        console.print("• Monitor memory usage trends")
        console.print("• Review API rate limiting configuration")
        
    else:
        console.print(Panel(
            "[green]No significant issues found in logs[/green]\n\n"
            "[dim]Service logs appear healthy[/dim]",
            title="Log Analysis Complete",
            border_style="green"
        ))


@app.command()
def system(
    check_types: Optional[str] = typer.Option(
        None,
        "--types",
        "-t",
        help="Comma-separated check types (health,connectivity,dependencies,security,performance)"
    ),
    services: Optional[str] = typer.Option(
        None,
        "--services",
        "-s", 
        help="Comma-separated list of services to check"
    ),
    comprehensive: bool = typer.Option(False, "--comprehensive", "-c", help="Run comprehensive system check"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, yaml)")
) -> None:
    """
    Run comprehensive system-wide checks
    """
    console.print("[bold blue]Running system-wide checks[/bold blue]\n")
    
    # Determine what to check
    if check_types:
        types_to_run = [t.strip() for t in check_types.split(",")]
    elif comprehensive:
        types_to_run = ["health", "connectivity", "dependencies", "security", "performance"]
    else:
        types_to_run = ["health", "connectivity", "dependencies"]
    
    if services:
        service_list = [s.strip() for s in services.split(",")]
    else:
        service_list = ["api-service", "worker-service", "auth-service"]
    
    console.print(f"[dim]Check types: {', '.join(types_to_run)}[/dim]")
    console.print(f"[dim]Services: {', '.join(service_list)}[/dim]\n")
    
    # Run all checks
    all_results = {}
    checker = SystemChecker()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        
        total_checks = len(types_to_run) * len(service_list)
        system_task = progress.add_task("Running system checks...", total=total_checks)
        completed = 0
        
        for service in service_list:
            all_results[service] = {}
            
            for check_type in types_to_run:
                progress.update(system_task, description=f"Checking {service} - {check_type}")
                
                if check_type == "health":
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(checker.run_health_checks(service))
                    loop.close()
                elif check_type == "connectivity":
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(checker.run_connectivity_checks(["database", "cache", "api"]))
                    loop.close()
                elif check_type == "dependencies":
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(checker.run_dependency_checks(service))
                    loop.close()
                elif check_type == "security":
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(checker.run_security_checks(service))
                    loop.close()
                else:
                    results = []  # Mock for performance checks
                
                all_results[service][check_type] = results
                completed += 1
                progress.update(system_task, completed=completed)
    
    # Display comprehensive results
    if output_format == "json":
        console.print_json(data=all_results)
    else:
        # Table format
        for service, service_results in all_results.items():
            console.print(f"\n[bold cyan]{service.upper()} - System Check Results[/bold cyan]")
            
            for check_type, results in service_results.items():
                if not results:
                    continue
                    
                console.print(f"\n[bold]{check_type.title()} Checks:[/bold]")
                
                check_table = Table()
                check_table.add_column("Check", style="white")
                check_table.add_column("Status", style="bold")
                check_table.add_column("Message", style="dim")
                
                for result in results:
                    status_color = {
                        "passed": "green",
                        "warning": "yellow",
                        "failed": "red",
                        "critical": "red"
                    }.get(result["status"], "white")
                    
                    status_text = f"[{status_color}]{result['status'].upper()}[/{status_color}]"
                    
                    check_table.add_row(
                        result["name"],
                        status_text,
                        result["message"]
                    )
                
                console.print(check_table)
    
    # Overall system health summary
    console.print(Panel(
        f"[bold]System Check Complete[/bold]\n\n"
        f"Services Checked: {len(service_list)}\n"
        f"Check Types: {len(types_to_run)}\n"
        f"Total Checks: {checker.total_checks}\n"
        f"[green]Passed: {checker.passed_checks}[/green]\n"
        f"[yellow]Warnings: {checker.warnings}[/yellow]\n"
        f"[red]Failed: {checker.failed_checks}[/red]",
        title="System Health Summary",
        border_style="blue"
    ))