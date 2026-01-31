"""Utility to check and list available databases in PostgreSQL container."""

import subprocess
import sys
from .config import load_config


def list_databases(config_path=None):
    """List all databases in the PostgreSQL container.
    
    Args:
        config_path: Optional path to configuration file.
    """
    config = load_config(config_path)
    
    try:
        # Connect to PostgreSQL and list databases
        result = subprocess.run(
            [
                "docker", "exec", "bird_critic_postgresql",
                "psql", "-U", config.postgres_user,
                "-c", "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        print("Available databases:")
        print(result.stdout)
        
        # Also list template databases
        result = subprocess.run(
            [
                "docker", "exec", "bird_critic_postgresql",
                "psql", "-U", config.postgres_user,
                "-c", "SELECT datname FROM pg_database WHERE datistemplate = true AND datname LIKE '%_template' ORDER BY datname;"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        print("Template databases:")
        print(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error output: {e.stderr}")


def check_init_script_logs(config_path=None):
    """Check PostgreSQL logs to see if init script ran.
    
    Args:
        config_path: Optional path to configuration file.
    """
    config = load_config(config_path)
    
    print("Checking PostgreSQL initialization logs...")
    try:
        result = subprocess.run(
            ["docker", "logs", "bird_critic_postgresql", "2>&1"],
            capture_output=True,
            text=True,
            check=False
        )
        logs = result.stdout
        
        # Look for key messages
        if "Done creating real DBs" in logs:
            print("✓ Database initialization completed")
        elif "Done creating template DBs" in logs:
            print("⚠ Template databases created, but real databases may not be created yet")
        else:
            print("⚠ Could not find initialization completion message")
        
        # Show last 50 lines
        print("\nLast 50 lines of logs:")
        print("\n".join(logs.split("\n")[-50:]))
        
    except Exception as e:
        print(f"Error checking logs: {e}")


def create_database_from_template(db_name: str, config_path=None):
    """Create a database from its template if it doesn't exist.
    
    Args:
        db_name: Name of the database to create (e.g., "codebase_community")
        config_path: Optional path to configuration file.
    """
    config = load_config(config_path)
    template_name = f"{db_name}_template"
    
    print(f"Creating database '{db_name}' from template '{template_name}'...")
    
    try:
        # Check if database already exists
        result = subprocess.run(
            [
                "docker", "exec", "bird_critic_postgresql",
                "psql", "-U", config.postgres_user,
                "-tc", f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "1" in result.stdout.strip():
            print(f"Database '{db_name}' already exists")
            return True
        
        # Check if template exists
        result = subprocess.run(
            [
                "docker", "exec", "bird_critic_postgresql",
                "psql", "-U", config.postgres_user,
                "-tc", f"SELECT 1 FROM pg_database WHERE datname='{template_name}'"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "1" not in result.stdout.strip():
            print(f"Error: Template database '{template_name}' does not exist")
            print("Please ensure database dumps are loaded correctly")
            return False
        
        # Create database from template
        result = subprocess.run(
            [
                "docker", "exec", "bird_critic_postgresql",
                "psql", "-U", config.postgres_user,
                "-c", f"CREATE DATABASE {db_name} WITH OWNER={config.postgres_user} TEMPLATE={template_name};"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"✓ Database '{db_name}' created successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error creating database: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error output: {e.stderr}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check and manage PostgreSQL databases")
    parser.add_argument("--list", action="store_true", help="List all databases")
    parser.add_argument("--logs", action="store_true", help="Check initialization logs")
    parser.add_argument("--create", type=str, help="Create a database from template (e.g., codebase_community)")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    
    args = parser.parse_args()
    
    if args.list:
        list_databases(args.config)
    elif args.logs:
        check_init_script_logs(args.config)
    elif args.create:
        create_database_from_template(args.create, args.config)
    else:
        # Default: list databases
        list_databases(args.config)
        print("\n" + "="*50)
        check_init_script_logs(args.config)
