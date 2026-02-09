"""
Sequel2SQL Agent

A Pydantic AI agent using LLMs for SQL query assistance.
This is the foundational agent before adding RAG and AST components.
"""

from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent

from src.agent.prompts.db_agent_prompt import DB_AGENT_PROMPT
from src.database import AgentDeps, Database, execute_sql

load_dotenv()

# Optional: Configure LogFire for monitoring and debugging
# Uncomment the lines below after running: uv run logfire auth
# import logfire
# logfire.configure()
# logfire.instrument_pydantic_ai()


# =============================================================================
# Helper Functions
# =============================================================================


def get_database_deps(
    database_name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "root",
    password: str = "123123",
    max_return_values: int = 200,
) -> AgentDeps:
    """Create AgentDeps with a Database instance for the specified database.

    Args:
            database_name: Name of the PostgreSQL database to connect to
            host: PostgreSQL host (default: localhost)
            port: PostgreSQL port (default: 5432)
            user: PostgreSQL username (default: root)
            password: PostgreSQL password (default: 123123)
            max_return_values: Maximum number of result values to return (default: 200)

    Returns:
            AgentDeps instance ready to be passed to the agent
    """
    database = Database(
        database_name=database_name,
        host=host,
        port=port,
        user=user,
        password=password,
    )
    return AgentDeps(database=database, max_return_values=max_return_values)


# =============================================================================
# Pydantic Models for validate_query tool
# =============================================================================


class ValidateQueryInput(BaseModel):
    """Input for SQL validation."""

    sql: str
    schema_def: Optional[Dict[str, Dict[str, str]]] = None
    dialect: str = "postgres"


class ValidationError(BaseModel):
    """A single validation error."""

    message: str
    error_type: str  # e.g., 'syntax_error', 'schema_hallucination_col'
    line: Optional[int] = None
    column: Optional[int] = None


class QueryMetadata(BaseModel):
    """Metadata about query structure and complexity."""

    tables: List[str] = []
    columns: List[str] = []
    complexity_score: Optional[float] = None


class ValidationResult(BaseModel):
    """Result of SQL query validation."""

    valid: bool
    errors: List[ValidationError] = []
    sql: str = ""
    query_metadata: Optional[QueryMetadata] = None
    tags: List[str] = []  # e.g., ['schema_hallucination_col']


# =============================================================================
# Pydantic Models for find_similar_examples tool
# =============================================================================


class FindSimilarInput(BaseModel):
    """Input for finding similar SQL examples."""

    intent: str
    sql_query: str
    n_results: int = 5


class SimilarExample(BaseModel):
    """A single similar example from the vector database."""

    intent: str
    sql_query: str
    difficulty: str
    complexity_score: float
    pattern_signature: str
    clauses_present: List[str]
    distance: float
    db_id: str


class SimilarExamplesResult(BaseModel):
    """Result containing list of similar examples."""

    examples: List[SimilarExample]
    query_intent: str  # The original intent searched for


# =============================================================================
# Agent Definition
# =============================================================================

agent = Agent(
    "google-gla:gemini-3-flash-preview",
    deps_type=AgentDeps,
    system_prompt=DB_AGENT_PROMPT,
    tools=[execute_sql],
)

# =============================================================================
# Tool Definitions
# =============================================================================


@agent.tool_plain
def validate_query(input: ValidateQueryInput) -> ValidationResult:
    """
    Validate SQL query syntax and optionally check against a database schema.

    Use this tool to:
    - Check if a SQL query has valid PostgreSQL syntax
    - Detect schema errors like non-existent tables/columns (if schema provided)
    - Get metadata about query structure

    Returns validation status, any errors found, and structural metadata.
    """
    raise NotImplementedError("AST validation not yet implemented")


@agent.tool_plain
def find_similar_examples(input: FindSimilarInput) -> SimilarExamplesResult:
    """
    Find similar SQL query examples from the training database using semantic search.

    Use this tool to:
    - Find examples of similar queries that were previously corrected
    - Get context for how similar errors were fixed
    - Retrieve queries with similar intent/structure

    Returns top-k similar examples with their metadata and similarity scores.
    """
    raise NotImplementedError("RAG retrieval not yet implemented")
