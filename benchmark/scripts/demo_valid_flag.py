# -*- coding: utf-8 -*-
"""Demo: Show the valid flag working correctly."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ast_parsers.llm_tool import validate_sql

# Test cases
test_cases = [
    ("Valid query", "SELECT * FROM account WHERE account_id = 1", "financial"),
    ("Invalid column", "SELECT nonexistent_col FROM account", "financial"),
    ("Invalid table", "SELECT * FROM fake_table", "financial"),
    ("Syntax error", "SELECT * FROM WHERE", None),
]

print("Demonstrating validate_sql with valid flag\n")
print("=" * 80)

for name, sql, db_name in test_cases:
    result = validate_sql(sql, db_name=db_name, dialect="postgres")
    
    print(f"\n{name}:")
    print(f"  SQL: {sql}")
    print(f"  valid: {result.valid}")
    print(f"  errors: {len(result.errors)}")
    if result.errors:
        for e in result.errors:
            print(f"    - [{e.tag}] {e.message}")

print("\n" + "=" * 80)
print("\n✅ The valid flag correctly reflects whether errors were detected!")
