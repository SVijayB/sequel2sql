# -*- coding: utf-8 -*-
"""
Error types and validation result classes for SQL query validation.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any


# =============================================================================
# Error Tag Constants
# =============================================================================

class SyntaxErrorTags:
    """Tags for Part 1: Static Analysis errors."""
    
    SYNTAX_ERROR = "syntax_error"
    """General syntax/parse error."""
    
    UNBALANCED_TOKENS = "syntax_unbalanced_tokens"
    """Mismatched parentheses, brackets, or quotes."""
    
    TRAILING_DELIMITER = "syntax_trailing_delimiter"
    """Trailing comma or delimiter before keyword (common LLM artifact)."""
    
    KEYWORD_MISUSE = "syntax_keyword_misuse"
    """Incorrect keyword usage or ordering."""
    
    UNTERMINATED_STRING = "syntax_unterminated_string"
    """Unterminated quoted string literal."""


class SchemaErrorTags:
    """Tags for Part 2: Semantic Validation errors."""
    
    HALLUCINATION_TABLE = "schema_hallucination_table"
    """Referenced table does not exist in schema."""
    
    HALLUCINATION_COLUMN = "schema_hallucination_col"
    """Referenced column does not exist in schema."""
    
    AMBIGUOUS_COLUMN = "schema_ambiguous_col"
    """Column reference is ambiguous (exists in multiple tables)."""
    
    TYPE_MISMATCH = "schema_type_mismatch"
    """Type mismatch in expression or comparison."""
    
    UNKNOWN_ERROR = "schema_unknown_error"
    """Unclassified schema validation error."""
    
    DUPLICATE_OBJECT = "schema_duplicate_object"
    """Duplicate object (table, column, etc.) definition."""
    
    UNDEFINED_FUNCTION = "schema_undefined_function"
    """Referenced function does not exist."""
    
    DATATYPE_MISMATCH = "schema_datatype_mismatch"
    """Data type mismatch in expression or comparison."""


class LogicalErrorTags:
    """Tags for logical errors (grouping, aggregation, windowing, etc.)."""
    
    GROUPING_ERROR = "logical_grouping_error"
    """Column must appear in GROUP BY clause or be used in aggregate function."""
    
    AGGREGATION_ERROR = "logical_aggregation_error"
    """Error in aggregation logic."""
    
    WINDOWING_ERROR = "logical_windowing_error"
    """Error in window function usage."""
    
    INTEGRITY_VIOLATION = "logical_integrity_violation"
    """Integrity constraint violation."""
    
    FOREIGN_KEY_VIOLATION = "logical_foreign_key_violation"
    """Foreign key constraint violation."""
    
    UNIQUE_VIOLATION = "logical_unique_violation"
    """Unique constraint violation."""
    
    CHECK_VIOLATION = "logical_check_violation"
    """Check constraint violation."""


class JoinErrorTags:
    """Tags for join-related errors."""
    
    MISSING_JOIN = "join_missing_join"
    """Required join is missing."""
    
    WRONG_JOIN_TYPE = "join_wrong_join_type"
    """Incorrect join type used."""
    
    EXTRA_TABLE = "join_extra_table"
    """Unnecessary table included in query."""
    
    JOIN_CONDITION_ERROR = "join_condition_error"
    """Error in join condition."""


class AggregationErrorTags:
    """Tags for aggregation-related errors."""
    
    MISSING_GROUPBY = "aggregation_missing_groupby"
    """Missing GROUP BY clause when required."""
    
    MISUSE_HAVING = "aggregation_misuse_having"
    """Incorrect use of HAVING clause."""
    
    AGGREGATION_ERROR = "aggregation_error"
    """General aggregation error."""


class FilterErrorTags:
    """Tags for filter condition errors."""
    
    INCORRECT_WHERE_COLUMN = "filter_incorrect_where_column"
    """Incorrect column used in WHERE clause."""
    
    TYPE_MISMATCH_WHERE = "filter_type_mismatch_where"
    """Type mismatch in WHERE clause condition."""
    
    MISSING_WHERE = "filter_missing_where"
    """Missing WHERE clause when required."""


class SubqueryErrorTags:
    """Tags for subquery-related errors."""
    
    UNUSED_SUBQUERY = "subquery_unused_subquery"
    """Subquery that is not used or referenced."""
    
    INCORRECT_CORRELATION = "subquery_incorrect_correlation"
    """Incorrect correlated subquery."""
    
    SUBQUERY_ERROR = "subquery_error"
    """General subquery error."""


class SetOperationErrorTags:
    """Tags for set operation errors (UNION, INTERSECT, EXCEPT)."""
    
    UNION_ERROR = "set_union_error"
    """Error in UNION operation."""
    
    INTERSECTION_ERROR = "set_intersection_error"
    """Error in INTERSECT operation."""
    
    EXCEPT_ERROR = "set_except_error"
    """Error in EXCEPT operation."""


class StructuralErrorTags:
    """Tags for structural query errors."""
    
    MISSING_ORDERBY = "structural_missing_orderby"
    """Missing ORDER BY clause when required."""
    
    MISSING_LIMIT = "structural_missing_limit"
    """Missing LIMIT clause when required."""
    
    STRUCTURAL_ERROR = "structural_error"
    """General structural error."""


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ValidationError:
    """
    Represents a single validation error with classification.
    
    Attributes:
        tag: Error classification tag (e.g., 'syntax_trailing_delimiter')
        message: Human-readable error description
        location: Character position in the SQL string where error occurred (if available)
        context: Additional context information (e.g., the problematic token)
        error_code: PostgreSQL SQLSTATE error code (e.g., '42703', '42P01')
        taxonomy_category: High-level taxonomy category (e.g., 'syntax', 'semantic', 'logical')
        affected_clauses: List of SQL clauses affected by this error (e.g., ['WHERE', 'JOIN'])
    """
    tag: str
    message: str
    location: Optional[int] = None
    context: Optional[str] = None
    error_code: Optional[str] = None
    taxonomy_category: Optional[str] = None
    affected_clauses: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
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
        """Convert to dictionary representation."""
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
        """Get list of all error tags."""
        return [e.tag for e in self.errors]
    
    @property
    def error_messages(self) -> List[str]:
        """Get list of all error messages."""
        return [e.message for e in self.errors]
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation (excludes AST)."""
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