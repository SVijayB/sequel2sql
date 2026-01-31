"""Copy eval-ready baseline output to BIRD-CRITIC repo for run_eval.sh.

Reads config, copies baseline_gemini_final_output.jsonl to
{bird_critic_repo_path}/evaluation/data/postgresql_300.jsonl,
creates the directory if needed, and prints the exact run_eval.sh commands.
"""

import os
import shutil
import argparse
from typing import Optional


def copy_baseline_to_bird(config_path: Optional[str] = None) -> None:
    """Copy baseline_gemini_final_output.jsonl to BIRD-CRITIC evaluation/data."""
    from .config import load_config

    config = load_config(config_path)
    src = config.get_output_path("data", "results", "baseline_gemini_final_output.jsonl")
    dest_dir = os.path.join(config.bird_critic_repo_path, "evaluation", "data")
    dest = os.path.join(dest_dir, "postgresql_300.jsonl")

    if not os.path.exists(src):
        raise FileNotFoundError(
            f"Baseline file not found: {src}. Run sequel2sql_integration first."
        )

    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"Copied baseline to: {dest}\n")

    eval_run = os.path.join(config.bird_critic_repo_path, "evaluation", "run")
    print("Run BIRD-CRITIC evaluation:")
    print("  1. In BIRD-CRITIC repo: enable PostgreSQL in evaluation/docker-compose.yml")
    print("  2. From BIRD-CRITIC repo:")
    print(f"       cd {os.path.join(config.bird_critic_repo_path, 'evaluation')}")
    print("       docker compose up --build")
    print("  3. In another terminal:")
    print("       docker compose exec so_eval_env bash")
    print(f"       cd run")
    print("       # Ensure dialect=postgresql and mode=pred in run_eval.sh")
    print("       bash run_eval.sh")
    print("\nReport will be written next to the JSONL (e.g. *_output_with_status.jsonl).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Copy eval-ready baseline to BIRD-CRITIC repo for run_eval.sh"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: config.json in evaluation directory)",
    )
    args = parser.parse_args()

    try:
        copy_baseline_to_bird(args.config)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise SystemExit(1)
