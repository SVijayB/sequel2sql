# Skill: subquery

## Description
Covers errors in subquery construction: subqueries that are written
but their result is never referenced, subqueries that are needed but
missing, and correlation errors where an inner subquery references an
outer alias incorrectly.

## Core Approaches

### Approach 1: Unused Subquery
**When to use:** Tag is `subquery_unused_subquery`. A subquery
appears in the FROM clause or CTE but its alias is never used
elsewhere in the query.
**Steps:**
1. Check whether the subquery result is referenced in the outer
   SELECT, WHERE, JOIN, or GROUP BY.
2. If not needed: remove the entire subquery.
3. If needed: add the alias reference where the subquery's output
   should be consumed.

**Example fix:**
```sql
-- Before (subquery result "recent" never used)
SELECT u.name FROM users u,
  (SELECT id FROM orders WHERE created_at > NOW() - INTERVAL '7 days') recent

-- After
SELECT u.name
FROM users u
WHERE u.id IN (
  SELECT user_id FROM orders
  WHERE created_at > NOW() - INTERVAL '7 days'
)
```

### Approach 2: Missing Subquery
**When to use:** Tag is `subquery_missing`. The question implies a
multi-step or filtered aggregation that needs a subquery but the SQL
attempts it in a single flat query.
**Steps:**
1. Identify the intermediate result that must be computed first.
2. Write an inner subquery or CTE that produces that result.
3. Reference it in the outer query.

**Example fix:**
```sql
-- Before (cannot filter on aggregate directly without subquery)
SELECT department, avg_salary
FROM employees
WHERE AVG(salary) > 70000
GROUP BY department

-- After
SELECT department, avg_salary
FROM (
  SELECT department, AVG(salary) AS avg_salary
  FROM employees
  GROUP BY department
) dept_avgs
WHERE avg_salary > 70000
```

### Approach 3: Subquery Correlation Error
**When to use:** Tag is `subquery_correlation_error`. The inner
subquery references an outer alias that is not in scope, or the
correlation column name is wrong.
**Steps:**
1. Identify the outer table alias the inner query is trying to
   reference.
2. Confirm the alias is defined in the outer FROM/JOIN clause.
3. Correct the column or alias name in the inner subquery's WHERE.

**Example fix:**
```sql
-- Before (outer alias "o" not defined at the subquery level)
SELECT * FROM orders
WHERE amount > (
  SELECT AVG(amount) FROM orders WHERE user_id = o.user_id
)

-- After
SELECT * FROM orders o
WHERE amount > (
  SELECT AVG(amount) FROM orders WHERE user_id = o.user_id
)
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
