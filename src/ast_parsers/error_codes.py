# -*- coding: utf-8 -*-
"""PostgreSQL SQLSTATE to taxonomy mapping and error code extraction."""

import re
from typing import Optional, Dict, List


POSTGRES_ERROR_CODE_MAP: Dict[str, str] = {
    "42601": "syntax",
    "42602": "syntax",
    "42611": "syntax",
    "42622": "syntax",
    "42702": "semantic",
    "42703": "semantic",
    "42704": "semantic",
    "42710": "semantic",
    "42712": "semantic",
    "42723": "semantic",
    "42725": "semantic",
    "42P01": "semantic",
    "42P02": "semantic",
    "42P03": "semantic",
    "42P04": "semantic",
    "42P05": "semantic",
    "42P06": "semantic",
    "42P07": "semantic",
    "42803": "logical",
    "42804": "semantic",
    "42809": "logical",
    "42830": "logical",
    "42846": "semantic",
    "42883": "semantic",
    "42884": "semantic",
    "42P20": "logical",
    "22005": "semantic",
    "22007": "semantic",
    "22008": "semantic",
    "22012": "semantic",
    "22023": "semantic",
    "22P02": "semantic",
    "22P03": "semantic",
    "22P04": "semantic",
    "22P05": "semantic",
    "23000": "logical",
    "23001": "logical",
    "23502": "logical",
    "23503": "logical",
    "23505": "logical",
    "23514": "logical",
}


TAXONOMY_CATEGORIES: Dict[str, List[str]] = {
    "syntax": [
        "syntax_error",
        "syntax_unbalanced_tokens",
        "syntax_trailing_delimiter",
        "syntax_keyword_misuse",
        "syntax_unterminated_string",
        "syntax_invalid_token",
        "syntax_unsupported_dialect",
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


def extract_error_code(error_message: str) -> Optional[str]:
    """Extract SQLSTATE from message; None if not found."""
    sqlstate_pattern = r'(?:SQLSTATE|ERROR)[\s:]*([0-9][0-9A-Z]{4})|\[([0-9][0-9A-Z]{4})\]'
    match = re.search(sqlstate_pattern, error_message, re.IGNORECASE)
    if match:
        return (match.group(1) or match.group(2)).upper()
    error_patterns = {
        r"syntax error": "42601",
        r"unterminated quoted string": "42601",
        r"column reference .* is ambiguous": "42702",
        r"column reference is ambiguous": "42702",
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
        if re.search(pattern, error_lower, re.IGNORECASE):
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
    """Tags for a taxonomy category; [] if unknown."""
    if category is None:
        return []
    
    return TAXONOMY_CATEGORIES.get(category, [])


# Class fallback when exact SQLSTATE unknown (first two chars).
SQLSTATE_CLASS_FALLBACK: Dict[str, str] = {
    "42": "semantic", "22": "semantic", "23": "logical", "28": "semantic",
    "2B": "semantic", "2D": "logical", "2F": "semantic", "34": "semantic",
    "38": "semantic", "39": "semantic", "3B": "logical", "3D": "semantic",
    "3F": "semantic", "40": "logical", "44": "logical", "53": "semantic",
    "54": "semantic", "55": "semantic", "57": "semantic", "58": "semantic",
    "72": "semantic", "0A": "semantic", "XX": "semantic", "F0": "semantic",
    "HV": "semantic", "P0": "semantic",
}


def get_taxonomy_category_with_fallback(error_code: Optional[str]) -> Optional[str]:
    """Map SQLSTATE to category; use class fallback if exact code unknown."""
    if error_code is None:
        return None
    specific = POSTGRES_ERROR_CODE_MAP.get(error_code)
    if specific is not None:
        return specific
    if len(error_code) >= 2:
        return SQLSTATE_CLASS_FALLBACK.get(error_code[:2])
    return None


POSTGRES_SQLSTATE_TO_TAG: Dict[str, str] = {
    "42601": "syntax_error",
    "42602": "syntax_invalid_name",
    "42702": "schema_ambiguous_col",
    "42703": "schema_hallucination_col",
    "42704": "schema_unknown_error",
    "42P01": "schema_hallucination_table",
    "42803": "logical_grouping_error",
    "42P20": "logical_windowing_error",
    "23502": "logical_integrity_violation",
    "23503": "logical_foreign_key_violation",
    "23505": "logical_unique_violation",
    "23514": "logical_check_violation",
    "42883": "schema_undefined_function",
    "42884": "schema_undefined_function",
    "42804": "schema_type_mismatch",
    "22P02": "value_format_mismatch",
    "22012": "value_format_mismatch",
}


def get_tag_for_sqlstate(sqlstate: Optional[str]) -> Optional[str]:
    """Return single best tag for a SQLSTATE, or None."""
    if sqlstate is None:
        return None
    return POSTGRES_SQLSTATE_TO_TAG.get(sqlstate)


def get_category_for_tag(tag: str) -> Optional[str]:
    """Taxonomy category for a tag, or None."""
    for category, tags in TAXONOMY_CATEGORIES.items():
        if tag in tags or tag.startswith(category + "_"):
            return category
    if tag.startswith("syntax_"):
        return "syntax"
    elif tag.startswith("schema_"):
        return "semantic"  # schema errors are semantic
    if tag.startswith("logical_"):
        return "logical"
    if tag.startswith("join_"):
        return "join_related"
    if tag.startswith("aggregation_"):
        return "aggregation"
    if tag.startswith("filter_"):
        return "filter_conditions"
    if tag.startswith("value_"):
        return "value_representation"
    if tag.startswith("subquery_"):
        return "subquery_formulation"
    if tag.startswith("set_"):
        return "set_operations"
    if tag.startswith("structural_"):
        return "structural"
    return None
