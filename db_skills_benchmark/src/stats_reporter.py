import json
import sys
from pathlib import Path

from ui import console
from rich.panel import Panel
from rich.table import Table
from db_skills_benchmark.src.config import TARGET_DB_ID

def _safe_division(n, d):
    return (n / d * 100) if d > 0 else 0.0

def _get_avg_sim(results):
    sims = [r["top_retrieved_similarity"] for r in results if r["top_retrieved_similarity"] is not None]
    return sum(sims) / len(sims) if sims else 0.0

def _get_retrieved_count(results):
    return sum(1 for r in results if r["retrieved_fixes"])

def _get_acc_count(results):
    return sum(1 for r in results if r.get("execution_correct", False))

def print_report(seen_results: list[dict], unseen_results: list[dict], mode: str, seeder_summary: dict, run_output_dir: Path) -> None:
    seen_exec = _get_acc_count(seen_results)
    seen_ret = _get_retrieved_count(seen_results)
    seen_avg = _get_avg_sim(seen_results)
    
    unseen_exec = _get_acc_count(unseen_results)
    unseen_ret = _get_retrieved_count(unseen_results)
    unseen_avg = _get_avg_sim(unseen_results)

    seen_acc_pct = _safe_division(seen_exec, len(seen_results))
    unseen_acc_pct = _safe_division(unseen_exec, len(unseen_results))
    delta_pct = seen_acc_pct - unseen_acc_pct
    
    with open(run_output_dir / "results_seen.json", "w") as f:
        json.dump(seen_results, f, indent=2)
    with open(run_output_dir / "results_unseen.json", "w") as f:
        json.dump(unseen_results, f, indent=2)
        
    summary_dict = {
        "mode": mode,
        "db": TARGET_DB_ID,
        "seeding": seeder_summary,
        "metrics": {
            "seen": {
                "count": len(seen_results),
                "accuracy": seen_acc_pct,
                "retrieved": seen_ret,
                "avg_sim": seen_avg
            },
            "unseen": {
                "count": len(unseen_results),
                "accuracy": unseen_acc_pct,
                "retrieved": unseen_ret,
                "avg_sim": unseen_avg
            }
        }
    }
    
    with open(run_output_dir / "metrics.json", "w") as f:
        json.dump(summary_dict, f, indent=2)

    console.print()
    console.print(f"[bold cyan]{'=' * 52}[/bold cyan]")
    console.print(f"  [bold]DB SKILLS BENCHMARK — {TARGET_DB_ID}[/bold]")
    console.print(f"  Mode: {mode} | DB Skills: seeded ({seeder_summary.get('saved', 0)} fixes)")
    console.print(f"[bold cyan]{'=' * 52}[/bold cyan]")
    console.print()
    
    console.print("[bold yellow]SEEDING SUMMARY[/bold yellow]")
    console.print(f"  Attempted:    {seeder_summary.get('attempted', 0)}")
    console.print(f"  Saved:        {seeder_summary.get('saved', 0)}")
    console.print(f"  Duplicates:   {seeder_summary.get('duplicates', 0)}")
    console.print(f"  Failed:       {seeder_summary.get('failed', 0)}")
    console.print()
    
    console.print(f"[bold yellow]SEEN QUERIES[/bold yellow] ({len(seen_results)} examples — these were seeded into db_skills)")
    console.print(f"  Execution Accuracy:       {seen_exec}/{len(seen_results)}  ({seen_acc_pct:.1f}%)")
    console.print(f"  Retrieved a fix:          {seen_ret}/{len(seen_results)}  ({_safe_division(seen_ret, len(seen_results)):.1f}%)")
    console.print(f"  Avg top similarity:       {seen_avg:.3f}")
    console.print()
    
    console.print(f"[bold yellow]UNSEEN QUERIES[/bold yellow] ({len(unseen_results)} examples — no prior knowledge)")
    console.print(f"  Execution Accuracy:       {unseen_exec}/{len(unseen_results)}  ({unseen_acc_pct:.1f}%)")
    console.print(f"  Retrieved a fix:          {unseen_ret}/{len(unseen_results)}  ({_safe_division(unseen_ret, len(unseen_results)):.1f}%)")
    console.print(f"  Avg top similarity:       {unseen_avg:.3f}")
    console.print()

    console.print("[bold yellow]RETRIEVAL DETAIL[/bold yellow]")
    table = Table(show_header=True, header_style="bold cyan", padding=(0, 1))
    table.add_column("instance_id")
    table.add_column("intent")
    table.add_column("sim", justify="right")
    
    for r in seen_results + unseen_results:
        intent = r["intent"]
        short_intent = intent[:57] + "..." if len(intent) > 60 else intent
        sim = f"{r['top_retrieved_similarity']:.4f}" if r["top_retrieved_similarity"] is not None else ""
        table.add_row(r["instance_id"], short_intent, sim)
        
    console.print(table)
    console.print()

    console.print("[bold yellow]OVERALL[/bold yellow]")
    console.print(f"  Seen accuracy:    {seen_acc_pct:.1f}%")
    console.print(f"  Unseen accuracy:  {unseen_acc_pct:.1f}%")
    sign = "+" if delta_pct >= 0 else ""
    console.print(f"  Accuracy delta:   [bold green]{sign}{delta_pct:.1f}%[/bold green]")
    console.print(f"[bold cyan]{'=' * 52}[/bold cyan]")
