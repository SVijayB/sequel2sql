"""
Sequel2SQL Agent

A Pydantic AI agent using LLMs for SQL query assistance.
This is the foundational agent before adding RAG and AST components.
"""

from typing import Optional, Dict, List
from pydantic import BaseModel
from pydantic_ai import Agent
from dotenv import load_dotenv

load_dotenv()

# Optional: Configure LogFire for monitoring and debugging
# Uncomment the lines below after running: uv run logfire auth
# import logfire
# logfire.configure()
# logfire.instrument_pydantic_ai()


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
	'google-gla:gemini-3-flash-preview',
	system_prompt=(
		'You are a SQL assistant specialized in PostgreSQL. '
		'You help users write, understand, debug, and optimize PostgreSQL queries. '
		'Provide clear explanations and correct SQL syntax. '
		'When fixing errors, explain what was wrong and why your solution works.'
	)
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
