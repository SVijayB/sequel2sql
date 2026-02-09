import sys
from pathlib import Path

# Add src to path FIRST
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db_tools.tools import (
    get_database_schema,
    get_sample_rows,
    execute_query,
    get_table_columns,
)

print("=" * 70)
print("TEST 1: Database Schema (Markdown Format)")
print("=" * 70)
schema = get_database_schema(database_name="financial")
print(schema.to_markdown())

print("\n" + "=" * 70)
print("TEST 2: Sample Rows (JSON Format)")
print("=" * 70)
rows = get_sample_rows(database_name="financial", table_name="loan", limit=5)
print(rows.to_markdown())

print("\n" + "=" * 70)
print("TEST 3: Sample Columns (JSON Format)")
print("=" * 70)
cols = get_table_columns(database_name="financial", table_name="loan")
print(cols.to_markdown())

print("\n" + "=" * 70)
print("TEST 3: Custom Query (JSON Format)")
print("=" * 70)
result = execute_query(
    database_name="financial",
    query="SELECT account_id, COUNT(*) as loan_count FROM loan GROUP BY account_id",
)
print(result.to_markdown())
