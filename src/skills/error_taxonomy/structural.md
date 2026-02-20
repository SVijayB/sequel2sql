# Skill: select

## Description
Covers errors in the SELECT clause itself: selecting incorrect or
extra columns that do not match the question intent, selecting
columns in the wrong order when a specific order is expected, and
selecting too many or too few values relative to what the question
asks for.

## Core Approaches

### Approach 1: Incorrect or Extra Columns Selected
**When to use:** Tag is `select_incorrect_extra_values`. The SELECT
list includes columns the question did not ask for, or omits columns
it did ask for.
**Steps:**
1. Re-read the question to determine the exact output columns
   expected.
2. Remove columns not asked for; add columns that are missing.
3. Check the schema to confirm all selected columns exist.

**Example fix:**
```sql
-- Before (question asked only for name and email, not phone)
SELECT name, email, phone FROM users WHERE active = TRUE

-- After
SELECT name, email FROM users WHERE active = TRUE
```

### Approach 2: Columns Selected in Wrong Order
**When to use:** Tag is `select_incorrect_order`. The question
specifies an output order (e.g. "return name then salary") but the
SELECT list has them reversed.
**Steps:**
1. Map the expected output order from the question.
2. Reorder the columns in the SELECT list to match.

**Example fix:**
```sql
-- Before (question asked for name then salary)
SELECT salary, name FROM employees ORDER BY name

-- After
SELECT name, salary FROM employees ORDER BY name
```

### Approach 3: Missing Alias for Computed Column
**When to use:** A computed expression in SELECT has no alias, making
the output column name unclear or causing downstream reference
errors.
**Steps:**
1. Add an AS alias to every computed expression or aggregate.

**Example fix:**
```sql
-- Before
SELECT department, COUNT(*), AVG(salary) FROM employees GROUP BY department

-- After
SELECT department, COUNT(*) AS employee_count, AVG(salary) AS avg_salary
FROM employees
GROUP BY department
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
