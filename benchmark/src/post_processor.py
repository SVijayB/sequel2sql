"""Post-processor to extract SQL from LLM responses"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

from .logger_config import get_logger

# Regex pattern to extract SQL from markdown code blocks
SQL_PATTERN = re.compile(r"```[ \t]*sql\s*([\s\S]*?)```", re.IGNORECASE | re.DOTALL)


def extract_sql_from_response(response: str) -> List[str]:
    """
    Extract SQL statements from markdown code blocks in response.

    Args:
        response: LLM response string containing ```sql blocks

    Returns:
        List of extracted SQL statements
    """
    sql_statements = SQL_PATTERN.findall(response)
    return [stmt.strip() for stmt in sql_statements if stmt.strip()]


def process_responses_file(input_path: Path, output_path: Path) -> int:
    """
    Process responses file to extract SQL statements and merge with gold solutions.

    Args:
        input_path: Path to input JSONL file with responses
        output_path: Path to output JSONL file with extracted SQL

    Returns:
        Number of instances processed
    """
    logger = get_logger()

    logger.info(f"Processing responses from {input_path}")

    # Read input file
    with open(input_path, "r", encoding="utf-8") as f:
        data_list = [json.loads(line) for line in f]

    # Load gold solutions
    gold_solutions = {}
    gold_sol_path = Path(__file__).parent.parent / "data" / "pg_sol.jsonl"

    if gold_sol_path.exists():
        logger.info(f"Loading gold solutions from {gold_sol_path}")
        with open(gold_sol_path, "r", encoding="utf-8") as f:
            for line in f:
                sol_data = json.loads(line)
                instance_id = sol_data.get("instance_id")
                if instance_id:
                    gold_solutions[instance_id] = sol_data
    else:
        logger.warning(f"Gold solutions file not found at {gold_sol_path}")

    # Process each instance
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for data in tqdm(data_list, desc="Extracting SQL"):
            response = data.get("response", "")

            # Extract SQL statements
            sql_list = extract_sql_from_response(response)

            # Add extracted SQL to data
            data["pred_sqls"] = sql_list

            # Merge gold solution if available
            instance_id = data.get("instance_id")
            if instance_id and instance_id in gold_solutions:
                gold_data = gold_solutions[instance_id]
                data["sol_sql"] = gold_data.get("sol_sql", [])
                data["test_cases"] = gold_data.get("test_cases", [])

            # Remove large fields to reduce file size
            data.pop("prompt", None)
            data.pop("_index", None)
            data.pop("reasoning_content", None)  # If exists from some models

            # Write to output
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    logger.info(f"✓ Processed {len(data_list)} responses and saved to {output_path}")
    logger.info(
        f"  Merged {len([d for d in data_list if d.get('instance_id') in gold_solutions])} gold solutions"
    )

    return len(data_list)


def load_processed_data(output_path: Path) -> List[Dict[str, Any]]:
    """
    Load processed data with extracted SQL.

    Args:
        output_path: Path to output JSONL file

    Returns:
        List of data instances with pred_sqls
    """
    with open(output_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


if __name__ == "__main__":
    # Test post-processor
    from datetime import datetime

    from .logger_config import setup_logger

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setup_logger(timestamp)

    # Test SQL extraction
    test_response = """
    Here's the corrected SQL for your query:
    
    ```sql
    SELECT * FROM users WHERE age > 21;
    ```
    
    This query will fetch all users older than 21.
    """

    extracted = extract_sql_from_response(test_response)
    print(f"\n✓ Extracted {len(extracted)} SQL statement(s):")
    for i, sql in enumerate(extracted, 1):
        print(f"\n{i}. {sql}")

    # Test with multiple SQL blocks
    test_response2 = """
    I'll fix both queries:
    
    ```sql
    UPDATE products SET price = 100 WHERE id = 1;
    ```
    
    And also:
    
    ```sql
    DELETE FROM orders WHERE status = 'cancelled';
    ```
    """

    extracted2 = extract_sql_from_response(test_response2)
    print(f"\n✓ Extracted {len(extracted2)} SQL statement(s) from second test")

    print("\n✓ Post-processor test complete!\n")
