"""
Example usage of the database module with the SQL agent.

This demonstrates how to use the refactored database module for various tasks.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent.sqlagent import agent, get_database_deps
from database import Database


def example_1_direct_database():
    """Example 1: Using Database class directly without agent."""
    print("=" * 70)
    print("EXAMPLE 1: Direct Database Usage")
    print("=" * 70)

    # Create database connection
    db = Database("california_schools_template")

    # Get list of tables
    print(f"\nTables in database: {db.table_names}")

    # Get schema for specific tables
    print("\n" + "-" * 70)
    print("Schema for 'schools' table:")
    print("-" * 70)
    schema = db.describe_schema(["schools"])
    print(schema)

    # Execute a query
    print("\n" + "-" * 70)
    print("Sample data from schools:")
    print("-" * 70)
    result = db.execute_sql("SELECT * FROM schools LIMIT 3")
    print(result.to_markdown())

    # Access last query
    print(f"\nLast query executed: {db.last_query.sql}")
    print(f"Execution time: {db.last_query.duration}")
    print(f"Rows returned: {db.last_query.row_count}")


def example_2_agent_with_database():
    """Example 2: Using agent with database tools."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Agent with Database Tools")
    print("=" * 70)

    # Create database dependencies
    deps = get_database_deps("california_schools_template", max_return_values=200)

    # Run queries through the agent
    queries = [
        "What tables are available in this database?",
        "Show me 5 sample rows from the schools table",
        "How many schools are in the database?",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n{'-' * 70}")
        print(f"Query {i}: {query}")
        print("-" * 70)

        result = agent.run_sync(query, deps=deps)
        result_text = str(result.data) if hasattr(result, "data") else str(result)
        print(result_text)


def example_3_custom_connection():
    """Example 3: Custom database connection parameters."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Custom Connection Parameters")
    print("=" * 70)

    # Create database with custom parameters
    deps = get_database_deps(
        database_name="formula_1_template",
        host="localhost",
        port=5433,
        user="root",
        password="123123",
        max_return_values=100,  # Return fewer results
    )

    print("\nDatabase connected successfully!")
    print(f"Tables: {deps.database.table_names}")

    # Query through agent
    result = agent.run_sync(
        "List all tables and tell me what kind of data this database contains",
        deps=deps,
    )
    result_text = str(result.data) if hasattr(result, "data") else str(result)
    print(f"\nAgent response:\n{result_text}")


def example_4_error_handling():
    """Example 4: Error handling."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Error Handling")
    print("=" * 70)

    db = Database("postgres")

    # Try an invalid query (non-SELECT)
    print("\nAttempting invalid query (INSERT):")
    try:
        db.execute_sql("INSERT INTO test VALUES (1)")
    except Exception as e:
        print(f"✓ Caught expected error: {e}")

    # Try a query with syntax error
    print("\nAttempting query with syntax error:")
    try:
        db.execute_sql("SELECT * FORM pg_tables")  # Typo: FORM instead of FROM
    except Exception as e:
        print(f"✓ Caught expected error: {type(e).__name__}")
        print(f"  Error details: {str(e)[:100]}...")


def example_5_export_results():
    """Example 5: Exporting results to CSV."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Exporting Results to CSV")
    print("=" * 70)

    db = Database("california_schools_template")

    # Execute query
    result = db.execute_sql("SELECT * FROM schools LIMIT 5")

    # Export to CSV
    csv_data = result.to_csv()

    print("\nCSV output:")
    print(csv_data)

    # Save to file
    output_file = Path("schools_export.csv")
    output_file.write_text(csv_data)
    print(f"\n✓ Exported to {output_file.absolute()}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("DATABASE MODULE USAGE EXAMPLES")
    print("=" * 70)
    print("\nMake sure PostgreSQL Docker container is running:")
    print("  docker compose -f benchmark/docker-compose.yml up -d postgresql\n")

    try:
        # Run examples
        example_1_direct_database()
        example_2_agent_with_database()
        example_3_custom_connection()
        example_4_error_handling()
        example_5_export_results()

        print("\n" + "=" * 70)
        print("🎉 All examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
