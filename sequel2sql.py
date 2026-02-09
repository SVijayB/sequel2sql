"""
Sequel2SQL - Main Application Entry Point

Runs a web-based chat interface for the SQL agent using Pydantic AI's built-in web UI.
The agent is connected to a PostgreSQL database running in Docker.

Usage:
    # Use default database (postgres)
    uv run python sequel2sql.py

    # Connect to a specific database
    DATABASE=california_schools_template uv run python sequel2sql.py

    # Or set in .env file:
    DATABASE=formula_1_template
"""

import os
import sys

from dotenv import load_dotenv
from pydantic_ai import Agent

from src.agent.prompts.db_agent_prompt import DB_AGENT_PROMPT
from src.agent.sqlagent import get_database_deps
from src.database import AgentDeps, execute_sql

# Load environment variables
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

# Get database name from environment variable or use default
DATABASE_NAME = os.getenv("DATABASE", "postgres")

print("=" * 70)
print("SEQUEL2SQL - Web Interface with Database Connection")
print("=" * 70)
print(f"\nDatabase: {DATABASE_NAME}")
print("To use a different database, set DATABASE environment variable")

# =============================================================================
# Connect to Database
# =============================================================================

try:
    print(f"Connecting to {DATABASE_NAME}...")
    deps = get_database_deps(DATABASE_NAME)
    print(f"Connected successfully!")
    print(f"   Tables available: {len(deps.database.table_names)}")
    if deps.database.table_names:
        print(f"   Sample tables: {', '.join(deps.database.table_names[:5])}")
        if len(deps.database.table_names) > 5:
            print(f"   ... and {len(deps.database.table_names) - 5} more")
except Exception as e:
    print(f"\nFailed to connect to database '{DATABASE_NAME}': {e}")
    print("\nMake sure PostgreSQL Docker container is running:")
    print("   docker compose -f benchmark/docker-compose.yml up -d postgresql")
    sys.exit(1)

# =============================================================================
# Create Agent with Database Connection
# =============================================================================

# Create agent with database connection baked in via default deps
agent_with_db = Agent(
    "google-gla:gemini-3-flash-preview",
    deps_type=AgentDeps,
    system_prompt=DB_AGENT_PROMPT
    + f"\n\n# Connected Database\n\nYou are connected to the database: {DATABASE_NAME}\n\nAvailable tables:\n"
    + "\n".join(f"- {table}" for table in deps.database.table_names[:20]),
    tools=[execute_sql],
)

# Create web application - pass deps directly
app = agent_with_db.to_web(deps=deps)

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print("Starting Web Interface")
    print("=" * 70)
    print(f"\nOpen http://localhost:8000 in your browser")
    print(f"Connected database: {DATABASE_NAME}")
    print(f"\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
