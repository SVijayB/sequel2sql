# -*- coding: utf-8 -*-
"""
SQL validation with a single entry point.

    result = validate(sql)                         # syntax only
    result = validate(sql, schema=my_schema)       # syntax + schema (static)
    result = validate_with_db(sql, engine)         # syntax + schema + live EXPLAIN

Both functions collect ALL errors (syntax AND semantic) simultaneously —
a syntax error no longer prevents schema checks from running.
One function in, one ValidationResult out.
Parses exactly once, runs analyze_query exactly once.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

# Per-engine live-schema cache: str(engine.url) → {table: {col: type}}
_live_schema_cache: Dict[str, Dict[str, Dict[str, str]]] = {}

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, ParseError

from ast_parsers.query_analyzer import analyze_query
from ast_parsers.result import ValidationError, ValidationResult
from ast_parsers.tags import (
    ErrorTag,
    extract_error_code,
    tag_for_sqlstate,
)


def validate(
    sql: str,
    schema: Optional[Dict[str, Dict[str, str]]] = None,
    dialect: str = "postgres",
) -> ValidationResult:
    """
    Validate SQL syntax and (optionally) check against a database schema.

    Unlike the previous implementation this function *does not* stop on the
    first error.  A query with a recoverable syntax problem still goes through
    schema validation so you get the full error picture in one call.

    Args:
        sql:     SQL query string to validate.
        schema:  Optional ``{table_name: {column_name: type}}`` dict.
                 When provided, table existence and column references are
                 checked even when syntax errors are present (as long as a
                 partial AST can be recovered).
        dialect: SQL dialect (default: ``"postgres"``).

    Returns:
        ValidationResult with:
          - ``valid`` – True when no errors were found.
          - ``errors`` – list of ALL ValidationErrors (syntax + semantic).
          - ``query_metadata`` – structural metadata (complexity, clauses, …).
    """
    # ── 1. Parse (with recovery) ──────────────────────────────────────────────
    ast, syntax_errors = _parse_with_recovery(sql, dialect)

    # ── 2. Detect issues sqlglot silently accepts ─────────────────────────────
    silent_errors: List[ValidationError] = []
    schema_errors: List[ValidationError] = []
    metadata = None

    if ast is not None:
        silent_errors = _detect_silent_fixes(sql)
        metadata = analyze_query(ast)
        if schema is not None:
            schema_errors = _check_schema(ast, schema)

    all_errors = syntax_errors + silent_errors + schema_errors
    return ValidationResult(
        valid=len(all_errors) == 0,
        sql=sql,
        errors=all_errors,
        query_metadata=metadata,
    )


def validate_with_db(
    sql: str,
    engine,  # sqlalchemy.engine.Engine — not typed to avoid hard dep at import
    schema: Optional[Dict[str, Dict[str, str]]] = None,
    dialect: str = "postgres",
) -> ValidationResult:
    """
    Full validation pipeline using a live PostgreSQL database.

    Error collection strategy (all run independently, then merged):

    1. **Syntax** — ``_parse_with_recovery()`` classifies parse errors and
       attempts WARN-level recovery to get a partial AST.
    2. **Token schema** — ``_extract_identifiers_from_tokens()`` walks the
       sqlglot token stream (never throws on broken SQL) to extract table and
       column candidates, then checks them against the live DB schema.  This
       fires even when the AST is too broken to use.
    3. **AST schema** — ``_check_schema()`` does a precise alias-resolved
       column walk when the AST is available.  More accurate than the token
       check for qualified references.
    4. **EXPLAIN** — ``EXPLAIN {sql}`` on the live DB catches whatever the
       above miss (type errors, permission issues, constraint violations) at
       the cost of reporting only the *first* server error.

    All four lists are merged and deduplicated.  EXPLAIN errors take priority;
    AST-schema errors supersede token-schema errors for the same identifier.

    Args:
        sql:     SQL query string.
        engine:  SQLAlchemy ``Engine`` connected to the target database.
        schema:  Ignored — the live DB schema is always used.  Kept for
                 backward compatibility with call sites that pass a JSON schema.
        dialect: SQL dialect for the static parser (default: ``"postgres"``).

    Returns:
        ValidationResult with ``valid=True`` only when all checks pass.
    """
    # ── 1. Syntax + partial AST ───────────────────────────────────────────────
    ast, syntax_errors = _parse_with_recovery(sql, dialect)
    silent_errors = _detect_silent_fixes(sql) if ast is not None else []
    metadata = analyze_query(ast) if ast is not None else None

    # ── 2. Live schema from DB (cached per engine URL) ────────────────────────
    live_schema = _get_live_schema(engine)

    # ── 3. Token-stream schema check (always runs, AST-independent) ──────────
    table_cands, col_cands = _extract_identifiers_from_tokens(sql)
    token_schema_errors = _check_identifiers_against_schema(
        table_cands, col_cands, live_schema
    )

    # ── 4. AST schema check (precise, only when AST is good) ─────────────────
    ast_schema_errors: List[ValidationError] = []
    if ast is not None:
        ast_schema_errors = _check_schema(ast, live_schema)

    # ── 5. EXPLAIN — DB-native first error ───────────────────────────────────
    db_errors = _explain(sql, engine)

    # ── 6. Merge, deduplicate by (tag, context) ───────────────────────────────
    # Priority: EXPLAIN > AST-schema > token-schema > syntax > silent
    all_errors = _merge_errors(
        db_errors,
        ast_schema_errors,
        token_schema_errors,
        syntax_errors,
        silent_errors,
    )

    return ValidationResult(
        valid=len(all_errors) == 0,
        sql=sql,
        errors=all_errors,
        query_metadata=metadata,
    )


# ─── Internal: parsing ────────────────────────────────────────────────────────


def _parse_with_recovery(
    sql: str, dialect: str
) -> Tuple[Optional[exp.Expression], List[ValidationError]]:
    """
    Try strict parse first.  If that fails, collect syntax errors and then
    retry with ErrorLevel.WARN to get a partial AST so that schema checks can
    still run on the remainder of the query.

    Returns: (ast_or_None, syntax_errors)
    """
    try:
        ast = sqlglot.parse_one(sql, read=dialect, error_level=ErrorLevel.RAISE)
        return ast, []
    except ParseError as exc:
        syntax_errors = _classify_parse_error(sql, exc)
    except Exception as exc:
        syntax_errors = _classify_generic_error(sql, exc)

    # Recovery attempt — get a partial AST even though syntax is broken
    try:
        ast = sqlglot.parse_one(sql, read=dialect, error_level=ErrorLevel.WARN)
    except Exception:
        ast = None

    return ast, syntax_errors


# ─── Internal: silent-fix detection ──────────────────────────────────────────


def _detect_silent_fixes(sql: str) -> List[ValidationError]:
    """Return errors for patterns sqlglot silently accepts but that are wrong."""
    errors: List[ValidationError] = []

    pos = _find_trailing_delimiter(sql)
    if pos is not None:
        errors.append(
            ValidationError(
                tag=ErrorTag.TRAILING_DELIMITER,
                message="Trailing comma or delimiter before keyword",
                location=pos,
                context=sql[max(0, pos - 10) : pos + 15],
            )
        )
        return errors  # one silent-fix error at a time is enough

    if _has_empty_select(sql):
        errors.append(
            ValidationError(
                tag=ErrorTag.KEYWORD_MISUSE,
                message="SELECT clause has no columns specified",
            )
        )

    return errors


# ─── Internal: schema checks ──────────────────────────────────────────────────


def _check_schema(
    ast: exp.Expression,
    schema: Dict[str, Dict[str, str]],
) -> List[ValidationError]:
    """
    Check table and column references against the schema dict.

    Replaces the previous ``sqlglot.optimize()``-based implementation which
    lowercased column names before comparison and therefore missed hallucinated
    columns whose schema keys contain spaces or mixed-case characters (e.g.
    ``"County Code"``).

    This implementation:
    * Walks ``exp.Column`` nodes directly — no optimizer involvement.
    * Compares names case-insensitively via ``.lower()``.
    * Builds an alias map from ``exp.Table`` nodes so qualified references like
      ``t1.column_name`` are resolved correctly.
    * Reports the enclosing SQL clause for each error via ``_clause_of()``.
    """
    errors: List[ValidationError] = []

    # ── Normalised schema lookup ──────────────────────────────────────────────
    # schema_lower: {table_lower -> {col_lower -> original_col_name}}
    schema_lower: Dict[str, Dict[str, str]] = {
        t.lower(): {c.lower(): c for c in cols} for t, cols in schema.items()
    }

    # ── Collect CTE aliases so they are never flagged as missing tables ────────
    cte_aliases: Set[str] = set()
    for cte_node in ast.find_all(exp.CTE):
        if cte_node.alias:
            cte_aliases.add(cte_node.alias.lower())

    # ── Collect subquery aliases (these are also virtual tables) ──────────────
    for sq_node in ast.find_all(exp.Subquery):
        if sq_node.alias:
            cte_aliases.add(sq_node.alias.lower())

    # ── Alias map: {alias_or_table_lower -> real_table_lower} ─────────────────
    alias_map: Dict[str, str] = {}
    for table_node in ast.find_all(exp.Table):
        real = table_node.name.lower()
        if real:
            alias_map[real] = real
        if table_node.alias:
            alias_map[table_node.alias.lower()] = real

    # ── 1. Table existence ────────────────────────────────────────────────────
    missing_tables: List[str] = []
    for table_node in ast.find_all(exp.Table):
        t = table_node.name.lower()
        if t and t not in schema_lower and t not in cte_aliases:
            missing_tables.append(table_node.name)
            errors.append(
                ValidationError(
                    tag=ErrorTag.HALLUCINATION_TABLE,
                    message=f"Table '{table_node.name}' does not exist in schema",
                    context=table_node.name,
                    affected_clauses=["FROM"],
                )
            )

    if missing_tables:
        # Column checks are unreliable when tables themselves are wrong
        return errors

    # ── 2. Column references ──────────────────────────────────────────────────
    # Collect the set of all table names referenced in the query (lower)
    referenced_tables: Set[str] = set(alias_map.values())

    for col_node in ast.find_all(exp.Column):
        col_name: str = col_node.name  # bare column string, original case
        qualifier: str = col_node.table  # syntactic qualifier (alias/table), if any

        col_lower = col_name.lower()

        if qualifier:
            # Qualified reference: resolve alias → real table
            resolved = alias_map.get(qualifier.lower())
            if resolved is None or qualifier.lower() in cte_aliases:
                # Unknown qualifier or CTE/subquery alias — skip
                continue
            table_cols = schema_lower.get(resolved, {})
            if col_lower not in table_cols:
                clause = _clause_of(col_node)
                errors.append(
                    ValidationError(
                        tag=ErrorTag.HALLUCINATION_COLUMN,
                        message=(
                            f"Column '{col_name}' does not exist in table "
                            f"'{resolved}' (referenced as '{qualifier}.{col_name}')"
                        ),
                        context=f"{qualifier}.{col_name}",
                        affected_clauses=[clause] if clause else [],
                    )
                )
        else:
            # Unqualified reference: column must exist in at least one
            # referenced table
            found = any(col_lower in schema_lower.get(t, {}) for t in referenced_tables)
            if not found:
                clause = _clause_of(col_node)
                errors.append(
                    ValidationError(
                        tag=ErrorTag.HALLUCINATION_COLUMN,
                        message=(
                            f"Column '{col_name}' does not exist in any "
                            f"referenced table"
                        ),
                        context=col_name,
                        affected_clauses=[clause] if clause else [],
                    )
                )

    return errors


def _clause_of(node: exp.Expression) -> Optional[str]:
    """Walk parent chain to find the name of the enclosing SQL clause."""
    _CLAUSE_MAP = {
        exp.Select: "SELECT",
        exp.From: "FROM",
        exp.Where: "WHERE",
        exp.Join: "JOIN",
        exp.Having: "HAVING",
        exp.Group: "GROUP BY",
        exp.Order: "ORDER BY",
    }
    curr = node.parent
    while curr is not None:
        for clause_type, name in _CLAUSE_MAP.items():
            if isinstance(curr, clause_type):
                return name
        curr = curr.parent
    return None


# ─── Internal: live DB validation ────────────────────────────────────────────


def _get_live_schema(engine) -> Dict[str, Dict[str, str]]:
    """
    Reflect the full schema from the live database and cache it by engine URL.

    Returns ``{table_name: {column_name: sql_type}}`` — same format as the
    JSON schema files so it can be passed to ``_check_schema()`` directly.
    """
    key = str(engine.url)
    if key not in _live_schema_cache:
        from sqlalchemy import MetaData as SAMetaData

        meta = SAMetaData()
        meta.reflect(bind=engine)
        _live_schema_cache[key] = {
            table_name: {col.name: str(col.type) for col in table_obj.columns}
            for table_name, table_obj in meta.tables.items()
        }
    return _live_schema_cache[key]


def _extract_identifiers_from_tokens(
    sql: str,
) -> Tuple[List[str], List[str]]:
    """
    Walk the sqlglot token stream (which **never throws** on broken SQL) and
    extract:

    * ``table_candidates`` — bare identifiers immediately following a
      ``FROM``, ``JOIN``, or ``INTO`` keyword.
    * ``col_candidates`` — all double-quoted ``IDENTIFIER`` tokens that are
      *not* in a table-name position.  Double-quoted tokens in PostgreSQL are
      always object names, so false positives are near-zero.

    This is intentionally simple and positional — it is not a full SQL
    parser.  Its job is to catch hallucinated names when the AST is too
    broken to use.
    """
    from sqlglot.tokens import Tokenizer as _Tokenizer
    from sqlglot.tokens import TokenType

    try:
        toks = _Tokenizer().tokenize(sql)
    except Exception:
        return [], []

    TABLE_TRIGGERS: Set = {
        TokenType.FROM,
        TokenType.JOIN,
        TokenType.INTO,
    }
    # Token types to skip between a trigger and the actual table name
    SKIP_TYPES: Set = {TokenType.L_PAREN}

    table_candidates: List[str] = []
    table_positions: Set[int] = set()

    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok.token_type in TABLE_TRIGGERS:
            j = i + 1
            while j < len(toks) and toks[j].token_type in SKIP_TYPES:
                j += 1
            if j < len(toks) and toks[j].token_type in (
                TokenType.VAR,
                TokenType.IDENTIFIER,
            ):
                table_candidates.append(toks[j].text)
                table_positions.add(j)
        i += 1

    # Second pass: double-quoted IDENTIFIER tokens not in table positions
    col_candidates: List[str] = [
        toks[idx].text
        for idx, tok in enumerate(toks)
        if tok.token_type == TokenType.IDENTIFIER and idx not in table_positions
    ]

    return table_candidates, col_candidates


def _check_identifiers_against_schema(
    table_cands: List[str],
    col_cands: List[str],
    schema: Dict[str, Dict[str, str]],
) -> List[ValidationError]:
    """
    Check token-extracted table and column candidates against the live schema.

    Column candidates are checked against the union of columns in all
    *valid* referenced tables.  When every referenced table is hallucinated
    (nothing valid found) the column check falls back to the full schema so
    we still report columns that don't exist anywhere.
    """
    errors: List[ValidationError] = []
    schema_lower: Dict[str, Set[str]] = {
        t.lower(): {c.lower() for c in cols} for t, cols in schema.items()
    }

    valid_tables: Set[str] = set()
    for t in table_cands:
        if t.lower() in schema_lower:
            valid_tables.add(t.lower())
        else:
            errors.append(
                ValidationError(
                    tag=ErrorTag.HALLUCINATION_TABLE,
                    message=f"Table '{t}' does not exist in the database",
                    context=t,
                    affected_clauses=["FROM"],
                )
            )

    # If we found valid tables, restrict column search to those; otherwise
    # search the whole schema so we don't miss anything.
    search_cols: Set[str] = set()
    for t in valid_tables if valid_tables else schema_lower.keys():
        search_cols.update(schema_lower.get(t, set()))

    for col in col_cands:
        if col.lower() not in search_cols:
            errors.append(
                ValidationError(
                    tag=ErrorTag.HALLUCINATION_COLUMN,
                    message=f"Column '{col}' does not exist in the database",
                    context=col,
                )
            )

    return errors


def _merge_errors(*error_lists: List[ValidationError]) -> List[ValidationError]:
    """
    Merge multiple error lists, deduplicating by ``(tag, context_lower)``.

    Lists are processed in order; earlier lists have priority (their entry
    wins when two errors share tag + normalised context).
    """
    seen: Set[Tuple[ErrorTag, str]] = set()
    merged: List[ValidationError] = []
    for lst in error_lists:
        for err in lst:
            key = (err.tag, (err.context or "").lower())
            if key not in seen:
                seen.add(key)
                merged.append(err)
    return merged


def _explain(sql: str, engine) -> List[ValidationError]:
    """
    Run ``EXPLAIN {sql}`` on the live database and convert any exception into
    a ValidationError list.  Returns an empty list when the query is valid.
    """
    try:
        # Import here to avoid hard dependency when validate() is used standalone
        from sqlalchemy import text as sa_text

        with engine.connect() as conn:
            conn.execute(sa_text(f"EXPLAIN {sql}"))
        return []
    except Exception as exc:
        # Extract PostgreSQL SQLSTATE + message when available
        orig = getattr(exc, "orig", None)
        sqlstate: Optional[str] = None
        pg_message: str = str(exc)

        if orig is not None:
            sqlstate = getattr(orig, "pgcode", None)
            pg_message = getattr(orig, "pgerror", None) or str(exc)
        else:
            sqlstate = extract_error_code(str(exc))

        tag = tag_for_sqlstate(sqlstate) or _infer_tag_from_explain_message(pg_message)

        return [
            ValidationError(
                tag=tag,
                message=_clean_pg_message(pg_message),
                error_code=sqlstate,
                context="PostgreSQL EXPLAIN",
            )
        ]


def _infer_tag_from_explain_message(message: str) -> ErrorTag:
    """Heuristic tag mapping when no SQLSTATE is available."""
    msg = message.lower()
    if "column" in msg and ("does not exist" in msg or "not found" in msg):
        return ErrorTag.HALLUCINATION_COLUMN
    if "relation" in msg and "does not exist" in msg:
        return ErrorTag.HALLUCINATION_TABLE
    if "syntax error" in msg:
        return ErrorTag.SYNTAX_ERROR
    if "operator does not exist" in msg or "type" in msg:
        return ErrorTag.TYPE_MISMATCH
    if "ambiguous" in msg:
        return ErrorTag.AMBIGUOUS_COLUMN
    return ErrorTag.SCHEMA_UNKNOWN_ERROR


def _clean_pg_message(message: str) -> str:
    """Strip leading ERROR: / DETAIL: boilerplate from a PostgreSQL error string."""
    lines = []
    for line in message.splitlines():
        stripped = re.sub(r"^(ERROR|DETAIL|HINT|CONTEXT):\s*", "", line.strip())
        if stripped:
            lines.append(stripped)
    return " | ".join(lines) if lines else message


# ─── Internal: syntax error classification ───────────────────────────────────


def _classify_parse_error(sql: str, exc: ParseError) -> List[ValidationError]:
    """Map a sqlglot ParseError to one or more ValidationErrors."""
    msg = str(exc)
    msg_lower = msg.lower()
    location = getattr(exc, "col", None)
    error_code = extract_error_code(msg)

    if "unterminated" in msg_lower or _has_unterminated_string(sql):
        return [
            ValidationError(
                tag=ErrorTag.UNTERMINATED_STRING,
                message="Unterminated quoted string",
                location=location,
                context=msg,
                error_code=error_code,
            )
        ]

    if _has_unbalanced_tokens(sql):
        return [
            ValidationError(
                tag=ErrorTag.UNBALANCED_TOKENS,
                message="Unbalanced parentheses or brackets",
                location=location,
                context=_describe_imbalance(sql),
                error_code=error_code,
            )
        ]

    pos = _find_trailing_delimiter(sql)
    if pos is not None:
        return [
            ValidationError(
                tag=ErrorTag.TRAILING_DELIMITER,
                message="Trailing comma or delimiter before keyword",
                location=pos,
                context=sql[max(0, pos - 10) : pos + 10],
                error_code=error_code,
            )
        ]

    if "expecting )" in msg_lower or "expecting (" in msg_lower:
        return [
            ValidationError(
                tag=ErrorTag.UNBALANCED_TOKENS,
                message=msg,
                location=location,
                context="Parser reported expecting parenthesis",
                error_code=error_code,
            )
        ]

    if "unexpected token" in msg_lower or "invalid expression" in msg_lower:
        return [
            ValidationError(
                tag=ErrorTag.INVALID_TOKEN,
                message=msg,
                location=location,
                error_code=error_code,
            )
        ]

    if "unsupported syntax" in msg_lower or "falling back to parsing as" in msg_lower:
        return [
            ValidationError(
                tag=ErrorTag.UNSUPPORTED_DIALECT,
                message=msg,
                location=location,
                error_code=error_code,
            )
        ]

    return [
        ValidationError(
            tag=ErrorTag.KEYWORD_MISUSE,
            message=msg,
            location=location,
            error_code=error_code,
        )
    ]


def _classify_generic_error(sql: str, exc: Exception) -> List[ValidationError]:
    """Map unexpected non-ParseError exceptions to ValidationErrors."""
    msg = str(exc)
    error_code = extract_error_code(msg)
    if "unterminated" in msg.lower() or _has_unterminated_string(sql):
        return [
            ValidationError(
                tag=ErrorTag.UNTERMINATED_STRING,
                message="Unterminated quoted string",
                context=msg,
                error_code=error_code,
            )
        ]
    return [
        ValidationError(
            tag=ErrorTag.SYNTAX_ERROR,
            message=msg,
            error_code=error_code,
        )
    ]


# ─── Internal: SQL text helpers ──────────────────────────────────────────────


def _find_trailing_delimiter(sql: str) -> Optional[int]:
    """Return character position of a trailing comma before a keyword, or None."""
    sql_upper = sql.upper()
    for kw in ("FROM", "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "UNION", "JOIN"):
        match = re.search(rf",\s+{re.escape(kw)}\b", sql_upper)
        if match:
            pos = match.start()
            before = sql[:pos].rstrip()
            if before and before[-1].isalnum():
                return pos
    return None


def _has_empty_select(sql: str) -> bool:
    return bool(re.search(r"\bSELECT\s+FROM\b", sql, re.IGNORECASE))


def _has_unbalanced_tokens(sql: str) -> bool:
    """Count paren/bracket depth while skipping string literals."""
    depth_paren = 0
    depth_bracket = 0
    in_string = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if in_string:
            if ch == "'" and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            elif ch == "'":
                in_string = False
        else:
            if ch == "'":
                in_string = True
            elif ch == "(":
                depth_paren += 1
            elif ch == ")":
                depth_paren -= 1
            elif ch == "[":
                depth_bracket += 1
            elif ch == "]":
                depth_bracket -= 1
        i += 1
    return depth_paren != 0 or depth_bracket != 0


def _describe_imbalance(sql: str) -> str:
    """Human-readable description of which tokens are unbalanced."""
    p = sql.count("(") - sql.count(")")
    b = sql.count("[") - sql.count("]")
    parts = []
    if p > 0:
        parts.append(f"{p} unclosed '('")
    elif p < 0:
        parts.append(f"{-p} extra ')'")
    if b > 0:
        parts.append(f"{b} unclosed '['")
    elif b < 0:
        parts.append(f"{-b} extra ']'")
    return ", ".join(parts) or "unknown imbalance"


def _has_unterminated_string(sql: str) -> bool:
    """
    Heuristic: track whether we end up inside an open single-quoted string.
    Handles SQL-style escaped quotes ('') correctly.
    """
    in_string = False
    i = 0
    while i < len(sql):
        if sql[i] == "'":
            if in_string and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 2
                continue
            in_string = not in_string
        i += 1
    return in_string
