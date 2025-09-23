"""
DafelHub CLI Main Entry Point
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from dafelhub import __version__
from dafelhub.core.config import settings
from dafelhub.core.logging import get_logger
from dafelhub.cli.commands import init, check, spec, plan, deploy, monitor

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="dafelhub",
    help="DafelHub - Enterprise SaaS Consulting Hub CLI",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

app.add_typer(init.app, name="init", help="Initialize new projects and services")
app.add_typer(spec.app, name="spec", help="Manage specifications and requirements") 
app.add_typer(plan.app, name="plan", help="Create and manage project plans")
app.add_typer(deploy.app, name="deploy", help="Deploy services and infrastructure")
app.add_typer(monitor.app, name="monitor", help="Monitor system health and metrics")


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, 
        "--version", 
        "-v", 
        help="Show version and exit"
    ),
    verbose: Optional[bool] = typer.Option(
        False,
        "--verbose",
        help="Enable verbose logging"
    ),
) -> None:
    """
    🚀 DafelHub - Enterprise SaaS Consulting Hub
    
    Built with Spec-Driven Development for scalable consulting services.
    """
    if version:
        console.print(f"[bold blue]DafelHub[/bold blue] version [green]{__version__}[/green]")
        raise typer.Exit()
    
    if verbose:
        settings.LOG_LEVEL = "DEBUG"
        logger.info("Verbose logging enabled")


@app.command()
def check(
    project_path: Optional[Path] = typer.Option(
        Path.cwd(),
        "--path",
        "-p",
        help="Path to project directory"
    )
) -> None:
    """
    🔍 Check project health and configuration
    """
    console.print(Panel(
        f"[bold green]✓[/bold green] DafelHub v{__version__} is working correctly!\n"
        f"[dim]Project path: {project_path}[/dim]\n"
        f"[dim]Configuration: {settings.ENVIRONMENT}[/dim]",
        title="[bold blue]System Check[/bold blue]",
        border_style="green"
    ))


@app.command()
def info() -> None:
    """
    📊 Show system information and status
    """
    info_text = Text()
    info_text.append("DafelHub Enterprise SaaS Platform\n", style="bold blue")
    info_text.append(f"Version: {__version__}\n", style="green")
    info_text.append(f"Environment: {settings.ENVIRONMENT}\n", style="yellow")
    info_text.append(f"Python: {sys.version.split()[0]}\n", style="cyan")
    
    console.print(Panel(
        info_text,
        title="[bold blue]System Information[/bold blue]",
        border_style="blue"
    ))


if __name__ == "__main__":
    app()