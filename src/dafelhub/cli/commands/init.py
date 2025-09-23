"""
DafelHub Init Command
Initialize new projects, services, and infrastructure components.
"""

from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from dafelhub.core.logging import get_logger
from dafelhub.services.project_manager import ProjectManager
from dafelhub.services.template_engine import TemplateEngine

logger = get_logger(__name__)
console = Console()

app = typer.Typer(help="Initialize new projects and services")


@app.command()
def project(
    name: str = typer.Argument(..., help="Project name"),
    path: Optional[Path] = typer.Option(
        None,
        "--path", 
        "-p", 
        help="Project directory path"
    ),
    template: str = typer.Option(
        "saas-service",
        "--template",
        "-t",
        help="Project template"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Interactive mode"
    )
) -> None:
    """
    🚀 Initialize a new DafelHub project
    """
    console.print(f"[bold blue]Initializing project:[/bold blue] {name}")
    
    # Interactive project setup
    if interactive:
        project_type = Prompt.ask(
            "Project type",
            choices=["saas-service", "microservice", "web-app", "data-pipeline"],
            default="saas-service"
        )
        
        enable_ai = Confirm.ask("Enable AI agents integration?", default=True)
        enable_monitoring = Confirm.ask("Enable monitoring and observability?", default=True)
        enable_testing = Confirm.ask("Enable comprehensive testing suite?", default=True)
        
        # Show configuration summary
        config_table = Table(title="Project Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")
        
        config_table.add_row("Name", name)
        config_table.add_row("Type", project_type)
        config_table.add_row("AI Integration", "✓" if enable_ai else "✗")
        config_table.add_row("Monitoring", "✓" if enable_monitoring else "✗")
        config_table.add_row("Testing Suite", "✓" if enable_testing else "✗")
        
        console.print(config_table)
        
        if not Confirm.ask("Proceed with this configuration?"):
            console.print("[yellow]Project initialization cancelled[/yellow]")
            return
    
    try:
        # Initialize project using ProjectManager service
        project_manager = ProjectManager()
        project_path = project_manager.create_project(
            name=name,
            template=template,
            path=path,
            config={
                "ai_enabled": enable_ai if interactive else True,
                "monitoring_enabled": enable_monitoring if interactive else True,
                "testing_enabled": enable_testing if interactive else True,
            }
        )
        
        console.print(Panel(
            f"[green]✓[/green] Project '{name}' created successfully!\n"
            f"[dim]Location: {project_path}[/dim]\n\n"
            f"[bold]Next steps:[/bold]\n"
            f"1. cd {project_path}\n"
            f"2. dafelhub spec create\n"
            f"3. dafelhub plan generate\n"
            f"4. dafelhub deploy local",
            title="[bold green]Project Created[/bold green]",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def service(
    name: str = typer.Argument(..., help="Service name"),
    service_type: str = typer.Option(
        "api",
        "--type",
        "-t", 
        help="Service type"
    )
) -> None:
    """
    🔧 Initialize a new microservice
    """
    console.print(f"[bold blue]Creating service:[/bold blue] {name}")
    
    try:
        project_manager = ProjectManager()
        service_path = project_manager.create_service(name, service_type)
        
        console.print(Panel(
            f"[green]✓[/green] Service '{name}' created!\n"
            f"[dim]Location: {service_path}[/dim]",
            title="[bold green]Service Created[/bold green]",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"Failed to create service: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def agent(
    name: str = typer.Argument(..., help="Agent name"),
    agent_type: str = typer.Option(
        "general",
        "--type",
        "-t",
        help="Agent specialization"
    )
) -> None:
    """
    🤖 Initialize a new AI agent
    """
    console.print(f"[bold blue]Creating AI agent:[/bold blue] {name}")
    
    specializations = [
        "general", "data-analysis", "code-review", 
        "testing", "deployment", "monitoring", "customer-service"
    ]
    
    if agent_type not in specializations:
        agent_type = Prompt.ask(
            "Agent specialization",
            choices=specializations,
            default="general"
        )
    
    try:
        project_manager = ProjectManager()
        agent_path = project_manager.create_agent(name, agent_type)
        
        console.print(Panel(
            f"[green]✓[/green] AI Agent '{name}' created!\n"
            f"[dim]Specialization: {agent_type}[/dim]\n"
            f"[dim]Location: {agent_path}[/dim]",
            title="[bold green]Agent Created[/bold green]",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)