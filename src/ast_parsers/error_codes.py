# -*- coding: utf-8 -*-
"""
PostgreSQL Error Code Mapping and Taxonomy

Maps PostgreSQL SQLSTATE error codes to taxonomy categories and provides
error code extraction from pglast ParseError exceptions.
"""

import re
from typing import Optional, Dict, List


# =============================================================================
# PostgreSQL Error Code to Taxonomy Category Mapping
# =============================================================================

# SQLSTATE class codes:
# 42xxx - Syntax errors or access rule violations
# 22xxx - Data exceptions
# 23xxx - Integrity constraint violations
# 28xxx - Invalid authorization specification
# 2Bxxx - Dependent privilege descriptors still exist
# 2Dxxx - Invalid transaction termination
# 2Fxxx - SQL routine exception
# 34xxx - Invalid cursor name
# 38xxx - External routine exception
# 39xxx - External routine invocation exception
# 3Bxxx - Savepoint exception
# 3Dxxx - Invalid catalog name
# 3Fxxx - Invalid schema name
# 40xxx - Transaction rollback
# 42xxx - Syntax error or access rule violation
# 44xxx - WITH CHECK OPTION violation
# 53xxx - Insufficient resources
# 54xxx - Program limit exceeded
# 55xxx - Object not in prerequisite state
# 57xxx - Operator intervention
# 58xxx - System error
# 72xxx - Snapshot too old
# F0xxx - Configuration file error
# HVxxx - Foreign data wrapper error
# P0xxx - PL/pgSQL error
# XXxxx - Internal error

POSTGRES_ERROR_CODE_MAP: Dict[str, str] = {
    # Syntax errors (42601)
    "42601": "syntax",  # syntax_error
    "42602": "syntax",  # invalid_name
    "42611": "syntax",  # invalid_column_definition
    "42622": "syntax",  # name_too_long
    
    # Semantic errors - Column/Table resolution (42xxx, 427xx)
    "42702": "semantic",  # ambiguous_column
    "42703": "semantic",  # undefined_column
    "42704": "semantic",  # undefined_object
    "42710": "semantic",  # duplicate_object
    "42712": "semantic",  # duplicate_table
    "42723": "semantic",  # duplicate_function
    "42725": "semantic",  # ambiguous_function
    
    # Table errors (42P01, 42P02, etc.)
    "42P01": "semantic",  # undefined_table
    "42P02": "semantic",  # undefined_parameter
    "42P03": "semantic",  # duplicate_cursor
    "42P04": "semantic",  # duplicate_database
    "42P05": "semantic",  # duplicate_prepared_statement
    "42P06": "semantic",  # duplicate_schema
    "42P07": "semantic",  # duplicate_table
    
    # Logical errors - Grouping/Aggregation (42803, 42804, etc.)
    "42803": "logical",  # grouping_error (column must appear in GROUP BY)
    "42804": "semantic",  # datatype_mismatch
    "42809": "logical",  # wrong_object_type
    "42830": "logical",  # invalid_foreign_key
    "42846": "semantic",  # cannot_coerce
    "42883": "semantic",  # undefined_function
    "42884": "semantic",  # no_function_matches
    
    # Windowing errors (42P20)
    "42P20": "logical",  # windowing_error
    
    # Data type errors (22xxx)
    "22005": "semantic",  # error_in_assignment
    "22007": "semantic",  # invalid_datetime_format
    "22008": "semantic",  # datetime_field_overflow
    "22012": "semantic",  # division_by_zero
    "22023": "semantic",  # invalid_parameter_value
    "22P02": "semantic",  # invalid_text_representation
    "22P03": "semantic",  # invalid_binary_representation
    "22P04": "semantic",  # bad_copy_file_format
    "22P05": "semantic",  # untranslatable_character
    
    # Integrity constraint violations (23xxx)
    "23000": "logical",  # integrity_constraint_violation
    "23001": "logical",  # restrict_violation
    "23502": "logical",  # not_null_violation
    "23503": "logical",  # foreign_key_violation
    "23505": "logical",  # unique_violation
    "23514": "logical",  # check_violation
    
    # Join-related errors (inferred from context)
    # These don't have specific SQLSTATE codes, but we can infer from error messages
    # "JOIN_ERROR": "join_related",
    # "MISSING_JOIN": "join_related",
    
    # Aggregation errors (inferred)
    # "AGGREGATION_ERROR": "aggregation",
    # "MISSING_GROUPBY": "aggregation",
}


# =============================================================================
# Taxonomy Categories and Their Tags
# =============================================================================

TAXONOMY_CATEGORIES: Dict[str, List[str]] = {
    "syntax": [
        "syntax_error",
        "syntax_unbalanced_tokens",
        "syntax_trailing_delimiter",
        "syntax_keyword_misuse",
        "syntax_unterminated_string",
        "syntax_invalid_name",
        "syntax_invalid_column_definition",
    ],
    "semantic": [
        "schema_hallucination_table",
        "schema_hallucination_col",
        "schema_ambiguous_col",
        "schema_type_mismatch",
        "schema_unknown_error",
        "schema_duplicate_object",
        "schema_undefined_function",
        "schema_datatype_mismatch",
    ],
    "logical": [
        "logical_grouping_error",
        "logical_aggregation_error",
        "logical_windowing_error",
        "logical_integrity_violation",
        "logical_foreign_key_violation",
        "logical_unique_violation",
        "logical_check_violation",
    ],
    "schema_linking": [
        "schema_hallucination_table",
        "schema_hallucination_col",
        "schema_ambiguous_col",
        "schema_incorrect_foreign_key",
    ],
    "join_related": [
        "join_missing_join",
        "join_wrong_join_type",
        "join_extra_table",
        "join_condition_error",
    ],
    "aggregation": [
        "aggregation_missing_groupby",
        "aggregation_misuse_having",
        "aggregation_error",
        "logical_grouping_error",
    ],
    "filter_conditions": [
        "filter_incorrect_where_column",
        "filter_type_mismatch_where",
        "filter_missing_where",
    ],
    "value_representation": [
        "value_hardcoded_value",
        "value_format_mismatch",
    ],
    "subquery_formulation": [
        "subquery_unused_subquery",
        "subquery_incorrect_correlation",
        "subquery_error",
    ],
    "set_operations": [
        "set_union_error",
        "set_intersection_error",
        "set_except_error",
    ],
    "structural": [
        "structural_missing_orderby",
        "structural_missing_limit",
        "structural_error",
    ],
}


# =============================================================================
# Error Code Extraction from pglast ParseError
# =============================================================================

def extract_error_code(error_message: str) -> Optional[str]:
    """
    Extract PostgreSQL SQLSTATE error code from error message.
    
    pglast ParseError messages may contain SQLSTATE codes in various formats:
    - Direct SQLSTATE: "ERROR: 42703: column 'x' does not exist"
    - Pattern-based: Need to match error patterns to codes
    
    Args:
        error_message: The error message string from pglast ParseError
    
    Returns:
        SQLSTATE error code (e.g., "42703", "42P01") or None if not found
    """
    # Pattern 1: Direct SQLSTATE code in error message
    # Format: "ERROR: 42703: ..." or "SQLSTATE 42703" or "[42703]"
    sqlstate_pattern = r'(?:SQLSTATE|ERROR)[\s:]*([0-9A-Z]{5})|\[([0-9A-Z]{5})\]'
    match = re.search(sqlstate_pattern, error_message, re.IGNORECASE)
    if match:
        return match.group(1) or match.group(2)
    
    # Pattern 2: Match error message patterns to known error codes
    # This is a fallback when SQLSTATE is not directly available
    error_patterns = {
        r"syntax error": "42601",
        r"unterminated quoted string": "42601",
        r"column reference .* is ambiguous": "42702",
        r"column .* does not exist": "42703",
        r"undefined column": "42703",
        r"table .* does not exist": "42P01",
        r"undefined table": "42P01",
        r"table name .* specified more than once": "42712",
        r"aggregate function .* cannot contain": "42803",
        r"must appear in the GROUP BY clause": "42803",
        r"window function .* cannot contain": "42P20",
        r"argument of .* must be type boolean": "42804",
        r"invalid hexadecimal": "22P02",
        r"invalid input syntax": "22P02",
        r"division by zero": "22012",
        r"duplicate key": "23505",
        r"foreign key violation": "23503",
        r"not null violation": "23502",
    }
    
    error_lower = error_message.lower()
    for pattern, code in error_patterns.items():
        if re.search(pattern, error_lower):
            return code
    
    return None


def get_taxonomy_category(error_code: Optional[str]) -> Optional[str]:
    """
    Map PostgreSQL error code to taxonomy category.
    
    Args:
        error_code: PostgreSQL SQLSTATE error code (e.g., "42703", "42P01")
    
    Returns:
        Taxonomy category ("syntax", "semantic", "logical", etc.) or None
    """
    if error_code is None:
        return None
    
    return POSTGRES_ERROR_CODE_MAP.get(error_code)


def get_tags_for_category(category: Optional[str]) -> List[str]:
    """
    Get all error tags associated with a taxonomy category.
    
    Args:
        category: Taxonomy category name (e.g., "syntax", "semantic")
    
    Returns:
        List of error tags for that category
    """
    if category is None:
        return []
    
    return TAXONOMY_CATEGORIES.get(category, [])


# =============================================================================
# Reverse Mapping: Tag to Category
# =============================================================================

def get_category_for_tag(tag: str) -> Optional[str]:
    """
    Find which taxonomy category a specific error tag belongs to.
    
    Args:
        tag: Error tag (e.g., "syntax_trailing_delimiter", "schema_hallucination_col")
    
    Returns:
        Taxonomy category name or None if not found
    """
    for category, tags in TAXONOMY_CATEGORIES.items():
        if tag in tags or tag.startswith(category + "_"):
            return category
    
    # Check prefix patterns
    if tag.startswith("syntax_"):
        return "syntax"
    elif tag.startswith("schema_"):
        return "semantic"  # schema errors are semantic
    elif tag.startswith("logical_"):
        return "logical"
    elif tag.startswith("join_"):
        return "join_related"
    elif tag.startswith("aggregation_"):
        return "aggregation"
    elif tag.startswith("filter_"):
        return "filter_conditions"
    elif tag.startswith("value_"):
        return "value_representation"
    elif tag.startswith("subquery_"):
        return "subquery_formulation"
    elif tag.startswith("set_"):
        return "set_operations"
    elif tag.startswith("structural_"):
        return "structural"
    
    return None
