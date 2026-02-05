#!/usr/bin/env python
"""Run 1–2 complex queries through syntax/schema validation and error-context pipeline."""

import os
import sys

# Allow importing ast_parsers from src when run as script (e.g. python tests/run_complex_queries.py)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_root, "src"))

from ast_parsers import (
    validate_syntax,
    validate_schema,
    validate_query,
    build_error_context,
    analyze_query,
    extract_sql_clauses,
    calculate_complexity,
    generate_pattern_signature,
)

# Schema for schema validation
SCHEMA = {
    "users": {"id": "int", "name": "text", "email": "text", "created_at": "timestamp"},
    "orders": {"id": "int", "user_id": "int", "total": "decimal", "status": "text"},
    "order_items": {"id": "int", "order_id": "int", "product_id": "int", "qty": "int"},
    "products": {"id": "int", "name": "text", "price": "decimal"},
}

# Query 1: CTEs, multiple joins, aggregation, HAVING, ORDER BY, LIMIT
QUERY_1 = """
WITH user_totals AS (
    SELECT u.id, u.name, COUNT(o.id) AS order_count, SUM(o.total) AS total_spent
    FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
    WHERE o.status = 'completed' OR o.id IS NULL
    GROUP BY u.id, u.name
),
top_users AS (
    SELECT id, name, order_count, total_spent
    FROM user_totals
    WHERE total_spent > 100
)
SELECT tu.name, tu.order_count, tu.total_spent,
       (SELECT COUNT(*) FROM order_items oi JOIN orders o ON oi.order_id = o.id WHERE o.user_id = tu.id) AS item_count
FROM top_users tu
ORDER BY tu.total_spent DESC
LIMIT 10
"""

# Query 2: Subqueries, multiple joins, window-like pattern
QUERY_2 = """
SELECT o.id, o.user_id, o.total,
       u.name,
       (SELECT SUM(oi.qty) FROM order_items oi WHERE oi.order_id = o.id) AS total_items,
       (SELECT name FROM products p WHERE p.id = (SELECT product_id FROM order_items WHERE order_id = o.id LIMIT 1)) AS first_product
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.total > (SELECT AVG(total) FROM orders)
ORDER BY o.total DESC
"""

def run_one(label: str, sql: str, use_schema: bool = True) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print("SQL (first 200 chars):", sql.strip()[:200] + "..." if len(sql) > 200 else sql.strip())
    print()

    # Syntax
    syn = validate_syntax(sql)
    print("Syntax:", "OK" if syn.valid else "FAIL")
    if not syn.valid:
        for e in syn.errors:
            print("  -", e.tag, ":", e.message[:80])
        return
    if syn.ast:
        clauses = extract_sql_clauses(syn.ast)
        comp = calculate_complexity(syn.ast)
        sig = generate_pattern_signature(syn.ast)
        print("  Clauses:", ", ".join(clauses[:12]), "..." if len(clauses) > 12 else "")
        print("  Complexity:", comp, "| Signature:", sig[:60] + "..." if len(sig) > 60 else sig)

    # Schema (if requested)
    if use_schema:
        sch = validate_schema(sql, schema=SCHEMA)
        print("Schema:", "OK" if sch.valid else "FAIL")
        if not sch.valid:
            for e in sch.errors:
                print("  -", e.tag, ":", e.message[:80])
    else:
        sch = validate_query(sql)
        print("Schema: (skipped)")

    # Error context from a fake “exception” (message only)
    class FakeErr:
        def __str__(self):
            return "ERROR: 42703: column \"nonexistent\" does not exist"
    ctx = build_error_context(sql, ast=syn.ast if syn.ast else None, error=FakeErr())
    print("ErrorContext (fake 42703): sqlstate =", ctx.sqlstate, "| tags =", [t.tag for t in ctx.tags][:5], "..." if len(ctx.tags) > 5 else [t.tag for t in ctx.tags])

def main():
    print("Complex query tests (syntax + schema + error context)")
    run_one("Query 1: CTEs, joins, aggregation, subquery, ORDER BY, LIMIT", QUERY_1)
    run_one("Query 2: Subqueries, JOIN, correlated subquery, ORDER BY", QUERY_2)
    print("\nDone.")

if __name__ == "__main__":
    main()
