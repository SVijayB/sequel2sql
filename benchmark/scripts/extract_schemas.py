#!/usr/bin/env python3
"""Extract schema definitions from PostgreSQL table dump files into JSON format.

Parses CREATE TABLE statements from .sql files in postgre_table_dumps/
and outputs JSON schema files compatible with validate_sql().
"""

import json
import re
from pathlib import Path
import sqlglot
from sqlglot import exp


def extract_create_table_sql(file_content: str) -> list[str]:
    """Extract CREATE TABLE statements from a SQL file."""
    # Match CREATE TABLE ... ending with );
    pattern = r"CREATE TABLE\s+[^;]+;\s*"
    matches = re.findall(pattern, file_content, re.IGNORECASE | re.DOTALL)
    return matches


def parse_create_table(sql: str) -> dict[str, dict[str, str]] | None:
    """Parse a CREATE TABLE statement and extract table name and columns.
    
    Returns: {table_name: {column_name: column_type}}
    """
    try:
        ast = sqlglot.parse_one(sql, read="postgres")
        if not isinstance(ast, exp.Create):
            return None
        
        table_expr = ast.this
        if not isinstance(table_expr, exp.Schema):
            return None
        
        # Get table name (strip schema prefix like "public.")
        table_name_expr = table_expr.this
        if isinstance(table_name_expr, exp.Table):
            table_name = table_name_expr.name
        else:
            table_name = str(table_name_expr)
        
        # Extract columns
        columns = {}
        for column_def in table_expr.expressions:
            if isinstance(column_def, exp.ColumnDef):
                col_name = column_def.name
                col_type = column_def.kind
                if col_type:
                    # Get the SQL representation of the type
                    type_str = col_type.sql(dialect="postgres")
                    columns[col_name] = type_str
        
        if columns:
            return {table_name: columns}
        return None
        
    except Exception as e:
        print(f"  Warning: Failed to parse: {e}")
        return None


def extract_schema_from_directory(db_dir: Path) -> dict[str, dict[str, str]]:
    """Extract all table schemas from a database directory."""
    schema = {}
    
    for sql_file in sorted(db_dir.glob("*.sql")):
        print(f"  Processing {sql_file.name}...")
        content = sql_file.read_text(encoding="utf-8", errors="ignore")
        
        create_statements = extract_create_table_sql(content)
        for stmt in create_statements:
            result = parse_create_table(stmt)
            if result:
                schema.update(result)
    
    return schema


def main():
    # Paths
    base_dir = Path(__file__).parent.parent / "data" / "postgre_table_dumps"
    output_dir = Path(__file__).parent.parent / "data" / "schemas"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Source: {base_dir}")
    print(f"Output: {output_dir}\n")
    
    # Process each database directory
    db_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()])
    
    for db_dir in db_dirs:
        db_name = db_dir.name
        print(f"Processing {db_name}...")
        
        schema = extract_schema_from_directory(db_dir)
        
        if schema:
            output_file = output_dir / f"{db_name}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
            print(f"  -> Saved {len(schema)} tables to {output_file.name}\n")
        else:
            print(f"  -> No tables found\n")
    
    print("Done!")


if __name__ == "__main__":
    main()
