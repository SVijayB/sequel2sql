# Skill: syntax

## Description
Covers malformed SQL such as misspelled keywords, missing or extra
commas, unbalanced parentheses, trailing delimiters, unterminated
string literals, and incorrect clause ordering. These are caught by
the sqlglot AST parser before the query reaches PostgreSQL.

## Core Approaches

### Approach 1: Keyword Typo Correction
**When to use:** Tag is `syntax_error`, `syntax_keyword_misuse`, or
`syntax_invalid_token`. The keyword itself is misspelled or wrong.
**Steps:**
1. Identify the misspelled keyword (e.g. `SELCT`, `FORM`, `WHER`,
   `GORUP BY`).
2. Replace with the correct spelling.
3. Re-validate with `validate_query`.

**Example fix:**
```sql
-- Before
SELCT name FORM users WHER id = 1

-- After
SELECT name FROM users WHERE id = 1
```

### Approach 2: Trailing Delimiter Removal
**When to use:** Tag is `syntax_trailing_delimiter`. A comma appears
immediately before a clause keyword.
**Steps:**
1. Find the trailing comma preceding `FROM`, `WHERE`, `GROUP BY`,
   `ORDER BY`, or `HAVING`.
2. Remove the comma.

**Example fix:**
```sql
-- Before
SELECT name, age, FROM users

-- After
SELECT name, age FROM users
```

### Approach 3: Unbalanced Parentheses
**When to use:** Tag is `syntax_unbalanced_tokens`. Opening and
closing parentheses counts do not match.
**Steps:**
1. Count `(` and `)` in the query.
2. Locate the clause where the mismatch first occurs.
3. Add or remove the missing parenthesis.

**Example fix:**
```sql
-- Before
SELECT * FROM users WHERE (id = 1 AND name = 'Alice'

-- After
SELECT * FROM users WHERE (id = 1 AND name = 'Alice')
```

### Approach 4: Unterminated String Literal
**When to use:** Tag is `syntax_unterminated_string`. A single-quote
is opened but never closed, or an odd number of single quotes exists.
**Steps:**
1. Find the unclosed string literal.
2. Add the missing closing single quote.
3. If the string itself needs a literal quote, escape it as `''`.

**Example fix:**
```sql
-- Before
SELECT * FROM users WHERE name = 'O'Brien'

-- After
SELECT * FROM users WHERE name = 'O''Brien'
```

## Learned Examples
<!-- MAX_EXAMPLES=10 -->
