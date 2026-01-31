"""Integration module for testing sequel2sql on BIRD-CRITIC dataset.

This module loads BIRD-CRITIC instances and uses sequel2sql to analyze error SQL.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# Import sequel2sql modules
import sqlglot
from ..ast_parsers.validator import validate_syntax
from ..ast_parsers.progressive_analyzer import ProgressiveQueryAnalyzer
from ..ast_parsers.query_analyzer import analyze_query, analyze_query_lightweight


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


def analyze_with_sequel2sql(instance: Dict) -> Dict:
    """Analyze an instance using sequel2sql.
    
    Args:
        instance: BIRD-CRITIC instance with issue_sql, query, and schema.
    
    Returns:
        Dictionary with sequel2sql analysis results.
    """
    issue_sql = instance.get("issue_sql", [])
    if not issue_sql:
        return {"error": "No issue_sql found"}
    
    # Get the first SQL statement (or combine if multiple)
    if isinstance(issue_sql, list):
        sql_text = issue_sql[0] if len(issue_sql) == 1 else "\n".join(issue_sql)
    else:
        sql_text = issue_sql
    
    results = {
        "instance_id": instance.get("instance_id"),
        "original_sql": sql_text,
        "analysis": {}
    }
    
    try:
        # Step 1: Validate syntax
        validation_result = validate_syntax(sql_text, dialect="postgres")
        results["analysis"]["validation"] = {
            "valid": validation_result.valid,
            "errors": [
                {
                    "code": err.code,
                    "message": err.message,
                    "location": err.location
                }
                for err in validation_result.errors
            ] if validation_result.errors else []
        }
        
        # Step 2: Progressive analysis (if available)
        try:
            # Parse SQL to AST first
            parsed = sqlglot.parse_one(sql_text, dialect="postgres")
            if parsed:
                analyzer = ProgressiveQueryAnalyzer()
                # Use analyze_with_expansion with no error node for full analysis
                analysis_metadata = analyzer.analyze_with_expansion(parsed, error_node=None)
                results["analysis"]["progressive"] = {
                    "complexity_score": analysis_metadata.complexity_score,
                    "pattern_signature": analysis_metadata.pattern_signature,
                    "clauses_present": analysis_metadata.clauses_present,
                    "num_joins": analysis_metadata.num_joins,
                    "num_subqueries": analysis_metadata.num_subqueries,
                    "num_ctes": analysis_metadata.num_ctes,
                    "num_aggregations": analysis_metadata.num_aggregations,
                }
            else:
                results["analysis"]["progressive"] = {"error": "Failed to parse SQL"}
        except Exception as e:
            results["analysis"]["progressive"] = {"error": str(e)}
        
        # Step 3: Query analysis (if available)
        try:
            # Parse SQL to AST first
            parsed = sqlglot.parse_one(sql_text, dialect="postgres")
            if parsed:
                query_metadata = analyze_query_lightweight(parsed)
                results["analysis"]["query"] = {
                    "complexity_score": query_metadata.complexity_score,
                    "pattern_signature": query_metadata.pattern_signature,
                    "clauses_present": query_metadata.clauses_present,
                    "num_joins": query_metadata.num_joins,
                    "num_subqueries": query_metadata.num_subqueries,
                    "num_ctes": query_metadata.num_ctes,
                    "num_aggregations": query_metadata.num_aggregations,
                }
            else:
                results["analysis"]["query"] = {"error": "Failed to parse SQL"}
        except Exception as e:
            results["analysis"]["query"] = {"error": str(e)}
    
    except Exception as e:
        results["error"] = str(e)
    
    return results




def run_sequel2sql_evaluation(config_path: Optional[str] = None) -> None:
    """Run sequel2sql evaluation on BIRD-CRITIC dataset.
    
    Args:
        config_path: Optional path to configuration file.
    """
    from .config import load_config
    
    # Load configuration
    config = load_config(config_path)
    
    # Step 1: Load combined dataset
    print("\n=== Step 1: Loading dataset ===")
    data_path = config.get_output_path("data", "combined", "postgresql_combined.jsonl")
    
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"Combined dataset not found: {data_path}. "
            f"Please run data preparation first."
        )
    
    instances = load_jsonl(data_path)
    print(f"Loaded {len(instances)} instances")
    
    # Step 2: Analyze with sequel2sql
    print("\n=== Step 2: Analyzing with sequel2sql ===")
    sequel2sql_results = []
    
    for i, instance in enumerate(instances):
        if (i + 1) % 10 == 0:
            print(f"Processing {i + 1}/{len(instances)}")
        
        result = analyze_with_sequel2sql(instance)
        result["original_instance"] = instance  # Keep reference to original
        sequel2sql_results.append(result)
    
    # Save sequel2sql results
    seq_output_path = config.get_output_path(
        "data", "results", "sequel2sql_analysis.jsonl"
    )
    dump_jsonl(sequel2sql_results, seq_output_path)
    print(f"Saved sequel2sql analysis to: {seq_output_path}")
    
    # Step 3: Save results
    print("\n=== Step 3: Saving results ===")
    results_path = config.get_output_path(
        "data", "results", "sequel2sql_analysis.jsonl"
    )
    dump_jsonl(sequel2sql_results, results_path)
    print(f"Results saved to: {results_path}")
    
    print("\n=== Sequel2SQL evaluation complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run sequel2sql evaluation on BIRD-CRITIC dataset"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: looks for config.json in evaluation directory)"
    )
    
    args = parser.parse_args()
    
    try:
        run_sequel2sql_evaluation(args.config)
    except Exception as e:
        print(f"Error during sequel2sql evaluation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
