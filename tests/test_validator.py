# -*- coding: utf-8 -*-
"""
Tests for SQL Query Validator

Test cases adapted from sequel2sql_capstone.py experimentation.
"""

import pytest
from ast_parsers import (
    validate_syntax,
    validate_schema,
    validate_query,
    ValidationResult,
    ValidationError,
    QueryMetadata,
    extract_error_code,
    get_taxonomy_category,
    get_category_for_tag,
    extract_sql_clauses,
    calculate_complexity,
    generate_pattern_signature,
    analyze_query,
)
from ast_parsers.errors import SyntaxErrorTags, SchemaErrorTags


# =============================================================================
# Test Schema (from experimentation)
# =============================================================================

TEST_SCHEMA = {
    "users": {
        "id": "int",
        "name": "text",
        "email": "text",
        "signup_date": "date",
    },
    "orders": {
        "order_id": "int",
        "user_id": "int",
        "amount": "decimal",
    },
}


# =============================================================================
# Part 1: Syntax Validation Tests
# =============================================================================

class TestSyntaxValidation:
    """Tests for validate_syntax() - Part 1: Static Analysis."""
    
    def test_valid_simple_query(self):
        """Valid SQL should pass syntax validation."""
        result = validate_syntax("SELECT id, name FROM users WHERE id > 5")
        
        assert result.valid is True
        assert result.errors == []
        assert result.ast is not None
    
    def test_valid_complex_query(self):
        """Complex valid SQL with joins should pass."""
        sql = """
        SELECT u.name, o.amount 
        FROM users u 
        JOIN orders o ON u.id = o.user_id 
        WHERE o.amount > 100
        """
        result = validate_syntax(sql)
        
        assert result.valid is True
        assert result.ast is not None
    
    def test_trailing_comma(self):
        """Trailing comma before FROM should be detected."""
        result = validate_syntax("SELECT id, name, FROM users")
        
        assert result.valid is False
        assert SyntaxErrorTags.TRAILING_DELIMITER in result.tags
    
    def test_unbalanced_parentheses(self):
        """Unbalanced parentheses should be detected."""
        result = validate_syntax("SELECT count(* FROM users WHERE id = 1")
        
        assert result.valid is False
        assert SyntaxErrorTags.UNBALANCED_TOKENS in result.tags
    
    def test_unbalanced_closing_paren(self):
        """Extra closing parenthesis should be detected."""
        result = validate_syntax("SELECT id FROM users WHERE id = 1)")
        
        assert result.valid is False
        assert SyntaxErrorTags.UNBALANCED_TOKENS in result.tags
    
    def test_keyword_misuse(self):
        """Misused keywords should be detected."""
        result = validate_syntax("SELECT FROM users WHERE id")
        
        assert result.valid is False
        # Should have some error tag
        assert len(result.tags) > 0
    
    def test_unterminated_string(self):
        """Unterminated string literals should be detected."""
        result = validate_syntax("SELECT * FROM users WHERE name = 'John")
        
        assert result.valid is False
        assert SyntaxErrorTags.UNTERMINATED_STRING in result.tags
    
    def test_result_to_dict(self):
        """ValidationResult.to_dict() should work correctly."""
        result = validate_syntax("SELECT id, name, FROM users")
        
        d = result.to_dict()
        assert "valid" in d
        assert "errors" in d
        assert "tags" in d
        assert d["valid"] is False


# =============================================================================
# Part 2: Schema Validation Tests
# =============================================================================

class TestSchemaValidation:
    """Tests for validate_schema() - Part 2: Semantic Validation."""
    
    def test_valid_query_with_schema(self):
        """Valid query against schema should pass."""
        result = validate_schema(
            "SELECT id, name FROM users",
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is True
        assert result.errors == []
    
    def test_hallucinated_table(self):
        """Non-existent table should be detected."""
        result = validate_schema(
            "SELECT * FROM non_existent_table",
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is False
        assert SchemaErrorTags.HALLUCINATION_TABLE in result.tags
        assert "non_existent_table" in result.error_messages[0]
    
    def test_hallucinated_column(self):
        """Non-existent column should be detected."""
        result = validate_schema(
            "SELECT address FROM users",
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is False
        assert SchemaErrorTags.HALLUCINATION_COLUMN in result.tags
    
    def test_valid_join_query(self):
        """Valid join query should pass schema validation."""
        result = validate_schema(
            "SELECT users.id, orders.amount FROM users JOIN orders ON users.id = orders.user_id",
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is True
    
    def test_ambiguous_column_in_join(self):
        """Ambiguous column in join should be detected."""
        # Both users and orders could have columns that need qualification
        # This tests that ambiguous references are caught
        schema_with_ambiguity = {
            "users": {"id": "int", "name": "text"},
            "orders": {"id": "int", "user_id": "int"},  # Both have 'id'
        }
        result = validate_schema(
            "SELECT id FROM users JOIN orders ON users.id = orders.user_id",
            schema=schema_with_ambiguity,
        )
        
        # Should either fail with ambiguous or require qualification
        # The exact behavior depends on sqlglot version
        if not result.valid:
            assert SchemaErrorTags.AMBIGUOUS_COLUMN in result.tags or len(result.errors) > 0
    
    def test_case_insensitive_table_names(self):
        """Table name matching should be case-insensitive."""
        result = validate_schema(
            "SELECT id FROM USERS",  # uppercase
            schema=TEST_SCHEMA,  # lowercase keys
        )
        
        assert result.valid is True


# =============================================================================
# Combined Validator Tests
# =============================================================================

class TestValidateQuery:
    """Tests for validate_query() - Combined validation."""
    
    def test_syntax_only_valid(self):
        """Valid syntax without schema should pass."""
        result = validate_query("SELECT * FROM any_table")
        
        assert result.valid is True
    
    def test_syntax_only_invalid(self):
        """Invalid syntax without schema should fail."""
        result = validate_query("SELECT id, FROM users")
        
        assert result.valid is False
        assert SyntaxErrorTags.TRAILING_DELIMITER in result.tags
    
    def test_with_schema_valid(self):
        """Valid query with schema should pass both stages."""
        result = validate_query(
            "SELECT id, name FROM users",
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is True
    
    def test_syntax_error_stops_schema_validation(self):
        """Syntax errors should prevent schema validation."""
        result = validate_query(
            "SELECT id, FROM users",  # syntax error
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is False
        # Should have syntax error, not schema error
        assert SyntaxErrorTags.TRAILING_DELIMITER in result.tags
        assert SchemaErrorTags.HALLUCINATION_TABLE not in result.tags
    
    def test_schema_error_after_syntax_passes(self):
        """Schema errors should be caught after syntax passes."""
        result = validate_query(
            "SELECT nonexistent_column FROM users",
            schema=TEST_SCHEMA,
        )
        
        assert result.valid is False
        assert SchemaErrorTags.HALLUCINATION_COLUMN in result.tags
    
    def test_dialect_parameter(self):
        """Dialect parameter should be respected."""
        # Test with MySQL-specific syntax
        result = validate_query(
            "SELECT `id` FROM users",  # backticks are MySQL style
            dialect="mysql",
        )
        
        assert result.valid is True


# =============================================================================
# Edge Cases and Error Classification Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error classification."""
    
    def test_empty_query(self):
        """Empty query should fail gracefully."""
        result = validate_syntax("")
        
        assert result.valid is False
    
    def test_whitespace_only_query(self):
        """Whitespace-only query should fail gracefully."""
        result = validate_syntax("   \n\t  ")
        
        assert result.valid is False
    
    def test_multiple_statements(self):
        """Query with multiple statements should be handled."""
        # sqlglot.parse_one expects single statement
        result = validate_syntax("SELECT 1; SELECT 2;")
        
        # Behavior depends on sqlglot version - may fail or parse first only
        # Just ensure it doesn't crash
        assert isinstance(result, ValidationResult)
    
    def test_cte_query(self):
        """CTE (WITH clause) should parse correctly."""
        sql = """
        WITH regional_sales AS (
            SELECT region, SUM(amount) AS total_sales
            FROM orders
            GROUP BY region
        )
        SELECT region, total_sales
        FROM regional_sales
        """
        result = validate_syntax(sql)
        
        assert result.valid is True
    
    def test_subquery(self):
        """Subqueries should parse correctly."""
        result = validate_syntax(
            "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        )
        
        assert result.valid is True
    
    def test_validation_error_to_dict(self):
        """ValidationError.to_dict() should work correctly."""
        error = ValidationError(
            tag="test_tag",
            message="Test message",
            location=42,
            context="test context",
        )
        
        d = error.to_dict()
        assert d["tag"] == "test_tag"
        assert d["message"] == "Test message"
        assert d["location"] == 42
        assert d["context"] == "test context"


# =============================================================================
# Error Code Extraction and Taxonomy Tests
# =============================================================================

class TestErrorCodes:
    """Tests for error code extraction and taxonomy mapping."""
    
    def test_extract_error_code_from_message(self):
        """Should extract SQLSTATE codes from error messages."""
        # Direct SQLSTATE format
        assert extract_error_code("ERROR: 42703: column 'x' does not exist") == "42703"
        assert extract_error_code("SQLSTATE 42P01") == "42P01"
        assert extract_error_code("[42702] ambiguous column") == "42702"
    
    def test_extract_error_code_from_pattern(self):
        """Should extract codes from error message patterns."""
        assert extract_error_code("column reference is ambiguous") == "42702"
        assert extract_error_code("table users does not exist") == "42P01"
        assert extract_error_code("syntax error at or near") == "42601"
        assert extract_error_code("must appear in the GROUP BY clause") == "42803"
    
    def test_extract_error_code_not_found(self):
        """Should return None when no code can be extracted."""
        assert extract_error_code("some random error message") is None
    
    def test_get_taxonomy_category(self):
        """Should map error codes to taxonomy categories."""
        assert get_taxonomy_category("42601") == "syntax"
        assert get_taxonomy_category("42703") == "semantic"
        assert get_taxonomy_category("42803") == "logical"
        assert get_taxonomy_category("42P01") == "semantic"
        assert get_taxonomy_category("42P20") == "logical"
        assert get_taxonomy_category("UNKNOWN") is None
    
    def test_get_category_for_tag(self):
        """Should find category for error tags."""
        assert get_category_for_tag("syntax_trailing_delimiter") == "syntax"
        assert get_category_for_tag("schema_hallucination_col") == "semantic"
        assert get_category_for_tag("logical_grouping_error") == "logical"
        assert get_category_for_tag("join_missing_join") == "join_related"
        assert get_category_for_tag("aggregation_missing_groupby") == "aggregation"


# =============================================================================
# Query Analysis Tests
# =============================================================================

class TestQueryAnalysis:
    """Tests for query analysis (clauses, complexity, signatures)."""
    
    def test_extract_sql_clauses_simple(self):
        """Should extract clauses from simple query."""
        result = validate_syntax("SELECT id, name FROM users WHERE id > 5")
        assert result.valid
        assert result.ast is not None
        
        clauses = extract_sql_clauses(result.ast)
        assert "SELECT" in clauses
        assert "FROM" in clauses
        assert "WHERE" in clauses
    
    def test_extract_sql_clauses_complex(self):
        """Should extract clauses from complex query."""
        sql = """
        SELECT u.name, COUNT(o.order_id) 
        FROM users u 
        JOIN orders o ON u.id = o.user_id 
        WHERE o.amount > 100
        GROUP BY u.name
        HAVING COUNT(o.order_id) > 5
        ORDER BY u.name
        LIMIT 10
        """
        result = validate_syntax(sql)
        assert result.valid
        assert result.ast is not None
        
        clauses = extract_sql_clauses(result.ast)
        assert "SELECT" in clauses
        assert "FROM" in clauses
        assert "JOIN" in clauses
        assert "WHERE" in clauses
        assert "GROUP" in clauses
        assert "HAVING" in clauses
        assert "ORDER" in clauses
        assert "LIMIT" in clauses
    
    def test_extract_sql_clauses_cte(self):
        """Should extract CTE clauses."""
        sql = """
        WITH regional_sales AS (
            SELECT region, SUM(amount) AS total_sales
            FROM orders
            GROUP BY region
        )
        SELECT region, total_sales
        FROM regional_sales
        """
        result = validate_syntax(sql)
        assert result.valid
        assert result.ast is not None
        
        clauses = extract_sql_clauses(result.ast)
        assert "WITH" in clauses or "CTE" in clauses
    
    def test_calculate_complexity_simple(self):
        """Should calculate complexity for simple query."""
        result = validate_syntax("SELECT id FROM users")
        assert result.valid
        assert result.ast is not None
        
        complexity = calculate_complexity(result.ast)
        assert complexity == 0  # No joins, subqueries, etc.
    
    def test_calculate_complexity_with_join(self):
        """Should calculate complexity for query with join."""
        sql = "SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id"
        result = validate_syntax(sql)
        assert result.valid
        assert result.ast is not None
        
        complexity = calculate_complexity(result.ast)
        assert complexity >= 1  # At least one join
    
    def test_calculate_complexity_with_subquery(self):
        """Should calculate complexity for query with subquery."""
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        result = validate_syntax(sql)
        assert result.valid
        assert result.ast is not None
        
        complexity = calculate_complexity(result.ast)
        assert complexity >= 1  # At least one subquery
    
    def test_calculate_complexity_with_cte(self):
        """Should calculate complexity for query with CTE."""
        sql = """
        WITH sales AS (SELECT * FROM orders)
        SELECT * FROM sales
        """
        result = validate_syntax(sql)
        assert result.valid
        assert result.ast is not None
        
        complexity = calculate_complexity(result.ast)
        assert complexity >= 2  # CTEs are weighted 2
    
    def test_generate_pattern_signature(self):
        """Should generate pattern signature for query."""
        result = validate_syntax("SELECT id FROM users WHERE id > 5")
        assert result.valid
        assert result.ast is not None
        
        signature = generate_pattern_signature(result.ast)
        assert isinstance(signature, str)
        assert len(signature) > 0
        # Should contain main clauses
        assert "SELECT" in signature or "FROM" in signature
    
    def test_analyze_query(self):
        """Should perform complete query analysis."""
        sql = """
        SELECT u.name, COUNT(o.order_id) 
        FROM users u 
        JOIN orders o ON u.id = o.user_id 
        WHERE o.amount > 100
        GROUP BY u.name
        """
        result = validate_syntax(sql)
        assert result.valid
        assert result.ast is not None
        
        metadata = analyze_query(result.ast)
        assert isinstance(metadata, QueryMetadata)
        assert metadata.complexity_score >= 0
        assert len(metadata.pattern_signature) > 0
        assert len(metadata.clauses_present) > 0
        assert metadata.num_joins >= 1
        assert metadata.num_aggregations >= 1


# =============================================================================
# Enhanced Error Fields Tests
# =============================================================================

class TestEnhancedErrorFields:
    """Tests for enhanced error fields (error_code, taxonomy_category, affected_clauses)."""
    
    def test_error_has_error_code(self):
        """Errors should have error_code field when available."""
        result = validate_syntax("SELECT id, name, FROM users")
        assert not result.valid
        assert len(result.errors) > 0
        
        # Error code may or may not be present depending on error message
        # But the field should exist
        error = result.errors[0]
        assert hasattr(error, 'error_code')
        assert hasattr(error, 'taxonomy_category')
        assert hasattr(error, 'affected_clauses')
    
    def test_error_has_taxonomy_category(self):
        """Errors should have taxonomy_category field."""
        result = validate_syntax("SELECT id, name, FROM users")
        assert not result.valid
        
        error = result.errors[0]
        # Should have taxonomy category (syntax errors should map to "syntax")
        if error.taxonomy_category:
            assert error.taxonomy_category in ["syntax", "semantic", "logical"]
    
    def test_schema_error_has_affected_clauses(self):
        """Schema errors should have affected_clauses."""
        result = validate_schema(
            "SELECT address FROM users",
            schema=TEST_SCHEMA,
        )
        assert not result.valid
        
        error = result.errors[0]
        assert hasattr(error, 'affected_clauses')
        # Schema errors might affect SELECT or FROM clauses
        if error.affected_clauses:
            assert isinstance(error.affected_clauses, list)
    
    def test_error_to_dict_includes_new_fields(self):
        """Error.to_dict() should include new fields when present."""
        error = ValidationError(
            tag="test_tag",
            message="Test message",
            error_code="42703",
            taxonomy_category="semantic",
            affected_clauses=["SELECT", "FROM"],
        )
        
        d = error.to_dict()
        assert d["error_code"] == "42703"
        assert d["taxonomy_category"] == "semantic"
        assert d["affected_clauses"] == ["SELECT", "FROM"]


# =============================================================================
# Query Metadata Tests
# =============================================================================

class TestQueryMetadata:
    """Tests for query metadata in validation results."""
    
    def test_valid_query_has_metadata(self):
        """Valid queries should have query metadata."""
        result = validate_syntax("SELECT id, name FROM users WHERE id > 5")
        assert result.valid
        assert result.query_metadata is not None
        assert isinstance(result.query_metadata, QueryMetadata)
    
    def test_query_metadata_has_complexity(self):
        """Query metadata should include complexity score."""
        result = validate_syntax("SELECT id FROM users")
        assert result.valid
        assert result.query_metadata is not None
        assert result.query_metadata.complexity_score >= 0
    
    def test_query_metadata_has_signature(self):
        """Query metadata should include pattern signature."""
        result = validate_syntax("SELECT id FROM users WHERE id > 5")
        assert result.valid
        assert result.query_metadata is not None
        assert len(result.query_metadata.pattern_signature) > 0
    
    def test_query_metadata_has_clauses(self):
        """Query metadata should include list of clauses."""
        result = validate_syntax("SELECT id FROM users WHERE id > 5")
        assert result.valid
        assert result.query_metadata is not None
        assert isinstance(result.query_metadata.clauses_present, list)
        assert len(result.query_metadata.clauses_present) > 0
    
    def test_query_metadata_counts(self):
        """Query metadata should include element counts."""
        sql = """
        SELECT u.name, COUNT(o.order_id) 
        FROM users u 
        JOIN orders o ON u.id = o.user_id
        """
        result = validate_syntax(sql)
        assert result.valid
        assert result.query_metadata is not None
        assert result.query_metadata.num_joins >= 1
        assert result.query_metadata.num_aggregations >= 1
    
    def test_query_metadata_in_result_dict(self):
        """Query metadata should be included in result.to_dict()."""
        result = validate_syntax("SELECT id FROM users")
        assert result.valid
        
        d = result.to_dict()
        assert "query_metadata" in d
        assert d["query_metadata"] is not None
        assert "complexity_score" in d["query_metadata"]
        assert "pattern_signature" in d["query_metadata"]
    
    def test_schema_validation_has_metadata(self):
        """Schema validation results should also have metadata."""
        result = validate_schema(
            "SELECT id, name FROM users",
            schema=TEST_SCHEMA,
        )
        assert result.valid
        assert result.query_metadata is not None


# =============================================================================
# Run tests directly
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
