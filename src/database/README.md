# Database Module

A clean, PostgreSQL-focused database interaction module for Sequel2SQL, inspired by the [dbdex](https://github.com/Finndersen/dbdex) pattern.

## Overview

This module provides a simplified interface for executing SQL queries and retrieving database schema information. It's designed to work seamlessly with Pydantic AI agents through dependency injection.

## Features

- **Single Database Class**: One centralized class managing all database operations
- **Query Result Container**: Structured `QueryResult` with markdown and CSV export
- **Dependency Injection**: Clean integration with Pydantic AI agents via `AgentDeps`
- **Schema Introspection**: Human-readable schema descriptions optimized for LLMs
- **Connection Efficiency**: Engine initialized once, connections managed by SQLAlchemy
- **Error Handling**: Clear exceptions for invalid queries and missing tables

## Architecture

```
src/database/
├── __init__.py          # Public API exports
├── database.py          # Database and QueryResult classes
├── deps.py              # AgentDeps for dependency injection
├── format_schema.py     # Schema formatting utilities
└── tools.py             # Pydantic AI tool functions
```

## Key Components

### Database Class

The main class for database interaction:

```python
from database import Database

# Initialize (engine created once)
db = Database("my_database")

# List tables
print(db.table_names)

# Execute query
result = db.execute_sql("SELECT * FROM users LIMIT 5")
print(result.to_markdown())

# Get schema
schema = db.describe_schema(["users", "orders"])
print(schema)
```

### QueryResult

Container for query results with multiple output formats:

```python
result = db.execute_sql("SELECT * FROM users")

# Properties
result.success       # bool: Was query successful?
result.row_count     # int: Number of rows returned
result.columns       # list[str]: Column names
result.duration      # timedelta: Execution time

# Export formats
result.to_markdown()           # Markdown table for LLMs
result.to_markdown(include_details=False)  # Just the table
result.to_csv()               # CSV format
```

### AgentDeps

Dependency injection for Pydantic AI agents:

```python
from database import AgentDeps
from agent.sqlagent import agent, get_database_deps

# Create dependencies
deps = get_database_deps("my_database", max_return_values=200)

# Use with agent
result = agent.run_sync("Show me all users", deps=deps)
```

### Agent Tools

Pydantic AI tools for query execution:

```python
from database import execute_sql

# Tool automatically uses context deps
@agent.tool
def execute_sql(ctx: RunContext[AgentDeps], sql: str) -> DBQueryResponse:
    # Validates SELECT-only
    # Limits results based on max_return_values
    # Returns structured response
    ...
```

## Usage Examples

### Example 1: Direct Database Access

```python
from database import Database

db = Database("california_schools_template")

# Get all tables
tables = db.table_names
print(f"Found {len(tables)} tables")

# Query data
result = db.execute_sql("SELECT * FROM schools LIMIT 3")
print(result.to_markdown())

# Export to CSV
csv_data = result.to_csv()
with open("schools.csv", "w") as f:
    f.write(csv_data)
```

### Example 2: Agent Integration

```python
from database import AgentDeps, Database
from agent.sqlagent import agent

# Create database connection
db = Database("california_schools_template")
deps = AgentDeps(database=db, max_return_values=200)

# Run queries through agent
result = agent.run_sync("How many schools are there?", deps=deps)
print(result.data)
```

### Example 3: Schema Inspection

```python
from database import Database

db = Database("formula_1_template")

# Get schema for specific tables
schema = db.describe_schema(["drivers", "races"])
print(schema)

# Example output:
# TABLE drivers (
#     COLUMNS
#         id INTEGER PRIMARY KEY NOT NULL
#         name VARCHAR(100) NOT NULL
#         nationality VARCHAR(50)
#     ---
#     INDEXES
#         INDEX idx_name (name ASC)
#     ---
#     CONSTRAINTS
#         FOREIGN KEY (team_id) REFERENCES teams (id)
# )
```

## Configuration

### Connection Parameters

Default connection (matches Docker setup):
- **Host**: `localhost`
- **Port**: `5432`
- **User**: `root`
- **Password**: `123123`

Custom connection:
```python
db = Database(
    database_name="my_db",
    host="custom.host.com",
    port=5433,
    user="myuser",
    password="mypass",
)
```

### Result Limiting

Control how many results are returned to the LLM:

```python
deps = AgentDeps(
    database=db,
    max_return_values=100,  # Fewer results for faster responses
)
```

The `execute_sql` tool calculates max rows as: `5 + max_return_values / num_columns`

## Design Decisions

### Why This Architecture?

1. **Database Class vs Functions**: Enables state tracking (`last_query`), one-time engine initialization, cleaner API
2. **Readable Text Schema**: Better LLM comprehension than JSON, includes all schema elements
3. **Dependency Injection**: Cleaner agent code, easier testing, follows proven patterns
4. **Markdown Tables**: Native format for LLMs, more readable than JSON wrappers
5. **No Redundant Functions**: Everything achievable via SQL - simpler mental model

### Changes from Original db_tools

- **Removed**: `get_table_columns()` - use `SELECT * FROM table LIMIT 0`
- **Removed**: `get_sample_rows()` - use `SELECT * FROM table LIMIT N`
- **Removed**: Complex JSON join-graph schema - use readable text format
- **Removed**: `_execute_in_docker()` - deprecated approach
- **Consolidated**: 438 lines → ~200 lines total across 5 focused files
- **Improved**: Engine created once vs per-call (major performance gain)

## Comparison with dbdex

This module is inspired by [dbdex](https://github.com/Finndersen/dbdex) but simplified for PostgreSQL-only usage:

### Similarities
- Database class with engine/metadata management
- QueryResult with to_markdown() and to_csv()
- Agent tools with dependency injection
- SELECT-only query validation

### Differences
- **PostgreSQL-only** (dbdex supports multiple databases)
- **Simpler schema format** (text DDL vs dbdex's detailed format)
- **No CLI tools** (focused on agent integration)
- **Fewer abstractions** (streamlined for specific use case)

## Testing

Run the test suite:
```bash
# Start PostgreSQL
docker compose -f benchmark/docker-compose.yml up -d postgresql

# Run tests
python test_database.py

# Run examples
python examples_database.py
```

## Error Handling

The module raises clear exceptions:

```python
from database import Database, InvalidQueryError, TableNotFoundError

db = Database("my_database")

# InvalidQueryError for non-SELECT queries
try:
    db.execute_sql("DELETE FROM users")
except InvalidQueryError as e:
    print(f"Only SELECT allowed: {e}")

# TableNotFoundError for invalid tables
try:
    schema = db.describe_schema(["nonexistent_table"])
except TableNotFoundError as e:
    print(f"Table not found: {e}")

# SQL errors preserved in QueryResult
try:
    result = db.execute_sql("SELECT * FROM invalid_syntax")
except Exception as e:
    # Error stored in db.last_query.error
    print(f"SQL error: {e}")
```

## API Reference

### Database

```python
Database(
    database_name: str,
    host: str = "localhost",
    port: int = 5432,
    user: str = "root",
    password: str = "123123",
)
```

**Properties:**
- `dialect: str` - Database dialect ("postgresql")
- `table_names: list[str]` - All table names
- `last_query: QueryResult | None` - Most recent query

**Methods:**
- `execute_sql(sql_query: str) -> QueryResult` - Execute SELECT query
- `describe_schema(table_names: list[str] | None = None) -> str` - Get schema

### QueryResult

```python
@dataclass
class QueryResult:
    sql: str
    rows: list[Row[Any]]
    executed_at: datetime
    duration: timedelta | None = None
    error: Exception | None = None
```

**Properties:**
- `success: bool` - Query succeeded
- `row_count: int` - Number of rows
- `columns: list[str] | None` - Column names

**Methods:**
- `to_markdown(include_details: bool = True) -> str` - Format as markdown
- `to_csv() -> str` - Format as CSV

### AgentDeps

```python
@dataclass
class AgentDeps:
    database: Database
    max_return_values: int = 200
```

### Tools

```python
def execute_sql(ctx: RunContext[AgentDeps], sql: str) -> DBQueryResponse:
    """Execute SELECT query with result limiting."""
```

## Contributing

When modifying this module:

1. Keep it PostgreSQL-focused (don't add multi-DB support)
2. Maintain the clean separation of concerns
3. Ensure markdown output is LLM-friendly
4. Update tests when adding features
5. Follow the dbdex pattern for consistency

## Credits

- Inspired by [dbdex](https://github.com/Finndersen/dbdex) by Finndersen
- Built with SQLAlchemy and Pydantic AI
- Part of the Sequel2SQL project
