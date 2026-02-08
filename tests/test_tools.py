#!/usr/bin/env python3
"""
Test script for db_tools/tools.py

Run this to verify all database tools are working correctly.
Creates test database and tables automatically.
"""

import subprocess
import sys
from pathlib import Path

# Add src to path (go up one level from tests/ to root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db_tools.tools import (
    get_database_schema,
    get_table_columns,
    get_sample_rows,
    execute_query,
)


def setup_test_database(
    container_name: str = "sequel2sql_postgres",
    db_name: str = "test_db",
):
    """
    Create test database with sample tables and data.

    Args:
        container_name: Docker container name
        db_name: Name of test database to create
    """
    print("\n" + "=" * 70)
    print("SETUP: Creating Test Database and Tables")
    print("=" * 70)

    # SQL setup script
    setup_sql = f"""
-- Drop existing test database if it exists
DROP DATABASE IF EXISTS {db_name};

-- Create test database
CREATE DATABASE {db_name};

-- Connect to test database and create tables
\\c {db_name}

-- Create users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create posts table
CREATE TABLE posts (
    post_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    title VARCHAR(200) NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create comments table
CREATE TABLE comments (
    comment_id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(post_id),
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample users
INSERT INTO users (username, email) VALUES
('alice', 'alice@example.com'),
('bob', 'bob@example.com'),
('charlie', 'charlie@example.com'),
('diana', 'diana@example.com'),
('eve', 'eve@example.com');

-- Insert sample posts
INSERT INTO posts (user_id, title, content) VALUES
(1, 'First Post', 'This is Alice first post about databases'),
(1, 'SQL Tips', 'Learn advanced SQL techniques'),
(2, 'PostgreSQL Guide', 'A comprehensive guide to PostgreSQL'),
(3, 'Data Modeling', 'Best practices for database design'),
(4, 'Query Optimization', 'How to optimize slow queries'),
(5, 'Indexing Strategies', 'Understanding database indexes');

-- Insert sample comments
INSERT INTO comments (post_id, user_id, content) VALUES
(1, 2, 'Great post Alice!'),
(1, 3, 'Very informative'),
(2, 4, 'Thanks for the tips'),
(3, 1, 'Excellent guide Bob'),
(3, 5, 'Very helpful'),
(4, 2, 'I learned a lot'),
(5, 1, 'This is exactly what I needed'),
(6, 3, 'Perfect explanation');

-- Create indexes
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE UNIQUE INDEX idx_users_email ON users(email);
"""

    try:
        # Write SQL to temp file and execute in container
        cmd = [
            "docker",
            "exec",
            "-i",
            container_name,
            "psql",
            "-U",
            "root",
            "-d",
            "postgres",
        ]

        result = subprocess.run(
            cmd,
            input=setup_sql,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"✗ Setup failed: {result.stderr}")
            return False

        print("✓ Test database created successfully")
        print(f"  Database name: {db_name}")
        print("  Tables: users, posts, comments")
        print("  Sample data: 5 users, 6 posts, 8 comments")
        return True

    except subprocess.TimeoutExpired:
        print("✗ Setup timed out")
        return False
    except Exception as e:
        print(f"✗ Setup error: {e}")
        return False


def cleanup_test_database(
    container_name: str = "sequel2sql_postgres",
    db_name: str = "test_db",
):
    """
    Clean up test database.

    Args:
        container_name: Docker container name
        db_name: Name of test database to drop
    """
    try:
        cmd = [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            "root",
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {db_name};",
        ]

        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        pass  # Ignore cleanup errors


def test_get_database_schema():
    """Test getting database schema."""
    print("\n" + "=" * 70)
    print("TEST 1: Get Database Schema")
    print("=" * 70)

    result = get_database_schema(
        database_name="test_db",
    )

    print(f"Success: {result.success}")
    if result.duration:
        print(f"Duration: {result.duration.total_seconds():.3f}s")

    if result.success:
        print("\n✓ Schema retrieved successfully:")
        print(result.to_markdown())
    else:
        print(f"✗ Error: {result.error}")

    return result.success


def test_get_table_columns():
    """Test getting columns from a specific table."""
    print("\n" + "=" * 70)
    print("TEST 2: Get Table Columns")
    print("=" * 70)

    result = get_table_columns(
        database_name="test_db",
        table_name="users",
    )

    print(f"Success: {result.success}")
    if result.duration:
        print(f"Duration: {result.duration.total_seconds():.3f}s")

    if result.success:
        print("\n✓ Columns retrieved successfully:")
        print(result.to_markdown())
    else:
        print(f"✗ Error: {result.error}")

    return result.success


def test_get_sample_rows():
    """Test getting sample rows from a table."""
    print("\n" + "=" * 70)
    print("TEST 3: Get Sample Rows")
    print("=" * 70)

    result = get_sample_rows(
        database_name="test_db",
        table_name="posts",
        limit=3,
    )

    print(f"Success: {result.success}")
    if result.duration:
        print(f"Duration: {result.duration.total_seconds():.3f}s")

    if result.success:
        print("\n✓ Sample rows retrieved successfully:")
        print(result.to_markdown())
    else:
        print(f"✗ Error: {result.error}")

    return result.success


def test_get_sample_rows_with_columns():
    """Test getting sample rows with specific columns."""
    print("\n" + "=" * 70)
    print("TEST 3B: Get Sample Rows (Specific Columns)")
    print("=" * 70)

    result = get_sample_rows(
        database_name="test_db",
        table_name="comments",
        column_names=["comment_id", "content", "created_at"],
        limit=5,
    )

    print(f"Success: {result.success}")
    if result.duration:
        print(f"Duration: {result.duration.total_seconds():.3f}s")

    if result.success:
        print("\n✓ Sample rows retrieved successfully:")
        print(result.to_markdown())
    else:
        print(f"✗ Error: {result.error}")

    return result.success


def test_execute_query():
    """Test executing a custom SQL query."""
    print("\n" + "=" * 70)
    print("TEST 4: Execute Custom Query")
    print("=" * 70)

    query = """
    SELECT 
        u.username, 
        COUNT(p.post_id) as post_count,
        COUNT(c.comment_id) as comment_count
    FROM users u
    LEFT JOIN posts p ON u.user_id = p.user_id
    LEFT JOIN comments c ON u.user_id = c.user_id
    GROUP BY u.username
    ORDER BY post_count DESC
    LIMIT 5
    """

    result = execute_query(
        database_name="test_db",
        query=query,
    )

    print(f"Success: {result.success}")
    if result.duration:
        print(f"Duration: {result.duration.total_seconds():.3f}s")

    if result.success:
        print("\n✓ Query executed successfully:")
        print(result.to_markdown())
    else:
        print(f"✗ Error: {result.error}")

    return result.success


def test_invalid_query():
    """Test error handling with invalid query."""
    print("\n" + "=" * 70)
    print("TEST 5: Error Handling (Invalid Query)")
    print("=" * 70)

    # Try an UPDATE query (should fail - only SELECT allowed)
    query = "UPDATE users SET email = 'test@example.com' WHERE user_id = 1"
    result = execute_query(
        database_name="test_db",
        query=query,
    )

    print(f"Success: {result.success}")

    if not result.success:
        print(f"✓ Correctly rejected invalid query:")
        print(f"  Error: {result.error}")
    else:
        print(f"✗ Should have failed for non-SELECT query")

    return not result.success  # Should return True if error was caught


def test_nonexistent_table():
    """Test error handling with nonexistent table."""
    print("\n" + "=" * 70)
    print("TEST 6: Error Handling (Nonexistent Table)")
    print("=" * 70)

    result = get_table_columns(
        database_name="test_db",
        table_name="nonexistent_table",
    )

    print(f"Success: {result.success}")

    if not result.success:
        print(f"✓ Correctly handled nonexistent table:")
        print(f"  Error: {result.error}")
    else:
        print(f"✗ Should have failed for nonexistent table")

    return not result.success  # Should return True if error was caught


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "DATABASE TOOLS TEST SUITE" + " " * 30 + "║")
    print("╚" + "=" * 68 + "╝")

    # Setup test database
    if not setup_test_database():
        print("\n❌ Setup failed. Cannot continue with tests.")
        return 1

    tests = [
        ("Get Database Schema", test_get_database_schema),
        ("Get Table Columns", test_get_table_columns),
        ("Get Sample Rows", test_get_sample_rows),
        ("Get Sample Rows (Specific Columns)", test_get_sample_rows_with_columns),
        ("Execute Custom Query", test_execute_query),
        ("Error Handling (Invalid Query)", test_invalid_query),
        ("Error Handling (Nonexistent Table)", test_nonexistent_table),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            results[test_name] = False

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_flag in results.items():
        status = "✓ PASS" if passed_flag else "✗ FAIL"
        print(f"{status:8} | {test_name}")

    print("-" * 70)
    print(f"Total: {passed}/{total} tests passed")

    # Cleanup
    print("\n" + "=" * 70)
    print("CLEANUP: Removing Test Database")
    print("=" * 70)
    cleanup_test_database()
    print("✓ Test database cleaned up")

    print("=" * 70 + "\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
