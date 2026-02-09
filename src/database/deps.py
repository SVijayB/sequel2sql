"""
Dependency injection pattern for Pydantic AI agents.

Provides AgentDeps dataclass to pass Database instance and configuration
to agent tools in a clean, testable way.
"""

from dataclasses import dataclass

from .database import Database


@dataclass
class AgentDeps:
    """Dependencies for SQL agent tools.

    Attributes:
        database: Database instance for executing queries
        max_return_values: Maximum number of values (rows × columns) to return to the LLM
    """

    database: Database
    max_return_values: int = 200
