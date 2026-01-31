"""Docker management module for BIRD-CRITIC evaluation environment."""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional


class DockerManager:
    """Manager for Docker containers used in evaluation."""
    
    def __init__(self, config):
        """Initialize Docker manager.
        
        Args:
            config: EvaluationConfig instance.
        """
        self.config = config
        self.compose_file = None
    
    def check_docker_available(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Docker version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Docker is not available. Please install Docker.")
            return False
    
    def check_docker_compose_available(self) -> bool:
        """Check if Docker Compose is available."""
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"Docker Compose version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Docker Compose is not available. Please install Docker Compose.")
            return False
    
    def generate_docker_compose(self, output_path: str) -> str:
        """Generate Docker Compose file with configured paths.
        
        Args:
            output_path: Path to save the generated docker-compose.yml file.
        
        Returns:
            Path to the generated docker-compose.yml file.
        """
        # Get absolute paths and normalize
        bird_repo = os.path.abspath(self.config.bird_critic_repo_path)
        postgres_dumps = os.path.abspath(self.config.postgres_dumps_path)
        eval_output = os.path.abspath(self.config.eval_output_dir)
        
        # Build context path
        build_context = os.path.join(bird_repo, "evaluation")
        
        # Verify paths exist
        if not os.path.exists(build_context):
            raise FileNotFoundError(
                f"BIRD-CRITIC evaluation directory not found: {build_context}\n"
                f"Please check that bird_critic_repo_path is correct: {bird_repo}"
            )
        
        if not os.path.exists(postgres_dumps):
            raise FileNotFoundError(
                f"PostgreSQL dumps directory not found: {postgres_dumps}\n"
                f"Please check that postgres_dumps_path is correct."
            )
        
        # Convert Windows paths to forward slashes for Docker (Docker handles this, but be explicit)
        # Docker Compose on Windows can handle backslashes, but forward slashes are more reliable
        def normalize_path_for_docker(path: str) -> str:
            """Normalize path for Docker Compose (use forward slashes)."""
            return path.replace('\\', '/')
        
        build_context_docker = normalize_path_for_docker(build_context)
        postgres_dumps_docker = normalize_path_for_docker(postgres_dumps)
        eval_output_docker = normalize_path_for_docker(eval_output)
        
        # Docker Compose template
        compose_content = f"""services:
  postgresql:
    build:
      context: {build_context_docker}
      dockerfile: ./env/Dockerfile.postgresql
    container_name: bird_critic_postgresql
    environment:
      POSTGRES_USER: {self.config.postgres_user}
      POSTGRES_PASSWORD: {self.config.postgres_password}
      TZ: "Asia/Hong_Kong"
    volumes:
      - postgresql_data:/var/lib/postgresql/data
      - {postgres_dumps_docker}:/docker-entrypoint-initdb.d/postgre_table_dumps
    command:
      - "-c"
      - "max_connections=300"
      - "-c"
      - "shared_buffers=256MB"
    ports:
      - "{self.config.postgres_port}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {self.config.postgres_user}"]
      interval: 10s
      timeout: 5s
      retries: 5

  so_eval_env:
    build:
      context: {build_context_docker}
      dockerfile: ./env/Dockerfile.so_eval
    container_name: so_eval_env
    volumes:
      - {build_context_docker}:/app/evaluation
      - {postgres_dumps_docker}:/app/postgre_table_dumps
      - {eval_output_docker}:/app/eval_output
    depends_on:
      postgresql:
        condition: service_healthy
    command: ["tail", "-f", "/dev/null"]
    environment:
      POSTGRES_HOST: postgresql
      POSTGRES_PORT: 5432
      POSTGRES_USER: {self.config.postgres_user}
      POSTGRES_PASSWORD: {self.config.postgres_password}

volumes:
  postgresql_data:
"""
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Write compose file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(compose_content)
        
        # Return absolute path
        abs_output_path = os.path.abspath(output_path)
        print(f"Generated Docker Compose file: {abs_output_path}")
        return abs_output_path
    
    def build_containers(self, compose_file: str) -> bool:
        """Build Docker containers.
        
        Args:
            compose_file: Path to docker-compose.yml file.
        
        Returns:
            True if successful, False otherwise.
        """
        if not self.check_docker_available():
            return False
        
        # Convert to absolute path
        compose_file = os.path.abspath(compose_file)
        compose_dir = os.path.dirname(compose_file)
        
        if not os.path.exists(compose_file):
            print(f"Error: Docker Compose file not found: {compose_file}")
            return False
        
        print(f"Building Docker containers from: {compose_file}")
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "build"],
                check=True,
                cwd=compose_dir
            )
            print("Docker containers built successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error building Docker containers: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                print(f"Error details: {e.stderr}")
            return False
    
    def start_containers(self, compose_file: str) -> bool:
        """Start Docker containers.
        
        Args:
            compose_file: Path to docker-compose.yml file.
        
        Returns:
            True if successful, False otherwise.
        """
        if not self.check_docker_available():
            return False
        
        # Convert to absolute path
        compose_file = os.path.abspath(compose_file)
        compose_dir = os.path.dirname(compose_file)
        
        if not os.path.exists(compose_file):
            print(f"Error: Docker Compose file not found: {compose_file}")
            return False
        
        print(f"Starting Docker containers from: {compose_file}")
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "up", "-d"],
                check=True,
                cwd=compose_dir
            )
            print("Docker containers started")
            
            # Wait a bit for containers to start
            print("Waiting for containers to start...")
            time.sleep(5)
            
            # Check if containers are running (with retries)
            # For database setup, we mainly care about PostgreSQL
            max_retries = 6
            for i in range(max_retries):
                # Check if PostgreSQL is at least running
                try:
                    result = subprocess.run(
                        ["docker", "ps", "--filter", "name=bird_critic_postgresql", "--format", "{{.Names}}"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    if "bird_critic_postgresql" in result.stdout:
                        print("PostgreSQL container is running")
                        # Check so_eval_env separately (it's less critical)
                        result2 = subprocess.run(
                            ["docker", "ps", "--filter", "name=so_eval_env", "--format", "{{.Names}}"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if "so_eval_env" in result2.stdout:
                            print("All containers are running")
                        else:
                            print("so_eval_env container may still be starting (this is OK)")
                        return True
                except:
                    pass
                
                if i < max_retries - 1:
                    print(f"Waiting for containers to be ready... ({i+1}/{max_retries})")
                    time.sleep(5)
            
            # Final check
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", "name=bird_critic_postgresql", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                if "bird_critic_postgresql" in result.stdout:
                    print("PostgreSQL container is running")
                    return True
            except:
                pass
            
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error starting Docker containers: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                print(f"Error details: {e.stderr}")
            return False
    
    def stop_containers(self, compose_file: str) -> bool:
        """Stop Docker containers.
        
        Args:
            compose_file: Path to docker-compose.yml file.
        
        Returns:
            True if successful, False otherwise.
        """
        if not self.check_docker_available():
            return False
        
        # Convert to absolute path
        compose_file = os.path.abspath(compose_file)
        compose_dir = os.path.dirname(compose_file)
        
        print("Stopping Docker containers...")
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "down"],
                check=True,
                cwd=compose_dir
            )
            print("Docker containers stopped")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error stopping Docker containers: {e}")
            return False
    
    def check_containers_running(self) -> bool:
        """Check if containers are running.
        
        Returns:
            True if containers are running, False otherwise.
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=bird_critic", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True
            )
            containers = result.stdout.strip().split("\n")
            containers = [c for c in containers if c]
            
            expected = ["bird_critic_postgresql", "so_eval_env"]
            running = all(container in containers for container in expected)
            
            if running:
                print("All containers are running")
            else:
                # Check which ones are missing
                missing = [c for c in expected if c not in containers]
                print(f"Found containers: {containers}")
                if missing:
                    print(f"Missing containers: {missing}")
                    # Check if they exist but aren't running
                    for container in missing:
                        result = subprocess.run(
                            ["docker", "ps", "-a", "--filter", f"name={container}", "--format", "{{.Names}} {{.Status}}"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if result.stdout.strip():
                            print(f"  {container}: {result.stdout.strip()}")
            
            return running
        except subprocess.CalledProcessError as e:
            print(f"Error checking containers: {e}")
            return False
    
    def exec_in_container(self, container_name: str, command: list) -> subprocess.CompletedProcess:
        """Execute a command in a Docker container.
        
        Args:
            container_name: Name of the container.
            command: Command to execute (as list of strings).
        
        Returns:
            CompletedProcess result.
        """
        cmd = ["docker", "exec", container_name] + command
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
