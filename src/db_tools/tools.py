"""
Database tools for SQL query debugging.

Provides utilities to interact with databases:
- Get schema information (optimized for context)
- Fetch column information from tables
- Get sample rows from tables
- All functions work with Docker containers
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, inspect, text


@dataclass
class ToolResult:
    """Container for tool execution results."""

    success: bool
    data: Any
    error: Optional[str] = None
    duration: Optional[timedelta] = None
    source: str = "docker"  # "docker" or "local"

    def to_markdown(self) -> str:
        """Format tool result as markdown.

        Returns:
            Markdown formatted output
        """
        if not self.success:
            return f"❌ Error: {self.error}"

        if isinstance(self.data, str):
            return self.data

        # For dict/list data, format as markdown
        if isinstance(self.data, dict):
            return json.dumps(self.data, indent=2)

        if isinstance(self.data, list):
            return json.dumps(self.data, indent=2)

        return str(self.data)


def _execute_in_docker(
    container_name: str,
    python_code: str,
    timeout: int = 30,
) -> ToolResult:
    """
    Execute Python code inside a Docker container.
    NOTE: This is kept for reference but we now connect directly from host.

    Args:
        container_name: Name of the Docker container
        python_code: Python code to execute
        timeout: Timeout in seconds

    Returns:
        ToolResult with execution output
    """
    # This function is deprecated - we now connect directly from the host
    # Keeping for backwards compatibility if needed
    pass


def get_database_schema(
    database_name: str,
    postgres_host: str = "localhost",
    postgres_port: str = "5432",
    postgres_user: str = "root",
    postgres_password: str = "123123",
) -> ToolResult:
    """
    Get database schema in a concise, context-optimized markdown format.

    Args:
        database_name: Name of the database to describe
        postgres_host: PostgreSQL host
        postgres_port: PostgreSQL port
        postgres_user: PostgreSQL username
        postgres_password: PostgreSQL password

    Returns:
        ToolResult with schema in markdown format
    """
    start_time = datetime.now()

    try:
        # Create connection string
        db_uri = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{database_name}"
        engine = create_engine(db_uri)
        inspector = inspect(engine)

        schema_data = {}

        # Get all tables
        tables = inspector.get_table_names()

        for table in tables:
            columns = inspector.get_columns(table)
            pk = inspector.get_pk_constraint(table)
            fks = inspector.get_foreign_keys(table)
            indexes = inspector.get_indexes(table)

            table_info = {
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col["nullable"],
                        "primary_key": col["name"]
                        in (pk.get("constrained_columns", [])),
                    }
                    for col in columns
                ],
                "primary_key": pk.get("constrained_columns", []),
                "foreign_keys": [
                    {
                        "columns": fk.get("constrained_columns", []),
                        "references": fk.get("referred_table"),
                        "ref_columns": fk.get("referred_columns", []),
                    }
                    for fk in fks
                ],
                "indexes": [
                    {
                        "name": idx["name"],
                        "columns": idx["column_names"],
                        "unique": idx.get("unique", False),
                    }
                    for idx in indexes
                ],
            }
            schema_data[table] = table_info

        # Format as markdown
        markdown = "# Database Schema\n\n"

        for table_name, table_info in schema_data.items():
            markdown += f"## {table_name}\n\n"

            # Columns
            markdown += "**Columns:**\n"
            for col in table_info["columns"]:
                nullable = "NULL" if col["nullable"] else "NOT NULL"
                pk_badge = " *[PK]*" if col["primary_key"] else ""
                markdown += f"- `{col['name']}` {col['type']} {nullable}{pk_badge}\n"

            # Primary Key
            if table_info["primary_key"]:
                markdown += (
                    f"\n**Primary Key:** {', '.join(table_info['primary_key'])}\n"
                )

            # Foreign Keys
            if table_info["foreign_keys"]:
                markdown += "\n**Foreign Keys:**\n"
                for fk in table_info["foreign_keys"]:
                    cols = ", ".join(fk["columns"])
                    ref_cols = ", ".join(fk["ref_columns"])
                    markdown += f"- `{cols}` → `{fk['references']}({ref_cols})`\n"

            # Indexes
            if table_info["indexes"]:
                markdown += "\n**Indexes:**\n"
                for idx in table_info["indexes"]:
                    unique_badge = " [UNIQUE]" if idx["unique"] else ""
                    markdown += f"- `{idx['name']}` on {', '.join(idx['columns'])}{unique_badge}\n"

            markdown += "\n"

        duration = datetime.now() - start_time
        return ToolResult(
            success=True,
            data=markdown,
            duration=duration,
            source="direct",
        )

    except Exception as e:
        duration = datetime.now() - start_time
        return ToolResult(
            success=False,
            data=None,
            error=str(e),
            duration=duration,
            source="direct",
        )


def get_table_columns(
    database_name: str,
    table_name: str,
    postgres_host: str = "localhost",
    postgres_port: str = "5432",
    postgres_user: str = "root",
    postgres_password: str = "123123",
) -> ToolResult:
    """
    Fetch column information from a specific table.

    Args:
        database_name: Name of the database
        table_name: Name of the table
        postgres_host: PostgreSQL host
        postgres_port: PostgreSQL port
        postgres_user: PostgreSQL username
        postgres_password: PostgreSQL password

    Returns:
        ToolResult with list of column information
    """
    start_time = datetime.now()

    try:
        db_uri = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{database_name}"
        engine = create_engine(db_uri)
        inspector = inspect(engine)

        columns = inspector.get_columns(table_name)
        pk = inspector.get_pk_constraint(table_name).get("constrained_columns", [])

        column_list = []
        for col in columns:
            is_pk = col["name"] in pk
            column_list.append(
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "primary_key": is_pk,
                    "default": (
                        str(col.get("default", "")) if col.get("default") else None
                    ),
                }
            )

        duration = datetime.now() - start_time
        return ToolResult(
            success=True,
            data=column_list,
            duration=duration,
            source="direct",
        )

    except Exception as e:
        duration = datetime.now() - start_time
        return ToolResult(
            success=False,
            data=None,
            error=str(e),
            duration=duration,
            source="direct",
        )


def get_sample_rows(
    database_name: str,
    table_name: str,
    column_names: Optional[list[str]] = None,
    limit: int = 5,
    postgres_host: str = "localhost",
    postgres_port: str = "5432",
    postgres_user: str = "root",
    postgres_password: str = "123123",
) -> ToolResult:
    """
    Get sample rows from a table.

    Args:
        database_name: Name of the database
        table_name: Name of the table
        column_names: List of column names to fetch (None = all columns)
        limit: Number of sample rows to fetch (default: 5)
        postgres_host: PostgreSQL host
        postgres_port: PostgreSQL port
        postgres_user: PostgreSQL username
        postgres_password: PostgreSQL password

    Returns:
        ToolResult with sample rows in markdown table format
    """
    start_time = datetime.now()

    try:
        db_uri = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{database_name}"
        engine = create_engine(db_uri)

        # Build query
        if column_names:
            columns_str = ", ".join(f'"{col}"' for col in column_names)
            query_str = f"SELECT {columns_str} FROM {table_name} LIMIT {limit}"
        else:
            query_str = f"SELECT * FROM {table_name} LIMIT {limit}"

        with engine.connect() as conn:
            result = conn.execute(text(query_str))
            columns = result.keys()
            rows = result.fetchall()

        # Format as markdown table
        markdown = f"# Sample Rows from {table_name}\n\n"

        if rows:
            markdown += "| " + " | ".join(columns) + " |\n"
            markdown += "|" + "|".join(["---"] * len(columns)) + "|\n"

            for row in rows:
                values = [str(val) if val is not None else "" for val in row]
                markdown += "| " + " | ".join(values) + " |\n"
        else:
            markdown += "No rows found in table."

        duration = datetime.now() - start_time
        return ToolResult(
            success=True,
            data=markdown,
            duration=duration,
            source="direct",
        )

    except Exception as e:
        duration = datetime.now() - start_time
        return ToolResult(
            success=False,
            data=None,
            error=str(e),
            duration=duration,
            source="direct",
        )


def execute_query(
    database_name: str,
    query: str,
    postgres_host: str = "localhost",
    postgres_port: str = "5432",
    postgres_user: str = "root",
    postgres_password: str = "123123",
) -> ToolResult:
    """
    Execute a SQL SELECT query on the database.

    Args:
        database_name: Name of the database
        query: SQL SELECT query to execute
        postgres_host: PostgreSQL host
        postgres_port: PostgreSQL port
        postgres_user: PostgreSQL username
        postgres_password: PostgreSQL password

    Returns:
        ToolResult with query results in markdown table format
    """
    start_time = datetime.now()

    try:
        # Validate query
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        db_uri = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{database_name}"
        engine = create_engine(db_uri)

        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = result.keys()
            rows = result.fetchall()

        # Format as markdown table
        markdown = "# Query Results\n\n"

        if rows:
            markdown += "| " + " | ".join(columns) + " |\n"
            markdown += "|" + "|".join(["---"] * len(columns)) + "|\n"

            for row in rows:
                values = [str(val) if val is not None else "" for val in row]
                markdown += "| " + " | ".join(values) + " |\n"
        else:
            markdown += "No results returned."

        duration = datetime.now() - start_time
        return ToolResult(
            success=True,
            data=markdown,
            duration=duration,
            source="direct",
        )

    except Exception as e:
        duration = datetime.now() - start_time
        return ToolResult(
            success=False,
            data=None,
            error=str(e),
            duration=duration,
            source="direct",
        )


if __name__ == "__main__":
    # Example usage
    print("Database Tools Module")
    print("=" * 50)

    # Test get_database_schema
    print("\n1. Getting database schema...")
    schema_result = get_database_schema("postgres")
    print(f"   Success: {schema_result.success}")
    if schema_result.success:
        print(schema_result.to_markdown())

    # Test get_table_columns
    print("\n2. Getting table columns...")
    columns_result = get_table_columns("postgres", "pg_catalog.pg_tables")
    print(f"   Success: {columns_result.success}")
    if columns_result.success:
        print(columns_result.to_markdown())

    # Test get_sample_rows
    print("\n3. Getting sample rows...")
    rows_result = get_sample_rows("postgres", "pg_catalog.pg_tables", limit=3)
    print(f"   Success: {rows_result.success}")
    if rows_result.success:
        print(rows_result.to_markdown())
