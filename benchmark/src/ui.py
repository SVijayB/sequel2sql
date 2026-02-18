"""Enhanced UI with questionary for better user experience"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import questionary
from pyfiglet import Figlet
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def display_logo() -> None:
    """Display the SEQUEL2SQL benchmark logo."""
    f = Figlet(font="ansi_shadow", width=100)
    logo = f.renderText("SEQUEL2SQL")

    console.print()
    console.print(
        Panel(
            f"[bold cyan]{logo}[/bold cyan]\n"
            f"[bold white]BENCHMARK EVALUATION SYSTEM[/bold white]\n"
            f"[dim]BIRD-CRITIC BENCHMARK[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def get_previous_runs(outputs_dir: Path) -> List[Dict[str, Any]]:
    """
    Scan outputs directory for previous runs with checkpoint data.

    Args:
        outputs_dir: Path to outputs directory

    Returns:
        List of run info dictionaries
    """
    runs = []

    if not outputs_dir.exists():
        return runs

    for run_dir in sorted(outputs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
            continue

        checkpoint_file = run_dir / "checkpoint.json"
        if not checkpoint_file.exists():
            continue

        try:
            with open(checkpoint_file, "r") as f:
                checkpoint = json.load(f)

            # Extract timestamp from directory name
            timestamp_str = run_dir.name.replace("run_", "")

            # Parse checkpoint data
            total = checkpoint.get("total_queries", 0)
            completed = checkpoint.get("completed_queries", 0)
            failed = checkpoint.get("failed_queries", 0)
            phase = checkpoint.get("phase", "unknown")

            # Determine status
            eval_done = checkpoint.get("evaluation_completed", False)
            if completed >= total and eval_done:
                status = "✓ Completed"
                is_resumable = False
            elif completed >= total and not eval_done:
                status = "⏸ Eval Pending"
                is_resumable = True
            else:
                status = "⏸ Incomplete"
                is_resumable = True

            runs.append(
                {
                    "dir": run_dir,
                    "timestamp": timestamp_str,
                    "total": total,
                    "completed": completed,
                    "failed": failed,
                    "phase": phase,
                    "status": status,
                    "is_resumable": is_resumable,
                    "checkpoint": checkpoint,
                }
            )
        except Exception:
            # Skip invalid checkpoints
            continue

    return runs


def show_main_menu() -> Dict[str, Any]:
    """
    Show main menu with questionary.

    Returns:
        User's choice dictionary
    """
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice("Start a complete run (531 queries)", value="complete"),
            questionary.Choice("Start a run on a subset of queries", value="subset"),
            questionary.Choice("View previous runs", value="previous"),
            questionary.Choice("Exit", value="exit"),
        ],
    ).ask()

    if choice is None:
        return {"action": "exit"}

    return {"action": choice}


def ask_provider(providers: Dict[str, Any]) -> Optional[str]:
    """
    Ask the user to select an LLM provider/model.

    Args:
        providers: Dict mapping provider key -> config dict with 'display_name'

    Returns:
        Selected provider key (e.g. "google"), or None if cancelled
    """
    choices = [
        questionary.Choice(
            f"{cfg['display_name']}",
            value=key,
        )
        for key, cfg in providers.items()
    ]

    answer = questionary.select(
        "Which model would you like to use?",
        choices=choices,
    ).ask()

    return answer


def ask_subset_size() -> Optional[int]:

    def validate_number(text):
        if not text.isdigit():
            return "Please enter a valid number"
        num = int(text)
        if num < 1 or num > 531:
            return "Please enter a number between 1 and 531"
        return True

    answer = questionary.text(
        "How many queries do you want to run?", default="20", validate=validate_number
    ).ask()

    if answer is None:
        return None

    return int(answer)


def show_previous_runs_menu(runs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Show menu with previous runs.

    Args:
        runs: List of run info dictionaries

    Returns:
        Selected run dict, or None if back
    """
    if not runs:
        console.print("[yellow]No previous runs found.[/yellow]\n")
        console.print("Press Enter to return to main menu...")
        input()
        return None

    # Create choices list
    choices = []
    for i, run in enumerate(runs):
        timestamp = run["timestamp"]
        completed = run["completed"]
        total = run["total"]
        status = run["status"]

        # Format timestamp nicely
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%d_%H-%M-%S")
            display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            display_time = timestamp

        choice_text = f"{status}  {display_time}  ({completed}/{total} queries)"
        choices.append(questionary.Choice(choice_text, value=i))

    choices.append(questionary.Choice("⬅ Back to main menu", value=-1))

    answer = questionary.select(
        "Select a run to view details or resume:", choices=choices
    ).ask()

    if answer is None or answer == -1:
        return None

    return runs[answer]


def show_run_details_and_confirm(run: Dict[str, Any]) -> str:
    """
    Show run details and ask if user wants to resume.

    Args:
        run: Run info dictionary

    Returns:
        "resume" to resume, "delete" to delete, "back" to go back
    """
    # Display run details
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")

    try:
        dt = datetime.strptime(run["timestamp"], "%Y-%m-%d_%H-%M-%S")
        display_time = dt.strftime("%Y-%m-%d at %H:%M:%S")
    except Exception:
        display_time = run["timestamp"]

    progress_pct = (run["completed"] / run["total"] * 100) if run["total"] > 0 else 0

    table.add_row("Started", display_time)
    table.add_row("Status", run["status"])
    table.add_row(
        "Progress", f"{run['completed']}/{run['total']} ({progress_pct:.1f}%)"
    )
    table.add_row("Success", str(run["completed"] - run["failed"]))
    table.add_row("Failed", str(run["failed"]))
    table.add_row("Phase", run["phase"])
    table.add_row("Location", str(run["dir"]))

    console.print()
    console.print(Panel(table, title="[bold]Run Details[/bold]", border_style="cyan"))
    console.print()

    # Ask what to do
    choices = []

    if run["is_resumable"]:
        choices.append(questionary.Choice("▶️  Resume this run", value="resume"))

    choices.extend(
        [
            questionary.Choice("🗑️  Delete this run", value="delete"),
            questionary.Choice("⬅ Back to previous runs", value="back"),
        ]
    )

    answer = questionary.select("What would you like to do?", choices=choices).ask()

    if answer is None:
        return "back"

    return answer


def confirm_delete(run: Dict[str, Any]) -> bool:
    """Confirm deletion of a run."""
    answer = questionary.confirm(
        "Are you sure you want to delete this run? This cannot be undone.",
        default=False,
    ).ask()

    if answer is None:
        return False

    return answer


def display_config_summary(config: Dict[str, Any], total_queries: int) -> None:
    """Display configuration summary."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Dialect", "PostgreSQL 14.12")
    table.add_row(
        "Model", config.get("display_name", config.get("model_id", "Unknown"))
    )
    table.add_row("Provider", config.get("provider", "Unknown").capitalize())
    table.add_row("Total Queries", str(total_queries))
    table.add_row("Processing", "Sequential (one query at a time)")

    console.print(Panel(table, title="[bold]Configuration[/bold]", border_style="blue"))
    console.print()


def confirm_start() -> bool:
    """Confirm starting the benchmark."""
    answer = questionary.confirm("Start benchmark?", default=True).ask()

    if answer is None:
        return False

    return answer


def display_phase_header(phase: str, description: str = "") -> None:
    """Display a phase header."""
    console.print()
    console.print(f"[bold cyan]{'=' * 70}[/bold cyan]")
    console.print(f"[bold cyan]{phase.upper()}[/bold cyan]")
    if description:
        console.print(f"[dim]{description}[/dim]")
    console.print(f"[bold cyan]{'=' * 70}[/bold cyan]")
    console.print()


def display_success(message: str) -> None:
    """Display a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def display_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[bold red]✗[/bold red] {message}")


def display_results(stats: Dict[str, Any]) -> None:
    """Display benchmark results summary."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")

    if "total_queries" in stats:
        table.add_row("Total Queries", str(stats["total_queries"]))
    if "completed_queries" in stats:
        table.add_row("Completed", str(stats["completed_queries"]))
    if "failed_queries" in stats:
        table.add_row("Failed", str(stats["failed_queries"]))
    if "total_api_calls" in stats:
        table.add_row("Total API Calls", str(stats["total_api_calls"]))
    if "average_query_time" in stats and stats["average_query_time"] > 0:
        table.add_row("Avg Query Time", f"{stats['average_query_time']:.1f}s")
    if "execution_time" in stats:
        table.add_row("Execution Time", f"{stats['execution_time']:.1f}s")
    if "queries_per_minute" in stats:
        table.add_row("Rate", f"{stats['queries_per_minute']:.1f} queries/min")

    console.print(Panel(table, title="[bold]Results[/bold]", border_style="green"))
    console.print()
