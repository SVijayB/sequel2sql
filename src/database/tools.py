"""
Pydantic AI tool functions for database operations.

Provides tools that can be registered with a Pydantic AI agent to enable
SQL query execution and result display.
"""

from typing import Any

from pydantic import BaseModel
from pydantic_ai import ModelRetry, RunContext

from .database import InvalidQueryError
from .deps import AgentDeps


class DBQueryResponse(BaseModel):
    """Result of a database query execution.

    Attributes:
        columns: List of column names in the result set
        rows: List of rows, where each row is a list of values
        note: Optional note about the query (e.g., truncation message)
    """

    columns: list[str] | None = None
    rows: list[list[Any]] | None = None
    note: str | None = None


def execute_sql(ctx: RunContext[AgentDeps], sql: str) -> DBQueryResponse:
    """Execute the given SQL query and return the result.

    This tool executes a SELECT query on the database and returns structured
    results. The results may be truncated if they contain lots of data based
    on the max_return_values configuration.

    Args:
        ctx: Run context containing AgentDeps (database, max_return_values)
        sql: SQL SELECT query to execute

    Returns:
        DBQueryResponse with columns, rows, and optional truncation note

    Raises:
        ModelRetry: If the query is not a SELECT statement (guides agent to retry)
    """
    _SYSTEM_CATALOGS = ("information_schema", "pg_catalog", "pg_toast")
    sql_lower = sql.lower()
    if any(catalog in sql_lower for catalog in _SYSTEM_CATALOGS):
        raise ModelRetry(
            "System catalog tables (information_schema, pg_catalog) are not "
            "accessible. Use the describe_database_schema tool instead to "
            "discover tables and columns."
        )

    try:
        result = ctx.deps.database.execute_sql(sql)
    except InvalidQueryError as e:
        raise ModelRetry(str(e)) from e

    if not result.rows:
        return DBQueryResponse(note="No results")
    else:
        assert result.columns is not None
        # Calculate number of rows to return based on max_return_values
        # Formula: allow at least 5 rows, then distribute max_return_values across columns
        max_return_rows = 5 + ctx.deps.max_return_values // len(result.columns)
        rows = [list(row) for row in result.rows[:max_return_rows]]
        note = None
        if len(result.rows) > max_return_rows:
            note = f"Query returned {len(result.rows)} rows, showing first {max_return_rows} only"
        return DBQueryResponse(columns=result.columns, rows=rows, note=note)
