"""Database setup module for BIRD-CRITIC evaluation.

This module sets up the PostgreSQL database in Docker with all tables from dumps.
"""

import os
import subprocess
import time
from typing import Optional

from .config import load_config
from .docker_manager import DockerManager


def setup_database(config_path: Optional[str] = None) -> None:
    """Set up PostgreSQL database in Docker with all tables.
    
    Args:
        config_path: Optional path to configuration file.
    """
    # Load configuration
    config = load_config(config_path)
    
    # Initialize Docker manager
    docker_manager = DockerManager(config)
    
    # Check Docker availability
    if not docker_manager.check_docker_available():
        raise RuntimeError("Docker is not available")
    
    if not docker_manager.check_docker_compose_available():
        raise RuntimeError("Docker Compose is not available")
    
    # Step 1: Generate Docker Compose file
    print("\n=== Step 1: Generating Docker Compose configuration ===")
    compose_file = config.get_output_path("docker-compose.yml")
    docker_manager.generate_docker_compose(compose_file)
    
    # Step 2: Build containers
    print("\n=== Step 2: Building Docker containers ===")
    if not docker_manager.build_containers(compose_file):
        raise RuntimeError("Failed to build Docker containers")
    
    # Step 3: Start containers
    print("\n=== Step 3: Starting Docker containers ===")
    if not docker_manager.start_containers(compose_file):
        raise RuntimeError("Failed to start Docker containers")
    
    # Step 4: Wait for PostgreSQL to be ready
    print("\n=== Step 4: Waiting for PostgreSQL to be ready ===")
    max_wait = 180  # seconds (3 minutes - database initialization can take time)
    waited = 0
    
    # First, check if PostgreSQL container exists
    print("Checking PostgreSQL container status...")
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=bird_critic_postgresql", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"PostgreSQL container status: {result.stdout.strip()}")
    except:
        pass
    
    while waited < max_wait:
        # Try to connect to PostgreSQL
        try:
            result = docker_manager.exec_in_container(
                "bird_critic_postgresql",
                ["pg_isready", "-U", config.postgres_user]
            )
            if result.returncode == 0:
                print("PostgreSQL is ready!")
                break
        except subprocess.CalledProcessError as e:
            # Container might not be ready yet
            pass
        except Exception as e:
            # Container might not exist or not be accessible yet
            pass
        
        time.sleep(5)
        waited += 5
        if waited % 15 == 0:  # Print every 15 seconds
            print(f"Waiting for PostgreSQL... ({waited}s/{max_wait}s)")
    else:
        # Check what the actual status is
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=bird_critic_postgresql", "--format", "{{.Names}} {{.Status}}"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"PostgreSQL container status: {result.stdout.strip()}")
            
            # Check logs
            print("\nChecking PostgreSQL logs (last 20 lines):")
            result = subprocess.run(
                ["docker", "logs", "--tail", "20", "bird_critic_postgresql"],
                capture_output=True,
                text=True,
                check=False
            )
            print(result.stdout)
        except:
            pass
        
        raise RuntimeError("PostgreSQL did not become ready in time")
    
    print("\n=== Database setup complete ===")
    print(f"PostgreSQL is running on port {config.postgres_port}")
    print(f"Connection: postgresql://{config.postgres_user}:{config.postgres_password}@localhost:{config.postgres_port}")


def get_database_connection_string(config_path: Optional[str] = None) -> str:
    """Get database connection string.
    
    Args:
        config_path: Optional path to configuration file.
    
    Returns:
        PostgreSQL connection string.
    """
    config = load_config(config_path)
    return f"postgresql://{config.postgres_user}:{config.postgres_password}@localhost:{config.postgres_port}"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Set up PostgreSQL database for BIRD-CRITIC evaluation"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    try:
        setup_database(args.config)
    except Exception as e:
        print(f"Error during database setup: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
