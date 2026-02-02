# -*- coding: utf-8 -*-
"""Query structure analysis: clauses, complexity, pattern signature."""

from typing import List, Set, Any
import hashlib

from sqlglot import exp

from ast_parsers.errors import QueryMetadata


def extract_sql_clauses(ast: Any) -> List[str]:
    """Return sorted list of clause names (SELECT, FROM, WHERE, JOIN, etc.)."""
    if ast is None:
        return []
    
    clauses: Set[str] = set()
    for node in ast.walk():
        if isinstance(node, exp.Select):
            clauses.add("SELECT")
        if isinstance(node, exp.From):
            clauses.add("FROM")
        if isinstance(node, exp.Where):
            clauses.add("WHERE")
        if isinstance(node, exp.Join):
            clauses.add("JOIN")
            if node.kind:
                join_type = node.kind.upper()
                if join_type in ["INNER", "LEFT", "RIGHT", "FULL", "CROSS"]:
                    clauses.add(f"JOIN_{join_type}")
        
        # GROUP BY clause
        if isinstance(node, exp.Group):
            clauses.add("GROUP")
        
        # ORDER BY clause
        if isinstance(node, exp.Order):
            clauses.add("ORDER")
        
        # HAVING clause
        if isinstance(node, exp.Having):
            clauses.add("HAVING")
        
        # LIMIT clause
        if isinstance(node, exp.Limit):
            clauses.add("LIMIT")
        
        # OFFSET clause
        if isinstance(node, exp.Offset):
            clauses.add("OFFSET")
        
        # UNION/INTERSECT/EXCEPT
        if isinstance(node, exp.Union):
            clauses.add("UNION")
        if isinstance(node, exp.Intersect):
            clauses.add("INTERSECT")
        if isinstance(node, exp.Except):
            clauses.add("EXCEPT")
        if isinstance(node, exp.CTE):
            clauses.add("CTE")
        if isinstance(node, exp.With):
            clauses.add("WITH")
        if isinstance(node, exp.Select):
            if node.args.get("distinct"):
                clauses.add("DISTINCT")
        
        if isinstance(node, exp.Distinct) and node.args.get("on"):
            clauses.add("DISTINCT_ON")
        
        # WINDOW / OVER (window functions)
        if isinstance(node, (exp.Window, exp.WindowSpec)):
            clauses.add("WINDOW")
        
        if isinstance(node, exp.Partition):
            clauses.add("PARTITION")
        
        # FILTER (Postgres aggregate filter: agg() FILTER (WHERE ...))
        if isinstance(node, exp.Filter):
            clauses.add("FILTER")
        
        if isinstance(node, exp.Lateral):
            clauses.add("LATERAL")
        
        # VALUES (values list / table value constructor)
        if isinstance(node, exp.Values):
            clauses.add("VALUES")
        
        if isinstance(node, exp.Qualify):
            clauses.add("QUALIFY")
        
        # TABLESAMPLE
        if isinstance(node, exp.TableSample):
            clauses.add("TABLESAMPLE")
        
        if isinstance(node, exp.Lock):
            clauses.add("LOCKING")
        
        # Subquery
        if isinstance(node, exp.Subquery):
            clauses.add("SUBQUERY")
        
        if isinstance(node, exp.Insert):
            clauses.add("INSERT")
        if isinstance(node, exp.Update):
            clauses.add("UPDATE")
        if isinstance(node, exp.Delete):
            clauses.add("DELETE")
        if isinstance(node, exp.Merge):
            clauses.add("MERGE")
        if isinstance(node, exp.Returning):
            clauses.add("RETURNING")
    
    return sorted(list(clauses))


def get_clause_for_node(node: Any) -> List[str]:
    """Return clause names containing this node (walk up AST)."""
    clauses: Set[str] = set()
    current = node
    
    while current is not None:
        if isinstance(current, exp.Select):
            clauses.add("SELECT")
        elif isinstance(current, exp.From):
            clauses.add("FROM")
        elif isinstance(current, exp.Where):
            clauses.add("WHERE")
        elif isinstance(current, exp.Join):
            clauses.add("JOIN")
        elif isinstance(current, exp.Group):
            clauses.add("GROUP")
        elif isinstance(current, exp.Order):
            clauses.add("ORDER")
        elif isinstance(current, exp.Having):
            clauses.add("HAVING")
        elif isinstance(current, exp.Limit):
            clauses.add("LIMIT")
        elif isinstance(current, exp.Offset):
            clauses.add("OFFSET")
        elif isinstance(current, exp.Union):
            clauses.add("UNION")
        elif isinstance(current, exp.Intersect):
            clauses.add("INTERSECT")
        elif isinstance(current, exp.Except):
            clauses.add("EXCEPT")
        elif isinstance(current, exp.CTE):
            clauses.add("CTE")
        elif isinstance(current, exp.With):
            clauses.add("WITH")
        elif isinstance(current, exp.Subquery):
            clauses.add("SUBQUERY")
        elif isinstance(current, exp.Distinct) and getattr(current, "args", {}).get("on"):
            clauses.add("DISTINCT_ON")
        elif isinstance(current, (exp.Window, exp.WindowSpec)):
            clauses.add("WINDOW")
        elif isinstance(current, exp.Partition):
            clauses.add("PARTITION")
        elif isinstance(current, exp.Filter):
            clauses.add("FILTER")
        elif isinstance(current, exp.Lateral):
            clauses.add("LATERAL")
        elif isinstance(current, exp.Values):
            clauses.add("VALUES")
        elif isinstance(current, exp.Qualify):
            clauses.add("QUALIFY")
        elif isinstance(current, exp.TableSample):
            clauses.add("TABLESAMPLE")
        elif isinstance(current, exp.Lock):
            clauses.add("LOCKING")
        elif isinstance(current, exp.Insert):
            clauses.add("INSERT")
        elif isinstance(current, exp.Update):
            clauses.add("UPDATE")
        elif isinstance(current, exp.Delete):
            clauses.add("DELETE")
        elif isinstance(current, exp.Merge):
            clauses.add("MERGE")
        elif isinstance(current, exp.Returning):
            clauses.add("RETURNING")
        
        # Walk up to parent
        current = getattr(current, 'parent', None)
    
    return sorted(list(clauses))


def calculate_complexity(ast: Any) -> int:
    """Weighted complexity: CTE 2, subquery/join/agg/case 1, union 2."""
    if ast is None:
        return 0
    
    score = 0
    for node in ast.walk():
        if isinstance(node, exp.CTE):
            score += 2
        
        # Subqueries add complexity (weighted 1)
        if isinstance(node, exp.Subquery):
            score += 1
        if isinstance(node, exp.Join):
            score += 1
        
        # Aggregation functions add complexity (weighted 1)
        if isinstance(node, exp.AggFunc):
            score += 1
        if isinstance(node, exp.Case):
            score += 1
        
        # Set operations are more complex (weighted 2)
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            score += 2
        if isinstance(node, (exp.Window, exp.WindowSpec)):
            score += 1
        
        # LATERAL adds complexity (weighted 1)
        if isinstance(node, exp.Lateral):
            score += 1
        if isinstance(node, exp.Qualify):
            score += 1
        
        # MERGE is complex (weighted 2)
        if isinstance(node, exp.Merge):
            score += 2
    
    return score


def count_query_elements(ast: Any) -> dict:
    """Count joins, subqueries, ctes, aggregations, etc."""
    if ast is None:
        return {
            'joins': 0,
            'subqueries': 0,
            'ctes': 0,
            'aggregations': 0,
            'case_statements': 0,
            'unions': 0,
            'windows': 0,
            'laterals': 0,
            'qualify': 0,
            'tablesample': 0,
            'locking': 0,
            'distinct_on': 0,
            'values': 0,
            'filter_agg': 0,
            'insert': 0,
            'update': 0,
            'delete': 0,
            'merge': 0,
            'returning': 0,
        }
    
    counts = {
        'joins': 0,
        'subqueries': 0,
        'ctes': 0,
        'aggregations': 0,
        'case_statements': 0,
        'unions': 0,
        'windows': 0,
        'laterals': 0,
        'qualify': 0,
        'tablesample': 0,
        'locking': 0,
        'distinct_on': 0,
        'values': 0,
        'filter_agg': 0,
        'insert': 0,
        'update': 0,
        'delete': 0,
        'merge': 0,
        'returning': 0,
    }
    
    for node in ast.walk():
        if isinstance(node, exp.Join):
            counts['joins'] += 1
        elif isinstance(node, exp.Subquery):
            counts['subqueries'] += 1
        elif isinstance(node, exp.CTE):
            counts['ctes'] += 1
        elif isinstance(node, exp.AggFunc):
            counts['aggregations'] += 1
        elif isinstance(node, exp.Case):
            counts['case_statements'] += 1
        elif isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            counts['unions'] += 1
        elif isinstance(node, (exp.Window, exp.WindowSpec)):
            counts['windows'] += 1
        elif isinstance(node, exp.Lateral):
            counts['laterals'] += 1
        elif isinstance(node, exp.Qualify):
            counts['qualify'] += 1
        elif isinstance(node, exp.TableSample):
            counts['tablesample'] += 1
        elif isinstance(node, exp.Lock):
            counts['locking'] += 1
        elif isinstance(node, exp.Distinct) and node.args.get("on"):
            counts['distinct_on'] += 1
        elif isinstance(node, exp.Values):
            counts['values'] += 1
        elif isinstance(node, exp.Filter):
            counts['filter_agg'] += 1
        elif isinstance(node, exp.Insert):
            counts['insert'] += 1
        elif isinstance(node, exp.Update):
            counts['update'] += 1
        elif isinstance(node, exp.Delete):
            counts['delete'] += 1
        elif isinstance(node, exp.Merge):
            counts['merge'] += 1
        elif isinstance(node, exp.Returning):
            counts['returning'] += 1
    
    return counts


# =============================================================================
# Pattern Signature Generation
# =============================================================================

def generate_pattern_signature(ast: Any) -> str:
    """
    Generate a structural fingerprint/signature for the query.
    
    Creates a normalized representation of the query structure:
    - Example: "SELECT-FROM-WHERE-JOIN-GROUP-ORDER"
    - Or hash-based signature for more complex queries
    
    Args:
        ast: sqlglot Expression AST node
    
    Returns:
        Pattern signature string
    """
    if ast is None:
        return "EMPTY"
    
    clauses = extract_sql_clauses(ast)
    
    if not clauses:
        return "UNKNOWN"
    clause_order = [
        "WITH", "CTE", "SELECT", "DISTINCT", "DISTINCT_ON",
        "FROM", "LATERAL", "JOIN", "JOIN_INNER", "JOIN_LEFT", "JOIN_RIGHT", "JOIN_FULL", "JOIN_CROSS",
        "TABLESAMPLE", "VALUES",
        "WHERE", "GROUP", "PARTITION", "FILTER", "HAVING",
        "WINDOW", "QUALIFY",
        "ORDER", "LIMIT", "OFFSET", "LOCKING",
        "UNION", "INTERSECT", "EXCEPT", "SUBQUERY",
        "INSERT", "UPDATE", "DELETE", "MERGE", "RETURNING",
    ]
    signature_parts = []
    for clause in clause_order:
        if clause in clauses:
            signature_parts.append(clause)
    for clause in sorted(clauses):
        if clause not in clause_order:
            signature_parts.append(clause)
    
    signature = "-".join(signature_parts)
    
    # For very long signatures, create a hash
    if len(signature) > 100:
        signature_hash = hashlib.md5(signature.encode()).hexdigest()[:16]
        return f"HASH_{signature_hash}"
    
    return signature


def analyze_query(ast: Any) -> QueryMetadata:
    """QueryMetadata: complexity, signature, clauses, counts."""
    if ast is None:
        return QueryMetadata(
            complexity_score=0,
            pattern_signature="EMPTY",
            clauses_present=[],
            num_joins=0,
            num_subqueries=0,
            num_ctes=0,
            num_aggregations=0,
        )
    
    clauses = extract_sql_clauses(ast)
    complexity = calculate_complexity(ast)
    signature = generate_pattern_signature(ast)
    counts = count_query_elements(ast)
    
    return QueryMetadata(
        complexity_score=complexity,
        pattern_signature=signature,
        clauses_present=clauses,
        num_joins=counts['joins'],
        num_subqueries=counts['subqueries'],
        num_ctes=counts['ctes'],
        num_aggregations=counts['aggregations'],
    )
