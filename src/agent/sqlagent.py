"""
Sequel2SQL Agent

A Pydantic AI agent using LLMs for SQL query assistance.
Deterministic orchestration pipeline that validates SQL, fixes syntax
errors, retrieves few-shot examples, and calls the main agent.
"""

import sys
from pathlib import Path
from typing import List, Optional

import logfire
import sqlglot
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.mistral import MistralModel
from sqlglot import exp

# Add both project root and src/ to sys.path for imports to work
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# noqa: E402 - Ignore import order since we need to set up sys.path first
from src.agent.prompts.benchmark_prompt import BENCHMARK_PROMPT  # noqa: E402
from src.agent.prompts.webui_prompt import WEBUI_PROMPT  # noqa: E402
from src.ast_parsers.llm_tool import validate_sql  # noqa: E402
from src.ast_parsers.models import ValidationErrorOut  # noqa: E402
from src.database import AgentDeps, Database, DBQueryResponse  # noqa: E402
from src.database import execute_sql as _execute_sql  # noqa: E402
from src.query_intent_vectordb.search_similar_query import (  # noqa: E402
    FewShotExample,
    find_similar_examples,
)
from src.skills.generic_skills import (  # noqa: E402
    get_error_taxonomy_skill as _get_taxonomy_skill,
)
from src.skills.generic_skills import (
    update_taxonomy_skill,
)

load_dotenv()

# =============================================================================
# Model Configuration
# =============================================================================

# Supported models — add new ones here
SUPPORTED_MODELS = {
    "mistral": "mistral:mistral-large-latest",
    "google": "google-gla:gemini-3-flash-preview",
}
DEFAULT_MODEL = "mistral:mistral-large-latest"


# Logfire configuration (make sure to set LOGFIRE_TOKEN in .env for logging to work)
logfire.configure(send_to_logfire="if-token-present")
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
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        tables = set()
        for table in parsed.find_all(exp.Table):
            if table.name:
                tables.add(table.name)
        return tables
    except Exception:
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


# BELOW MODELS FOR FUTURE USE ONCE WE ADD AGENT PIPELINE, NOT USED NOW

# class AgentPipelineResult(BaseModel):
#     """Output of the full orchestration pipeline."""

#     corrected_sql: str = ""
#     explanation: str = ""
#     success: bool = False


# class AgentResponse(BaseModel):
#     """Structured response from the main SQL fixing agent."""

#     corrected_sql: str = Field(..., description="The corrected/optimized SQL query")
#     explanation: str = Field(..., description="Explanation of what was fixed and why")


class SchemaDescription(BaseModel):
    """Database schema information returned by describe_database_schema tool."""

    database_id: str
    available_tables: list[str]
    schema_description: str


class SQLAnalysisContext(BaseModel):
    """Comprehensive context for SQL query fixing (webui_agent tool)."""

    # Schema information
    database_id: str
    available_tables: List[str]
    schema_description: str  # DDL-like formatted schema

    # Validation results
    has_errors: bool
    # Each dict: {tag, message, taxonomy_category}
    validation_errors: List[dict]

    # Few-shot examples
    similar_examples: List[dict]  # [{sql: "...", intent: "...", explanation: "..."}]

    # Taxonomy skill guidance (populated when errors have a known category)
    taxonomy_skill_guidance: Optional[str] = None

    # Metadata
    query_intent: str
    dialect: str


# =============================================================================
# Agent Definition
# =============================================================================

# Default agent
agent = Agent(
    DEFAULT_MODEL,
    deps_type=AgentDeps,
    system_prompt=BENCHMARK_PROMPT,
)

# Web UI agent
webui_agent = Agent(
    DEFAULT_MODEL,
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
    DEFAULT_MODEL,
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
def analyze_and_fix_sql(
    ctx: RunContext[AgentDeps],
    issue_sql: str,
    query_intent: str,
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
            include_all_tables: Whether to include all tables in schema (default: False)

    Returns:
            SQLAnalysisContext with schema, validation errors, and similar examples
    """

    # Derive db_id and dialect from deps (PostgreSQL-only project)
    database = ctx.deps.database
    db_id = database.database_name
    dialect = "postgres"

    if include_all_tables:
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
                schema_description = database.describe_schema()
                available_tables = database.table_names
        except Exception:
            schema_description = database.describe_schema()
            available_tables = database.table_names

    # Step 2: Validate SQL query
    validation_errors = validate_sql(issue_sql, db_name=db_id, dialect=dialect)

    # Step 3: Get similar examples
    examples = find_similar_examples(query_intent, n_results=6)

    similar_examples_formatted = [
        {
            "sql": ex.sql,
            "intent": ex.intent,
            "complexity_score": ex.complexity_score,
            "pattern_signature": ex.pattern_signature,
        }
        for ex in examples
    ]

    # Step 4: Look up taxonomy skill guidance for the first categorised error
    validation_errors_formatted = [
        {
            "tag": err.tag,
            "message": err.message,
            "taxonomy_category": err.taxonomy_category,
        }
        for err in validation_errors
    ]

    taxonomy_skill_guidance: Optional[str] = None
    for err in validation_errors:
        if err.taxonomy_category:
            guidance = _get_taxonomy_skill(err.taxonomy_category)
            # Only use it if a real skill file was found
            if not guidance.startswith("No skill file") and not guidance.startswith(
                "Skill file"
            ):
                taxonomy_skill_guidance = guidance
            break

    return SQLAnalysisContext(
        database_id=db_id,
        available_tables=available_tables,
        schema_description=schema_description,
        has_errors=(len(validation_errors) > 0),
        validation_errors=validation_errors_formatted,
        similar_examples=similar_examples_formatted,
        taxonomy_skill_guidance=taxonomy_skill_guidance,
        query_intent=query_intent,
        dialect=dialect,
    )


@agent.tool
def describe_database_schema(
    ctx: RunContext[AgentDeps],
    table_names: list[str] | None = None,
) -> SchemaDescription:
    """Get the database schema description. Use this to discover
    available tables and their columns, types, and constraints.

    Call with no arguments to list all tables and their full schemas.
    Call with specific table_names to get schema for only those tables.

    Args:
        ctx: Run context containing database connection
        table_names: Optional list of specific table names to describe

    Returns:
        SchemaDescription with table list and DDL-like schema text
    """
    database = ctx.deps.database
    return SchemaDescription(
        database_id=database.database_name,
        available_tables=database.table_names,
        schema_description=database.describe_schema(table_names),
    )


@agent.tool_plain
def get_error_taxonomy_skill(error_category: str) -> str:
    """
    Look up best-practice approaches for fixing a SQL error of
    the given taxonomy category.

    Call this BEFORE attempting to fix any categorized error.
    Pass the taxonomy_category from a ValidationErrorOut
    (e.g. "join_related", "syntax", "aggregation", "semantic").

    Returns a markdown guide with core approaches and any
    previously learned examples from confirmed past fixes.
    """
    return _get_taxonomy_skill(error_category)


@agent.tool_plain
def record_taxonomy_fix(
    category: str,
    original_sql: str,
    fixed_sql: str,
    approach_description: str,
) -> str:
    """
    Record a confirmed successful SQL fix for future reference.

    Call this ONLY after the user has confirmed the fix is correct.
    Do not call it speculatively or before user confirmation.

    Args:
            category: taxonomy_category from the ValidationErrorOut
                      (e.g. "join_related", "syntax", "aggregation").
            original_sql: The broken SQL query.
            fixed_sql: The corrected SQL query.
            approach_description: One sentence describing what was fixed.

    Returns:
            "recorded" if saved successfully, "skipped" if category
            unknown or file missing.
    """
    ok = update_taxonomy_skill(category, original_sql, fixed_sql, approach_description)
    return "recorded" if ok else "skipped"


webui_agent.tool(name="execute_sql_query")(execute_sql_query)
webui_agent.tool_plain(name="validate_query")(validate_query)
webui_agent.tool_plain(name="find_similar_examples")(similar_examples_tool)
webui_agent.tool(name="analyze_and_fix_sql")(analyze_and_fix_sql)
webui_agent.tool(name="describe_database_schema")(describe_database_schema)
webui_agent.tool_plain(name="get_error_taxonomy_skill")(get_error_taxonomy_skill)
webui_agent.tool_plain(name="record_taxonomy_fix")(record_taxonomy_fix)


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
