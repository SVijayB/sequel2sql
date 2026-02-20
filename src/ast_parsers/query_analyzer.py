# -*- coding: utf-8 -*-
"""
Query structure analysis: single-pass AST traversal → QueryMetadata.

Public API:
    analyze_query(ast) -> QueryMetadata

That's it. One entry point, one exit point.
All clause detection, complexity scoring, and count collection happen inside
a single ast.walk() call. No secondary traversals.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from typing import Any, Dict, Set

from sqlglot import exp

from ast_parsers.result import QueryMetadata


@lru_cache(maxsize=1)
def _load_complexity_config() -> dict:
    """Load complexity weights/bounds once and cache."""
    data_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data",
        "complexity_config.json",
    )
    try:
        with open(data_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# Canonical clause ordering for pattern signatures
_CLAUSE_ORDER: list[str] = [
    "WITH",
    "CTE",
    "SELECT",
    "DISTINCT",
    "DISTINCT_ON",
    "FROM",
    "JOIN",
    "JOIN_INNER",
    "JOIN_LEFT",
    "JOIN_RIGHT",
    "JOIN_FULL",
    "JOIN_CROSS",
    "LATERAL",
    "WHERE",
    "GROUP",
    "HAVING",
    "WINDOW",
    "PARTITION",
    "QUALIFY",
    "UNION",
    "INTERSECT",
    "EXCEPT",
    "ORDER",
    "LIMIT",
    "OFFSET",
    "TABLESAMPLE",
    "VALUES",
    "FILTER",
    "LOCKING",
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "RETURNING",
]


def analyze_query(ast: Any) -> QueryMetadata:
    """
    Analyze a sqlglot AST in a single pass and return QueryMetadata.

    This is the *only* public function in this module.  Callers that previously
    called extract_sql_clauses / calculate_complexity / count_query_elements
    separately should instead call this once and read the relevant fields from
    the returned QueryMetadata.
    """
    if ast is None:
        return QueryMetadata(complexity_score=0.0, pattern_signature="EMPTY")

    cfg = _load_complexity_config()
    weights: Dict[str, float] = cfg.get("complexity_weights", {})
    bounds: Dict[str, float] = cfg.get("normalization_bounds", {})

    clauses: Set[str] = set()
    unique_tables: Set[str] = set()
    counts: Dict[str, int] = {
        k: 0
        for k in (
            "num_tables",
            "num_predicates",
            "num_boolean_ops",
            "nesting_depth",
            "num_aggregates",
            "num_joins",
            "num_subqueries",
            "ctes",
            "unions",
            "windows",
            "laterals",
            "values",
            "qualify",
            "tablesample",
            "locking",
            "insert",
            "update",
            "delete",
            "merge",
            "returning",
            "aggregations",
            "case_statements",
            "distinct_on",
            "filter_agg",
        )
    }

    # ── Single walk: classify every node ────────────────────────────────────
    for node in ast.walk():
        if isinstance(node, exp.Select):
            clauses.add("SELECT")
            if node.args.get("distinct"):
                clauses.add("DISTINCT")
            # Nesting depth: count Subquery/CTE ancestors above this Select
            depth = 0
            curr = node.parent
            while curr:
                if isinstance(curr, (exp.Subquery, exp.CTE)):
                    depth += 1
                curr = curr.parent
            if depth > counts["nesting_depth"]:
                counts["nesting_depth"] = depth

        elif isinstance(node, exp.From):
            clauses.add("FROM")

        elif isinstance(node, exp.Where):
            clauses.add("WHERE")
            counts["num_predicates"] += 1

        elif isinstance(node, exp.Join):
            clauses.add("JOIN")
            counts["num_joins"] += 1
            counts["num_predicates"] += 1
            kind = (node.kind or "").upper()
            if kind in {"INNER", "LEFT", "RIGHT", "FULL", "CROSS"}:
                clauses.add(f"JOIN_{kind}")

        elif isinstance(node, exp.Group):
            clauses.add("GROUP")

        elif isinstance(node, exp.Order):
            clauses.add("ORDER")

        elif isinstance(node, exp.Having):
            clauses.add("HAVING")
            counts["num_predicates"] += 1

        elif isinstance(node, exp.Limit):
            clauses.add("LIMIT")

        elif isinstance(node, exp.Offset):
            clauses.add("OFFSET")

        elif isinstance(node, exp.Table):
            if node.name:
                unique_tables.add(node.name.lower())

        elif isinstance(node, (exp.And, exp.Or)):
            counts["num_boolean_ops"] += 1

        elif isinstance(node, exp.Union):
            clauses.add("UNION")
            counts["unions"] += 1

        elif isinstance(node, exp.Intersect):
            clauses.add("INTERSECT")
            counts["unions"] += 1

        elif isinstance(node, exp.Except):
            clauses.add("EXCEPT")
            counts["unions"] += 1

        elif isinstance(node, exp.CTE):
            clauses.add("CTE")
            counts["ctes"] += 1

        elif isinstance(node, exp.With):
            clauses.add("WITH")

        elif isinstance(node, exp.Distinct) and node.args.get("on"):
            clauses.add("DISTINCT_ON")
            counts["distinct_on"] += 1

        elif isinstance(node, (exp.Window, exp.WindowSpec)):
            clauses.add("WINDOW")
            counts["windows"] += 1

        elif isinstance(node, exp.Partition):
            clauses.add("PARTITION")

        elif isinstance(node, exp.Filter):
            clauses.add("FILTER")
            counts["filter_agg"] += 1

        elif isinstance(node, exp.Lateral):
            clauses.add("LATERAL")
            counts["laterals"] += 1

        elif isinstance(node, exp.Values):
            clauses.add("VALUES")
            counts["values"] += 1

        elif isinstance(node, exp.Qualify):
            clauses.add("QUALIFY")
            counts["qualify"] += 1

        elif isinstance(node, exp.TableSample):
            clauses.add("TABLESAMPLE")
            counts["tablesample"] += 1

        elif isinstance(node, exp.Lock):
            clauses.add("LOCKING")
            counts["locking"] += 1

        elif isinstance(node, exp.Subquery):
            clauses.add("SUBQUERY")
            counts["num_subqueries"] += 1

        elif isinstance(node, exp.Insert):
            clauses.add("INSERT")
            counts["insert"] += 1

        elif isinstance(node, exp.Update):
            clauses.add("UPDATE")
            counts["update"] += 1

        elif isinstance(node, exp.Delete):
            clauses.add("DELETE")
            counts["delete"] += 1

        elif isinstance(node, exp.Merge):
            clauses.add("MERGE")
            counts["merge"] += 1

        elif isinstance(node, exp.Returning):
            clauses.add("RETURNING")
            counts["returning"] += 1

        elif isinstance(node, exp.AggFunc):
            counts["aggregations"] += 1
            counts["num_aggregates"] += 1

        elif isinstance(node, exp.Case):
            counts["case_statements"] += 1

    counts["num_tables"] = len(unique_tables)

    # ── Complexity score  [0, 1]  ────────────────────────────────────────────
    def _norm(value: int, key: str) -> float:
        bound = float(bounds.get(key, 10.0))
        return min(float(value) / bound, 1.0) if bound > 0 else 0.0

    raw_score = (
        weights.get("nesting_depth", 0.0)
        * _norm(counts["nesting_depth"], "nesting_depth")
        + weights.get("num_joins", 0.0) * _norm(counts["num_joins"], "num_joins")
        + weights.get("num_subqueries", 0.0)
        * _norm(counts["num_subqueries"], "num_subqueries")
        + weights.get("num_predicates", 0.0)
        * _norm(counts["num_predicates"], "num_predicates")
        + weights.get("num_tables", 0.0) * _norm(counts["num_tables"], "num_tables")
        + weights.get("num_boolean_ops", 0.0)
        * _norm(counts["num_boolean_ops"], "num_boolean_ops")
        + weights.get("num_aggregates", 0.0)
        * _norm(counts["num_aggregates"], "num_aggregates")
    )
    # Normalise by actual weight sum so score stays in [0, 1] even if weights
    # don't sum to exactly 1.0.
    total_weight = sum(weights.values()) or 1.0
    complexity = raw_score / total_weight

    # ── Pattern signature ────────────────────────────────────────────────────
    ordered = [c for c in _CLAUSE_ORDER if c in clauses]
    extras = sorted(c for c in clauses if c not in _CLAUSE_ORDER)
    ordered.extend(extras)
    signature = "-".join(ordered) if ordered else "UNKNOWN"

    if len(signature) > 100:
        h = hashlib.md5(signature.encode()).hexdigest()[:16]
        signature = f"HASH_{h}"

    return QueryMetadata(
        complexity_score=round(complexity, 4),
        pattern_signature=signature,
        clauses_present=sorted(clauses),
        tables=sorted(unique_tables),
        num_joins=counts["num_joins"],
        num_subqueries=counts["num_subqueries"],
        num_ctes=counts["ctes"],
        num_aggregations=counts["aggregations"],
    )
