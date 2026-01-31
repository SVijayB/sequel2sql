"""Verify Docker DB integration for BIRD-CRITIC evaluation.

Run: python -m src.evaluation.check_docker_db [--config path]

Checks:
- Docker and Docker Compose are available
- Container bird_critic_postgresql is running (if you use our database_setup)
- Can list databases and connect via localhost (psycopg2)

Note: The baseline pipeline (data_prep → Gemini → copy) does NOT require Docker.
Docker is only needed for database_setup and sql_tester.
"""

import subprocess
import sys
from typing import Optional


def check_docker() -> bool:
    """Check Docker is available."""
    try:
        r = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"  Docker: {r.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  Docker: not found (install Docker if you need local DB)")
        return False


def check_docker_compose() -> bool:
    """Check Docker Compose is available."""
    try:
        r = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"  Docker Compose: {r.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  Docker Compose: not found")
        return False


def check_container_running(container: str = "bird_critic_postgresql") -> bool:
    """Check if the PostgreSQL container is running."""
    try:
        r = subprocess.run(
            ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        out = r.stdout.strip()
        if out and container in out and "Up" in out:
            print(f"  Container {container}: running")
            return True
        print(f"  Container {container}: not running (run database_setup if you need it)")
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"  Container {container}: could not check")
        return False


def check_list_databases(config) -> bool:
    """List databases via docker exec (requires container running)."""
    try:
        r = subprocess.run(
            [
                "docker", "exec", "bird_critic_postgresql",
                "psql", "-U", config.postgres_user, "-d", "postgres",
                "-tc", "SELECT count(*) FROM pg_database WHERE datistemplate = false;",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        count = r.stdout.strip() or "0"
        print(f"  Databases (docker exec): {count} non-template DB(s)")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  Databases (docker exec): failed — {e}")
        return False


def check_psycopg2_connect(config) -> bool:
    """Connect via psycopg2 to localhost (same as sql_tester)."""
    try:
        import psycopg2
    except ImportError:
        print("  psycopg2: not installed (pip install psycopg2 for SQL testing)")
        return False
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=config.postgres_port,
            user=config.postgres_user,
            password=config.postgres_password,
            database="postgres",
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        print(f"  Connection localhost:{config.postgres_port}: OK (same as sql_tester)")
        return True
    except Exception as e:
        print(f"  Connection localhost:{config.postgres_port}: failed — {e}")
        return False


def main(config_path: Optional[str] = None) -> None:
    print("=== Docker DB integration check ===\n")
    print("Baseline pipeline (data_prep → Gemini → copy) does NOT require Docker.")
    print("Docker is only needed for database_setup and sql_tester.\n")

    from .config import load_config
    config = load_config(config_path)

    print("1. Docker availability")
    docker_ok = check_docker()
    compose_ok = check_docker_compose()
    print()

    print("2. PostgreSQL container (our database_setup)")
    container_ok = check_container_running()
    print()

    if container_ok:
        print("3. Database list (docker exec)")
        check_list_databases(config)
        print()
        print("4. Connection from host (psycopg2, same as sql_tester)")
        check_psycopg2_connect(config)
    else:
        print("3.–4. Skipped (container not running). Run: python -m src.evaluation.database_setup")

    print("\n=== Done ===")
    if not docker_ok or not compose_ok:
        sys.exit(1)
    # Don't exit non-zero if container isn't running; user may not need it


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Verify Docker DB integration for evaluation")
    p.add_argument("--config", type=str, default=None, help="Path to config.json")
    args = p.parse_args()
    main(args.config)
