"""Integration module for BIRD-CRITIC evaluation.

Runs baseline via Google AI API (Gemini or Gemma 3): loads combined dataset,
prompts model with query + issue_sql, extracts pred_sqls from response (```sql...```),
saves eval-ready baseline_gemini_final_output.jsonl. Default model: Gemma 3 27B (gemma-3-27b-it).

Sequel2sql (ast_parsers) integration is commented out below for later re-use.
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional

# --- Sequel2sql (ast_parsers) integration: commented out ---
# import sqlglot
# from ..ast_parsers.validator import validate_syntax
# from ..ast_parsers.progressive_analyzer import ProgressiveQueryAnalyzer
# from ..ast_parsers.query_analyzer import analyze_query, analyze_query_lightweight


def load_jsonl(file_path: str) -> List[Dict]:
    """Load data from a JSONL file."""
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


def dump_jsonl(data_list: List[Dict], out_path: str) -> None:
    """Write data to a JSONL file."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for obj in data_list:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# --- Sequel2sql (ast_parsers) integration: commented out for baseline ---
# def analyze_with_sequel2sql(instance: Dict) -> Dict: ...


def _extract_sql_blocks(response: str) -> List[str]:
    """Extract SQL from response using ```sql...``` blocks (BIRD-style).
    Returns a list of SQL strings for pred_sqls; if none found, returns [response.strip()] or [].
    """
    if not response or not response.strip():
        return []
    pattern = re.compile(r"```[ \t]*sql\s*([\s\S]*?)```", re.IGNORECASE | re.DOTALL)
    blocks = pattern.findall(response)
    blocks = [stmt.strip() for stmt in blocks if stmt.strip()]
    if blocks:
        return blocks
    return [response.strip()] if response.strip() else []


def _build_baseline_prompt(instance: Dict) -> str:
    """Build prompt for Gemini: user query + buggy SQL."""
    query = instance.get("query", "")
    issue_sql = instance.get("issue_sql", [])
    if isinstance(issue_sql, list):
        sql_text = issue_sql[0] if len(issue_sql) == 1 else "\n".join(issue_sql)
    else:
        sql_text = str(issue_sql or "")
    return (
        "The user has the following problem (PostgreSQL):\n\n"
        f"{query}\n\n"
        "Here is the buggy SQL that needs to be fixed:\n\n"
        f"{sql_text}\n\n"
        "Provide only the corrected PostgreSQL SQL, no explanation."
    )


def _call_google_ai(prompt: str, api_key: str, model_name: str) -> str:
    """Call Google AI API (Gemini or Gemma 3) and return model response text.
    Uses google-genai SDK (pip install google-genai); same API key for Gemini/Gemma.
    """
    # Use google.genai.Client so we get the right SDK when both google-genai and
    # google-generativeai are installed (they share the 'google' namespace).
    from google.genai import Client
    client = Client(api_key=api_key)
    response = client.models.generate_content(model=model_name, contents=prompt)
    if response and getattr(response, "text", None):
        return response.text.strip()
    return ""


def run_gemini_baseline(config_path: Optional[str] = None) -> None:
    """Run Gemini baseline: load dataset, prompt Gemini per instance, extract pred_sqls, save eval-ready baseline_gemini_final_output.jsonl."""
    from .config import load_config

    config = load_config(config_path)
    if not config.gemini_api_key:
        cwd_env = Path.cwd() / ".env"
        _config_file = Path(__file__).resolve()
        project_root = _config_file.parent.parent.parent
        root_env = project_root / ".env"
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is required for baseline. "
            "Set one in .env (e.g. GEMINI_API_KEY=your_key with no spaces around =) or in the environment. "
            f"Checked: {cwd_env} (exists={cwd_env.exists()}), {root_env} (exists={root_env.exists()})."
        )

    data_path = config.get_output_path("data", "combined", "postgresql_combined.jsonl")
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"Combined dataset not found: {data_path}. Run data preparation first."
        )

    instances = load_jsonl(data_path)
    print(f"\n=== Gemini baseline: {len(instances)} instances ===")

    results = []
    for i, instance in enumerate(instances):
        if (i + 1) % 10 == 0:
            print(f"Processing {i + 1}/{len(instances)}")

        prompt = _build_baseline_prompt(instance)
        try:
            predicted_sql = _call_google_ai(
                prompt, config.gemini_api_key, model_name=config.gemini_model
            )
        except Exception as e:
            predicted_sql = ""
            print(f"  API error for {instance.get('instance_id')}: {e}")

        pred_sqls = _extract_sql_blocks(predicted_sql)

        # Eval-ready row: preserve all fields BIRD eval expects + pred_sqls (list)
        row = {
            "instance_id": instance.get("instance_id"),
            "db_id": instance.get("db_id"),
            "query": instance.get("query", ""),
            "issue_sql": instance.get("issue_sql", []),
            "sol_sql": instance.get("sol_sql", []),
            "preprocess_sql": instance.get("preprocess_sql", []),
            "clean_up_sql": instance.get("clean_up_sql", []),
            "test_cases": instance.get("test_cases", []),
            "pred_sqls": pred_sqls,
        }
        if "efficiency" in instance:
            row["efficiency"] = instance["efficiency"]
        if "dialect" in instance:
            row["dialect"] = instance["dialect"]
        if "version" in instance:
            row["version"] = instance["version"]
        results.append(row)

    out_path = config.get_output_path("data", "results", "baseline_gemini_final_output.jsonl")
    dump_jsonl(results, out_path)
    print(f"Saved eval-ready baseline to: {out_path}\n=== Gemini baseline complete ===")


def run_sequel2sql_evaluation(config_path: Optional[str] = None) -> None:
    """Run evaluation: Gemini baseline (sequel2sql integration commented out)."""
    # --- Sequel2sql (ast_parsers) path: commented out ---
    # from .config import load_config
    # config = load_config(config_path)
    # data_path = config.get_output_path("data", "combined", "postgresql_combined.jsonl")
    # instances = load_jsonl(data_path)
    # sequel2sql_results = [analyze_with_sequel2sql(inst) for inst in instances]
    # dump_jsonl(sequel2sql_results, config.get_output_path("data", "results", "sequel2sql_analysis.jsonl"))

    run_gemini_baseline(config_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Gemini baseline on BIRD-CRITIC dataset (GEMINI_API_KEY in .env)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: config.json in evaluation directory)"
    )

    args = parser.parse_args()

    try:
        run_sequel2sql_evaluation(args.config)
    except Exception as e:
        print(f"Error during evaluation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
