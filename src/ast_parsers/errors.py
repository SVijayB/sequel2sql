# -*- coding: utf-8 -*-
"""Error types and validation result classes for SQL query validation."""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict


class SyntaxErrorTags:
    """Static analysis (syntax) error tags."""
    SYNTAX_ERROR = "syntax_error"
    UNBALANCED_TOKENS = "syntax_unbalanced_tokens"
    TRAILING_DELIMITER = "syntax_trailing_delimiter"
    KEYWORD_MISUSE = "syntax_keyword_misuse"
    UNTERMINATED_STRING = "syntax_unterminated_string"


class SchemaErrorTags:
    """Semantic (schema) error tags."""
    HALLUCINATION_TABLE = "schema_hallucination_table"
    HALLUCINATION_COLUMN = "schema_hallucination_col"
    AMBIGUOUS_COLUMN = "schema_ambiguous_col"
    TYPE_MISMATCH = "schema_type_mismatch"
    UNKNOWN_ERROR = "schema_unknown_error"
    DUPLICATE_OBJECT = "schema_duplicate_object"
    UNDEFINED_FUNCTION = "schema_undefined_function"
    DATATYPE_MISMATCH = "schema_datatype_mismatch"


class LogicalErrorTags:
    """Logical error tags (grouping, integrity, etc.)."""
    GROUPING_ERROR = "logical_grouping_error"
    AGGREGATION_ERROR = "logical_aggregation_error"
    WINDOWING_ERROR = "logical_windowing_error"
    INTEGRITY_VIOLATION = "logical_integrity_violation"
    FOREIGN_KEY_VIOLATION = "logical_foreign_key_violation"
    UNIQUE_VIOLATION = "logical_unique_violation"
    CHECK_VIOLATION = "logical_check_violation"


class JoinErrorTags:
    """Join-related error tags."""
    MISSING_JOIN = "join_missing_join"
    WRONG_JOIN_TYPE = "join_wrong_join_type"
    EXTRA_TABLE = "join_extra_table"
    JOIN_CONDITION_ERROR = "join_condition_error"


class AggregationErrorTags:
    """Aggregation-related error tags."""
    MISSING_GROUPBY = "aggregation_missing_groupby"
    MISUSE_HAVING = "aggregation_misuse_having"
    AGGREGATION_ERROR = "aggregation_error"


class FilterErrorTags:
    """Filter/WHERE error tags."""
    INCORRECT_WHERE_COLUMN = "filter_incorrect_where_column"
    TYPE_MISMATCH_WHERE = "filter_type_mismatch_where"
    MISSING_WHERE = "filter_missing_where"


class SubqueryErrorTags:
    """Subquery-related error tags."""
    UNUSED_SUBQUERY = "subquery_unused_subquery"
    INCORRECT_CORRELATION = "subquery_incorrect_correlation"
    SUBQUERY_ERROR = "subquery_error"


class SetOperationErrorTags:
    """Set operation error tags (UNION, INTERSECT, EXCEPT)."""
    UNION_ERROR = "set_union_error"
    INTERSECTION_ERROR = "set_intersection_error"
    EXCEPT_ERROR = "set_except_error"


class StructuralErrorTags:
    """Structural query error tags."""
    MISSING_ORDERBY = "structural_missing_orderby"
    MISSING_LIMIT = "structural_missing_limit"
    STRUCTURAL_ERROR = "structural_error"


# Provenance: pg_diag = PostgreSQL err.diag.* (NOT a DB cursor or editor).
SOURCE_PG_DIAG_COLUMN_NAME = "pg_diag.column_name"
SOURCE_PG_DIAG_TABLE_NAME = "pg_diag.table_name"
SOURCE_PG_DIAG_CONSTRAINT_NAME = "pg_diag.constraint_name"
SOURCE_PG_DIAG_DATATYPE_NAME = "pg_diag.datatype_name"
SOURCE_PG_DIAG_SCHEMA_NAME = "pg_diag.schema_name"
SOURCE_PG_DIAG_POSITION = "pg_diag.position"
SOURCE_SQLSTATE = "sqlstate"
SOURCE_REGEX = "regex"
SOURCE_AST_HEURISTIC = "ast_heuristic"

CONFIDENCE_HIGH = 0.95
CONFIDENCE_MEDIUM = 0.7
CONFIDENCE_LOW = 0.4


@dataclass(frozen=True)
class TagWithProvenance:
    """Error tag with source and confidence (0.0–1.0)."""
    tag: str
    source: str
    confidence: float

    def to_dict(self) -> dict:
        return {"tag": self.tag, "source": self.source, "confidence": self.confidence}


@dataclass
class Diagnostics:
    """PostgreSQL error diagnostics (err.diag.*). Fields may be None if not exposed."""
    message_primary: Optional[str] = None
    message_detail: Optional[str] = None
    message_hint: Optional[str] = None
    context: Optional[str] = None
    position: Optional[int] = None
    schema_name: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    datatype_name: Optional[str] = None
    constraint_name: Optional[str] = None
    internal_query: Optional[str] = None
    internal_position: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_primary": self.message_primary,
            "message_detail": self.message_detail,
            "message_hint": self.message_hint,
            "context": self.context,
            "position": self.position,
            "schema_name": self.schema_name,
            "table_name": self.table_name,
            "column_name": self.column_name,
            "datatype_name": self.datatype_name,
            "constraint_name": self.constraint_name,
            "internal_query": self.internal_query,
            "internal_position": self.internal_position,
        }


@dataclass
class ErrorContext:
    """Structured error context: sql, optional ast/sqlstate/diagnostics, tags with provenance."""
    sql: str
    ast: Optional[Any] = None
    sqlstate: Optional[str] = None
    diagnostics: Optional[Diagnostics] = None
    tags: List[TagWithProvenance] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "sql": self.sql,
            "sqlstate": self.sqlstate,
            "diagnostics": self.diagnostics.to_dict() if self.diagnostics else None,
            "tags": [t.to_dict() for t in self.tags],
        }


@dataclass
class ValidationError:
    """Single validation error with tag, message, optional location/context/error_code."""
    tag: str
    message: str
    location: Optional[int] = None
    context: Optional[str] = None
    error_code: Optional[str] = None
    taxonomy_category: Optional[str] = None
    affected_clauses: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        result = {
            "tag": self.tag,
            "message": self.message,
        }
        if self.location is not None:
            result["location"] = self.location
        if self.context is not None:
            result["context"] = self.context
        if self.error_code is not None:
            result["error_code"] = self.error_code
        if self.taxonomy_category is not None:
            result["taxonomy_category"] = self.taxonomy_category
        if self.affected_clauses:
            result["affected_clauses"] = self.affected_clauses
        return result


@dataclass
class QueryMetadata:
    """
    Metadata about a SQL query's structure and complexity.
    
    Attributes:
        complexity_score: Overall complexity score (weighted sum of joins, subqueries, etc.)
        pattern_signature: Structural fingerprint of the query (e.g., "SELECT-WHERE-JOIN-GROUPBY")
        clauses_present: List of SQL clauses present in the query (e.g., ['SELECT', 'FROM', 'WHERE', 'JOIN'])
        num_joins: Number of JOIN operations
        num_subqueries: Number of subqueries
        num_ctes: Number of CTEs (WITH clauses)
        num_aggregations: Number of aggregation functions
    """
    complexity_score: int
    pattern_signature: str
    clauses_present: List[str] = field(default_factory=list)
    num_joins: int = 0
    num_subqueries: int = 0
    num_ctes: int = 0
    num_aggregations: int = 0
    
    def to_dict(self) -> dict:
        return {
            "complexity_score": self.complexity_score,
            "pattern_signature": self.pattern_signature,
            "clauses_present": self.clauses_present,
            "num_joins": self.num_joins,
            "num_subqueries": self.num_subqueries,
            "num_ctes": self.num_ctes,
            "num_aggregations": self.num_aggregations,
        }


@dataclass
class ValidationResult:
    """
    Result of SQL query validation.
    
    Attributes:
        valid: Whether the query passed validation
        errors: List of validation errors found
        ast: The parsed AST (sqlglot Expression) if parsing succeeded
        sql: The original SQL query that was validated
        query_metadata: Metadata about query structure and complexity (if analyzed)
    """
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    ast: Optional[Any] = None  # sqlglot.Expression, using Any to avoid import
    sql: str = ""
    query_metadata: Optional[QueryMetadata] = None
    
    @property
    def tags(self) -> List[str]:
        return [e.tag for e in self.errors]

    @property
    def error_messages(self) -> List[str]:
        return [e.message for e in self.errors]

    def to_dict(self) -> dict:
        result = {
            "valid": self.valid,
            "sql": self.sql,
            "errors": [e.to_dict() for e in self.errors],
            "tags": self.tags,
        }
        if self.query_metadata is not None:
            result["query_metadata"] = self.query_metadata.to_dict()
        return result
    
    def __repr__(self) -> str:
        if self.valid:
            return f"ValidationResult(valid=True, sql={self.sql[:50]!r}...)"
        return f"ValidationResult(valid=False, tags={self.tags}, sql={self.sql[:50]!r}...)"
