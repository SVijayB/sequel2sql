# Skill: aggregation

## Description
Covers errors related to aggregate functions (COUNT, SUM, AVG, MIN,
MAX): using aggregates without a required GROUP BY clause, missing
columns in GROUP BY, misusing HAVING in place of WHERE, and using
HAVING without GROUP BY.

## Core Approaches

### Approach 1: Aggregation Without GROUP BY
**When to use:** Tag is `aggregation_agg_no_groupby`. An aggregate
function is applied with non-aggregated columns in SELECT but no
GROUP BY is present.
**Steps:**
1. Identify all non-aggregated columns in the SELECT list.
2. Add a GROUP BY clause listing every non-aggregated column.

**Example fix:**
```sql
-- Before (department is non-aggregated, no GROUP BY)
SELECT department, COUNT(*) FROM employees

-- After
SELECT department, COUNT(*) FROM employees GROUP BY department
```

### Approach 2: Missing Column in GROUP BY
**When to use:** Tag is `aggregation_groupby_missing_col`. GROUP BY
exists but not all non-aggregated SELECT columns are listed in it.
**Steps:**
1. List every column in SELECT that is not inside an aggregate.
2. Add any missing columns to the GROUP BY clause.

**Example fix:**
```sql
-- Before (location missing from GROUP BY)
SELECT department, location, COUNT(*)
FROM employees
GROUP BY department

-- After
SELECT department, location, COUNT(*)
FROM employees
GROUP BY department, location
```

### Approach 3: HAVING Without GROUP BY
**When to use:** Tag is `aggregation_having_without_groupby`. HAVING
is used but there is no GROUP BY clause.
**Steps:**
1. Determine whether the intent requires grouping.
2. If yes: add the missing GROUP BY clause.
3. If no (simple scalar filter): replace HAVING with WHERE.

**Example fix:**
```sql
-- Before (HAVING used without GROUP BY)
SELECT department, COUNT(*) FROM employees
HAVING COUNT(*) > 5

-- After
SELECT department, COUNT(*) FROM employees
GROUP BY department
HAVING COUNT(*) > 5
```

### Approach 4: HAVING vs. WHERE Confusion
**When to use:** Tag is `aggregation_having_vs_where`. The condition
filters on a non-aggregated column but is placed in HAVING instead
of WHERE.
**Steps:**
1. Check whether the condition involves an aggregate function or a
   plain column.
2. Move plain-column conditions to WHERE; keep aggregate conditions
   in HAVING.

**Example fix:**
```sql
-- Before (status is a plain column, not an aggregate)
SELECT department, COUNT(*)
FROM employees
GROUP BY department
HAVING status = 'active'

-- After
SELECT department, COUNT(*)
FROM employees
WHERE status = 'active'
GROUP BY department
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->

<!-- entry_start -->
### Example 1 — 2026-02-18
**Original (broken):**
```sql
SELECT School FROM schools GROUP BY School HAVING COUNT() > 1 ORDER BY COUNT() DESC;
```
**Fixed:**
```sql
SELECT school FROM schools WHERE county IN ('Alameda', 'Contra Costa') AND school IS NOT NULL GROUP BY school HAVING COUNT(DISTINCT county) = 2;
```
**Approach used:** Used WHERE IN with GROUP BY and HAVING COUNT(DISTINCT ...) = N to find entities associated with multiple specific categories.

---
<!-- entry_end -->
