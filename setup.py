#!/usr/bin/env python3
"""
SEQUEL2SQL Setup Script

Interactive setup script that:
1. Checks prerequisites (Python, Docker, UV)
2. Installs dependencies
3. Configures .env file
4. Sets up Docker containers with PostgreSQL
5. Verifies database connectivity
6. Checks ChromaDB initialization

Usage:
        # Interactive mode
        python setup.py

        # Non-interactive with API key
        python setup.py --skip-prompts --api-key YOUR_KEY

        # Check only (no setup)
        python setup.py --check-only

        # Full benchmark setup
        python setup.py --benchmark
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import questionary
from dotenv import dotenv_values, set_key
from pyfiglet import Figlet
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.database.database import Database

# Initialize Rich console
console = Console()

# =============================================================================
# Constants & Configuration
# =============================================================================

ROOT_DIR = Path(__file__).parent.resolve()
BENCHMARK_DIR = ROOT_DIR / "benchmark"
DATA_DIR = BENCHMARK_DIR / "data"
CHROMA_DB_PATH = ROOT_DIR / "src" / "chroma_db"
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE = ROOT_DIR / ".env.example"

REQUIRED_PYTHON_VERSION = (3, 12)
POSTGRES_CONTAINER = "sequel2sql_postgresql"
POSTGRES_USER = "root"
POSTGRES_PASSWORD = "123123"
POSTGRES_PORT = 5433  # Use 5433 to avoid conflicts with local PostgreSQL on 5432
# load postgres_db from env if set, otherwise default to "postgres"
POSTGRES_DB = dotenv_values(ENV_FILE).get("DATABASE", "postgres")

# =============================================================================
# Helper Functions
# =============================================================================


def display_logo():
    """Display the SEQUEL2SQL logo using pyfiglet."""
    fig = Figlet(font="ansi_shadow", width=100)
    logo = fig.renderText("SEQUEL2SQL")
    console.print(
        Panel(
            f"[bold cyan]{logo}[/bold cyan]\n"
            "[bold]Interactive Setup Script[/bold]\n"
            "This script will guide you through setting up SEQUEL2SQL",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()


def check_python_version() -> Tuple[bool, str]:
    """Check if Python version meets requirements."""
    current = sys.version_info[:2]
    required = REQUIRED_PYTHON_VERSION

    if current >= required:
        version_str = f"Python {current[0]}.{current[1]}"
        return True, version_str
    else:
        version_str = (
            f"Python {current[0]}.{current[1]} (requires {required[0]}.{required[1]}+)"
        )
        return False, version_str


def check_uv_available() -> Tuple[bool, str]:
    """Check if UV package manager is available."""
    uv_path = shutil.which("uv")
    if uv_path:
        return True, "uv package manager"
    else:
        return False, "uv not found (optional)"


def check_docker_installed() -> Tuple[bool, str]:
    """Check if Docker is installed."""
    docker_path = shutil.which("docker")
    if docker_path:
        return True, "Docker"
    else:
        return False, "Docker not found"


def check_docker_running() -> Tuple[bool, str]:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "Docker daemon"
        else:
            return False, "Docker not running"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "Docker not accessible"


def check_env_file() -> Tuple[bool, str]:
    """Check if .env file exists and has API key configured."""
    if not ENV_FILE.exists():
        return False, ".env file not found"

    env_vars = dotenv_values(ENV_FILE)
    api_key = env_vars.get("GOOGLE_API_KEY", "")

    if not api_key or api_key == "your_main_google_api_key_here":
        return False, ".env exists but GOOGLE_API_KEY not configured"

    return True, ".env with GOOGLE_API_KEY"


def check_data_files(benchmark_mode: bool) -> Tuple[bool, str]:
    """Check if required data files exist (for benchmark mode)."""
    if not benchmark_mode:
        return True, "Data files (not required for web UI)"

    missing = []

    # Check benchmark data files
    if not (DATA_DIR / "postgresql_full.jsonl").exists():
        missing.append("postgresql_full.jsonl")

    if not (DATA_DIR / "postgre_table_dumps").is_dir():
        missing.append("postgre_table_dumps/")

    if not (DATA_DIR / "schemas").is_dir():
        missing.append("schemas/")

    if missing:
        return False, f"Missing: {', '.join(missing)}"

    return True, "Benchmark data files"


def get_chromadb_count() -> int:
    """Get count of records in ChromaDB collection."""
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))
        collection = client.get_collection("query_intents")
        return collection.count()
    except Exception:
        return 0


def check_chromadb() -> Tuple[bool, str]:
    """Check if ChromaDB is initialized with data."""
    if not CHROMA_DB_PATH.exists():
        return False, "ChromaDB directory not found"

    count = get_chromadb_count()
    if count > 0:
        return True, f"ChromaDB ({count} training examples)"
    else:
        return True, "ChromaDB initialized (0 examples)"


def run_preflight_checks(benchmark_mode: bool = False) -> Dict[str, Tuple[bool, str]]:
    """Run all pre-flight checks and return results."""
    checks = {
        "Python Version": check_python_version(),
        "UV Package Manager": check_uv_available(),
        "Docker Installed": check_docker_installed(),
        "Docker Running": check_docker_running(),
        ".env Configuration": check_env_file(),
        "ChromaDB": check_chromadb(),
    }

    if benchmark_mode:
        checks["Benchmark Data"] = check_data_files(True)

    return checks


def display_check_results(checks: Dict[str, Tuple[bool, str]]) -> bool:
    """Display check results in a table. Returns True if all critical checks passed."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Status", style="bold", width=3)
    table.add_column("Check", style="cyan")
    table.add_column("Details")

    critical_failed = False
    optional_checks = ["UV Package Manager", "ChromaDB", "Benchmark Data"]

    for check_name, (passed, details) in checks.items():
        if passed:
            status = "[bold green]✓[/bold green]"
        else:
            if check_name in optional_checks:
                status = "[bold yellow]⚠[/bold yellow]"
            else:
                status = "[bold red]✗[/bold red]"
                critical_failed = True

        table.add_row(status, check_name, details)

    console.print(
        Panel(table, title="[bold]Pre-flight Checks[/bold]", border_style="cyan")
    )
    console.print()

    return not critical_failed


def show_error_guidance(checks: Dict[str, Tuple[bool, str]]):
    """Show guidance for failed checks."""
    python_ok, _ = checks.get("Python Version", (True, ""))
    if not python_ok:
        console.print("[bold red] Python 3.12+ Required[/bold red]")
        console.print("Please upgrade Python:")
        console.print("  • Visit: https://www.python.org/downloads/")
        console.print()

    docker_installed, _ = checks.get("Docker Installed", (True, ""))
    if not docker_installed:
        console.print("[bold red] Docker Not Found[/bold red]")
        console.print("Please install Docker:")
        console.print("  • Visit: https://docs.docker.com/get-docker/")
        console.print()

    docker_running, _ = checks.get("Docker Running", (True, ""))
    if docker_installed and not docker_running:
        console.print("[bold red] Docker Not Running[/bold red]")
        console.print("Please start Docker:")
        console.print("  • On Linux: sudo systemctl start docker")
        console.print("  • On Mac/Windows: Start Docker Desktop")
        console.print()

    env_ok, env_details = checks.get(".env Configuration", (True, ""))
    if not env_ok:
        console.print("[bold red] Environment Configuration Missing[/bold red]")
        console.print("Please configure your API key:")
        console.print(f"  • Copy: cp {ENV_EXAMPLE} {ENV_FILE}")
        console.print("  • Get API key from: https://aistudio.google.com/apikey")
        console.print("  • Edit .env and set GOOGLE_API_KEY")
        console.print()


def show_setup_menu() -> Optional[str]:
    """Show setup mode selection menu."""
    console.print("[bold cyan]Setup Mode:[/bold cyan]")
    console.print()

    choice = questionary.select(
        "What would you like to set up?",
        choices=[
            questionary.Choice("1) Web UI Only (minimal setup)", value="web"),
            questionary.Choice(
                "2) Full Benchmark (includes data files)", value="benchmark"
            ),
            questionary.Choice("3) Exit", value="exit"),
        ],
    ).ask()

    return choice


def setup_env_file(api_key: Optional[str] = None, interactive: bool = True) -> bool:
    """Set up .env file with API key."""
    console.print("[bold cyan]Setting up .env file...[/bold cyan]")

    # Copy example if .env doesn't exist
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
            console.print(f"[dim]Copied {ENV_EXAMPLE.name} to .env[/dim]")
        else:
            # Create minimal .env
            ENV_FILE.write_text("# SEQUEL2SQL Configuration\n\n")

    # Get API key
    if not api_key and interactive:
        console.print()
        console.print("[yellow]You need a Google API key from:[/yellow]")
        console.print("  https://aistudio.google.com/apikey")
        console.print()

        api_key = questionary.text(
            "Enter your Google API key:",
            validate=lambda x: len(x) > 10 or "API key seems too short",
        ).ask()

        if api_key is None:  # User cancelled
            return False

    if api_key:
        set_key(ENV_FILE, "GOOGLE_API_KEY", api_key)
        console.print("[bold green]✓[/bold green] API key configured")

    # Optionally set DATABASE
    if interactive:
        set_database = questionary.confirm(
            "Set a default database name? (optional, default: postgres)",
            default=False,
        ).ask()

        if set_database:
            db_name = questionary.text(
                "Database name:",
                default="postgres",
            ).ask()

            if db_name:
                set_key(ENV_FILE, "DATABASE", db_name)

    console.print()
    return True


def install_dependencies(use_uv: bool = True) -> bool:
    """Install Python dependencies."""
    console.print("[bold cyan]Installing Python dependencies...[/bold cyan]")
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if use_uv:
                task = progress.add_task("Running uv sync...", total=None)
                result = subprocess.run(
                    ["uv", "sync"],
                    cwd=ROOT_DIR,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            else:
                task = progress.add_task("Running pip install...", total=None)
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-e", "."],
                    cwd=ROOT_DIR,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            progress.update(task, completed=True)

        if result.returncode != 0:
            console.print("[bold red]✗[/bold red] Installation failed")
            console.print("[dim]Error output:[/dim]")
            console.print(result.stderr)
            return False

        console.print("[bold green]✓[/bold green] Dependencies installed")
        console.print()
        return True

    except subprocess.TimeoutExpired:
        console.print("[bold red]✗[/bold red] Installation timed out")
        return False
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Installation failed: {e}")
        return False


def setup_docker_containers() -> bool:
    """Build and start Docker containers."""
    console.print("[bold cyan]Setting up Docker containers...[/bold cyan]")
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building and starting containers...", total=None)

            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                cwd=BENCHMARK_DIR,
                capture_output=True,
                text=True,
                timeout=600,
            )

            progress.update(task, completed=True)

        if result.returncode != 0:
            console.print("[bold red]✗[/bold red] Docker setup failed")
            console.print("[dim]Error output:[/dim]")
            console.print(result.stderr)
            return False

        console.print("[bold green]✓[/bold green] Docker containers started")
        console.print()
        return True

    except subprocess.TimeoutExpired:
        console.print("[bold red]✗[/bold red] Docker build timed out")
        return False
    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Docker setup failed: {e}")
        return False


def wait_for_postgres(timeout: int = 60) -> bool:
    """Wait for PostgreSQL to be ready."""
    console.print("[bold cyan]Waiting for PostgreSQL to be ready...[/bold cyan]")
    console.print()

    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking PostgreSQL health...", total=None)

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        POSTGRES_CONTAINER,
                        "pg_isready",
                        "-U",
                        POSTGRES_USER,
                    ],
                    capture_output=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    progress.update(task, completed=True)
                    console.print("[bold green]✓[/bold green] PostgreSQL is ready")
                    console.print()
                    return True

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                pass

            time.sleep(2)

        progress.update(task, completed=True)

    console.print("[bold red]✗[/bold red] PostgreSQL failed to become ready")
    console.print(f"[dim]Waited {timeout} seconds[/dim]")
    console.print()
    return False


def verify_database_connection() -> bool:
    """Verify `database connection` using the Database class."""
    console.print("[bold cyan]Verifying database connection...[/bold cyan]")
    console.print()

    try:
        # Import Database class
        sys.path.insert(0, str(ROOT_DIR / "src"))
        # Try to connect
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting to PostgreSQL...", total=None)

            db = Database(
                database_name=POSTGRES_DB,
                host="localhost",
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
            )

            table_count = len(db.table_names)
            progress.update(task, completed=True)

        console.print("[bold green]✓[/bold green] Database connection verified")
        console.print(f"  [dim]Connected to database: {POSTGRES_DB}[/dim]")
        console.print(f"  [dim]Tables available: {table_count}[/dim]")
        console.print()
        return True

    except Exception as e:
        console.print(f"[bold red]✗[/bold red] Connection failed: {e}")
        console.print()
        console.print("[yellow]Troubleshooting:[/yellow]")
        console.print("  • Check Docker container: docker ps")
        console.print(f"  • Check logs: docker logs {POSTGRES_CONTAINER}")
        console.print()
        return False


def show_success_summary(setup_type: str):
    """Display success summary with next steps."""
    if setup_type == "web":
        next_steps = """[bold green]✓ Setup Complete![/bold green]

[bold]Next Steps:[/bold]

1. Start the web interface:
   [cyan]uv run python sequel2sql.py[/cyan]

2. Open your browser:
   [cyan]http://localhost:8000[/cyan]

3. Start querying your database!

[dim]Optional: Configure DATABASE environment variable to use a specific database[/dim]
"""
    else:  # benchmark
        next_steps = """[bold green]✓ Setup Complete![/bold green]

[bold]Next Steps:[/bold]

1. Run the web interface:
   [cyan]uv run python sequel2sql.py[/cyan]

2. Or run the benchmark:
   [cyan]./benchmark.sh[/cyan]
   [dim]Use --limit 20 for a quick test[/dim]

3. Access web UI:
   [cyan]http://localhost:8000[/cyan]

[dim]Tip: Check benchmark/README.md for detailed benchmark instructions[/dim]
"""

    console.print(Panel(next_steps, border_style="green", padding=(1, 2)))


# =============================================================================
# Main Orchestration
# =============================================================================


def run_setup(
    benchmark_mode: bool = False,
    skip_docker: bool = False,
    skip_prompts: bool = False,
    api_key: Optional[str] = None,
    check_only: bool = False,
) -> int:
    """Main setup orchestration."""

    # Display logo
    display_logo()

    # Run pre-flight checks
    console.print("[bold]Running pre-flight checks...[/bold]")
    console.print()
    checks = run_preflight_checks(benchmark_mode)
    all_critical_passed = display_check_results(checks)

    if check_only:
        return 0 if all_critical_passed else 1

    # Show errors if critical checks failed
    if not all_critical_passed:
        show_error_guidance(checks)
        console.print(
            "[bold red]Please fix the issues above before continuing.[/bold red]"
        )
        return 1

    # Show warnings for optional checks
    uv_available, _ = checks.get("UV Package Manager", (True, ""))
    if not uv_available:
        console.print("[bold yellow]⚠ UV not found[/bold yellow]")
        console.print("  Will use pip instead. For faster performance, install uv:")
        console.print("  [cyan]pip install uv[/cyan]")
        console.print()

    chromadb_ok, chromadb_details = checks.get("ChromaDB", (True, ""))
    if "0 examples" in chromadb_details:
        console.print("[bold yellow]⚠ ChromaDB is empty[/bold yellow]")
        console.print("  To populate with training examples:")
        console.print(
            "  [cyan]cd src/query_intent_vectordb && uv run python embed_query_intent.py[/cyan]"
        )
        console.print()

    # Interactive mode - ask what to setup
    if not skip_prompts and not benchmark_mode:
        setup_choice = show_setup_menu()
        if setup_choice is None or setup_choice == "exit":
            console.print("[yellow]Setup cancelled[/yellow]")
            return 0

        benchmark_mode = setup_choice == "benchmark"

        # Re-check data files if benchmark mode selected
        if benchmark_mode:
            checks["Benchmark Data"] = check_data_files(True)
            data_ok, data_details = checks["Benchmark Data"]
            if not data_ok:
                console.print(f"[bold red]✗[/bold red] {data_details}")
                console.print()
                console.print(
                    "[yellow]Please ensure benchmark data files are present:[/yellow]"
                )
                console.print(f"  • {DATA_DIR / 'postgresql_full.jsonl'}")
                console.print(f"  • {DATA_DIR / 'postgre_table_dumps/'}")
                console.print(f"  • {DATA_DIR / 'schemas/'}")
                console.print()
                return 1

    console.print(
        f"[bold]Setup mode: {'Full Benchmark' if benchmark_mode else 'Web UI Only'}[/bold]"
    )
    console.print()

    # Setup steps
    env_ok, _ = checks.get(".env Configuration", (True, ""))
    if not env_ok:
        if not setup_env_file(api_key=api_key, interactive=not skip_prompts):
            console.print("[yellow]Setup cancelled during .env configuration[/yellow]")
            return 0

    # Install dependencies
    if not install_dependencies(use_uv=uv_available):
        return 1

    # Docker setup
    if not skip_docker:
        if not setup_docker_containers():
            return 1

        if not wait_for_postgres(timeout=60):
            return 1

        if not verify_database_connection():
            return 1
    else:
        console.print("[yellow]⚠ Skipping Docker setup (--skip-docker)[/yellow]")
        console.print()

    # Success!
    setup_type = "benchmark" if benchmark_mode else "web"
    show_success_summary(setup_type)

    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SEQUEL2SQL Interactive Setup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py                          # Interactive mode
  python setup.py --check-only             # Run checks only
  python setup.py --benchmark              # Setup for benchmarking
  python setup.py --skip-prompts           # Non-interactive
  python setup.py --api-key YOUR_KEY       # Provide API key
  python setup.py --skip-docker            # Skip Docker setup
		""",
    )

    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Setup for full benchmark (includes data validation)",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker container setup",
    )
    parser.add_argument(
        "--skip-prompts",
        action="store_true",
        help="Non-interactive mode (use defaults)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Google API key (avoids prompting)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run pre-flight checks only, don't setup",
    )

    args = parser.parse_args()

    try:
        exit_code = run_setup(
            benchmark_mode=args.benchmark,
            skip_docker=args.skip_docker,
            skip_prompts=args.skip_prompts,
            api_key=args.api_key,
            check_only=args.check_only,
        )
        sys.exit(exit_code)

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Setup cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print()
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")
        import traceback

        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
