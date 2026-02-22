import questionary
import sys
from pathlib import Path

from benchmark.src.ui import console, display_logo
from rich.panel import Panel

def show_main_menu(db_id: str) -> str:
    console.print()
    console.print(f"[bold cyan]{'=' * 52}[/bold cyan]")
    console.print(f"  [bold]DB SKILLS BENCHMARK[/bold]")
    console.print(f"  Database: {db_id}")
    console.print(f"[bold cyan]{'=' * 52}[/bold cyan]")
    console.print()
    
    choice = questionary.select(
        "Select evaluation mode:",
        choices=[
            questionary.Choice("[1] Simple model — no tools, no db_skills", value="simple"),
            questionary.Choice("[2] Pipeline — full tools, WITH seeded db_skills", value="pipeline_seeded"),
            questionary.Choice("[3] Pipeline — full tools, WITHOUT db_skills (control)", value="pipeline_control"),
            questionary.Choice("[q] Quit", value="quit"),
        ],
    ).ask()
    
    return choice

def ask_subset_limit() -> int | None:
    choice = questionary.select(
        "Run volume:",
        choices=[
            questionary.Choice("[1] Run benchmark on whole subsets", value="all"),
            questionary.Choice("[2] Run benchmark on subset of subsets (specific limit)", value="limit"),
        ],
    ).ask()
    
    if choice == "limit":
        limit_str = questionary.text(
            "Enter number of queries to run per subset (e.g., 5):",
            validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter a positive integer"
        ).ask()
        if not limit_str:
            return None
        return int(limit_str)
    
    return None

def confirm_summary(mode: str, subset_desc: str, seen_count: int, unseen_count: int, seed_dbskills: bool) -> bool:
    console.print()
    console.print(Panel(
        f"[bold]RUN SUMMARY[/bold]\n"
        f"Mode: [cyan]{mode}[/cyan]\n"
        f"Volume: [cyan]{subset_desc}[/cyan] (seen: {seen_count}, unseen: {unseen_count})\n"
        f"Seed Chroma: [cyan]{'Yes' if seed_dbskills else 'No (Clear Only)'}[/cyan]",
        border_style="cyan"
    ))
    
    return questionary.confirm("Proceed with this configuration?", default=True).ask()
