# -*- coding: utf-8 -*-
"""Build ErrorContext from PostgreSQL error (err.diag.*). Supports psycopg2/3, asyncpg, pglast."""

import re
from typing import Optional, List, Any

from ast_parsers.errors import (
    Diagnostics,
    ErrorContext,
    TagWithProvenance,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    SOURCE_PG_DIAG_COLUMN_NAME,
    SOURCE_PG_DIAG_TABLE_NAME,
    SOURCE_PG_DIAG_CONSTRAINT_NAME,
    SOURCE_PG_DIAG_DATATYPE_NAME,
    SOURCE_PG_DIAG_SCHEMA_NAME,
    SOURCE_PG_DIAG_POSITION,
    SOURCE_SQLSTATE,
    SOURCE_REGEX,
    SOURCE_AST_HEURISTIC,
    SchemaErrorTags,
    LogicalErrorTags,
    JoinErrorTags,
    AggregationErrorTags,
    FilterErrorTags,
    SyntaxErrorTags,
)
from ast_parsers.error_codes import (
    extract_error_code,
    get_taxonomy_category_with_fallback,
    get_tag_for_sqlstate,
    get_tags_for_category,
)


def extract_diagnostics(exception: Any) -> Diagnostics:
    """Extract err.diag.*-style fields from exception. Missing fields are None."""
    message_primary = getattr(exception, "pgerror", None) or getattr(exception, "message", None) if exception else None
    if message_primary is None and exception is not None:
        message_primary = str(exception)
    message_detail = message_hint = context = None
    position = schema_name = table_name = column_name = datatype_name = constraint_name = None
    internal_query = internal_position = None

    if exception is None:
        return Diagnostics(message_primary=message_primary)

    # Driver-specific diag object (psycopg2, psycopg3)
    inner = getattr(exception, "diag", None)
    if inner is not None:
        message_primary = _get_attr(inner, "message_primary") or message_primary
        message_detail = _get_attr(inner, "message_detail")
        message_hint = _get_attr(inner, "message_hint")
        context = _get_attr(inner, "context")
        position = _get_attr(inner, "statement_position") or _get_attr(inner, "position")
        schema_name = _get_attr(inner, "schema_name")
        table_name = _get_attr(inner, "table_name")
        column_name = _get_attr(inner, "column_name")
        datatype_name = _get_attr(inner, "datatype_name")
        constraint_name = _get_attr(inner, "constraint_name")
        internal_query = _get_attr(inner, "internal_query")
        internal_position = _get_attr(inner, "internal_position")

    if hasattr(exception, "get_server_error_message"):
        try:
            m = exception.get_server_error_message()
            if m:
                message_primary = m
        except Exception:
            pass
    _detail = getattr(exception, "get_detail", None) or getattr(exception, "get_server_error_detail", None)
    if _detail is not None:
        try:
            v = _detail()
            if v is not None:
                message_detail = v
        except Exception:
            pass
    for attr, var_name in (
        ("hint", "message_hint"),
        ("schema_name", "schema_name"),
        ("table_name", "table_name"),
        ("column_name", "column_name"),
        ("datatype_name", "datatype_name"),
        ("constraint_name", "constraint_name"),
    ):
        getter = getattr(exception, "get_" + attr, None) or getattr(exception, "get_server_error_" + attr, None)
        if getter is not None:
            try:
                v = getter()
                if v is not None:
                    if var_name == "message_hint":
                        message_hint = v
                    elif var_name == "schema_name":
                        schema_name = v
                    elif var_name == "table_name":
                        table_name = v
                    elif var_name == "column_name":
                        column_name = v
                    elif var_name == "datatype_name":
                        datatype_name = v
                    elif var_name == "constraint_name":
                        constraint_name = v
            except Exception:
                pass

    return Diagnostics(
        message_primary=message_primary,
        message_detail=message_detail,
        message_hint=message_hint,
        context=context,
        position=position,
        schema_name=schema_name,
        table_name=table_name,
        column_name=column_name,
        datatype_name=datatype_name,
        constraint_name=constraint_name,
        internal_query=internal_query,
        internal_position=internal_position,
    )


def _get_attr(obj: Any, name: str) -> Optional[Any]:
    v = getattr(obj, name, None)
    if v is not None and (isinstance(v, str) and v.strip() == ""):
        return None
    return v


def _get_sqlstate_from_exception(exception: Any) -> Optional[str]:
    if exception is None:
        return None
    code = getattr(exception, "pgcode", None) or getattr(exception, "sqlstate", None)
    if code is not None:
        return str(code).strip()
    # Fallback: extract from message
    msg = getattr(exception, "pgerror", None) or str(exception)
    return extract_error_code(msg)


# =============================================================================
# 2) Convert diagnostic fields into high-confidence tags (pg_diag-derived)
# =============================================================================

def tags_from_cursor_diagnostics(diagnostics: Optional[Diagnostics]) -> List[TagWithProvenance]:
    """
    Generate tags from PostgreSQL diagnostic fields (err.diag.*). pg_diag-derived tags are high confidence.
    column_name → schema_hallucination_col / schema_ambiguous_col (by SQLSTATE)
    table_name → schema_hallucination_table, join_missing_join
    constraint_name → logical_unique_violation, logical_foreign_key_violation, etc.
    datatype_name → schema_type_mismatch, value_format_mismatch, filter_type_mismatch_where
    """
    out: List[TagWithProvenance] = []
    if diagnostics is None:
        return out

    if diagnostics.column_name is not None:
        out.append(TagWithProvenance(
            tag=SchemaErrorTags.HALLUCINATION_COLUMN,
            source=SOURCE_PG_DIAG_COLUMN_NAME,
            confidence=CONFIDENCE_HIGH,
        ))
        out.append(TagWithProvenance(
            tag=SchemaErrorTags.AMBIGUOUS_COLUMN,
            source=SOURCE_PG_DIAG_COLUMN_NAME,
            confidence=CONFIDENCE_HIGH,
        ))

    if diagnostics.table_name is not None:
        out.append(TagWithProvenance(
            tag=SchemaErrorTags.HALLUCINATION_TABLE,
            source=SOURCE_PG_DIAG_TABLE_NAME,
            confidence=CONFIDENCE_HIGH,
        ))
        out.append(TagWithProvenance(
            tag=JoinErrorTags.MISSING_JOIN,
            source=SOURCE_PG_DIAG_TABLE_NAME,
            confidence=CONFIDENCE_HIGH,
        ))

    if diagnostics.constraint_name is not None:
        out.append(TagWithProvenance(
            tag=LogicalErrorTags.UNIQUE_VIOLATION,
            source=SOURCE_PG_DIAG_CONSTRAINT_NAME,
            confidence=CONFIDENCE_HIGH,
        ))
        out.append(TagWithProvenance(
            tag=LogicalErrorTags.FOREIGN_KEY_VIOLATION,
            source=SOURCE_PG_DIAG_CONSTRAINT_NAME,
            confidence=CONFIDENCE_HIGH,
        ))
        out.append(TagWithProvenance(
            tag="schema_incorrect_foreign_key",
            source=SOURCE_PG_DIAG_CONSTRAINT_NAME,
            confidence=CONFIDENCE_HIGH,
        ))
        out.append(TagWithProvenance(
            tag=LogicalErrorTags.CHECK_VIOLATION,
            source=SOURCE_PG_DIAG_CONSTRAINT_NAME,
            confidence=CONFIDENCE_HIGH,
        ))

    if diagnostics.datatype_name is not None:
        out.append(TagWithProvenance(
            tag=SchemaErrorTags.TYPE_MISMATCH,
            source=SOURCE_PG_DIAG_DATATYPE_NAME,
            confidence=CONFIDENCE_HIGH,
        ))
        out.append(TagWithProvenance(
            tag=FilterErrorTags.TYPE_MISMATCH_WHERE,
            source=SOURCE_PG_DIAG_DATATYPE_NAME,
            confidence=CONFIDENCE_HIGH,
        ))

    if diagnostics.schema_name is not None:
        out.append(TagWithProvenance(
            tag=SchemaErrorTags.HALLUCINATION_TABLE,
            source=SOURCE_PG_DIAG_SCHEMA_NAME,
            confidence=CONFIDENCE_HIGH,
        ))

    return out


def tags_from_sqlstate(sqlstate: Optional[str]) -> List[TagWithProvenance]:
    """Tags from SQLSTATE (medium confidence)."""
    out: List[TagWithProvenance] = []
    if sqlstate is None:
        return out
    specific_tag = get_tag_for_sqlstate(sqlstate)
    if specific_tag is not None:
        out.append(TagWithProvenance(tag=specific_tag, source=SOURCE_SQLSTATE, confidence=CONFIDENCE_MEDIUM))
        return out
    category = get_taxonomy_category_with_fallback(sqlstate)
    if category is not None:
        for tag in get_tags_for_category(category):
            out.append(TagWithProvenance(tag=tag, source=SOURCE_SQLSTATE, confidence=CONFIDENCE_MEDIUM))
    return out


def tags_from_regex(message: Optional[str]) -> List[TagWithProvenance]:
    """Infer tag from error message when SQLSTATE/diag not available. Low confidence."""
    out: List[TagWithProvenance] = []
    if not message:
        return out
    code = extract_error_code(message)
    if code is not None:
        tag = get_tag_for_sqlstate(code)
        if tag is not None:
            out.append(TagWithProvenance(tag=tag, source=SOURCE_REGEX, confidence=CONFIDENCE_LOW))
        else:
            category = get_taxonomy_category_with_fallback(code)
            if category is not None:
                for t in get_tags_for_category(category):
                    out.append(TagWithProvenance(tag=t, source=SOURCE_REGEX, confidence=CONFIDENCE_LOW))
    return out


def localize_position(sql: str, position: Optional[int]) -> Optional[dict]:
    """Return token and context_snippet at position. Keys: token, start, end, context_snippet."""
    if position is None or position < 0 or not sql:
        return None
    if position >= len(sql):
        return {"token": None, "start": position, "end": position, "context_snippet": sql[-50:] if len(sql) > 50 else sql}
    # Simple token at position: extend to word boundaries
    start = position
    while start > 0 and sql[start - 1].isalnum() or sql[start - 1] in "_.":
        start -= 1
    end = position
    while end < len(sql) and (sql[end].isalnum() or sql[end] in "_."):
        end += 1
    token = sql[start:end] if end > start else sql[position:position + 1]
    snippet_start = max(0, position - 25)
    snippet_end = min(len(sql), position + 25)
    return {
        "token": token or None,
        "start": start,
        "end": end,
        "context_snippet": sql[snippet_start:snippet_end],
    }


def tags_from_position(sql: str, position: Optional[int], diagnostics: Optional[Diagnostics]) -> List[TagWithProvenance]:
    """Structural/syntax tags from position (e.g. trailing_delimiter, unbalanced_tokens)."""
    out: List[TagWithProvenance] = []
    if position is None or not sql:
        return out
    loc = localize_position(sql, position)
    if loc is None:
        return out
    token = loc.get("token")
    snippet = (loc.get("context_snippet") or "").upper()
    # Heuristics: trailing comma before keyword
    if "," in snippet and any(kw in snippet for kw in ("FROM", "WHERE", "GROUP", "ORDER", "JOIN", "HAVING", "LIMIT")):
        out.append(TagWithProvenance(
            tag=SyntaxErrorTags.TRAILING_DELIMITER,
            source=SOURCE_PG_DIAG_POSITION,
            confidence=CONFIDENCE_MEDIUM,
        ))
    if snippet.count("(") != snippet.count(")"):
        out.append(TagWithProvenance(
            tag=SyntaxErrorTags.UNBALANCED_TOKENS,
            source=SOURCE_PG_DIAG_POSITION,
            confidence=CONFIDENCE_MEDIUM,
        ))
    if token and re.match(r"^['\"]?[^'\"]*$", token):
        out.append(TagWithProvenance(
            tag="value_hardcoded_value",
            source=SOURCE_PG_DIAG_POSITION,
            confidence=CONFIDENCE_LOW,
        ))
    return out


# =============================================================================
# 5) Combine PostgreSQL diagnostics with AST analysis (cross-signals)
# =============================================================================

def tags_from_ast_cross_signals(
    ast: Any,
    diagnostics: Optional[Diagnostics],
    sqlstate: Optional[str],
) -> List[TagWithProvenance]:
    """
    Cross-signals: undefined column + column in subquery → subquery_incorrect_correlation;
    GROUP BY error + aggregate/non-aggregate mix → aggregation_missing_groupby;
    table not joined → join_missing_join.
    """
    out: List[TagWithProvenance] = []
    if ast is None:
        return out

    try:
        from sqlglot import exp
    except ImportError:
        return out
    if sqlstate == "42803":
        has_agg = any(1 for n in ast.walk() if isinstance(n, exp.AggFunc))
        has_group = any(1 for n in ast.walk() if isinstance(n, exp.Group))
        if has_agg and has_group:
            out.append(TagWithProvenance(
                tag=AggregationErrorTags.MISSING_GROUPBY,
                source=SOURCE_AST_HEURISTIC,
                confidence=CONFIDENCE_MEDIUM,
            ))
        out.append(TagWithProvenance(
            tag=LogicalErrorTags.GROUPING_ERROR,
            source=SOURCE_AST_HEURISTIC,
            confidence=CONFIDENCE_MEDIUM,
        ))

    # Undefined column 42703 + column might be in subquery only
    if sqlstate == "42703" and diagnostics and diagnostics.column_name:
        # Heuristic: query has subqueries → possible correlation error
        has_subquery = any(1 for n in ast.walk() if isinstance(n, exp.Subquery))
        if has_subquery:
            out.append(TagWithProvenance(
                tag="subquery_incorrect_correlation",
                source=SOURCE_AST_HEURISTIC,
                confidence=CONFIDENCE_LOW,
            ))
    if diagnostics and diagnostics.table_name:
        tables_in_ast = [t.name for t in ast.find_all(exp.Table)]
        if len(tables_in_ast) >= 2 and diagnostics.table_name not in tables_in_ast:
            out.append(TagWithProvenance(
                tag=JoinErrorTags.MISSING_JOIN,
                source=SOURCE_AST_HEURISTIC,
                confidence=CONFIDENCE_MEDIUM,
            ))

    return out


# =============================================================================
# 6) Build ErrorContext from pipeline input { sql, ast, error }
# =============================================================================

def build_error_context(
    sql: str,
    ast: Optional[Any] = None,
    error: Optional[Any] = None,
) -> ErrorContext:
    """
    Build structured ErrorContext from pipeline input.
    Extracts full diagnostic surface, derives tags with provenance and confidence,
    and combines cursor diagnostics with AST cross-signals.
    """
    diagnostics = extract_diagnostics(error) if error is not None else None
    sqlstate = _get_sqlstate_from_exception(error) if error is not None else None
    if sqlstate is None and diagnostics and diagnostics.message_primary:
        sqlstate = extract_error_code(diagnostics.message_primary)

    tags: List[TagWithProvenance] = []
    tags.extend(tags_from_cursor_diagnostics(diagnostics))
    tags.extend(tags_from_sqlstate(sqlstate))
    if not sqlstate and diagnostics and diagnostics.message_primary:
        tags.extend(tags_from_regex(diagnostics.message_primary))
    pos = diagnostics.position if diagnostics else None
    tags.extend(tags_from_position(sql, pos, diagnostics))
    tags.extend(tags_from_ast_cross_signals(ast, diagnostics, sqlstate))
    seen: dict = {}
    for t in tags:
        key = (t.tag, t.source)
        if key not in seen or seen[key].confidence < t.confidence:
            seen[key] = t
    unique_tags = list(seen.values())

    return ErrorContext(
        sql=sql,
        ast=ast,
        sqlstate=sqlstate,
        diagnostics=diagnostics,
        tags=unique_tags,
    )
