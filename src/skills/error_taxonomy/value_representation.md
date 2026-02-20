# Skill: value

## Description
Covers errors where a hardcoded literal is used instead of a column
reference where a column was intended, or where the format of a
literal value is incompatible with the column's data type (e.g. wrong
date format, integer vs. string quoting).

## Core Approaches

### Approach 1: Hardcoded Literal Instead of Column
**When to use:** Tag is `value_hardcoded_value`. A SELECT list or
expression contains a constant string or number where a column name
was clearly intended.
**Steps:**
1. Identify the literal that should be a column reference.
2. Check the table schema to confirm the correct column name.
3. Replace the literal with the column reference.

**Example fix:**
```sql
-- Before ('active' hardcoded where a column reference was intended)
SELECT id, 'active' FROM users

-- After
SELECT id, status FROM users
```

### Approach 2: Value Format Incompatible With Column Type
**When to use:** Tag is `value_format_wrong`. The literal's format
does not match what PostgreSQL expects for that column type.
**Steps:**
1. Determine the column's PostgreSQL data type.
2. Reformat the literal to match:
   - Dates: `'YYYY-MM-DD'`
   - Timestamps: `'YYYY-MM-DD HH:MM:SS'`
   - Booleans: `TRUE` / `FALSE` (no quotes)
   - Integers: no quotes
   - UUIDs: `'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'`

**Example fix:**
```sql
-- Before (date in wrong format for PostgreSQL)
SELECT * FROM events WHERE event_date = '05/14/2023'

-- After
SELECT * FROM events WHERE event_date = '2023-05-14'
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
