# -*- coding: utf-8 -*-
"""Pydantic models for validation API. See README.md."""

from typing import Any, Dict, List, Literal, Optional, Tuple, get_args
import json
import os
import sys

from pydantic import BaseModel, Field


def _load_error_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data", "error_data.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {data_path} not found.", file=sys.stderr)
        return {"taxonomy_categories": {}}


def _load_complexity_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data", "complexity_config.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {data_path} not found.", file=sys.stderr)
        return {}

_ERROR_DATA = _load_error_data()
_COMPLEXITY_CONFIG = _load_complexity_config()
_CATEGORIES = _ERROR_DATA.get("taxonomy_categories", {})

# -----------------------------------------------------------------------------
# Error Tags (loaded from JSON)
SyntaxTag = str
SemanticTag = str
LogicalTag = str
JoinRelatedTag = str
AggregationTag = str
FilterTag = str
ValueTag = str
SubqueryTag = str
SetOperationTag = str
StructuralTag = str

# Unified TagName
TagName = str

# All tag strings the validator can return
_all_tags_list = []
for tags in _CATEGORIES.values():
    _all_tags_list.extend(tags)
ALL_TAG_NAMES: Tuple[str, ...] = tuple(sorted(_all_tags_list))



_CLAUSES = _COMPLEXITY_CONFIG.get("clause_complexity_categories", {})

# -----------------------------------------------------------------------------
# Clause set
# -----------------------------------------------------------------------------

StandardClause = str
JoinClause = str
SetClause = str
AdvancedClause = str

# Unified ClauseName
ClauseName = str

_all_clauses_list = []
for clauses in _CLAUSES.values():
    _all_clauses_list.extend(clauses)
ALL_CLAUSE_NAMES: Tuple[str, ...] = tuple(sorted(_all_clauses_list))


class ValidationInput(BaseModel):
    """Input: query, optional schema, optional ast."""

    query: str = Field(..., description="SQL query string to validate")
    table_schema: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None,
        alias="schema",
        description="Optional schema as {table_name: {column_name: type}}",
    )
    ast: Optional[Any] = Field(
        default=None,
        description="Optional pre-parsed AST (e.g. sqlglot Expression); if omitted, parsed from query",
    )

    model_config = {"extra": "forbid", "populate_by_name": True}


# -----------------------------------------------------------------------------
# Output: what the validation pipeline returns
# -----------------------------------------------------------------------------

class ValidationErrorOut(BaseModel):
    """A single validation error with a tag from the canonical tag set."""

    tag: TagName = Field(..., description="Canonical error tag")
    message: str = Field(..., description="Human-readable error message")
    location: Optional[int] = Field(default=None, description="Character position in SQL if known")
    context: Optional[str] = Field(default=None, description="Additional context or raw message")
    error_code: Optional[str] = Field(default=None, description="PostgreSQL SQLSTATE if known")
    taxonomy_category: Optional[str] = Field(default=None, description="Taxonomy category (e.g. syntax, semantic)")
    affected_clauses: List[ClauseName] = Field(default_factory=list, description="Affected SQL clauses (canonical set)")

    model_config = {"extra": "forbid"}


class QueryMetadataOut(BaseModel):
    """Query structure: complexity, signature, clauses, counts."""

    complexity_score: float = Field(..., description="Normalized complexity score (0-1)")
    pattern_signature: str = Field(..., description="Structural fingerprint (e.g. SELECT-WHERE-JOIN)")
    clauses_present: List[ClauseName] = Field(default_factory=list, description="Clauses present in the query (canonical set)")
    num_joins: int = Field(default=0, description="Number of JOINs")
    num_subqueries: int = Field(default=0, description="Number of subqueries")
    num_ctes: int = Field(default=0, description="Number of CTEs")
    num_aggregations: int = Field(default=0, description="Number of aggregations")

    model_config = {"extra": "forbid"}


class ValidationResultOut(BaseModel):
    """Result of SQL validation: valid flag, errors (with tags from the canonical set), sql, optional metadata."""

    valid: bool = Field(..., description="True if the query passed validation")
    errors: List[ValidationErrorOut] = Field(default_factory=list, description="Validation errors if invalid")
    sql: str = Field(default="", description="Original SQL that was validated")
    tags: List[TagName] = Field(default_factory=list, description="Error tags (same order as errors)")
    query_metadata: Optional[QueryMetadataOut] = Field(default=None, description="Structure metadata if analyzed")

    model_config = {"extra": "forbid"}

    @classmethod
    def from_validation_result(cls, result: Any) -> "ValidationResultOut":
        """From dataclass ValidationResult (ast_parsers.errors)."""
        from ast_parsers.errors import ValidationResult as VR

        if not isinstance(result, VR):
            raise TypeError("Expected ValidationResult")
        errors_out = [
            ValidationErrorOut(
                tag=e.tag,  # type: ignore[arg-type]
                message=e.message,
                location=e.location,
                context=e.context,
                error_code=e.error_code,
                taxonomy_category=e.taxonomy_category,
                affected_clauses=e.affected_clauses or [],
            )
            for e in result.errors
        ]
        metadata_out = None
        if result.query_metadata is not None:
            m = result.query_metadata
            metadata_out = QueryMetadataOut(
                complexity_score=m.complexity_score,
                pattern_signature=m.pattern_signature,
                clauses_present=m.clauses_present or [],
                num_joins=m.num_joins,
                num_subqueries=m.num_subqueries,
                num_ctes=m.num_ctes,
                num_aggregations=m.num_aggregations,
            )
        return cls(
            valid=result.valid,
            errors=errors_out,
            sql=result.sql or "",
            tags=result.tags or [],
            query_metadata=metadata_out,
        )
