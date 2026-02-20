# -*- coding: utf-8 -*-
"""
All canonical SQL error tags as a single flat Enum, plus SQLSTATE helpers.

This module is the single source of truth for:
  - Every error tag string (ErrorTag enum)
  - Taxonomy category for each tag (derived from tag value prefix)
  - SQLSTATE → tag / category mappings
  - Error-message-pattern → SQLSTATE inference

No JSON file is needed at runtime for tag lookups.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

# ─── Tag prefix → taxonomy category ──────────────────────────────────────────
# The convention is that every tag value is "{prefix}_{name}".
# The prefix determines the taxonomy category automatically.
_PREFIX_TO_CATEGORY: dict[str, str] = {
    "syntax": "syntax",
    "schema": "semantic",
    "logical": "logical",
    "join": "join_related",
    "aggregation": "aggregation",
    "filter": "filter_conditions",
    "value": "value_representation",
    "subquery": "subquery_formulation",
    "set": "set_operations",
    "structural": "structural",
}


class ErrorTag(str, Enum):
    """
    All canonical SQL error tags.

    Each member's *value* is the canonical tag string used in ValidationError
    and stored in ChromaDB / skill files.  Since this class inherits from str,
    members compare equal to their string values:
        ErrorTag.TRAILING_DELIMITER == "syntax_trailing_delimiter"  # True
    """

    # ── Syntax ────────────────────────────────────────────────────────────
    SYNTAX_ERROR = "syntax_error"
    UNBALANCED_TOKENS = "syntax_unbalanced_tokens"
    TRAILING_DELIMITER = "syntax_trailing_delimiter"
    KEYWORD_MISUSE = "syntax_keyword_misuse"
    UNTERMINATED_STRING = "syntax_unterminated_string"
    INVALID_TOKEN = "syntax_invalid_token"
    UNSUPPORTED_DIALECT = "syntax_unsupported_dialect"
    INVALID_NAME = "syntax_invalid_name"
    INVALID_COLUMN_DEF = "syntax_invalid_column_definition"

    # ── Semantic / schema ─────────────────────────────────────────────────
    HALLUCINATION_TABLE = "schema_hallucination_table"
    HALLUCINATION_COLUMN = "schema_hallucination_col"
    AMBIGUOUS_COLUMN = "schema_ambiguous_col"
    TYPE_MISMATCH = "schema_type_mismatch"
    SCHEMA_UNKNOWN_ERROR = "schema_unknown_error"
    DUPLICATE_OBJECT = "schema_duplicate_object"
    UNDEFINED_FUNCTION = "schema_undefined_function"
    DATATYPE_MISMATCH = "schema_datatype_mismatch"
    INCORRECT_FOREIGN_KEY = "schema_incorrect_foreign_key"

    # ── Logical ───────────────────────────────────────────────────────────
    GROUPING_ERROR = "logical_grouping_error"
    LOGICAL_AGGREGATION = "logical_aggregation_error"
    WINDOWING_ERROR = "logical_windowing_error"
    INTEGRITY_VIOLATION = "logical_integrity_violation"
    FOREIGN_KEY_VIOLATION = "logical_foreign_key_violation"
    UNIQUE_VIOLATION = "logical_unique_violation"
    CHECK_VIOLATION = "logical_check_violation"

    # ── Join ──────────────────────────────────────────────────────────────
    MISSING_JOIN = "join_missing_join"
    WRONG_JOIN_TYPE = "join_wrong_join_type"
    EXTRA_TABLE = "join_extra_table"
    JOIN_CONDITION_ERROR = "join_condition_error"

    # ── Aggregation ───────────────────────────────────────────────────────
    MISSING_GROUPBY = "aggregation_missing_groupby"
    MISUSE_HAVING = "aggregation_misuse_having"
    AGG_ERROR = "aggregation_error"

    # ── Filter conditions ─────────────────────────────────────────────────
    INCORRECT_WHERE_COLUMN = "filter_incorrect_where_column"
    FILTER_TYPE_MISMATCH = "filter_type_mismatch_where"
    MISSING_WHERE = "filter_missing_where"

    # ── Value representation ──────────────────────────────────────────────
    HARDCODED_VALUE = "value_hardcoded_value"
    VALUE_FORMAT_MISMATCH = "value_format_mismatch"

    # ── Subquery ──────────────────────────────────────────────────────────
    UNUSED_SUBQUERY = "subquery_unused_subquery"
    INCORRECT_CORRELATION = "subquery_incorrect_correlation"
    SUBQUERY_ERROR = "subquery_error"

    # ── Set operations ────────────────────────────────────────────────────
    UNION_ERROR = "set_union_error"
    INTERSECTION_ERROR = "set_intersection_error"
    EXCEPT_ERROR = "set_except_error"

    # ── Structural ────────────────────────────────────────────────────────
    MISSING_ORDERBY = "structural_missing_orderby"
    MISSING_LIMIT = "structural_missing_limit"
    STRUCTURAL_ERROR = "structural_error"

    @property
    def taxonomy_category(self) -> str:
        """Taxonomy category derived from tag value prefix (no lookup needed)."""
        prefix = self.value.split("_")[0]
        return _PREFIX_TO_CATEGORY.get(prefix, "syntax")


# ─── SQLSTATE → category (exact) ─────────────────────────────────────────────
_SQLSTATE_TO_CATEGORY: dict[str, str] = {
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
    "42809": "logical",
    "42830": "logical",
    "42P20": "logical",
    "42804": "semantic",
    "42846": "semantic",
    "42883": "semantic",
    "42884": "semantic",
    "22005": "semantic",
    "22007": "semantic",
    "22008": "semantic",
    "22012": "semantic",
    "22023": "semantic",
    "22P02": "semantic",
    "22P03": "semantic",
    "22P04": "semantic",
    "23000": "logical",
    "23001": "logical",
    "23502": "logical",
    "23503": "logical",
    "23505": "logical",
    "23514": "logical",
}

# SQLSTATE class prefix (first 2 chars) → fallback category
_SQLSTATE_CLASS_FALLBACK: dict[str, str] = {
    "42": "semantic",
    "22": "semantic",
    "23": "logical",
    "28": "semantic",
    "2B": "semantic",
    "2D": "logical",
    "2F": "semantic",
    "34": "semantic",
    "38": "semantic",
    "39": "semantic",
    "3B": "logical",
    "3D": "semantic",
    "3F": "semantic",
    "40": "logical",
    "44": "logical",
    "53": "semantic",
    "54": "semantic",
    "55": "semantic",
    "57": "semantic",
    "58": "semantic",
    "72": "semantic",
    "0A": "semantic",
    "XX": "semantic",
    "F0": "semantic",
    "HV": "semantic",
    "P0": "semantic",
}

# Exact SQLSTATE → single best ErrorTag
_SQLSTATE_TO_TAG: dict[str, ErrorTag] = {
    "42601": ErrorTag.SYNTAX_ERROR,
    "42602": ErrorTag.INVALID_NAME,
    "42702": ErrorTag.AMBIGUOUS_COLUMN,
    "42703": ErrorTag.HALLUCINATION_COLUMN,
    "42704": ErrorTag.SCHEMA_UNKNOWN_ERROR,
    "42P01": ErrorTag.HALLUCINATION_TABLE,
    "42803": ErrorTag.GROUPING_ERROR,
    "42P20": ErrorTag.WINDOWING_ERROR,
    "23502": ErrorTag.INTEGRITY_VIOLATION,
    "23503": ErrorTag.FOREIGN_KEY_VIOLATION,
    "23505": ErrorTag.UNIQUE_VIOLATION,
    "23514": ErrorTag.CHECK_VIOLATION,
    "42883": ErrorTag.UNDEFINED_FUNCTION,
    "42884": ErrorTag.UNDEFINED_FUNCTION,
    "42804": ErrorTag.TYPE_MISMATCH,
    "22P02": ErrorTag.VALUE_FORMAT_MISMATCH,
    "22012": ErrorTag.VALUE_FORMAT_MISMATCH,
}

# Error message substrings/patterns → SQLSTATE inference
_ERROR_PATTERNS: dict[str, str] = {
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
    r"must appear in the group by clause": "42803",
    r"window function .* cannot contain": "42P20",
    r"argument of .* must be type boolean": "42804",
    r"invalid hexadecimal": "22P02",
    r"invalid input syntax": "22P02",
    r"division by zero": "22012",
    r"duplicate key": "23505",
    r"foreign key violation": "23503",
    r"not null violation": "23502",
}


# ─── Public helpers ───────────────────────────────────────────────────────────


def extract_error_code(error_message: str) -> Optional[str]:
    """Extract a PostgreSQL SQLSTATE code from an error message string.

    Tries direct SQLSTATE patterns first, then falls back to message content.
    Returns None if nothing matches.
    """
    pattern = r"(?:SQLSTATE|ERROR)[\s:]*([0-9][0-9A-Z]{4})|\[([0-9][0-9A-Z]{4})\]"
    match = re.search(pattern, error_message, re.IGNORECASE)
    if match:
        return (match.group(1) or match.group(2)).upper()

    msg_lower = error_message.lower()
    for pat, code in _ERROR_PATTERNS.items():
        if re.search(pat, msg_lower, re.IGNORECASE):
            return code
    return None


def tag_for_sqlstate(code: Optional[str]) -> Optional[ErrorTag]:
    """Single best ErrorTag for a SQLSTATE code, or None."""
    if not code:
        return None
    return _SQLSTATE_TO_TAG.get(code)


def category_for_sqlstate(code: Optional[str]) -> Optional[str]:
    """Taxonomy category for a SQLSTATE code (exact match only); None if unknown."""
    if not code:
        return None
    return _SQLSTATE_TO_CATEGORY.get(code)


def category_for_sqlstate_with_fallback(code: Optional[str]) -> Optional[str]:
    """Taxonomy category for a SQLSTATE code with class-prefix fallback."""
    if not code:
        return None
    exact = _SQLSTATE_TO_CATEGORY.get(code)
    if exact:
        return exact
    if len(code) >= 2:
        return _SQLSTATE_CLASS_FALLBACK.get(code[:2].upper())
    return None


def category_for_tag(tag: "str | ErrorTag") -> Optional[str]:
    """Taxonomy category for a tag string or ErrorTag member; None if unrecognised."""
    if isinstance(tag, ErrorTag):
        return tag.taxonomy_category
    try:
        return ErrorTag(tag).taxonomy_category
    except ValueError:
        # Unknown string tag — try prefix heuristic
        prefix = tag.split("_")[0]
        return _PREFIX_TO_CATEGORY.get(prefix)
