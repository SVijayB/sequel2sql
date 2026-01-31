"""Summarize baseline_gemini_final_output.jsonl and explain how to get official metrics.

Run: python -m src.evaluation.interpret_baseline_results [path_to_jsonl]

- Prints coverage (non-empty pred_sqls) and a strict exact-match rate (normalized).
- Real performance = execution accuracy from BIRD-CRITIC run_eval.sh (run pred vs gold on DBs).
"""

import json
import sys
from pathlib import Path


def norm_sql(s) -> str:
    """Normalize SQL for strict string comparison (whitespace only)."""
    if isinstance(s, list):
        s = " ".join(s)
    return " ".join(str(s).split())


def main(jsonl_path: str) -> None:
    path = Path(jsonl_path)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    total = len(rows)
    non_empty = sum(
        1
        for r in rows
        if r.get("pred_sqls") and any(p and str(p).strip() for p in r["pred_sqls"])
    )
    empty = total - non_empty
    exact = sum(
        1
        for r in rows
        if norm_sql(r.get("pred_sqls", [])) == norm_sql(r.get("sol_sql", []))
        and norm_sql(r.get("pred_sqls", []))
    )

    print("=== Baseline results summary ===\n")
    print(f"File: {path}")
    print(f"Total instances: {total}")
    print(f"With non-empty pred_sqls: {non_empty} ({100 * non_empty / total:.1f}%)")
    print(f"With empty pred_sqls: {empty}")
    print(
        f"Exact string match (pred_sqls == sol_sql, normalized): {exact} ({100 * exact / total:.1f}%)"
    )
    print()
    print("How to interpret:")
    print("- Coverage: model produced at least one SQL for almost all instances.")
    print("- Exact match is very strict (same text); many correct fixes differ in formatting.")
    print("- Real performance = execution accuracy from BIRD-CRITIC evaluation.")
    print()
    print("To get official metrics (execution accuracy, pass/fail per instance):")
    print("  1. Copy this file to BIRD-CRITIC repo as evaluation/data/postgresql_300.jsonl")
    print("     (e.g. python -m src.evaluation.copy_baseline_to_bird)")
    print("  2. In BIRD-CRITIC repo: docker compose up, then docker compose exec so_eval_env bash")
    print("  3. cd run && bash run_eval.sh (dialect=postgresql, mode=pred)")
    print("  4. Check the output JSONL and report for pass rate / execution accuracy.")
    print("\n=== Done ===")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Summarize baseline results JSONL")
    p.add_argument(
        "jsonl",
        nargs="?",
        default=None,
        help="Path to baseline_gemini_final_output.jsonl (default: from config)",
    )
    args = p.parse_args()
    if args.jsonl:
        path = args.jsonl
    else:
        try:
            from .config import load_config
            config = load_config()
            path = config.get_output_path("data", "results", "baseline_gemini_final_output.jsonl")
        except Exception:
            path = "evaluation_output/data/results/baseline_gemini_final_output.jsonl"
    main(path)
