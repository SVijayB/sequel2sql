# Skill: filter

## Description
Covers errors in WHERE clause conditions: missing WHERE clauses that
the question implies, conditions that reference the wrong column, and
type mismatches between a column's data type and the comparison value.

## Core Approaches

### Approach 1: Missing WHERE Clause
**When to use:** Tag is `filter_missing_where`. The natural language
question implies a filter (e.g. "find active users", "orders from
2023") but the SQL has no WHERE clause.
**Steps:**
1. Identify the filter condition from the question intent.
2. Determine the correct column and value from the schema.
3. Add the WHERE clause.

**Example fix:**
```sql
-- Before (question asked for active users only)
SELECT * FROM users

-- After
SELECT * FROM users WHERE status = 'active'
```

### Approach 2: Condition on Wrong Column
**When to use:** Tag is `filter_condition_wrong_col`. The WHERE
clause filters on a column that is not the right one for this
question's intent.
**Steps:**
1. Re-read the question to identify which attribute is being
   filtered.
2. Find the correct column in the schema.
3. Replace the wrong column name in the WHERE condition.

**Example fix:**
```sql
-- Before (filtering by name instead of email)
SELECT * FROM users WHERE name = 'alice@example.com'

-- After
SELECT * FROM users WHERE email = 'alice@example.com'
```

### Approach 3: Type Mismatch in WHERE
**When to use:** Tag is `filter_condition_type_mismatch`. The
comparison value's type does not match the column's data type (e.g.
comparing an integer column to a quoted string).
**Steps:**
1. Check the column's data type via `describe_database_schema`.
2. Remove quotes if the column is numeric, or add quotes if it is
   text.
3. For dates, ensure the value uses ISO-8601 format `'YYYY-MM-DD'`.

**Example fix:**
```sql
-- Before (user_id is INTEGER, not VARCHAR)
SELECT * FROM orders WHERE user_id = '42'

-- After
SELECT * FROM orders WHERE user_id = 42
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
