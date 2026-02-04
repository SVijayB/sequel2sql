# AST Parsers Documentation

## Complexity Scoring

The complexity scoring system evaluates SQL queries based on structural features and normalizes the score to a 0-1 range.

### Formula
Score = Σ (Weight_i * Normalize(Count_i))

Where `Normalize(x) = min(x / Bound, 1.0)`

### Configuration
Weights and normalization bounds are defined in `data/complexity_config.json`.

**Metrics Tracked:**
- `nesting_depth`: Depth of subqueries/CTEs.
- `num_joins`: Explicit JOIN clauses.
- `num_subqueries`: Subquery expressions.
- `num_predicates`: WHERE, HAVING, ON conditions.
- `num_tables`: Unique table references.
- `num_boolean_ops`: AND/OR operators.
- `num_aggregates`: Aggregation functions.

## Pattern Signature
Generates a structural fingerprint (e.g., `SELECT-FROM-JOIN-WHERE`) to identify query shapes. Long signatures are hashed.

## Error Taxonomy
Error tags are dynamically loaded from `data/error_data.json` and categorized into:
- Syntax
- Semantic (Schema)
- Logical
- Join Related
- Aggregation
- Structural

## Analysis Logic
The `query_analyzer.py` module performs a single-pass traversal of the AST to collect:
1. **Clauses**: presence of `SELECT`, `JOIN`, `CTE`, etc.
2. **Counts**: occurrences of tables, predicates, ops.
3. **Depth**: calculated via post-traversal analysis or node inspection.

## Data Models
- **`ValidationResult`**: Top-level result container.
- **`ValidationError`**: Specific issue with tag, message, and location.
- **`QueryMetadata`**: Structural analysis output including score and signature.

