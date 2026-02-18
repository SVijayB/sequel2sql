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

from src.agent.sqlagent import get_database_deps, webui_agent

# Load environment variables
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

DATABASE_NAME = os.getenv("DATABASE", "postgres")

print("=" * 70)
print("SEQUEL2SQL - Web Interface")
print("=" * 70)
print(f"\nDatabase: {DATABASE_NAME}")
print("To use a different database, set DATABASE environment variable")

# =============================================================================
# Connect to Database
# =============================================================================

try:
    print(f"Connecting to {DATABASE_NAME}...")
    deps = get_database_deps(DATABASE_NAME)
    print("Connected successfully!")
    print(f"   Tables available: {len(deps.database.table_names)}")
except Exception as e:
    print(f"\nFailed to connect to database '{DATABASE_NAME}': {e}")
    print("\nMake sure PostgreSQL Docker container is running:")
    print("   docker compose -f benchmark/docker-compose.yml up -d postgresql")
    sys.exit(1)

# =============================================================================
# Web Application
# =============================================================================

app = webui_agent.to_web(
    deps=deps,
    models=[webui_agent.model, "google-gla:gemini-3-flash-preview"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
