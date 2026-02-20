# -*- coding: utf-8 -*-
"""
Unified Pydantic v2 models for SQL validation results.

Three types cover the entire public surface:
  ValidationError  – one error with a canonical ErrorTag
  QueryMetadata    – structural analysis of the SQL query
  ValidationResult – top-level result: valid flag + errors + metadata

This replaces the previous split between ast_parsers.errors (dataclasses) and
ast_parsers.models (Pydantic mirrors), collapsing six types into three and
eliminating the manual conversion layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field

from ast_parsers.tags import ErrorTag


class ValidationError(BaseModel):
    """A single validation error with a canonical tag."""

    tag: ErrorTag
    message: str
    location: Optional[int] = None
    context: Optional[str] = None
    error_code: Optional[str] = None
    affected_clauses: List[str] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def taxonomy_category(self) -> str:
        """Taxonomy category derived from the tag (no extra field needed)."""
        return self.tag.taxonomy_category

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "tag": self.tag.value,
            "message": self.message,
            "taxonomy_category": self.taxonomy_category,
        }
        if self.location is not None:
            d["location"] = self.location
        if self.context is not None:
            d["context"] = self.context
        if self.error_code is not None:
            d["error_code"] = self.error_code
        if self.affected_clauses:
            d["affected_clauses"] = self.affected_clauses
        return d

    model_config = {"extra": "forbid"}


class QueryMetadata(BaseModel):
    """Structural metadata about a SQL query (produced by a single AST pass)."""

    complexity_score: float
    pattern_signature: str
    clauses_present: List[str] = Field(default_factory=list)
    tables: List[str] = Field(default_factory=list)
    num_joins: int = 0
    num_subqueries: int = 0
    num_ctes: int = 0
    num_aggregations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "complexity_score": self.complexity_score,
            "pattern_signature": self.pattern_signature,
            "clauses_present": self.clauses_present,
            "tables": self.tables,
            "num_joins": self.num_joins,
            "num_subqueries": self.num_subqueries,
            "num_ctes": self.num_ctes,
            "num_aggregations": self.num_aggregations,
        }

    model_config = {"extra": "forbid"}


class ValidationResult(BaseModel):
    """Complete result of SQL validation: validity, errors, and query metadata."""

    valid: bool
    sql: str = ""
    errors: List[ValidationError] = Field(default_factory=list)
    query_metadata: Optional[QueryMetadata] = None

    @property
    def tags(self) -> List[ErrorTag]:
        """Error tags from all errors (in order)."""
        return [e.tag for e in self.errors]

    @property
    def error_messages(self) -> List[str]:
        """Error messages from all errors (in order)."""
        return [e.message for e in self.errors]

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "valid": self.valid,
            "sql": self.sql,
            "errors": [e.to_dict() for e in self.errors],
            "tags": [t.value for t in self.tags],
        }
        if self.query_metadata is not None:
            result["query_metadata"] = self.query_metadata.to_dict()
        return result

    def __repr__(self) -> str:
        if self.valid:
            return f"ValidationResult(valid=True, sql={self.sql[:50]!r})"
        return (
            f"ValidationResult(valid=False, tags={[t.value for t in self.tags]}, "
            f"sql={self.sql[:50]!r})"
        )

    model_config = {"extra": "forbid"}
