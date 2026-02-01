# -*- coding: utf-8 -*-
"""SQL validation (syntax + optional schema) and ErrorContext from PostgreSQL err.diag.*."""

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
    Diagnostics,
    ErrorContext,
    TagWithProvenance,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
)
from ast_parsers.validator import (
    validate_syntax,
    validate_schema,
    validate_query,
)
from ast_parsers.error_codes import (
    extract_error_code,
    get_taxonomy_category,
    get_taxonomy_category_with_fallback,
    get_tags_for_category,
    get_category_for_tag,
    get_tag_for_sqlstate,
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
from ast_parsers.error_context import (
    build_error_context,
    extract_diagnostics,
    localize_position,
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
    # Error context pipeline
    "ErrorContext",
    "Diagnostics",
    "TagWithProvenance",
    "build_error_context",
    "extract_diagnostics",
    "localize_position",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_MEDIUM",
    "CONFIDENCE_LOW",
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
    "get_taxonomy_category_with_fallback",
    "get_tags_for_category",
    "get_category_for_tag",
    "get_tag_for_sqlstate",
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
