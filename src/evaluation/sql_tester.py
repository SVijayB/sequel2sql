"""SQL testing module for BIRD-CRITIC evaluation.

This module provides functionality to:
1. Load a BIRD-CRITIC instance (with error SQL and true SQL)
2. Test the error SQL against the database
3. Compare with the true SQL solution
"""

import os
import json
import psycopg2
import subprocess
from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, Optional, List, Tuple, Any
from pathlib import Path

from .config import load_config, EvaluationConfig


def load_instance(instance_id: str, dataset_path: str) -> Optional[Dict]:
    """Load a specific instance from the combined dataset.
    
    Args:
        instance_id: Instance ID to load.
        dataset_path: Path to combined dataset JSONL file.
    
    Returns:
        Instance dictionary or None if not found.
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            instance = json.loads(line.strip())
            if instance.get("instance_id") == instance_id:
                return instance
    return None


def get_error_sql(instance: Dict) -> str:
    """Extract error SQL from instance.
    
    Args:
        instance: BIRD-CRITIC instance dictionary.
    
    Returns:
        Error SQL as string.
    """
    issue_sql = instance.get("issue_sql", [])
    if isinstance(issue_sql, list):
        return "\n".join(issue_sql) if issue_sql else ""
    return str(issue_sql) if issue_sql else ""


def get_true_sql(instance: Dict) -> str:
    """Extract true SQL solution from instance.
    
    Args:
        instance: BIRD-CRITIC instance dictionary.
    
    Returns:
        True SQL solution as string.
    """
    sol_sql = instance.get("sol_sql", [])
    if isinstance(sol_sql, list):
        return "\n".join(sol_sql) if sol_sql else ""
    return str(sol_sql) if sol_sql else ""


def get_database_name(instance: Dict) -> str:
    """Get database name for an instance.
    
    Args:
        instance: BIRD-CRITIC instance dictionary.
    
    Returns:
        Database name (db_id).
    """
    return instance.get("db_id", "")


def ensure_database_exists(db_name: str, config: Optional[EvaluationConfig] = None) -> bool:
    """Ensure a database exists, creating it from template if needed.
    
    Args:
        db_name: Database name to check/create.
        config: Configuration (loads default if None).
    
    Returns:
        True if database exists or was created, False otherwise.
    """
    if config is None:
        config = load_config()
    
    # Check if database exists
    try:
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
            return True  # Database exists
    except:
        pass
    
    # Database doesn't exist, try to create from template
    template_name = f"{db_name}_template"
    print(f"Database '{db_name}' not found. Attempting to create from template '{template_name}'...")
    
    try:
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
            print(f"Error: Template '{template_name}' does not exist. Database initialization may not have completed.")
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
        
        print(f"✓ Created database '{db_name}' from template")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error creating database: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        return False


def execute_sql(
    sql: str,
    db_name: str,
    config: Optional[EvaluationConfig] = None
) -> Tuple[bool, Optional[str], Optional[List]]:
    """Execute SQL against the database.
    
    Args:
        sql: SQL statement to execute.
        db_name: Database name to use.
        config: Configuration (loads default if None).
    
    Returns:
        Tuple of (success, error_message, results).
    """
    if config is None:
        config = load_config()
    
    # Ensure database exists before trying to connect
    if not ensure_database_exists(db_name, config):
        return False, f"Database '{db_name}' does not exist and could not be created from template", None
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=config.postgres_port,
            user=config.postgres_user,
            password=config.postgres_password,
            database=db_name
        )
        cur = conn.cursor()
        
        # Execute SQL
        cur.execute(sql)
        
        # Try to fetch results (for SELECT queries)
        try:
            results = cur.fetchall()
            column_names = [desc[0] for desc in cur.description] if cur.description else []
            conn.close()
            
            # Convert non-JSON-serializable types to strings
            serializable_results = []
            for row in results:
                serializable_row = []
                for value in row:
                    if isinstance(value, (date, datetime, time)):
                        serializable_row.append(value.isoformat())
                    elif isinstance(value, Decimal):
                        serializable_row.append(float(value))
                    elif isinstance(value, bytes):
                        serializable_row.append(value.decode('utf-8', errors='replace'))
                    else:
                        serializable_row.append(value)
                serializable_results.append(serializable_row)
            
            return True, None, {"columns": column_names, "rows": serializable_results}
        except psycopg2.ProgrammingError:
            # Not a SELECT query, commit and return
            conn.commit()
            conn.close()
            return True, None, None
        
    except psycopg2.Error as e:
        error_msg = str(e)
        return False, error_msg, None


def test_instance(
    instance_id: str,
    dataset_path: str,
    config_path: Optional[str] = None
) -> Dict:
    """Test a single instance: execute error SQL and compare with true SQL.
    
    Args:
        instance_id: Instance ID to test.
        dataset_path: Path to combined dataset.
        config_path: Optional config file path.
    
    Returns:
        Test results dictionary.
    """
    config = load_config(config_path)
    
    # Load instance
    instance = load_instance(instance_id, dataset_path)
    if not instance:
        return {"error": f"Instance {instance_id} not found"}
    
    # Get SQL statements
    error_sql = get_error_sql(instance)
    true_sql = get_true_sql(instance)
    db_name = get_database_name(instance)
    
    results = {
        "instance_id": instance_id,
        "db_name": db_name,
        "error_sql": error_sql,
        "true_sql": true_sql,
        "error_sql_result": None,
        "true_sql_result": None
    }
    
    # Test error SQL
    if error_sql:
        success, error_msg, data = execute_sql(error_sql, db_name, config)
        results["error_sql_result"] = {
            "success": success,
            "error": error_msg,
            "data": data
        }
    
    # Test true SQL
    if true_sql:
        success, error_msg, data = execute_sql(true_sql, db_name, config)
        results["true_sql_result"] = {
            "success": success,
            "error": error_msg,
            "data": data
        }
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test a BIRD-CRITIC instance against the database"
    )
    parser.add_argument(
        "--instance_id",
        type=str,
        required=True,
        help="Instance ID to test"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to combined dataset JSONL file"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    try:
        result = test_instance(args.instance_id, args.dataset, args.config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
