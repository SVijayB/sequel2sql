# -*- coding: utf-8 -*-
"""Simplified SQL validation for LLM agent tool calls."""

import json
import os
from pathlib import Path
from typing import Dict, Optional

from ast_parsers.models import ValidationResultOut
from ast_parsers.validator import validate_schema, validate_syntax

# Path to schema JSON files - supports SEQUEL2SQL_SCHEMA_DIR env var override
SCHEMA_DIR = Path(
    os.getenv(
        "SEQUEL2SQL_SCHEMA_DIR",
        Path(__file__).parent.parent.parent / "benchmark" / "data" / "schemas",
    )
)


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
) -> ValidationResultOut:
    """Validate SQL syntax and optionally schema, returning validation result with valid flag.

    Args:
        sql: SQL query string to validate.
        db_name: Optional database name (e.g., "california_schools_template").
                 If provided and schema file exists, validates against schema.
        dialect: SQL dialect (default: "postgres").

    Returns:
        ValidationResultOut with valid flag and errors list.
        - valid=True means no errors detected
        - valid=False means errors were found (check errors list)
    """
    schema = _load_schema(db_name) if db_name else None

    if schema is not None:
        result = validate_schema(sql, schema, dialect=dialect)
    else:
        result = validate_syntax(sql, dialect=dialect)

    return ValidationResultOut.from_validation_result(result)
