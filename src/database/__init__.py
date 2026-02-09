"""
Database module for PostgreSQL interaction.

Provides a clean interface for SQL query execution, schema retrieval,
and integration with Pydantic AI agents.

Example usage:
    >>> from database import Database, AgentDeps, execute_sql
    >>> db = Database("my_database")
    >>> deps = AgentDeps(database=db, max_return_values=200)
    >>> # Use deps with Pydantic AI agent
"""

from .database import (
    Database,
    InvalidQueryError,
    QueryResult,
    TableNotFoundError,
)
from .deps import AgentDeps
from .tools import DBQueryResponse, execute_sql

__all__ = [
    "Database",
    "QueryResult",
    "InvalidQueryError",
    "TableNotFoundError",
    "AgentDeps",
    "DBQueryResponse",
    "execute_sql",
]
