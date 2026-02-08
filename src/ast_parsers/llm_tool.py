# -*- coding: utf-8 -*-
"""Simplified SQL validation for LLM agent tool calls."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from ast_parsers.validator import validate_syntax, validate_schema
from ast_parsers.models import ValidationErrorOut

# Path to schema JSON files
SCHEMA_DIR = Path(__file__).parent.parent.parent / "benchmark" / "data" / "schemas"


def _load_schema(db_name: str) -> Optional[Dict[str, Dict[str, str]]]:
    """Load schema from JSON file if it exists."""
    schema_path = SCHEMA_DIR / f"{db_name}.json"
    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def validate_sql(
    sql: str,
    db_name: Optional[str] = None,
    dialect: str = "postgres",
) -> List[ValidationErrorOut]:
    """Validate SQL syntax and optionally schema, returning only errors.

    Args:
        sql: SQL query string to validate.
        db_name: Optional database name (e.g., "california_schools_template").
                 If provided and schema file exists, validates against schema.
        dialect: SQL dialect (default: "postgres").

    Returns:
        List of ValidationErrorOut. Empty list means the SQL is valid.
    """
    schema = _load_schema(db_name) if db_name else None
    
    if schema is not None:
        result = validate_schema(sql, schema, dialect=dialect)
    else:
        result = validate_syntax(sql, dialect=dialect)

    return [
        ValidationErrorOut(
            tag=e.tag,
            message=e.message,
            location=e.location,
            context=e.context,
            error_code=e.error_code,
            taxonomy_category=e.taxonomy_category,
            affected_clauses=e.affected_clauses or [],
        )
        for e in result.errors
    ]
