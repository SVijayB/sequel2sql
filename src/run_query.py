"""
SQL Query Executor with Docker Container Management

Executes SQL queries across different database dialects (PostgreSQL, MySQL, SQL Server, Oracle, SQLite)
by automatically starting the appropriate Docker container and collecting query statistics.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Database driver imports (will be installed via pyproject.toml)
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    pymysql = None

try:
    import pyodbc
except ImportError:
    pyodbc = None

try:
    import oracledb
except ImportError:
    oracledb = None

try:
    import sqlite3
except ImportError:
    sqlite3 = None


@dataclass
class QueryResult:
    """Result of a SQL query execution"""

    success: bool
    query: str
    dialect: str
    rows: list[dict[str, Any]] | None
    row_count: int
    execution_time_ms: float
    error: str | None = None
    statistics: dict[str, Any] | None = None

    def __str__(self) -> str:
        if not self.success:
            return f"❌ Query failed: {self.error}"

        stats = "\n".join(f"  {k}: {v}" for k, v in (self.statistics or {}).items())
        return f"""
✅ Query executed successfully
Dialect: {self.dialect}
Execution Time: {self.execution_time_ms:.2f} ms
Rows Returned: {self.row_count}
Statistics:
{stats}

Results:
{self._format_rows()}
"""

    def _format_rows(self) -> str:
        if not self.rows:
            return "  (No rows returned)"

        if self.row_count > 10:
            display_rows = self.rows[:10]
            suffix = f"\n  ... ({self.row_count - 10} more rows)"
        else:
            display_rows = self.rows
            suffix = ""

        lines = []
        for i, row in enumerate(display_rows, 1):
            lines.append(f"  Row {i}: {row}")

        return "\n".join(lines) + suffix


@dataclass
class DbConfig:
    """Database connection configuration"""

    dialect: str
    profile: str | None
    host: str
    port: int
    user: str
    password: str
    database: str
    driver: str | None = None  # For ODBC connections
    service_name: str | None = None  # For Oracle
    file_path: str | None = None  # For SQLite


def get_db_config(dialect: str | None) -> DbConfig:
    """Get database configuration for a given dialect"""
    d = (dialect or "postgres").strip().lower()

    if d in {"postgres", "postgresql"}:
        return DbConfig(
            dialect="postgres",
            profile=None,
            host="localhost",
            port=5432,
            user="root",
            password="123123",
            database="postgres",
        )

    if d == "mysql":
        return DbConfig(
            dialect="mysql",
            profile="mysql",
            host="localhost",
            port=3306,
            user="root",
            password="123123",
            database="mysql",
        )

    if d in {"sqlserver", "mssql"}:
        return DbConfig(
            dialect="sqlserver",
            profile="sqlserver",
            host="localhost",
            port=1433,
            user="sa",
            password="Y.sa123123",
            database="master",
            driver="ODBC Driver 18 for SQL Server",
        )

    if d == "oracle":
        return DbConfig(
            dialect="oracle",
            profile="oracle",
            host="localhost",
            port=1521,
            user="system",
            password="mypassword1",
            database="",
            service_name="ORCLPDB1",
        )

    if d in {"sqlite", "seqlite"}:
        return DbConfig(
            dialect="sqlite",
            profile="sqlite",
            host="",
            port=0,
            user="",
            password="",
            database="",
            file_path="./data/sqlite/example.db",  # Default path
        )

    raise ValueError(
        f"Unsupported dialect: {dialect!r}. Supported: postgres, mysql, sqlserver, oracle, sqlite"
    )


def ensure_container_running(config: DbConfig, wait_seconds: int = 10) -> None:
    """Start the Docker container for the specified database dialect"""

    if config.dialect == "sqlite":
        # SQLite doesn't need a container for basic usage unless mounting volumes
        print(f"📁 Using SQLite (file-based): {config.file_path}")
        return

    print(f"🐳 Starting Docker container for {config.dialect}...")

    # Build docker compose command
    compose_file = Path(__file__).parent.parent / "docker" / "docker-compose.yml"
    cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]

    # Add profile if needed
    if config.profile:
        cmd.insert(4, "--profile")
        cmd.insert(5, config.profile)

    # Start container
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to start container: {result.stderr}")

    print(f"⏳ Waiting {wait_seconds}s for {config.dialect} to be ready...")
    time.sleep(wait_seconds)
    print(f"✅ Container ready for {config.dialect}")


def execute_query_postgres(config: DbConfig, query: str) -> QueryResult:
    """Execute query on PostgreSQL"""
    if psycopg2 is None:
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=0,
            error="psycopg2 not installed. Install with: pip install psycopg2-binary",
        )

    start_time = time.time()

    try:
        conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
        )

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query)

            # Try to fetch results (for SELECT queries)
            try:
                rows = [dict(row) for row in cur.fetchall()]
                row_count = len(rows)
            except psycopg2.ProgrammingError:
                # No results (INSERT, UPDATE, DELETE, etc.)
                rows = None
                row_count = cur.rowcount

            conn.commit()

        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            success=True,
            query=query,
            dialect=config.dialect,
            rows=rows,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            statistics={
                "rows_affected": row_count,
                "connection": f"{config.host}:{config.port}/{config.database}",
            },
        )

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=execution_time_ms,
            error=str(e),
        )
    finally:
        if "conn" in locals():
            conn.close()


def execute_query_mysql(config: DbConfig, query: str) -> QueryResult:
    """Execute query on MySQL"""
    if pymysql is None:
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=0,
            error="pymysql not installed. Install with: pip install pymysql",
        )

    start_time = time.time()

    try:
        conn = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            cursorclass=pymysql.cursors.DictCursor,
        )

        with conn.cursor() as cur:
            cur.execute(query)

            # Try to fetch results (for SELECT queries)
            try:
                rows = cur.fetchall()
                row_count = len(rows)
            except:
                rows = None
                row_count = cur.rowcount

            conn.commit()

        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            success=True,
            query=query,
            dialect=config.dialect,
            rows=rows,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            statistics={
                "rows_affected": row_count,
                "connection": f"{config.host}:{config.port}/{config.database}",
            },
        )

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=execution_time_ms,
            error=str(e),
        )
    finally:
        if "conn" in locals():
            conn.close()


def execute_query_sqlserver(config: DbConfig, query: str) -> QueryResult:
    """Execute query on SQL Server"""
    if pyodbc is None:
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=0,
            error="pyodbc not installed. Install with: pip install pyodbc",
        )

    start_time = time.time()

    try:
        conn_str = (
            f"DRIVER={{{config.driver}}};"
            f"SERVER={config.host},{config.port};"
            f"DATABASE={config.database};"
            f"UID={config.user};"
            f"PWD={config.password};"
            "TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()

        cur.execute(query)

        # Try to fetch results (for SELECT queries)
        try:
            columns = [column[0] for column in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            row_count = len(rows)
        except:
            rows = None
            row_count = cur.rowcount

        conn.commit()

        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            success=True,
            query=query,
            dialect=config.dialect,
            rows=rows,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            statistics={
                "rows_affected": row_count,
                "connection": f"{config.host}:{config.port}/{config.database}",
            },
        )

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=execution_time_ms,
            error=str(e),
        )
    finally:
        if "conn" in locals():
            conn.close()


def execute_query_oracle(config: DbConfig, query: str) -> QueryResult:
    """Execute query on Oracle"""
    if oracledb is None:
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=0,
            error="oracledb not installed. Install with: pip install oracledb",
        )

    start_time = time.time()

    try:
        dsn = f"{config.host}:{config.port}/{config.service_name}"
        conn = oracledb.connect(user=config.user, password=config.password, dsn=dsn)

        cur = conn.cursor()
        cur.execute(query)

        # Try to fetch results (for SELECT queries)
        try:
            columns = [col[0] for col in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            row_count = len(rows)
        except:
            rows = None
            row_count = cur.rowcount

        conn.commit()

        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            success=True,
            query=query,
            dialect=config.dialect,
            rows=rows,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            statistics={"rows_affected": row_count, "connection": dsn},
        )

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=execution_time_ms,
            error=str(e),
        )
    finally:
        if "conn" in locals():
            conn.close()


def execute_query_sqlite(config: DbConfig, query: str) -> QueryResult:
    """Execute query on SQLite"""
    if sqlite3 is None:
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=0,
            error="sqlite3 not available (should be in standard library)",
        )

    start_time = time.time()

    try:
        # Ensure the directory exists
        db_path = Path(config.file_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        cur = conn.cursor()
        cur.execute(query)

        # Try to fetch results (for SELECT queries)
        try:
            rows = [dict(row) for row in cur.fetchall()]
            row_count = len(rows)
        except:
            rows = None
            row_count = cur.rowcount

        conn.commit()

        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            success=True,
            query=query,
            dialect=config.dialect,
            rows=rows,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            statistics={"rows_affected": row_count, "database_file": str(db_path)},
        )

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        return QueryResult(
            success=False,
            query=query,
            dialect=config.dialect,
            rows=None,
            row_count=0,
            execution_time_ms=execution_time_ms,
            error=str(e),
        )
    finally:
        if "conn" in locals():
            conn.close()


def run_query(
    query: str,
    dialect: str = "postgres",
    start_container: bool = True,
    wait_seconds: int = 10,
    sqlite_path: str | None = None,
) -> QueryResult:
    """
    Execute a SQL query on the specified database dialect.

    This is the main function to execute SQL queries across different databases.
    It handles container startup, query execution, and returns both the query
    results and execution statistics.

    Args:
        query: SQL query to execute (e.g., "SELECT * FROM users")
        dialect: Database dialect - "postgres" (default), "mysql", "sqlserver",
                "oracle", or "sqlite"
        start_container: Whether to start the Docker container (default: True)
        wait_seconds: Seconds to wait for container to be ready (default: 10)
        sqlite_path: Path to SQLite database file (only for SQLite)

    Returns:
        QueryResult object containing:
            - success: bool - Whether the query executed successfully
            - rows: list[dict] - Query output as list of row dictionaries
            - row_count: int - Number of rows returned/affected
            - execution_time_ms: float - Query execution time in milliseconds
            - statistics: dict - Additional statistics (connection info, etc.)
            - error: str - Error message if query failed
            - query: str - The executed query
            - dialect: str - The database dialect used

    Examples:
        >>> # Execute a PostgreSQL query
        >>> result = run_query("SELECT version()", dialect="postgres")
        >>> print(result.rows)  # [{'version': 'PostgreSQL 14.12...'}]
        >>> print(result.execution_time_ms)  # 45.23

        >>> # Execute a MySQL query
        >>> result = run_query("SELECT * FROM users WHERE age > 18", dialect="mysql")
        >>> if result.success:
        >>>     for row in result.rows:
        >>>         print(row)
        >>> else:
        >>>     print(f"Error: {result.error}")
    """
    # Get database configuration
    config = get_db_config(dialect)

    # Override SQLite path if provided
    if sqlite_path and config.dialect == "sqlite":
        config.file_path = sqlite_path

    # Start container if needed
    if start_container:
        ensure_container_running(config, wait_seconds)

    # Execute query based on dialect
    if config.dialect == "postgres":
        return execute_query_postgres(config, query)
    elif config.dialect == "mysql":
        return execute_query_mysql(config, query)
    elif config.dialect == "sqlserver":
        return execute_query_sqlserver(config, query)
    elif config.dialect == "oracle":
        return execute_query_oracle(config, query)
    elif config.dialect == "sqlite":
        return execute_query_sqlite(config, query)
    else:
        raise ValueError(f"Unsupported dialect: {config.dialect}")


def main():
    """Example usage"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Execute SQL queries across different database dialects"
    )
    parser.add_argument("query", help="SQL query to execute")
    parser.add_argument(
        "--dialect",
        "-d",
        default="postgres",
        choices=[
            "postgres",
            "postgresql",
            "mysql",
            "sqlserver",
            "mssql",
            "oracle",
            "sqlite",
        ],
        help="Database dialect (default: postgres)",
    )
    parser.add_argument(
        "--no-container",
        action="store_true",
        help="Don't start Docker container (assumes it's already running)",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=10,
        help="Seconds to wait for container to be ready (default: 10)",
    )
    parser.add_argument(
        "--sqlite-path", help="Path to SQLite database file (only for SQLite)"
    )

    args = parser.parse_args()

    result = run_query(
        query=args.query,
        dialect=args.dialect,
        start_container=not args.no_container,
        wait_seconds=args.wait,
        sqlite_path=args.sqlite_path,
    )

    print(result)


if __name__ == "__main__":
    main()
