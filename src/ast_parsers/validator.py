# -*- coding: utf-8 -*-
"""SQL validation: syntax (sqlglot) and optional schema-aware semantic checks."""

from typing import Optional, Dict, Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer import optimize

from ast_parsers.errors import (
    ValidationResult,
    ValidationError,
    SyntaxErrorTags,
    SchemaErrorTags,
)
from ast_parsers.error_codes import (
    extract_error_code,
    get_taxonomy_category,
    get_taxonomy_category_with_fallback,
    get_category_for_tag,
)
from ast_parsers.query_analyzer import (
    analyze_query,
    get_clause_for_node,
)


# =============================================================================
# Part 1: Static Analysis (Syntax Validation)
# =============================================================================

def validate_syntax(
    sql: str,
    dialect: str = "postgres",
) -> ValidationResult:
    """
    Validate SQL query syntax using sqlglot parser.
    
    This performs static analysis to detect basic syntax errors,
    malformed SQL, and common LLM artifacts like trailing delimiters.
    
    Args:
        sql: The SQL query string to validate
        dialect: SQL dialect (default: "postgres")
    
    Returns:
        ValidationResult with valid=True if syntax is correct,
        or valid=False with error details and tags
    
    Example:
        >>> result = validate_syntax("SELECT id, name, FROM users")
        >>> result.valid
        False
        >>> result.tags
        ['syntax_trailing_delimiter']
    """
    try:
        # Attempt to parse the SQL
        ast = sqlglot.parse_one(sql, read=dialect)
        
        # Check for issues that sqlglot silently fixes (like trailing commas)
        # by detecting patterns in the original SQL
        silent_errors = _detect_silent_fixes(sql)
        if silent_errors:
            result = ValidationResult(valid=False, errors=silent_errors, ast=ast, sql=sql)
            result.query_metadata = analyze_query(ast)
            return result
        
        result = ValidationResult(valid=True, ast=ast, sql=sql)
        result.query_metadata = analyze_query(ast)
        return result
    
    except ParseError as e:
        errors = _classify_syntax_error(sql, e)
        result = ValidationResult(valid=False, errors=errors, sql=sql)
        try:
            ast = sqlglot.parse_one(sql, read=dialect)
            result.ast = ast
            result.query_metadata = analyze_query(ast)
        except:
            pass
        return result
    
    except Exception as e:
        # Catch-all for unexpected parsing errors (including tokenization errors)
        # Still try to classify the error based on the SQL content
        errors = []
        error_message = str(e)
        
        # Extract error code; use class fallback when specific code unknown
        error_code = extract_error_code(error_message)
        taxonomy_category = get_taxonomy_category_with_fallback(error_code) or get_taxonomy_category(error_code)
        
        if "unterminated" in error_message.lower() or _has_unterminated_string(sql):
            errors.append(ValidationError(
                tag=SyntaxErrorTags.UNTERMINATED_STRING,
                message="Unterminated quoted string",
                context=error_message,
                error_code=error_code,
                taxonomy_category=taxonomy_category or "syntax",
            ))
        else:
            errors.append(ValidationError(
                tag=SyntaxErrorTags.SYNTAX_ERROR,
                message=error_message,
                error_code=error_code,
                taxonomy_category=taxonomy_category or "syntax",
            ))
        
        return ValidationResult(valid=False, errors=errors, sql=sql)


def _detect_silent_fixes(sql: str) -> list:
    """
    Detect issues that sqlglot silently fixes during parsing.
    
    sqlglot is lenient and auto-corrects some issues like trailing commas.
    We detect these by pattern matching on the original SQL.
    """
    errors = []
    
    # Check for trailing commas before keywords (sqlglot silently removes these)
    trailing_pos = _find_trailing_delimiter(sql, "")
    if trailing_pos is not None:
        errors.append(ValidationError(
            tag=SyntaxErrorTags.TRAILING_DELIMITER,
            message="Trailing comma or delimiter before keyword",
            location=trailing_pos,
            context=sql[max(0, trailing_pos-10):trailing_pos+15],
        ))
    if _has_empty_select(sql):
        errors.append(ValidationError(
            tag=SyntaxErrorTags.KEYWORD_MISUSE,
            message="SELECT clause has no columns specified",
        ))
    
    return errors


def _has_empty_select(sql: str) -> bool:
    """Check if SQL has SELECT immediately followed by FROM (no columns)."""
    import re
    # Match SELECT followed by optional whitespace, then FROM
    pattern = r'\bSELECT\s+FROM\b'
    return bool(re.search(pattern, sql, re.IGNORECASE))


def _classify_syntax_error(sql: str, error: ParseError) -> list:
    """
    Classify a syntax error and return appropriate error tags.
    
    Analyzes the error message and SQL context to determine
    the specific type of syntax error.
    """
    error_message = str(error)
    errors = []
    location = getattr(error, "col", None)
    error_code = extract_error_code(error_message)
    taxonomy_category = get_taxonomy_category(error_code)
    if _has_unbalanced_tokens(sql):
        errors.append(ValidationError(
            tag=SyntaxErrorTags.UNBALANCED_TOKENS,
            message="Unbalanced parentheses or brackets",
            location=location,
            context=_get_unbalanced_context(sql),
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))
    
    # 2. Check for trailing delimiters (common LLM error)
    trailing_pos = _find_trailing_delimiter(sql, error_message)
    if trailing_pos is not None:
        errors.append(ValidationError(
            tag=SyntaxErrorTags.TRAILING_DELIMITER,
            message="Trailing comma or delimiter before keyword",
            location=trailing_pos,
            context=sql[max(0, trailing_pos-10):trailing_pos+10],
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))
    if "unterminated" in error_message.lower() or _has_unterminated_string(sql):
        errors.append(ValidationError(
            tag=SyntaxErrorTags.UNTERMINATED_STRING,
            message="Unterminated quoted string",
            location=location,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))

    msg_lower = error_message.lower()
    if not errors and ("expecting )" in msg_lower or "expecting (" in msg_lower):
        errors.append(ValidationError(
            tag=SyntaxErrorTags.UNBALANCED_TOKENS,
            message=error_message,
            location=location,
            context="Parser reported expecting parenthesis",
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))
    if not errors and ("unexpected token" in msg_lower or "invalid expression" in msg_lower):
        errors.append(ValidationError(
            tag=SyntaxErrorTags.INVALID_TOKEN,
            message=error_message,
            location=location,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))
    if not errors and (
        "unknown option" in msg_lower
        or "unsupported syntax" in msg_lower
        or "falling back to parsing as" in msg_lower
    ):
        errors.append(ValidationError(
            tag=SyntaxErrorTags.UNSUPPORTED_DIALECT,
            message=error_message,
            location=location,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))
    if not errors:
        errors.append(ValidationError(
            tag=SyntaxErrorTags.KEYWORD_MISUSE,
            message=error_message,
            location=location,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "syntax",
        ))

    return errors


def _has_unbalanced_tokens(sql: str) -> bool:
    parens = sql.count('(') - sql.count(')')
    brackets = sql.count('[') - sql.count(']')
    return parens != 0 or brackets != 0


def _get_unbalanced_context(sql: str) -> str:
    """Get context about which tokens are unbalanced."""
    parens_diff = sql.count('(') - sql.count(')')
    brackets_diff = sql.count('[') - sql.count(']')
    
    parts = []
    if parens_diff > 0:
        parts.append(f"{parens_diff} unclosed '('")
    elif parens_diff < 0:
        parts.append(f"{-parens_diff} extra ')'")
    
    if brackets_diff > 0:
        parts.append(f"{brackets_diff} unclosed '['")
    elif brackets_diff < 0:
        parts.append(f"{-brackets_diff} extra ']'")
    
    return ", ".join(parts) if parts else "unknown imbalance"


def _find_trailing_delimiter(sql: str, error_message: str) -> Optional[int]:
    """Return position of trailing comma before keyword (e.g. SELECT a, FROM t)."""
    import re
    keywords = ['FROM', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT', 'UNION', 'JOIN']
    sql_upper = sql.upper()
    for keyword in keywords:
        pattern = rf',\s+{re.escape(keyword)}\b'
        match = re.search(pattern, sql_upper)
        if match:
            comma_pos = match.start()
            before_comma = sql[:comma_pos].rstrip()
            if before_comma and before_comma[-1].isalnum():
                return comma_pos
    return None


def _has_unterminated_string(sql: str) -> bool:
    """Check for unterminated string literals."""
    single_quotes = sql.count("'") - sql.count("\\'") * 2
    double_quotes = sql.count('"') - sql.count('\\"') * 2
    return single_quotes % 2 != 0 or double_quotes % 2 != 0


def validate_schema(
    sql: str,
    schema: Dict[str, Dict[str, str]],
    dialect: str = "postgres",
) -> ValidationResult:
    """Validate SQL against schema (tables/columns); requires valid syntax first."""
    syntax_result = validate_syntax(sql, dialect=dialect)
    if not syntax_result.valid:
        # Return syntax errors immediately - can't validate schema on invalid SQL
        return syntax_result
    
    # Get the parsed AST from syntax validation
    parsed = syntax_result.ast
    if parsed is None:
        # This shouldn't happen if syntax_result.valid is True, but handle it
        error = ValidationError(
            tag=SyntaxErrorTags.SYNTAX_ERROR,
            message="Failed to parse SQL for schema validation",
        )
        return ValidationResult(valid=False, errors=[error], sql=sql)
    
    errors = []
    missing_tables = _check_tables_exist(parsed, schema)
    for table_name in missing_tables:
        error_code = extract_error_code(f"table {table_name} does not exist")
        taxonomy_category = get_taxonomy_category(error_code)
        errors.append(ValidationError(
            tag=SchemaErrorTags.HALLUCINATION_TABLE,
            message=f"Table '{table_name}' does not exist in schema",
            context=table_name,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "semantic",
            affected_clauses=["FROM"],  # Table errors typically affect FROM clause
        ))
    
    # If tables are missing, we can't accurately validate columns
    if missing_tables:
        result = ValidationResult(valid=False, errors=errors, ast=parsed, sql=sql)
        result.query_metadata = analyze_query(parsed)
        return result
    try:
        optimize(
            parsed,
            schema=schema,
            dialect=dialect,
            validate_qualify_columns=True,
        )
    except sqlglot.errors.OptimizeError as e:
        column_errors = _classify_schema_error(str(e), ast=parsed)
        errors.extend(column_errors)
    except Exception as e:
        # Catch other optimization errors
        error_code = extract_error_code(str(e))
        taxonomy_category = get_taxonomy_category(error_code)
        errors.append(ValidationError(
            tag=SchemaErrorTags.UNKNOWN_ERROR,
            message=str(e),
            error_code=error_code,
            taxonomy_category=taxonomy_category or "semantic",
        ))
    
    result = ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        ast=parsed,
        sql=sql,
    )
    result.query_metadata = analyze_query(parsed)
    return result


def _check_tables_exist(parsed: exp.Expression, schema: Dict) -> list:
    missing = []
    schema_lower = {k.lower(): v for k, v in schema.items()}
    for table in parsed.find_all(exp.Table):
        if table.name.lower() not in schema_lower:
            missing.append(table.name)
    
    return missing


def _classify_schema_error(error_message: str, ast: Optional[Any] = None) -> list:
    """
    Classify a schema validation error into specific tags.
    
    Args:
        error_message: Error message string
        ast: Optional AST node to determine affected clauses
    """
    errors = []
    msg_lower = error_message.lower()
    error_code = extract_error_code(error_message)
    taxonomy_category = get_taxonomy_category(error_code)
    affected_clauses = []
    if ast is not None:
        try:
            from ast_parsers.query_analyzer import extract_sql_clauses
            all_clauses = extract_sql_clauses(ast)
            if any(c in all_clauses for c in ["WHERE", "JOIN"]):
                affected_clauses = [c for c in ["WHERE", "JOIN"] if c in all_clauses]
            elif "SELECT" in all_clauses:
                affected_clauses = ["SELECT"]
        except Exception:
            pass
    if ("column" in msg_lower and "could not be resolved" in msg_lower) or \
       "unknown column" in msg_lower or \
       ("column" in msg_lower and "not found" in msg_lower):
        errors.append(ValidationError(
            tag=SchemaErrorTags.HALLUCINATION_COLUMN,
            message=error_message,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "semantic",
            affected_clauses=affected_clauses,
        ))
    elif "ambiguous" in msg_lower:
        errors.append(ValidationError(
            tag=SchemaErrorTags.AMBIGUOUS_COLUMN,
            message=error_message,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "semantic",
            affected_clauses=affected_clauses,
        ))
    elif "type" in msg_lower:
        errors.append(ValidationError(
            tag=SchemaErrorTags.TYPE_MISMATCH,
            message=error_message,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "semantic",
            affected_clauses=affected_clauses,
        ))
    else:
        errors.append(ValidationError(
            tag=SchemaErrorTags.UNKNOWN_ERROR,
            message=error_message,
            error_code=error_code,
            taxonomy_category=taxonomy_category or "semantic",
            affected_clauses=affected_clauses,
        ))
    
    return errors


# =============================================================================
# Combined Validator (Main Entry Point)
# =============================================================================

def validate_query(
    sql: str,
    schema: Optional[Dict[str, Dict[str, str]]] = None,
    dialect: str = "postgres",
) -> ValidationResult:
    """
    Validate SQL query with optional schema validation.
    
    This is the main entry point for query validation. It runs:
    1. Part 1: Static Analysis (syntax validation) - always
    2. Part 2: Semantic Validation (schema validation) - if schema provided
    
    Args:
        sql: The SQL query string to validate
        schema: Optional schema definition as dict of {table_name: {column_name: type}}
        dialect: SQL dialect (default: "postgres")
    
    Returns:
        ValidationResult with validation status and any errors found
    
    Example:
        >>> # Syntax-only validation
        >>> result = validate_query("SELECT * FROM users")
        >>> result.valid
        True
        
        >>> # With schema validation
        >>> schema = {"users": {"id": "int", "name": "text"}}
        >>> result = validate_query("SELECT address FROM users", schema=schema)
        >>> result.valid
        False
        >>> result.tags
        ['schema_hallucination_col']
    """
    # Part 1: Static Analysis (always run)
    syntax_result = validate_syntax(sql, dialect=dialect)
    
    if not syntax_result.valid:
        return syntax_result
    
    # Part 2: Semantic Validation (only if schema provided)
    if schema is not None:
        schema_result = validate_schema(sql, schema, dialect=dialect)
        if schema_result.ast is None:
            schema_result.ast = syntax_result.ast
        if schema_result.query_metadata is None and schema_result.ast is not None:
            schema_result.query_metadata = analyze_query(schema_result.ast)
        return schema_result
    if syntax_result.query_metadata is None and syntax_result.ast is not None:
        syntax_result.query_metadata = analyze_query(syntax_result.ast)
    
    return syntax_result
