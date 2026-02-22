import os
import sys
from datetime import datetime
from pathlib import Path

# Add benchmark/src to path for shared logic (so direct imports work)
_benchmark_src = str(Path(__file__).parent.parent / "benchmark" / "src")
if _benchmark_src not in sys.path:
    sys.path.insert(0, _benchmark_src)

# Add our own db_skills_benchmark directory to path so src.module works
_our_src = str(Path(__file__).parent)
if _our_src not in sys.path:
    sys.path.insert(0, _our_src)
    
# Import from project root src
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmark.src.ui import display_logo, console
from db_skills_benchmark.src.config import TARGET_DB_ID, get_outputs_dir, get_logs_dir, validate_config
from db_skills_benchmark.src.cli import show_main_menu, confirm_summary, ask_subset_limit
from db_skills_benchmark.src.seeder import load_and_split_examples, seed_db_skills, backup_and_clear_db_skills
from db_skills_benchmark.src.runner import run_benchmark
from db_skills_benchmark.src.stats_reporter import print_report
from db_skills_benchmark.src.logger import setup_logger

import subprocess
import time

def check_docker() -> bool:
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def start_docker_containers() -> bool:
    benchmark_dir = Path(__file__).parent.parent / "benchmark"
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, cwd=benchmark_dir, timeout=10)
        running = result.stdout.strip().split("\n")
        if "sequel2sql_postgresql" in running and "sequel2sql_eval" in running:
            return True
            
        subprocess.run(["docker", "compose", "up", "-d", "--build"], capture_output=True, text=True, cwd=benchmark_dir, timeout=600)
        
        for i in range(30):
            result = subprocess.run(["docker", "exec", "sequel2sql_postgresql", "pg_isready", "-U", "root"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return True
            time.sleep(2)
        return False
    except Exception as e:
        return False

def main():
    display_logo()
    
    try:
        validate_config()
    except SystemExit:
        console.print("[red]❌ Benchmark configuration validation failed.[/red]")
        return 1
        
    console.print("Checking Docker status...")
    if not check_docker():
        console.print("[red]❌ Docker is not running or not accessible. Please start Docker Desktop.[/red]")
        return 1
        
    if not start_docker_containers():
        console.print("[red]❌ Failed to start required Docker containers.[/red]")
        return 1
        
    mode = show_main_menu(TARGET_DB_ID)
    if mode in (None, "quit"):
        return 0
        
    subset_limit = ask_subset_limit()
        
    seen_examples, unseen_examples = load_and_split_examples(TARGET_DB_ID)
    
    if subset_limit is not None:
        seen_examples = seen_examples[:subset_limit]
        unseen_examples = unseen_examples[:subset_limit]
        subset_desc = f"subset of subsets ({subset_limit} per subset)"
    else:
        subset_desc = "both (full)"
    
    do_seed = mode == "pipeline_seeded"
    runner_mode = "simple" if mode == "simple" else "pipeline"
    
    seen_count = len(seen_examples)
    unseen_count = len(unseen_examples)
    
    if not confirm_summary(runner_mode, subset_desc, seen_count, unseen_count, do_seed):
        console.print("User cancelled. Exiting...")
        return 0

    outputs_dir = get_outputs_dir()
    outputs_dir.mkdir(parents=True, exist_ok=True)
    
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
    run_dir = outputs_dir / f"run_{run_timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"\n[cyan]Starting Benchmark '{mode}' (Run {run_timestamp})...[/cyan]")
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger = setup_logger(timestamp)
    logger.info("=" * 70)
    logger.info(f"DB SKILLS BENCHMARK Starting (Run {run_timestamp})")
    logger.info(f"Mode: {mode}")
    logger.info(f"Target DB: {TARGET_DB_ID}")
    logger.info(f"Summary: {subset_desc} | Seen: {seen_count} | Unseen: {unseen_count}")
    logger.info("=" * 70)
    logger.info(f"Output directory: {run_dir}")
    
    seeder_summary = {
        "attempted": 0,
        "saved": 0,
        "duplicates": 0,
        "failed": 0,
        "seeded_instance_ids": []
    }
    
    if mode in ("pipeline_seeded", "pipeline_control"):
        logger.info("Applying DB backups or resetting Chroma cache...")
        backup_and_clear_db_skills(TARGET_DB_ID, run_dir)
        
    if mode == "pipeline_seeded" and seen_examples:
        logger.info("Seeding DB Skills database with 'Seen' query subset...")
        seeder_summary = seed_db_skills(seen_examples)
        
    seen_targets = seen_examples
    unseen_targets = unseen_examples
        
    logger.info("Executing Pipeline Inference against PostgreSQL Containers...")
    
    all_targets = []
    if seen_targets:
        for ex in seen_targets:
            ex["benchmark_subgroup"] = "seen"
        all_targets.extend(seen_targets)
        
    if unseen_targets:
        for ex in unseen_targets:
            ex["benchmark_subgroup"] = "unseen"
        all_targets.extend(unseen_targets)
        
    all_results = []
    if all_targets:
        all_results = run_benchmark(
            examples=all_targets,
            mode=runner_mode,
            use_db_skills=(mode == "pipeline_seeded"),
            run_output_dir=run_dir
        )
        
    seen_results = [r for r in all_results if r.get("benchmark_subgroup") == "seen"]
    unseen_results = [r for r in all_results if r.get("benchmark_subgroup") == "unseen"]
        
    print_report(seen_results, unseen_results, mode, seeder_summary, run_dir)
    logger.info(f"Benchmark complete! Outputs written to {run_dir}")
    
    return 0
    
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
