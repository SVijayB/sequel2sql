# -*- coding: utf-8 -*-
"""Error types and classes. See README.md."""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict


import json
import os
import sys

def _load_error_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data", "error_data.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback/Safety for when file isn't found (e.g. CI without data)
        print(f"Warning: {data_path} not found.", file=sys.stderr)
        return {"taxonomy_categories": {}}

_ERROR_DATA = _load_error_data()
_CATEGORIES = _ERROR_DATA.get("taxonomy_categories", {})

def _create_tag_class(class_name, category_key, prefix_to_strip, name_overrides=None):
    valid_tags = _CATEGORIES.get(category_key, [])
    attrs = {}
    overrides = name_overrides or {}
    
    for tag in valid_tags:
        if tag in overrides:
             attr_name = overrides[tag]
        # Heuristic: If tag is exactly "{prefix}error", keep full name (e.g. SYNTAX_ERROR)
        # Otherwise strip prefix (e.g. syntax_unbalanced_tokens -> UNBALANCED_TOKENS)
        elif tag == f"{prefix_to_strip}error":
             attr_name = tag.upper()
        elif tag.startswith(prefix_to_strip):
            attr_name = tag[len(prefix_to_strip):].upper()
        else:
            attr_name = tag.upper()
        
        attrs[attr_name] = tag
    
    # Create the class dynamically
    return type(class_name, (), attrs)

# Define classes using the dynamic generator
SyntaxErrorTags = _create_tag_class("SyntaxErrorTags", "syntax", "syntax_")
SchemaErrorTags = _create_tag_class(
    "SchemaErrorTags", 
    "semantic", 
    "schema_",
    name_overrides={
        "schema_hallucination_col": "HALLUCINATION_COLUMN",
        "schema_ambiguous_col": "AMBIGUOUS_COLUMN"
    }
)
LogicalErrorTags = _create_tag_class("LogicalErrorTags", "logical", "logical_")
JoinErrorTags = _create_tag_class("JoinErrorTags", "join_related", "join_")
AggregationErrorTags = _create_tag_class("AggregationErrorTags", "aggregation", "aggregation_")
FilterErrorTags = _create_tag_class("FilterErrorTags", "filter_conditions", "filter_")
SubqueryErrorTags = _create_tag_class("SubqueryErrorTags", "subquery_formulation", "subquery_")
SetOperationErrorTags = _create_tag_class("SetOperationErrorTags", "set_operations", "set_")
StructuralErrorTags = _create_tag_class("StructuralErrorTags", "structural", "structural_")


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
    """PostgreSQL err.diag.* fields; missing fields are None."""
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
    """One validation error: tag, message, optional location/context/error_code."""
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
    """Metadata about a SQL query's structure and complexity."""
    complexity_score: float
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
    """Validation result: valid flag, errors, optional ast/sql/query_metadata."""
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
