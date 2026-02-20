# Skill: set_op

## Description
Covers errors involving set operations: UNION, INTERSECT, and EXCEPT.
Common mistakes include using comma-separated queries instead of
UNION, column count or type mismatches between operands, and using
the wrong set operator for the intended logic.

## Core Approaches

### Approach 1: Missing UNION Operator
**When to use:** Tag is `set_op_union_missing`. Two SELECT statements
are written as if their results should be combined, but no UNION
(or UNION ALL) operator connects them.
**Steps:**
1. Identify the two SELECT blocks that should be unioned.
2. Insert `UNION` (for distinct rows) or `UNION ALL` (to keep
   duplicates) between them.

**Example fix:**
```sql
-- Before (two SELECTs with no connecting operator)
SELECT id, name FROM customers WHERE region = 'North'
SELECT id, name FROM customers WHERE region = 'South'

-- After
SELECT id, name FROM customers WHERE region = 'North'
UNION
SELECT id, name FROM customers WHERE region = 'South'
```

### Approach 2: Missing INTERSECT
**When to use:** Tag is `set_op_intersect_missing`. The question asks
for rows that appear in both result sets, but the SQL uses UNION or
a join instead.
**Steps:**
1. Replace UNION with INTERSECT.
2. Ensure both SELECT branches have the same number of columns and
   compatible types.

**Example fix:**
```sql
-- Before (should find customers who are also suppliers)
SELECT id FROM customers
UNION
SELECT id FROM suppliers

-- After
SELECT id FROM customers
INTERSECT
SELECT id FROM suppliers
```

### Approach 3: Missing EXCEPT
**When to use:** Tag is `set_op_except_missing`. The question asks
for rows in the first set that are not in the second, but the SQL
uses NOT IN or LEFT JOIN ... IS NULL instead of EXCEPT.
**Steps:**
1. Replace the NOT IN subquery or anti-join with EXCEPT.
2. Confirm column count and types match across both branches.

**Example fix:**
```sql
-- Before (verbose NOT IN approach)
SELECT id FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders)

-- After (idiomatic set operation)
SELECT id FROM customers
EXCEPT
SELECT customer_id FROM orders
```

### Approach 4: Column Count or Type Mismatch in Set Operation
**When to use:** PostgreSQL raises an error that the number of
columns or their types differ between the operands.
**Steps:**
1. Count the columns in each SELECT branch.
2. Align them by adding NULL casts for missing columns or casting
   mismatched types: `NULL::integer`, `NULL::text`, etc.

**Example fix:**
```sql
-- Before (left branch has 3 columns, right has 2)
SELECT id, name, email FROM customers
UNION
SELECT id, name FROM suppliers

-- After
SELECT id, name, email FROM customers
UNION
SELECT id, name, NULL::text FROM suppliers
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
