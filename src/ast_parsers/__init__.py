# -*- coding: utf-8 -*-
"""
ast_parsers — SQL validation and error taxonomy.

Public API
----------
Main entry point::

    from ast_parsers import validate
    result = validate(sql)                    # syntax only
    result = validate(sql, schema=my_schema)  # syntax + schema

Result types::

    from ast_parsers import ValidationResult, ValidationError, QueryMetadata

Error tags::

    from ast_parsers import ErrorTag
    if ErrorTag.TRAILING_DELIMITER in result.tags: ...

Utilities::

    from ast_parsers import extract_error_code, get_taxonomy_category, get_category_for_tag
"""

from ast_parsers.query_analyzer import analyze_query
from ast_parsers.result import QueryMetadata, ValidationError, ValidationResult
from ast_parsers.tags import (
    ErrorTag,
    category_for_sqlstate_with_fallback,
    extract_error_code,
    tag_for_sqlstate,
)
from ast_parsers.tags import (
    category_for_sqlstate as get_taxonomy_category,
)
from ast_parsers.tags import (
    category_for_tag as get_category_for_tag,
)
from ast_parsers.validator import validate, validate_with_db

__all__ = [
    # ── Main entry points ─────────────────────────────────────────────────
    "validate",
    "validate_with_db",
    # ── Result types ──────────────────────────────────────────────────────
    "ValidationResult",
    "ValidationError",
    "QueryMetadata",
    # ── Tags ──────────────────────────────────────────────────────────────
    "ErrorTag",
    # ── Utilities ─────────────────────────────────────────────────────────
    "extract_error_code",
    "get_taxonomy_category",
    "get_category_for_tag",
    "category_for_sqlstate_with_fallback",
    "tag_for_sqlstate",
    "analyze_query",
    # ── Live DB validation ────────────────────────────────────────────────
    # validate_with_db is also in the main entry points section above
]
