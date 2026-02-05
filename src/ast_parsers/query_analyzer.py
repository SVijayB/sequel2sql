# -*- coding: utf-8 -*-
"""Query structure analysis. See README.md for logic details."""

from typing import List, Set, Any, Dict, Tuple
import hashlib
import json
import os
import sys
from collections import defaultdict

from sqlglot import exp

from ast_parsers.errors import QueryMetadata

# Load complexity configuration
def _load_complexity_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data", "complexity_config.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {data_path} not found.", file=sys.stderr)
        return {}

_COMPLEXITY_CONFIG = _load_complexity_config()
_WEIGHTS = _COMPLEXITY_CONFIG.get("complexity_weights", {})
_BOUNDS = _COMPLEXITY_CONFIG.get("normalization_bounds", {})



def _analyze_ast_single_pass(ast: Any) -> Tuple[Set[str], float, Dict[str, int]]:
    """
    Single pass AST analysis. See README.md.
    
    Returns:
        (clauses, complexity, counts)
    """
    clauses: Set[str] = set()
    # counts: Dict[str, int] = defaultdict(int) <- causing issues with Pyre
    counts: Dict[str, int] = {}
    
    # Initialize all keys to 0
    keys_to_init = [
        'num_tables', 'num_predicates', 'num_boolean_ops', 'nesting_depth',
        'num_aggregates', 'num_joins', 'num_subqueries', 'joins', 'unions',
        'ctes', 'windows', 'laterals', 'values', 'qualify', 'tablesample',
        'locking', 'subqueries', 'insert', 'update', 'delete', 'merge',
        'returning', 'aggregations', 'case_statements', 'distinct_on', 'filter_agg'
    ]
    for k in keys_to_init:
        counts[k] = 0
    
    if ast is None:
        return clauses, 0.0, counts

    unique_tables = set()
    max_nesting_depth = 0


    max_nesting_depth = 0

    # Depth calculation: see README.md for strategy
    
    for node in ast.walk():
        # --- Clauses ---
        if isinstance(node, exp.Select):
            clauses.add("SELECT")
            # Safe access to args
            if hasattr(node, "args") and node.args.get("distinct"):
                clauses.add("DISTINCT")
        if isinstance(node, exp.From):
            clauses.add("FROM")
        if isinstance(node, exp.Where):
            clauses.add("WHERE")
            counts['num_predicates'] += 1
        if isinstance(node, exp.Join):
            clauses.add("JOIN")
            counts['joins'] += 1
            counts['num_joins'] += 1
            counts['num_predicates'] += 1
            if node.kind:
                join_type = node.kind.upper()
                if join_type in ["INNER", "LEFT", "RIGHT", "FULL", "CROSS"]:
                    clauses.add(f"JOIN_{join_type}")
        if isinstance(node, exp.Group):
            clauses.add("GROUP")
        if isinstance(node, exp.Order):
            clauses.add("ORDER")
        if isinstance(node, exp.Having):
            clauses.add("HAVING")
            counts['num_predicates'] += 1
        if isinstance(node, exp.Limit):
            clauses.add("LIMIT")
        if isinstance(node, exp.Offset):
            clauses.add("OFFSET")
        
        # --- Tables ---
        if isinstance(node, exp.Table):
            table_name = node.name
            if table_name:
                unique_tables.add(table_name)

        # --- Boolean Ops ---
        if isinstance(node, (exp.And, exp.Or)):
            counts['num_boolean_ops'] += 1

        if isinstance(node, exp.Union):
            clauses.add("UNION")
            counts['unions'] += 1
        if isinstance(node, exp.Intersect):
            clauses.add("INTERSECT")
            counts['unions'] += 1
        if isinstance(node, exp.Except):
            clauses.add("EXCEPT")
            counts['unions'] += 1
            
        if isinstance(node, exp.CTE):
            clauses.add("CTE")
            counts['ctes'] += 1
        if isinstance(node, exp.With):
            clauses.add("WITH")
            
        if isinstance(node, exp.Distinct) and hasattr(node, "args") and node.args.get("on"):
            clauses.add("DISTINCT_ON")
            counts['distinct_on'] += 1
            
        # Window / Over
        if isinstance(node, (exp.Window, exp.WindowSpec)):
            clauses.add("WINDOW")
            counts['windows'] += 1
        
        if isinstance(node, exp.Partition):
            clauses.add("PARTITION")
            
        if isinstance(node, exp.Filter):
            clauses.add("FILTER")
            counts['filter_agg'] += 1
            
        if isinstance(node, exp.Lateral):
            clauses.add("LATERAL")
            counts['laterals'] += 1
            
        if isinstance(node, exp.Values):
            clauses.add("VALUES")
            counts['values'] += 1
            
        if isinstance(node, exp.Qualify):
            clauses.add("QUALIFY")
            counts['qualify'] += 1
            
        if isinstance(node, exp.TableSample):
            clauses.add("TABLESAMPLE")
            counts['tablesample'] += 1
            
        if isinstance(node, exp.Lock):
            clauses.add("LOCKING")
            counts['locking'] += 1
            
        if isinstance(node, exp.Subquery):
            clauses.add("SUBQUERY")
            counts['subqueries'] += 1
            counts['num_subqueries'] += 1
            
        if isinstance(node, exp.Insert):
            clauses.add("INSERT")
            counts['insert'] += 1
        if isinstance(node, exp.Update):
            clauses.add("UPDATE")
            counts['update'] += 1
        if isinstance(node, exp.Delete):
            clauses.add("DELETE")
            counts['delete'] += 1
        if isinstance(node, exp.Merge):
            clauses.add("MERGE")
            counts['merge'] += 1
        if isinstance(node, exp.Returning):
            clauses.add("RETURNING")
            counts['returning'] += 1
            
        if isinstance(node, exp.AggFunc):
            counts['aggregations'] += 1
            counts['num_aggregates'] += 1
            
        if isinstance(node, exp.Case):
            counts['case_statements'] += 1

    # Post-loop calculations
    counts['num_tables'] = len(unique_tables)
    
    # Depth calculation (checking all nodes for max depth of subquery nesting)
    # Using a fresh walk or just the cached understanding?
    # Let's check depth of all SELECTs found in the tree (as they represent query scopes)
    if ast:
        max_depth = 0
        for node in ast.find_all(exp.Select):
            depth = 0
            curr = node.parent
            while curr:
                if isinstance(curr, (exp.Subquery, exp.CTE)):
                    depth += 1
                curr = curr.parent
            if depth > max_depth:
                max_depth = depth
        counts['nesting_depth'] = max_depth

    # --- Complexity Calculation (See README.md) ---
    
    def norm(value, metric_name):
        bound = _BOUNDS.get(metric_name, 10.0)
        return min(float(value) / float(bound), 1.0) if bound != 0 else 0.0

    score = 0.0
    score += _WEIGHTS.get("nesting_depth", 0.0) * norm(counts['nesting_depth'], "nesting_depth")
    score += _WEIGHTS.get("num_joins", 0.0) * norm(counts['num_joins'], "num_joins")
    score += _WEIGHTS.get("num_subqueries", 0.0) * norm(counts['num_subqueries'], "num_subqueries")
    score += _WEIGHTS.get("num_predicates", 0.0) * norm(counts['num_predicates'], "num_predicates")
    score += _WEIGHTS.get("num_tables", 0.0) * norm(counts['num_tables'], "num_tables")
    score += _WEIGHTS.get("num_boolean_ops", 0.0) * norm(counts['num_boolean_ops'], "num_boolean_ops")
    score += _WEIGHTS.get("num_aggregates", 0.0) * norm(counts['num_aggregates'], "num_aggregates")
    
    return clauses, score, counts


def extract_sql_clauses(ast: Any) -> List[str]:
    """Return sorted list of clause names (SELECT, FROM, WHERE, JOIN, etc.)."""
    clauses, _, _ = _analyze_ast_single_pass(ast)
    return sorted(list(clauses))


def calculate_complexity(ast: Any) -> float:
    """Normalized complexity score (0-1)."""
    _, complexity, _ = _analyze_ast_single_pass(ast)
    return complexity


def count_query_elements(ast: Any) -> dict:
    """Count joins, subqueries, ctes, aggregations, etc."""
    _, _, counts = _analyze_ast_single_pass(ast)
    
    # Ensure all keys are present for API consistency
    default_keys = [
        'joins', 'subqueries', 'ctes', 'aggregations', 'case_statements',
        'unions', 'windows', 'laterals', 'qualify', 'tablesample',
        'locking', 'distinct_on', 'values', 'filter_agg', 'insert',
        'update', 'delete', 'merge', 'returning',
        # New keys exposed if needed, or just kept internal?
        # Let's expose them if they are useful, but existing API might expect specific keys.
        # We will keep the legacy keys populated (joins, subqueries etc) above.
    ]
    for key in default_keys:
        if key not in counts:
            counts[key] = 0
            
    return counts


# =============================================================================
# Pattern Signature Generation
# =============================================================================

def generate_pattern_signature(ast: Any, clauses: List[str] = None) -> str:
    """Structural signature. See README.md."""
    if clauses is None:
        if ast is None:
            return "EMPTY"
        clauses = extract_sql_clauses(ast)
    
    # Check for empty clauses list even if ast was not None (or pre-computed list was empty)
    if not clauses:
        if ast is None: # Double check to match original logic if passed directly
             return "EMPTY"
        return "UNKNOWN"
    
    # Use alphabetical sort (clauses input is expected to be sorted, but ensure it)
    # If it came from extract_sql_clauses it is sorted. 
    # If passed from analyze_query it is sorted.
    signature = "-".join(clauses)
    
    # For very long signatures, create a hash
    if len(signature) > 100:
        signature_hash = hashlib.md5(signature.encode()).hexdigest()[:16]
        return f"HASH_{signature_hash}"
    
    return signature


def analyze_query(ast: Any) -> QueryMetadata:
    """QueryMetadata: complexity, signature, clauses, counts."""
    clauses_set, complexity, counts = _analyze_ast_single_pass(ast)
    
    clauses = sorted(list(clauses_set))
    # Optimization: Pass pre-computed clauses to avoid re-traversal
    signature = generate_pattern_signature(ast, clauses=clauses)
    
    # Ensure keys exist
    joins = counts.get('joins', 0)
    subqueries = counts.get('subqueries', 0)
    ctes = counts.get('ctes', 0)
    aggregations = counts.get('aggregations', 0)
    
    return QueryMetadata(
        complexity_score=complexity,
        pattern_signature=signature,
        clauses_present=clauses,
        num_joins=joins,
        num_subqueries=subqueries,
        num_ctes=ctes,
        num_aggregations=aggregations,
    )
