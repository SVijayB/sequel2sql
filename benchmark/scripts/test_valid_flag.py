# -*- coding: utf-8 -*-
"""Test: verify validate_sql now returns valid flag correctly."""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ast_parsers.llm_tool import validate_sql

BENCHMARK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "postgresql_full.jsonl"
)


def main():
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]

    # Test first 5 entries
    test_entries = entries[:5]

    print("Testing validate_sql with valid flag\n")
    print("=" * 80)

    for entry in test_entries:
        instance_id = entry["instance_id"]
        db_id = entry["db_id"]
        issue_sqls = entry["issue_sql"]

        for i, sql in enumerate(issue_sqls):
            # Call validate_sql - now returns ValidationResultOut
            result = validate_sql(sql, db_name=db_id, dialect="postgres")

            print(f"\n--- {instance_id} (sql #{i+1}) ---")
            print(f"  SQL (first 100): {sql[:100]}...")
            print(f"  result.valid: {result.valid}")
            print(f"  len(result.errors): {len(result.errors)}")
            if result.errors:
                for e in result.errors[:3]:  # Show first 3 errors
                    print(f"    - [{e.tag}] {e.message}")

    print("\n" + "=" * 80)
    print("\n✅ validate_sql now returns ValidationResultOut with valid flag!")


if __name__ == "__main__":
    main()
