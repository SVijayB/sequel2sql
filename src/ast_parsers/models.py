# -*- coding: utf-8 -*-
"""Pydantic models for validation API: input (query, optional schema/ast) and output (result + tag set)."""

from typing import Any, Dict, List, Literal, Optional, get_args

from pydantic import BaseModel, Field


TagName = Literal[
    "syntax_error",
    "syntax_unbalanced_tokens",
    "syntax_trailing_delimiter",
    "syntax_keyword_misuse",
    "syntax_unterminated_string",
    "syntax_invalid_token",
    "syntax_unsupported_dialect",
    "syntax_invalid_name",
    "syntax_invalid_column_definition",
    "schema_hallucination_table",
    "schema_hallucination_col",
    "schema_ambiguous_col",
    "schema_type_mismatch",
    "schema_unknown_error",
    "schema_duplicate_object",
    "schema_undefined_function",
    "schema_datatype_mismatch",
    "schema_incorrect_foreign_key",
    # Logical
    "logical_grouping_error",
    "logical_aggregation_error",
    "logical_windowing_error",
    "logical_integrity_violation",
    "logical_foreign_key_violation",
    "logical_unique_violation",
    "logical_check_violation",
    "join_missing_join",
    "join_wrong_join_type",
    "join_extra_table",
    "join_condition_error",
    # Aggregation
    "aggregation_missing_groupby",
    "aggregation_misuse_having",
    "aggregation_error",
    "filter_incorrect_where_column",
    "filter_type_mismatch_where",
    "filter_missing_where",
    # Value
    "value_hardcoded_value",
    "value_format_mismatch",
    "subquery_unused_subquery",
    "subquery_incorrect_correlation",
    "subquery_error",
    # Set operations
    "set_union_error",
    "set_intersection_error",
    "set_except_error",
    "structural_missing_orderby",
    "structural_missing_limit",
    "structural_error",
]

# All tag strings the validator can return (for validation, docs, serialization)
ALL_TAG_NAMES: tuple[str, ...] = get_args(TagName)


# -----------------------------------------------------------------------------
# Clause set: all clause names we detect and return (clauses_present, affected_clauses)
# -----------------------------------------------------------------------------

ClauseName = Literal[
    "SELECT",
    "FROM",
    "WHERE",
    "JOIN",
    "JOIN_INNER",
    "JOIN_LEFT",
    "JOIN_RIGHT",
    "JOIN_FULL",
    "JOIN_CROSS",
    "GROUP",
    "ORDER",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "UNION",
    "INTERSECT",
    "EXCEPT",
    "CTE",
    "WITH",
    "DISTINCT",
    "DISTINCT_ON",
    "WINDOW",
    "PARTITION",
    "FILTER",
    "LATERAL",
    "VALUES",
    "QUALIFY",
    "TABLESAMPLE",
    "LOCKING",
    "SUBQUERY",
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "RETURNING",
]

ALL_CLAUSE_NAMES: tuple[str, ...] = get_args(ClauseName)


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

    complexity_score: int = Field(..., description="Weighted complexity score")
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
