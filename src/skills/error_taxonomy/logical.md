# Skill: others

## Description
Covers logical and runtime errors that do not fit the other
categories: constraint violations (unique, foreign key, NOT NULL,
check), grouping/window function errors, missing ORDER BY when the
question implies ranked output, missing LIMIT, and unsupported
function calls.

## Core Approaches

### Approach 1: Missing ORDER BY
**When to use:** Tag is `others_order_by_missing`. The question asks
for "top N", "most recent", "ranked", or "sorted" results but no
ORDER BY is present.
**Steps:**
1. Identify the column and direction implied by the question
   (e.g. "most recent" → `ORDER BY created_at DESC`).
2. Add the ORDER BY clause before any LIMIT.

**Example fix:**
```sql
-- Before (no ordering for "most recent 5 orders")
SELECT * FROM orders LIMIT 5

-- After
SELECT * FROM orders ORDER BY created_at DESC LIMIT 5
```

### Approach 2: Missing LIMIT
**When to use:** Tag is `others_limit_missing`. The question asks for
"the top 1", "the single highest", or a specific count of rows but
no LIMIT is present.
**Steps:**
1. Determine how many rows the question expects.
2. Add `LIMIT N` after ORDER BY.

**Example fix:**
```sql
-- Before (question asked for the single most expensive product)
SELECT name, price FROM products ORDER BY price DESC

-- After
SELECT name, price FROM products ORDER BY price DESC LIMIT 1
```

### Approach 3: Duplicate Columns in SELECT
**When to use:** Tag is `others_duplicate_select`. The same column or
expression appears more than once in the SELECT list.
**Steps:**
1. Identify duplicated columns.
2. Remove all but one occurrence, or alias them if both are truly
   needed for different purposes.

**Example fix:**
```sql
-- Before
SELECT id, name, name FROM users

-- After
SELECT id, name FROM users
```

### Approach 4: Unsupported Function
**When to use:** Tag is `others_unsupported_function`. A function is
called that does not exist in PostgreSQL (e.g. MySQL-specific
functions like `GROUP_CONCAT`, `IFNULL`, `NOW()` used as `SYSDATE`).
**Steps:**
1. Identify the PostgreSQL equivalent:
   - `GROUP_CONCAT` → `STRING_AGG`
   - `IFNULL` → `COALESCE`
   - `SYSDATE` → `NOW()`
   - `DATE_FORMAT` → `TO_CHAR`
2. Rewrite the expression using the correct function.

**Example fix:**
```sql
-- Before (GROUP_CONCAT is MySQL-specific)
SELECT department, GROUP_CONCAT(name) FROM employees GROUP BY department

-- After
SELECT department, STRING_AGG(name, ',') FROM employees GROUP BY department
```

### Approach 5: Incorrect Foreign Key Relationship
**When to use:** Tag is `others_incorrect_foreign_key_relationship`.
The query joins tables along an incorrect relationship path (e.g.
joining A→C directly when the actual path is A→B→C).
**Steps:**
1. Use `describe_database_schema` to trace the actual foreign key
   relationships.
2. Add the intermediate join table(s) to traverse the correct path.

**Example fix:**
```sql
-- Before (orders does not link directly to products; needs order_items)
SELECT p.name FROM orders o
JOIN products p ON o.id = p.order_id

-- After
SELECT p.name FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
