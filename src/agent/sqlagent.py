"""
Sequel2SQL Agent

A Pydantic AI agent using LLMs for SQL query assistance.
Deterministic orchestration pipeline that validates SQL, fixes syntax
errors, retrieves few-shot examples, and calls the main agent.
"""

import os
import sys
from pathlib import Path

# Add both project root and src/ to sys.path for imports to work
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from typing import List, Optional

import logfire
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from src.agent.prompts.benchmark_prompt import BENCHMARK_PROMPT
from src.agent.prompts.webui_prompt import WEBUI_PROMPT
from src.ast_parsers.llm_tool import validate_sql
from src.ast_parsers.models import ValidationErrorOut
from src.database import AgentDeps, Database, DBQueryResponse
from src.database import execute_sql as _execute_sql
from src.query_intent_vectordb.search_similar_query import (
    FewShotExample,
    find_similar_examples,
)

load_dotenv()


# Logfire configuration (optional - uncomment if you have logfire auth set up)
logfire.configure()
logfire.instrument_pydantic_ai()

# =============================================================================
# Helper Functions
# =============================================================================


def get_database_deps(
    database_name: str,
    host: str = "localhost",
    port: int = 5433,
    user: str = "root",
    password: str = "123123",
    max_return_values: int = 200,
) -> AgentDeps:
    """Create AgentDeps with a Database instance for the specified database.

    Args:
            database_name: Name of the PostgreSQL database to connect to
            host: PostgreSQL host (default: localhost)
            port: PostgreSQL port (default: 5433)
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


def _extract_table_names(sql: str, dialect: str) -> set[str]:
    """
    Best-effort extraction of table names from SQL query using sqlglot.

    Returns empty set if parsing fails.
    """
    try:
        import sqlglot
        from sqlglot.optimizer.scope import build_scope

        # Parse SQL
        parsed = sqlglot.parse_one(sql, dialect=dialect)

        # Extract table names using scope analysis
        tables = set()
        for scope in build_scope(parsed).traverse():
            for table in scope.tables:
                tables.add(table)

        return tables
    except Exception:
        # If parsing fails, return empty set
        return set()


# =============================================================================
# Pydantic Models
# =============================================================================


class BenchmarkInputForAgent(BaseModel):
    """Unified input representing a benchmark query for the agent."""

    issue_sql: str
    db_id: str
    dialect: str = "postgres"
    query: str


class ValidateQueryToolInput(BaseModel):
    """Input for the SQL validation tool."""

    sql: str
    db_id: Optional[str] = None
    dialect: str = "postgres"


class FewShotExamplesResult(BaseModel):
    """Wrapper for few-shot examples returned by retrieval."""

    examples: List[FewShotExample]
    query_intent: str


class AgentPipelineResult(BaseModel):
    """Output of the full orchestration pipeline."""

    corrected_sql: str = ""
    explanation: str = ""
    success: bool = False


class AgentResponse(BaseModel):
    """Structured response from the main SQL fixing agent."""

    corrected_sql: str = Field(..., description="The corrected/optimized SQL query")
    explanation: str = Field(..., description="Explanation of what was fixed and why")


class SQLAnalysisContext(BaseModel):
    """Comprehensive context for SQL query fixing (webui_agent tool)."""

    # Schema information
    database_id: str
    available_tables: List[str]
    schema_description: str  # DDL-like formatted schema

    # Validation results
    has_errors: bool
    validation_errors: List[dict]  # [{tag: "SYNTAX_ERROR", message: "..."}]

    # Few-shot examples
    similar_examples: List[dict]  # [{sql: "...", intent: "...", explanation: "..."}]

    # Metadata
    query_intent: str
    dialect: str


# =============================================================================
# Agent Definition
# =============================================================================

# Default agent
agent = Agent(
    "google-gla:gemini-3-flash-preview",
    deps_type=AgentDeps,
    system_prompt=BENCHMARK_PROMPT,
)

# Web UI agen
webui_agent = Agent(
    "google-gla:gemini-3-flash-preview",
    deps_type=AgentDeps,
    system_prompt=WEBUI_PROMPT,
)

SYNTAX_FIXER_PROMPT = (
    "You are a PostgreSQL syntax fixer. "
    "Given an SQL query with syntax errors, the error details, and the "
    "database schema, return ONLY the corrected SQL query. "
    "Do not include any explanation, markdown, or commentary — "
    "just the raw SQL."
)

syntax_fixer_agent = Agent(
    "google-gla:gemini-3-flash-preview",
    system_prompt=SYNTAX_FIXER_PROMPT,
    output_type=str,
)


# =============================================================================
# Tool Definitions (kept for future use as agent tools)
# =============================================================================


@agent.tool
def execute_sql_query(ctx: RunContext[AgentDeps], sql: str) -> DBQueryResponse:
    """Execute the given SQL SELECT query on the connected database and return the result.

    Args:
        ctx: Run context containing database connection and configuration
        sql: SQL SELECT query to execute

    Returns:
        DBQueryResponse with columns, rows, and optional truncation note
    """
    return _execute_sql(ctx, sql)


@agent.tool_plain
def validate_query(input: ValidateQueryToolInput) -> List[ValidationErrorOut]:
    """
    Validate SQL query syntax and optionally check against a database schema.

    Use this tool to:
    - Check if a SQL query has valid PostgreSQL syntax
    - Detect schema errors like non-existent tables/columns (if schema provided)
    - Get metadata about query structure

    Returns validation status, any errors found, and structural metadata.
    """
    return validate_sql(
        input.sql,
        db_name=input.db_id,
        dialect=input.dialect,
    )


@agent.tool_plain
def similar_examples_tool(
    query: str,
    n_results: int = 6,
) -> FewShotExamplesResult:
    """
        Find similar SQL query examples from the training database
        using semantic search.

    Use this tool to:
    - Find examples of similar queries that were previously corrected
    - Get context for how similar errors were fixed
    - Retrieve queries with similar intent/structure

        Returns structurally diverse few-shot examples with metadata.
    """
    examples = find_similar_examples(query, n_results=n_results)
    return FewShotExamplesResult(
        examples=examples,
        query_intent=query,
    )


@agent.tool
async def analyze_and_fix_sql(
    ctx: RunContext[AgentDeps],
    issue_sql: str,
    query_intent: str,
    db_id: str,
    dialect: str = "postgres",
    include_all_tables: bool = False,
) -> SQLAnalysisContext:
    """
    Comprehensive SQL query analysis and context gathering for fixing.

    This tool orchestrates multiple analysis steps to provide complete context
    for fixing SQL queries:

    1. Schema Discovery - Get database schema (all tables or only referenced ones)
    2. Validation - Check for syntax and schema errors
    3. Semantic Search - Find similar query examples from training data

    After calling this tool, use the returned context to:
    - Understand what tables/columns are available
    - See what errors exist in the query
    - Learn from similar query examples
    - Optionally call execute_sql_query to sample rows from tables
    - Produce a corrected SQL query with explanation

    Args:
            issue_sql: The SQL query to analyze and fix
            query_intent: Natural language description of what the query should do
            db_id: Database identifier (must match ctx.deps.database.database_name)
            dialect: SQL dialect (default: postgres)
            include_all_tables: Whether to include all tables in schema (default: False)

    Returns:
            SQLAnalysisContext with schema, validation errors, and similar examples
    """

    # Step 1: Get schema information
    database = ctx.deps.database

    if include_all_tables:
        # Include all tables
        schema_description = database.describe_schema()
        available_tables = database.table_names
    else:
        # Try to extract referenced tables from the query
        # This is best-effort - if parsing fails, fall back to all tables
        try:
            referenced_tables = _extract_table_names(issue_sql, dialect)
            if referenced_tables:
                schema_description = database.describe_schema(list(referenced_tables))
                available_tables = list(referenced_tables)
            else:
                # No tables found, include all
                schema_description = database.describe_schema()
                available_tables = database.table_names
        except Exception:
            # Parsing failed, include all tables
            schema_description = database.describe_schema()
            available_tables = database.table_names

    # Step 2: Validate SQL query
    validation_errors = validate_sql(issue_sql, db_name=db_id, dialect=dialect)

    # Step 3: Get similar examples
    examples = find_similar_examples(query_intent, n_results=6)

    # Format similar examples
    similar_examples_formatted = [
        {
            "sql": ex.sql,
            "intent": ex.intent,
            "complexity_score": ex.complexity_score,
            "pattern_signature": ex.pattern_signature,
        }
        for ex in examples
    ]

    return SQLAnalysisContext(
        database_id=db_id,
        available_tables=available_tables,
        schema_description=schema_description,
        has_errors=(len(validation_errors) > 0),
        validation_errors=[
            {"tag": err.tag, "message": err.message} for err in validation_errors
        ],
        similar_examples=similar_examples_formatted,
        query_intent=query_intent,
        dialect=dialect,
    )


webui_agent.tool(name="execute_sql_query")(execute_sql_query)
webui_agent.tool_plain(name="validate_query")(validate_query)
webui_agent.tool_plain(name="find_similar_examples")(similar_examples_tool)
webui_agent.tool(name="analyze_and_fix_sql")(analyze_and_fix_sql)


# =============================================================================
# Note: Pipeline orchestration has been moved
# =============================================================================
#
# The run_pipeline() function has been moved to:
#   benchmark/agent/pipeline.py
#
# The benchmark runner has been moved to:
#   benchmark/agent/agent_benchmark.py
#
# For batch processing of SQL queries, use:
#   python -m benchmark.agent.agent_benchmark --limit 20
#
# =============================================================================
