# -*- coding: utf-8 -*-
"""
Sequel2SQL Query Validator

A reusable SQL query validation module with static analysis
and schema-aware semantic validation using sqlglot.
"""

from ast_parsers.errors import (
    ValidationResult,
    ValidationError,
    QueryMetadata,
    SyntaxErrorTags,
    SchemaErrorTags,
    LogicalErrorTags,
    JoinErrorTags,
    AggregationErrorTags,
    FilterErrorTags,
    SubqueryErrorTags,
    SetOperationErrorTags,
    StructuralErrorTags,
)
from ast_parsers.validator import (
    validate_syntax,
    validate_schema,
    validate_query,
)
from ast_parsers.error_codes import (
    extract_error_code,
    get_taxonomy_category,
    get_tags_for_category,
    get_category_for_tag,
    POSTGRES_ERROR_CODE_MAP,
    TAXONOMY_CATEGORIES,
)
from ast_parsers.query_analyzer import (
    extract_sql_clauses,
    calculate_complexity,
    generate_pattern_signature,
    analyze_query,
    get_clause_for_node,
    count_query_elements,
)

__version__ = "0.1.0"

__all__ = [
    # Core validation
    "ValidationResult",
    "ValidationError",
    "QueryMetadata",
    "validate_syntax",
    "validate_schema",
    "validate_query",
    # Error tags
    "SyntaxErrorTags",
    "SchemaErrorTags",
    "LogicalErrorTags",
    "JoinErrorTags",
    "AggregationErrorTags",
    "FilterErrorTags",
    "SubqueryErrorTags",
    "SetOperationErrorTags",
    "StructuralErrorTags",
    # Error codes
    "extract_error_code",
    "get_taxonomy_category",
    "get_tags_for_category",
    "get_category_for_tag",
    "POSTGRES_ERROR_CODE_MAP",
    "TAXONOMY_CATEGORIES",
    # Query analysis
    "extract_sql_clauses",
    "calculate_complexity",
    "generate_pattern_signature",
    "analyze_query",
    "get_clause_for_node",
    "count_query_elements",
]
