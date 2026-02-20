# -*- coding: utf-8 -*-
"""Comprehensive test: verify all validation functions work correctly."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ast_parsers.validator import validate_syntax, validate_schema, validate_query
from ast_parsers.llm_tool import validate_sql
from ast_parsers.errors import ValidationResult
from ast_parsers.models import ValidationResultOut

print("Testing all validation functions for consistency\n")
print("=" * 80)

# Test SQL
test_sql = "SELECT * FROM account WHERE account_id = 1"
invalid_sql = "SELECT * FROM nonexistent_table"

# 1. Test validate_syntax
print("\n1. validate_syntax()")
result = validate_syntax(test_sql, dialect="postgres")
print(f"   Return type: {type(result).__name__}")
print(f"   Has .valid attribute: {hasattr(result, 'valid')}")
print(f"   result.valid: {result.valid}")
assert isinstance(result, ValidationResult), "Should return ValidationResult"
assert result.valid == True, "Valid SQL should have valid=True"
print("   [PASS]")

# 2. Test validate_schema
print("\n2. validate_schema()")
schema = {"account": {"account_id": "bigint"}}
result = validate_schema(test_sql, schema, dialect="postgres")
print(f"   Return type: {type(result).__name__}")
print(f"   Has .valid attribute: {hasattr(result, 'valid')}")
print(f"   result.valid: {result.valid}")
assert isinstance(result, ValidationResult), "Should return ValidationResult"
assert result.valid == True, "Valid SQL should have valid=True"
print("   [PASS]")

# 3. Test validate_query
print("\n3. validate_query()")
result = validate_query(test_sql, schema=schema, dialect="postgres")
print(f"   Return type: {type(result).__name__}")
print(f"   Has .valid attribute: {hasattr(result, 'valid')}")
print(f"   result.valid: {result.valid}")
assert isinstance(result, ValidationResult), "Should return ValidationResult"
assert result.valid == True, "Valid SQL should have valid=True"
print("   [PASS]")

# 4. Test validate_sql
print("\n4. validate_sql()")
result = validate_sql(test_sql, db_name="financial", dialect="postgres")
print(f"   Return type: {type(result).__name__}")
print(f"   Has .valid attribute: {hasattr(result, 'valid')}")
print(f"   result.valid: {result.valid}")
assert isinstance(result, ValidationResultOut), "Should return ValidationResultOut"
assert result.valid == True, "Valid SQL should have valid=True"
print("   [PASS]")

# 5. Test with invalid SQL
print("\n5. Testing with invalid SQL")
result = validate_sql(invalid_sql, db_name="financial", dialect="postgres")
print(f"   result.valid: {result.valid}")
print(f"   len(result.errors): {len(result.errors)}")
assert result.valid == False, "Invalid SQL should have valid=False"
assert len(result.errors) > 0, "Invalid SQL should have errors"
print("   [PASS]")

print("\n" + "=" * 80)
print("\n[SUCCESS] ALL TESTS PASSED - All validation functions work correctly!")
print("   - validate_syntax, validate_schema, validate_query return ValidationResult")
print("   - validate_sql returns ValidationResultOut")
print("   - All include .valid flag that correctly reflects error state")

