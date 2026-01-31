"""Data preparation module for BIRD-CRITIC evaluation.

This module handles pulling the dataset from HuggingFace, extracting solution files,
and combining them into a format ready for evaluation.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional

try:
    from datasets import load_dataset
except ImportError:
    raise ImportError(
        "datasets library is required. Install with: pip install datasets"
    )

from .config import load_config
from .solution_extractor import (
    load_all_solutions,
    merge_solutions_with_dataset
)


def load_jsonl(file_path: str) -> List[Dict]:
    """Load data from a JSONL file."""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


def dump_jsonl(data_list: List[Dict], out_path: str) -> None:
    """Write data to a JSONL file."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for obj in data_list:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def pull_dataset_from_huggingface(dataset_name: str = "birdsql/bird-critic-1.0-open") -> List[Dict]:
    """Pull dataset from HuggingFace.
    
    Args:
        dataset_name: Name of the HuggingFace dataset to load.
    
    Returns:
        List of dataset instances.
    """
    print(f"Loading dataset from HuggingFace: {dataset_name}")
    dataset = load_dataset(dataset_name)
    
    # Get the appropriate split (usually "open" for open version)
    if "open" in dataset:
        data_list = list(dataset["open"])
    elif "flash" in dataset:
        data_list = list(dataset["flash"])
    else:
        # Use the first available split
        split_name = list(dataset.keys())[0]
        data_list = list(dataset[split_name])
    
    print(f"Loaded {len(data_list)} instances from dataset")
    return data_list


def filter_postgresql_only(data_list: List[Dict]) -> List[Dict]:
    """Filter dataset to only include PostgreSQL instances.
    
    Args:
        data_list: List of dataset instances.
    
    Returns:
        Filtered list containing only PostgreSQL instances.
    """
    postgresql_data = [
        instance for instance in data_list
        if instance.get("dialect", "").lower() == "postgresql"
    ]
    print(f"Filtered to {len(postgresql_data)} PostgreSQL instances")
    return postgresql_data


def prepare_data(config_path: Optional[str] = None) -> None:
    """Main function to prepare data for evaluation.
    
    Args:
        config_path: Optional path to configuration file.
    """
    # Load configuration
    config = load_config(config_path)
    
    # Step 1: Pull dataset from HuggingFace
    print("\n=== Step 1: Pulling dataset from HuggingFace ===")
    dataset = pull_dataset_from_huggingface()
    
    # Step 2: Filter for PostgreSQL only
    print("\n=== Step 2: Filtering for PostgreSQL dialect ===")
    postgresql_dataset = filter_postgresql_only(dataset)
    
    # Step 3: Load solution files
    print("\n=== Step 3: Loading solution files ===")
    # Look for pg_sol.zip in the solutions directory
    solutions_dir = Path(config.bird_solutions_path)
    pg_sol_zip = solutions_dir / "pg_sol.zip"
    
    if not pg_sol_zip.exists():
        # Try alternative names or directories
        possible_paths = [
            solutions_dir / "pg_sol.zip",
            solutions_dir / "BIRD-Critic-sol" / "pg_sol.zip",
            solutions_dir.parent / "BIRD-Critic-sol" / "pg_sol.zip",
        ]
        for path in possible_paths:
            if path.exists():
                pg_sol_zip = path
                break
        else:
            raise FileNotFoundError(
                f"PostgreSQL solution file (pg_sol.zip) not found in {solutions_dir}. "
                f"Please ensure the solution files are in the configured solutions path."
            )
    
    print(f"Loading solutions from: {pg_sol_zip}")
    solutions = load_all_solutions(str(pg_sol_zip))
    print(f"Loaded {len(solutions)} solutions")
    
    # Step 4: Merge solutions with dataset
    print("\n=== Step 4: Merging solutions with dataset ===")
    merged_dataset = merge_solutions_with_dataset(postgresql_dataset, solutions)
    print(f"Merged {len(merged_dataset)} instances with solutions")
    
    # Step 5: Save combined dataset
    print("\n=== Step 5: Saving combined dataset ===")
    output_path = config.get_output_path("data", "combined", "postgresql_combined.jsonl")
    dump_jsonl(merged_dataset, output_path)
    print(f"Saved combined dataset to: {output_path}")
    
    print("\n=== Data preparation complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare BIRD-CRITIC dataset for evaluation"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (default: looks for config.json in evaluation directory)"
    )
    
    args = parser.parse_args()
    
    try:
        prepare_data(args.config)
    except Exception as e:
        print(f"Error during data preparation: {e}", file=sys.stderr)
        sys.exit(1)
