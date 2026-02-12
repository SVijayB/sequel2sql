"""
Sequel2SQL Agent

A Pydantic AI agent using LLMs for SQL query assistance.
Deterministic orchestration pipeline that validates SQL, fixes syntax
errors, retrieves few-shot examples, and calls the main agent.
"""
import sys
import os
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
from src.query_intent_vectorDB.search_similar_query import (
	find_similar_examples,
	FewShotExample,
)
from src.database import AgentDeps, Database, DBQueryResponse
from src.database import execute_sql as _execute_sql

load_dotenv()


logfire.configure()
logfire.instrument_pydantic_ai()

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
	'google-gla:gemini-3-flash-preview',
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

webui_agent.tool(name="execute_sql_query")(execute_sql_query)
webui_agent.tool_plain(name="validate_query")(validate_query)
webui_agent.tool_plain(name="find_similar_examples")(similar_examples_tool)


# =============================================================================
# Orchestration Pipeline
# =============================================================================

async def run_pipeline(
	input: BenchmarkInputForAgent,
) -> AgentPipelineResult:
	"""Deterministic pipeline: validate → fix syntax once → retrieve examples → LLM."""

	current_sql = input.issue_sql

	# Step 1: Validate syntax
	errors = validate_sql(
		current_sql, db_name=input.db_id, dialect=input.dialect
	)

	# Step 2: Attempt syntax fix once (don't fail if it doesn't work)
	if errors:
		error_details = "\n".join(
			f"- [{e.tag}] {e.message}" for e in errors
		)
		fix_prompt = (
			f"Fix the syntax errors in this PostgreSQL query.\n\n"
			f"SQL:\n{current_sql}\n\n"
			f"Errors:\n{error_details}"
		)

		fix_result = await syntax_fixer_agent.run(fix_prompt)
		current_sql = fix_result.output.strip()

		# Re-validate after fix
		errors = validate_sql(
			current_sql, db_name=input.db_id, #dialect=input.dialect # need to match this to 'postgres'
		)

		# Print error summary if still has errors, but continue anyway
		if errors:
			error_summary = "; ".join(e.message for e in errors)
			print(f"Note: Syntax fixer couldn't resolve all errors: {error_summary}")
			print("Continuing to main agent with RAG context...")

	# Step 3: Retrieve few-shot examples
	examples = find_similar_examples(input.query)

	examples_text = "\n\n".join(
		f"Example {i + 1}:\n"
		f"  Intent: {ex.intent}\n"
		f"  SQL: {ex.sql}"
		for i, ex in enumerate(examples)
	)

	# Step 4: Final LLM call
	user_prompt = (
		f"Fix and optimize the following PostgreSQL query.\n\n"
		f"Intent: {input.query}\n\n"
		f"SQL Query:\n{current_sql}\n\n"
		f"Similar examples for reference:\n{examples_text}"
	)

	result = await agent.run(user_prompt)

	return AgentPipelineResult(
		corrected_sql=result.output.corrected_sql,
		explanation=result.output.explanation,
		success=True,
	)


if __name__ == "__main__":
	import asyncio
	import json
	from pathlib import Path

	test_file = Path(__file__).parent / "test_cases.json"
	with open(test_file) as f:
		tc = json.load(f)

	test_input = BenchmarkInputForAgent(
		issue_sql=tc["issue_sql"][0],
		db_id=tc["db_id"],
		query=tc["query"],
		dialect=tc["dialect"].lower(),
	)

	result = asyncio.run(run_pipeline(test_input))
	print(f"Success: {result.success}")
	print(f"Corrected SQL: {result.corrected_sql}")
	print(f"Explanation: {result.explanation}")
