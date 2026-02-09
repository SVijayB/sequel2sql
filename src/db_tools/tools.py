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
        """Format tool result as markdown for schema, JSON for other data.

        Returns:
            Markdown formatted output for schema, JSON for other data
        """
        if not self.success:
            return f"❌ Error: {self.error}"

        if isinstance(self.data, str):
            return self.data

        # For dict/list data, format as JSON
        if isinstance(self.data, (dict, list)):
            return json.dumps(self.data, indent=2, default=str)

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
    include_tables: bool = True,
) -> ToolResult:
    """
    Get database schema as a minimal join-graph JSON, returned as markdown.

    Intended for LLM SQL fixing with reduced context:
      - DB meta (dialect, quoting)
      - table names (optional)
      - FK edges (join graph)
    """
    start_time = datetime.now()

    try:
        db_uri = (
            f"postgresql://{postgres_user}:{postgres_password}"
            f"@{postgres_host}:{postgres_port}/{database_name}"
        )
        engine = create_engine(db_uri)
        inspector = inspect(engine)

        # In SQLAlchemy for Postgres, we can assume:
        # - dialect: postgresql
        # - identifier quoting: double quotes for delimited identifiers
        # (If you support multiple backends later, make this dynamic.)
        meta = {
            "db": database_name,
            "dialect": engine.dialect.name,  # "postgresql"
            "identifier_quote": '"',
        }

        # Schemas: useful when db has multiple namespaces.
        try:
            schemas = inspector.get_schema_names()
        except Exception:
            schemas = None

        if schemas:
            # Filter out noisy internal schemas if you want (optional):
            # schemas = [s for s in schemas if s not in ("pg_catalog", "information_schema")]
            meta["schemas"] = schemas

        joins = []
        tables_out = []

        # Prefer schema-qualified table enumeration if schemas exist
        if schemas:
            for schema in schemas:
                try:
                    table_names = inspector.get_table_names(schema=schema)
                except Exception:
                    continue
                for table in table_names:
                    fq_table = f"{schema}.{table}"
                    if include_tables:
                        tables_out.append(fq_table)

                    # FK edges (the key output)
                    for fk in inspector.get_foreign_keys(table, schema=schema):
                        child_cols = fk.get("constrained_columns") or []
                        parent_schema = fk.get("referred_schema") or schema
                        parent_table = fk.get("referred_table")
                        parent_cols = fk.get("referred_columns") or []
                        if not parent_table:
                            continue

                        joins.append(
                            {
                                "from": {"table": fq_table, "columns": child_cols},
                                "to": {
                                    "table": f"{parent_schema}.{parent_table}",
                                    "columns": parent_cols,
                                },
                                "constraint": fk.get("name"),
                            }
                        )
        else:
            # No schema awareness
            table_names = inspector.get_table_names()
            for table in table_names:
                if include_tables:
                    tables_out.append(table)
                for fk in inspector.get_foreign_keys(table):
                    child_cols = fk.get("constrained_columns") or []
                    parent_table = fk.get("referred_table")
                    parent_cols = fk.get("referred_columns") or []
                    if not parent_table:
                        continue
                    joins.append(
                        {
                            "from": {"table": table, "columns": child_cols},
                            "to": {"table": parent_table, "columns": parent_cols},
                            "constraint": fk.get("name"),
                        }
                    )

        # Deduplicate joins (some DBs can return duplicates depending on reflection)
        seen = set()
        uniq = []
        for j in joins:
            key = (
                j["from"]["table"],
                tuple(j["from"]["columns"]),
                j["to"]["table"],
                tuple(j["to"]["columns"]),
                j.get("constraint"),
            )
            if key not in seen:
                seen.add(key)
                uniq.append(j)
        joins = uniq

        payload = {
            "meta": meta,
            "tables": tables_out if include_tables else [],
            "joins": joins,
        }

        markdown = "```json\n" + json.dumps(payload, indent=2, default=str) + "\n```"

        duration = datetime.now() - start_time
        return ToolResult(
            success=True, data=markdown, duration=duration, source="direct"
        )

    except Exception as e:
        duration = datetime.now() - start_time
        return ToolResult(
            success=False, data=None, error=str(e), duration=duration, source="direct"
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
        ToolResult with sample rows in JSON format
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

        # Format as JSON list of objects
        json_data = []
        if rows:
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                json_data.append(row_dict)

        duration = datetime.now() - start_time
        return ToolResult(
            success=True,
            data=json_data,
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
        ToolResult with query results in JSON format
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

        # Format as JSON list of objects
        json_data = []
        if rows:
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                json_data.append(row_dict)

        duration = datetime.now() - start_time
        return ToolResult(
            success=True,
            data=json_data,
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
