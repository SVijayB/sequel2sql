# Skill: schema_link

## Description
Covers errors where the query references tables, columns, or
functions that do not exist in the database schema, or where column
references are ambiguous across multiple joined tables. Corresponds
to PostgreSQL SQLSTATE class 42 (undefined/ambiguous object) errors.

## Core Approaches

### Approach 1: Hallucinated Table Name
**When to use:** Tag is `schema_hallucination_table`. PostgreSQL
reports a table does not exist.
**Steps:**
1. Call `describe_database_schema` to list available tables.
2. Find the closest matching table name (check for plural/singular,
   underscores vs. spaces, abbreviated names).
3. Replace the non-existent table name with the correct one.

**Example fix:**
```sql
-- Before (table "user" does not exist, correct name is "users")
SELECT * FROM user WHERE id = 1

-- After
SELECT * FROM users WHERE id = 1
```

### Approach 2: Hallucinated Column Name
**When to use:** Tag is `schema_hallucination_col`. A column
referenced in SELECT, WHERE, JOIN, or GROUP BY does not exist on the
table.
**Steps:**
1. Call `describe_database_schema` for the relevant table(s).
2. Find the closest matching column (check abbreviations, different
   naming conventions, correct table).
3. Replace the non-existent column with the correct one.

**Example fix:**
```sql
-- Before ("username" does not exist, correct column is "user_name")
SELECT username FROM users WHERE id = 1

-- After
SELECT user_name FROM users WHERE id = 1
```

### Approach 3: Ambiguous Column Reference
**When to use:** Tag is `schema_ambiguous_col`. Multiple joined
tables have a column with the same name and the query does not
qualify it.
**Steps:**
1. Identify all tables in the FROM/JOIN clause.
2. Determine which table the ambiguous column belongs to for this
   query's intent.
3. Prefix the column with the correct table name or alias.

**Example fix:**
```sql
-- Before ("id" is ambiguous between orders and users)
SELECT id FROM orders JOIN users ON orders.user_id = users.id

-- After
SELECT orders.id FROM orders JOIN users ON orders.user_id = users.id
```

### Approach 4: Incorrect Foreign Key Column
**When to use:** Tag is `schema_incorrect_foreign_key`. The column
used for a join or foreign key reference does not match the actual
key column name.
**Steps:**
1. Inspect both tables' schemas to find the actual key columns.
2. Correct the join condition to use the right columns.

**Example fix:**
```sql
-- Before (orders.customer does not exist; correct is orders.user_id)
SELECT * FROM orders JOIN users ON orders.customer = users.id

-- After
SELECT * FROM orders JOIN users ON orders.user_id = users.id
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
