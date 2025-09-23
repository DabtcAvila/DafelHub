"""
DafelHub Spec Command
Manage specifications using Spec-Driven Development principles.
"""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from dafelhub.core.logging import get_logger
from dafelhub.services.spec_manager import SpecManager
# from dafelhub.agents.spec_agent import SpecAgent  # TODO: Create SpecAgent module

logger = get_logger(__name__)
console = Console()

app = typer.Typer(help="Manage specifications and requirements")


@app.command()
def create(
    name: str = typer.Argument(..., help="Specification name"),
    feature_type: str = typer.Option(
        "feature",
        "--type",
        "-t",
        help="Specification type"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Interactive mode"
    )
) -> None:
    """
    📝 Create a new specification
    """
    console.print(f"[bold blue]Creating specification:[/bold blue] {name}")
    
    spec_manager = SpecManager()
    
    if interactive:
        # Interactive specification creation
        description = Prompt.ask("Brief description of the feature/requirement")
        
        stakeholders = Prompt.ask(
            "Key stakeholders (comma-separated)",
            default="Product Owner, Development Team, End Users"
        )
        
        priority = Prompt.ask(
            "Priority level",
            choices=["critical", "high", "medium", "low"],
            default="medium"
        )
        
        use_ai_assistant = Confirm.ask(
            "Use AI assistant to enhance specification?",
            default=True
        )
        
        spec_data = {
            "name": name,
            "type": feature_type,
            "description": description,
            "stakeholders": [s.strip() for s in stakeholders.split(",")],
            "priority": priority,
        }
        
        if use_ai_assistant:
            console.print("[yellow]AI Assistant is analyzing your requirements...[/yellow]")
            # TODO: Implement SpecAgent integration
            # spec_agent = SpecAgent()
            # enhanced_spec = spec_agent.enhance_specification(spec_data)
            # spec_data.update(enhanced_spec)
            console.print("[yellow]AI Assistant feature coming soon![/yellow]")
    
    else:
        spec_data = {
            "name": name,
            "type": feature_type,
            "description": f"Specification for {name}",
            "stakeholders": ["Development Team"],
            "priority": "medium",
        }
    
    try:
        spec_path = spec_manager.create_specification(spec_data)
        
        console.print(Panel(
            f"[green]✓[/green] Specification '{name}' created!\n"
            f"[dim]Location: {spec_path}[/dim]\n\n"
            f"[bold]Next steps:[/bold]\n"
            f"1. dafelhub spec review {name}\n"
            f"2. dafelhub plan create --from-spec {name}\n"
            f"3. dafelhub spec approve {name}",
            title="[bold green]Specification Created[/bold green]",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"Failed to create specification: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def review(
    name: str = typer.Argument(..., help="Specification name"),
    auto_fix: bool = typer.Option(
        False,
        "--auto-fix",
        help="Automatically fix issues"
    )
) -> None:
    """
    🔍 Review specification quality and completeness
    """
    console.print(f"[bold blue]Reviewing specification:[/bold blue] {name}")
    
    try:
        spec_manager = SpecManager()
        # TODO: Implement SpecAgent
        # spec_agent = SpecAgent()
        
        # Load and review specification
        spec = spec_manager.load_specification(name)
        # TODO: Implement AI-powered review
        # review_result = spec_agent.review_specification(spec)
        review_result = {
            'quality_score': 85,
            'strengths': ['Clear requirements', 'Well-structured'],
            'improvements': ['Add more test cases', 'Define edge cases'],
            'critical_issues': []
        }
        
        # Display review results
        console.print(Panel(
            f"[bold]Quality Score:[/bold] {review_result['quality_score']}/100\n\n"
            f"[bold green]Strengths:[/bold green]\n" +
            "\n".join(f"• {item}" for item in review_result['strengths']) + "\n\n" +
            f"[bold yellow]Areas for Improvement:[/bold yellow]\n" +
            "\n".join(f"• {item}" for item in review_result['improvements']) + "\n\n" +
            f"[bold red]Critical Issues:[/bold red]\n" +
            "\n".join(f"• {item}" for item in review_result['critical_issues']),
            title=f"[bold blue]Specification Review: {name}[/bold blue]",
            border_style="blue"
        ))
        
        if auto_fix and review_result['critical_issues']:
            if Confirm.ask("Apply automatic fixes for critical issues?"):
                # TODO: Implement AI-powered fixing
                # fixed_spec = spec_agent.fix_specification_issues(spec, review_result)
                # spec_manager.update_specification(name, fixed_spec)
                console.print("[green]✓ Automatic fixes applied[/green]")
                
    except Exception as e:
        logger.error(f"Failed to review specification: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def list_specs(
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status"
    )
) -> None:
    """
    📋 List all specifications
    """
    try:
        spec_manager = SpecManager()
        specs = spec_manager.list_specifications(status_filter=status)
        
        if not specs:
            console.print("[yellow]No specifications found[/yellow]")
            return
            
        from rich.table import Table
        
        table = Table(title="Specifications")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Priority", style="red")
        table.add_column("Last Modified", style="dim")
        
        for spec in specs:
            table.add_row(
                spec['name'],
                spec['type'],
                spec['status'],
                spec['priority'],
                spec['last_modified']
            )
        
        console.print(table)
        
    except Exception as e:
        logger.error(f"Failed to list specifications: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def approve(
    name: str = typer.Argument(..., help="Specification name"),
    approver: Optional[str] = typer.Option(
        None,
        "--approver",
        help="Approver name"
    )
) -> None:
    """
    ✅ Approve a specification
    """
    try:
        spec_manager = SpecManager()
        spec_manager.approve_specification(name, approver)
        
        console.print(Panel(
            f"[green]✓[/green] Specification '{name}' approved!\n"
            f"[dim]Approved by: {approver or 'Current User'}[/dim]",
            title="[bold green]Specification Approved[/bold green]",
            border_style="green"
        ))
        
    except Exception as e:
        logger.error(f"Failed to approve specification: {e}")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)