# Skill: join

## Description
Covers errors in JOIN construction: missing JOIN conditions (causing
a cross join), wrong join type (INNER vs. LEFT vs. RIGHT), extra
tables included in FROM/JOIN that are never used, or incorrect
column names used in ON conditions.

## Core Approaches

### Approach 1: Missing JOIN Condition
**When to use:** Tag is `join_missing_join`. Two tables appear in the
FROM clause but no ON condition links them, producing a cartesian
product.
**Steps:**
1. Identify the foreign key relationship between the two tables using
   `describe_database_schema`.
2. Add an explicit JOIN ... ON clause with the correct key columns.

**Example fix:**
```sql
-- Before (cross join between orders and users)
SELECT * FROM orders, users WHERE orders.status = 'active'

-- After
SELECT * FROM orders
JOIN users ON orders.user_id = users.id
WHERE orders.status = 'active'
```

### Approach 2: Wrong Join Type
**When to use:** Tag is `join_wrong_type`. The query uses INNER JOIN
but some rows are missing because they have no match in the right
table (should be LEFT JOIN), or vice versa.
**Steps:**
1. Determine if all rows from the left table should appear regardless
   of a match in the right table.
2. Switch INNER JOIN → LEFT JOIN (or RIGHT JOIN) as appropriate.

**Example fix:**
```sql
-- Before (customers with no orders are excluded)
SELECT c.name, o.total
FROM customers
INNER JOIN orders o ON c.id = o.customer_id

-- After
SELECT c.name, o.total
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
```

### Approach 3: Unused Table in FROM/JOIN
**When to use:** Tag is `join_extra_table`. A table is listed in FROM
or JOIN but none of its columns appear anywhere in the query.
**Steps:**
1. Remove the unused table from the FROM/JOIN clause.
2. Remove any associated ON condition that referenced only that table.

**Example fix:**
```sql
-- Before (categories table is unused)
SELECT p.name, p.price
FROM products p
JOIN categories c ON p.category_id = c.id
JOIN inventory i ON p.id = i.product_id

-- After (if inventory is also unused)
SELECT p.name, p.price
FROM products p
JOIN categories c ON p.category_id = c.id
```

### Approach 4: Incorrect Column in ON Condition
**When to use:** Tag is `join_incorrect_col`. The ON clause uses a
column that does not exist on one of the joined tables.
**Steps:**
1. Inspect both tables' schemas.
2. Correct the column name(s) in the ON condition.

**Example fix:**
```sql
-- Before (orders has no column "uid"; correct is "user_id")
SELECT * FROM orders JOIN users ON orders.uid = users.id

-- After
SELECT * FROM orders JOIN users ON orders.user_id = users.id
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
