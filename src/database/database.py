"""
Database interaction module for PostgreSQL.

Provides a clean interface for executing queries and retrieving schema information.
Based on the dbdex pattern with improvements for PostgreSQL-only usage.
"""

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import MetaData, Row, create_engine, text
from sqlalchemy.engine import Engine


class InvalidQueryError(Exception):
    """Exception raised for invalid SQL queries."""


class TableNotFoundError(Exception):
    """Exception raised for invalid table names."""


@dataclass
class QueryResult:
    """Container for SQL query and its results."""

    sql: str
    rows: list[Row[Any]]
    executed_at: datetime
    duration: timedelta | None = None
    error: Exception | None = None

    @property
    def success(self) -> bool:
        """Check if query executed successfully."""
        return self.error is None

    @property
    def row_count(self) -> int:
        """Get number of rows returned."""
        return len(self.rows)

    @property
    def columns(self) -> list[str] | None:
        """Get column names if there are results."""
        if self.rows:
            return list(self.rows[0]._fields)
        return None

    def to_markdown(self, include_details: bool = True) -> str:
        """Format query results as a markdown table.

        Args:
            include_details: Whether to include the SQL query and execution time in the output

        Returns:
            Markdown formatted string with query results
        """
        md = ""

        if include_details:
            md += f"```sql\n{self.sql}\n```\n\n"
            if self.duration:
                duration_str = f"{self.duration.total_seconds():.3f}s"
                md += f"✓ Executed in {duration_str}\n\n"

        if self.error:
            md += f"❌ Error: {str(self.error)}\n"
            return md

        if not self.rows or not self.columns:
            md += "No results"
            return md

        # Build results table
        md += "| " + " | ".join(self.columns) + " |\n"
        md += "|" + "|".join(["---"] * len(self.columns)) + "|\n"

        # Add data rows
        for row in self.rows:
            values = [str(val) if val is not None else "" for val in row]
            md += "| " + " | ".join(values) + " |\n"

        return md

    def to_csv(self) -> str:
        """Format query results as a CSV string.

        Returns:
            CSV formatted string with query results
        """
        if not self.columns:
            return ""

        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(self.columns)
        writer.writerows(self.rows)
        return buffer.getvalue()


class Database:
    """A class to interact with a PostgreSQL database using SQLAlchemy.

    This class provides a clean interface for executing queries and retrieving
    schema information. The engine and metadata are initialized once for performance.
    """

    def __init__(
        self,
        database_name: str,
        host: str = "localhost",
        port: int = 5432,
        user: str = "root",
        password: str = "123123",
    ):
        """Initialize database connection and reflect schema.

        Args:
            database_name: Name of the PostgreSQL database
            host: PostgreSQL host (default: localhost)
            port: PostgreSQL port (default: 5432)
            user: PostgreSQL username (default: root)
            password: PostgreSQL password (default: 123123)
        """
        db_uri = f"postgresql://{user}:{password}@{host}:{port}/{database_name}"
        self.engine: Engine = create_engine(db_uri)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        self.last_query: QueryResult | None = None
        self.database_name = database_name

    @property
    def dialect(self) -> str:
        """Get database dialect name."""
        return self.engine.dialect.name

    @property
    def table_names(self) -> list[str]:
        """Get list of all table names in the database."""
        return list(self.metadata.tables.keys())

    def execute_sql(self, sql_query: str) -> QueryResult:
        """Execute a SQL query and return results. Blocks DDL statements.

        Args:
            sql_query: SQL query string to execute

        Returns:
            QueryResult with execution results

        Raises:
            InvalidQueryError: If query is a DDL statement
        """
        _DDL_KEYWORDS = {"CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME", "COMMENT"}
        first_token = sql_query.strip().split()[0].upper() if sql_query.strip() else ""
        if first_token in _DDL_KEYWORDS:
            raise InvalidQueryError(f"DDL statements ({first_token}) are not allowed")

        rows = []
        error = None
        with self.engine.connect() as conn:
            start_time = datetime.now()
            try:
                sql_result = conn.execute(text(sql_query))
                if sql_result.returns_rows:
                    rows = list(sql_result)
                    if len(rows) > 100:
                        rows = rows[:100]
            except Exception as e:
                # When an error occurs, details are stored in last_query, but
                # exception is re-raised
                error = e
                raise
            finally:
                duration = datetime.now() - start_time
                result = QueryResult(
                    sql=sql_query,
                    rows=rows,
                    executed_at=start_time,
                    duration=duration,
                    error=error,
                )
                self.last_query = result

        return result

    def describe_schema(self, table_names: list[str] | None = None) -> str:
        """Get a string representation of the structure of tables in the database.

        Args:
            table_names: List of specific table names to describe (None = all tables)

        Returns:
            Human-readable text representation of table schemas

        Raises:
            TableNotFoundError: If any specified table name is invalid
        """
        from .format_schema import format_table_schema

        if table_names:
            try:
                tables = [self.metadata.tables[table] for table in table_names]
            except KeyError as e:
                raise TableNotFoundError(f"Invalid table name: {e}") from e
        else:
            tables = list(self.metadata.tables.values())

        return "\n\n".join(format_table_schema(table) for table in tables)
