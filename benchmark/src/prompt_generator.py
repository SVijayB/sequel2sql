"""Prompt generator for SEQUEL2SQL Benchmark"""

import json
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

from .logger_config import get_logger

# Prompt template for PostgreSQL (baseline_v1 from bird-critic)
BASELINE_PROMPT_TEMPLATE = """You are a SQL assistant. Your task is to understand user issue and correct their problematic SQL given the database schema. Please wrap your corrected SQL with ```sql\n[Your Fixed SQL]\n``` tags in your response.

# Database Schema:
{schema}

# User issue:
{user_issue}

# Problematic SQL:
{issue_sql}

# Corrected SQL:
"""


def generate_prompt(
    data: Dict[str, Any], schema_field: str = "preprocess_schema"
) -> str:
    """
    Generate a prompt for a single query instance.

    Args:
        data: Query instance data
        schema_field: Field name containing the schema (default: "preprocess_schema")

    Returns:
        Generated prompt string
    """
    problem_statement = data["query"]
    issue_sql_list = data["issue_sql"]

    # Format issue SQL with code blocks
    issue_sql_str = ""
    for sql in issue_sql_list:
        issue_sql_str += f"```sql\n{sql}\n```\n"

    # Generate prompt using template
    prompt = BASELINE_PROMPT_TEMPLATE.format(
        schema=data[schema_field], user_issue=problem_statement, issue_sql=issue_sql_str
    )

    return prompt


def generate_prompts_from_file(
    input_path: Path,
    output_path: Path,
    schema_field: str = "preprocess_schema",
    limit: int = None,
) -> int:
    """
    Generate prompts from input JSONL file and save to output file.

    Args:
        input_path: Path to input JSONL file (postgresql_full.jsonl)
        output_path: Path to output JSONL file for prompts
        schema_field: Field name containing the schema
        limit: Optional limit on number of instances to process

    Returns:
        Number of prompts generated
    """
    logger = get_logger()

    # Load data
    logger.info(f"Loading data from {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data_list = [json.loads(line) for line in f]

    if limit:
        data_list = data_list[:limit]

    logger.info(f"Generating prompts for {len(data_list)} instances...")

    # Generate prompts
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, data in enumerate(tqdm(data_list, desc="Generating prompts")):
            # Generate prompt
            prompt = generate_prompt(data, schema_field)

            # Create output instance with prompt and index
            output_instance = data.copy()
            output_instance["prompt"] = prompt
            output_instance["_index"] = i

            # Write to file
            f.write(json.dumps(output_instance, ensure_ascii=False) + "\n")

    logger.info(f"✓ Generated {len(data_list)} prompts and saved to {output_path}")

    return len(data_list)


def load_prompts(prompts_path: Path) -> List[Dict[str, Any]]:
    """
    Load prompts from JSONL file.

    Args:
        prompts_path: Path to prompts JSONL file

    Returns:
        List of prompt instances
    """
    with open(prompts_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


if __name__ == "__main__":
    # Test prompt generator
    from datetime import datetime

    from .config import get_data_dir, get_outputs_dir
    from .logger_config import setup_logger

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setup_logger(timestamp)

    # Test with first 5 queries
    data_dir = get_data_dir()
    input_file = data_dir / "postgresql_full.jsonl"

    output_dir = get_outputs_dir() / f"test_{timestamp}"
    output_file = output_dir / "prompts.jsonl"

    num_generated = generate_prompts_from_file(input_file, output_file, limit=5)

    print(f"\n✓ Generated {num_generated} test prompts")
    print(f"  Output: {output_file}\n")

    # Display first prompt
    prompts = load_prompts(output_file)
    if prompts:
        print("First prompt preview:")
        print("=" * 70)
        print(prompts[0]["prompt"][:500])
        print("...")
        print("=" * 70)
