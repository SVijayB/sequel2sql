# -*- coding: utf-8 -*-
"""
Query Analyzer

Provides functions to analyze SQL query structure:
- Extract SQL clauses from AST
- Calculate complexity scores
- Generate pattern signatures
"""

from typing import List, Set, Any
import hashlib

from sqlglot import exp

from src.ast_parsers.errors import QueryMetadata


# =============================================================================
# SQL Clause Extraction
# =============================================================================

def extract_sql_clauses(ast: Any) -> List[str]:
    """
    Extract all SQL clauses present in the query from the AST.
    
    Args:
        ast: sqlglot Expression AST node
    
    Returns:
        List of clause names found (e.g., ['SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP', 'ORDER'])
    """
    if ast is None:
        return []
    
    clauses: Set[str] = set()
    
    # Walk the AST to find different clause types
    for node in ast.walk():
        # SELECT clause
        if isinstance(node, exp.Select):
            clauses.add("SELECT")
        
        # FROM clause
        if isinstance(node, exp.From):
            clauses.add("FROM")
        
        # WHERE clause
        if isinstance(node, exp.Where):
            clauses.add("WHERE")
        
        # JOIN clauses
        if isinstance(node, exp.Join):
            clauses.add("JOIN")
            # Check join type
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
        
        # CTE (WITH clause)
        if isinstance(node, exp.CTE):
            clauses.add("CTE")
        if isinstance(node, exp.With):
            clauses.add("WITH")
        
        # DISTINCT
        if isinstance(node, exp.Select):
            if node.args.get("distinct"):
                clauses.add("DISTINCT")
        
        # Subquery
        if isinstance(node, exp.Subquery):
            clauses.add("SUBQUERY")
    
    # Sort for consistent output
    return sorted(list(clauses))


def get_clause_for_node(node: Any) -> List[str]:
    """
    Determine which SQL clause(s) a node belongs to by walking up the AST.
    
    Args:
        node: sqlglot Expression node
    
    Returns:
        List of clause names that contain this node
    """
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
        
        # Walk up to parent
        current = getattr(current, 'parent', None)
    
    return sorted(list(clauses))


# =============================================================================
# Complexity Calculation
# =============================================================================

def calculate_complexity(ast: Any) -> int:
    """
    Calculate complexity score for a SQL query.
    
    Uses weighted scoring:
    - CTE: 2 points each
    - Subquery: 1 point each
    - Join: 1 point each
    - Aggregation function: 1 point each
    - Case statement: 1 point each
    - Union/Intersect/Except: 2 points each
    
    Args:
        ast: sqlglot Expression AST node
    
    Returns:
        Complexity score (integer)
    """
    if ast is None:
        return 0
    
    score = 0
    
    for node in ast.walk():
        # CTEs are more complex (weighted 2)
        if isinstance(node, exp.CTE):
            score += 2
        
        # Subqueries add complexity (weighted 1)
        if isinstance(node, exp.Subquery):
            score += 1
        
        # Joins add complexity (weighted 1)
        if isinstance(node, exp.Join):
            score += 1
        
        # Aggregation functions add complexity (weighted 1)
        if isinstance(node, exp.AggFunc):
            score += 1
        
        # Case statements add complexity (weighted 1)
        if isinstance(node, exp.Case):
            score += 1
        
        # Set operations are more complex (weighted 2)
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            score += 2
    
    return score


def count_query_elements(ast: Any) -> dict:
    """
    Count various elements in the query.
    
    Args:
        ast: sqlglot Expression AST node
    
    Returns:
        Dictionary with counts: {
            'joins': int,
            'subqueries': int,
            'ctes': int,
            'aggregations': int,
            'case_statements': int,
            'unions': int,
        }
    """
    if ast is None:
        return {
            'joins': 0,
            'subqueries': 0,
            'ctes': 0,
            'aggregations': 0,
            'case_statements': 0,
            'unions': 0,
        }
    
    counts = {
        'joins': 0,
        'subqueries': 0,
        'ctes': 0,
        'aggregations': 0,
        'case_statements': 0,
        'unions': 0,
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
    
    # Create a normalized signature from clause order
    # Main clauses in typical SQL order
    clause_order = [
        "WITH", "CTE", "SELECT", "DISTINCT", "FROM", "JOIN", "JOIN_INNER",
        "JOIN_LEFT", "JOIN_RIGHT", "JOIN_FULL", "JOIN_CROSS",
        "WHERE", "GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET",
        "UNION", "INTERSECT", "EXCEPT", "SUBQUERY"
    ]
    
    # Build signature in logical order
    signature_parts = []
    for clause in clause_order:
        if clause in clauses:
            signature_parts.append(clause)
    
    # Add any remaining clauses not in the standard order
    for clause in sorted(clauses):
        if clause not in clause_order:
            signature_parts.append(clause)
    
    signature = "-".join(signature_parts)
    
    # For very long signatures, create a hash
    if len(signature) > 100:
        signature_hash = hashlib.md5(signature.encode()).hexdigest()[:16]
        return f"HASH_{signature_hash}"
    
    return signature


# =============================================================================
# Combined Analysis
# =============================================================================

def analyze_query(ast: Any) -> QueryMetadata:
    """
    Perform complete query analysis and return QueryMetadata.
    
    Args:
        ast: sqlglot Expression AST node
    
    Returns:
        QueryMetadata object with all analysis results
    """
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