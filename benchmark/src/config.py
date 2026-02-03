"""Configuration management for SEQUEL2SQL Benchmark"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Load environment variables from root .env
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)


# Gemma 3 27B Model Configuration (hardcoded since we only use this model)
MODEL_CONFIG = {
    "model_name": "models/gemma-3-27b-it",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "timeout": 10,  # seconds
    "max_threads": 8,
    "checkpoint_frequency": 10,  # Save checkpoint every N queries
}


def load_api_keys() -> List[str]:
    """
    Load 8 Gemini API keys from environment variables.

    Returns:
        List of 8 API keys

    Raises:
        SystemExit: If .env file doesn't exist or keys are missing
    """
    if not ENV_PATH.exists():
        print(f"\n❌ Error: .env file not found at {ENV_PATH}")
        print(f"\n💡 Please create a .env file from the template:")
        print(f"   cp {ROOT_DIR}/.env.example {ROOT_DIR}/.env")
        print(f"   # Then edit .env and add your 8 Gemini API keys\n")
        sys.exit(1)

    api_keys = []
    missing_keys = []

    for i in range(1, 9):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if not key or key == "your_api_key_here":
            missing_keys.append(f"GEMINI_API_KEY_{i}")
        else:
            api_keys.append(key)

    if missing_keys:
        print(f"\n❌ Error: Missing or invalid API keys in .env:")
        for key_name in missing_keys:
            print(f"   - {key_name}")
        print(f"\n💡 Please edit {ENV_PATH} and add valid Gemini API keys")
        print(f"   Get your keys from: https://ai.google.dev/\n")
        sys.exit(1)

    return api_keys


def get_model_config() -> Dict[str, Any]:
    """
    Get model configuration for Gemma 3 27B.

    Returns:
        Dictionary containing model configuration
    """
    return MODEL_CONFIG.copy()


def validate_config() -> bool:
    """
    Validate the complete configuration.

    Returns:
        True if configuration is valid

    Raises:
        SystemExit: If configuration is invalid
    """
    # Validate API keys
    api_keys = load_api_keys()

    # Validate paths
    benchmark_dir = Path(__file__).parent.parent
    data_dir = benchmark_dir / "data"

    if not data_dir.exists():
        print(f"\n❌ Error: Data directory not found: {data_dir}")
        sys.exit(1)

    postgresql_data = data_dir / "postgresql_full.jsonl"
    if not postgresql_data.exists():
        print(f"\n❌ Error: PostgreSQL dataset not found: {postgresql_data}")
        print(f"\n💡 Please copy the dataset:")
        print(
            f"   cp bird-critic/baseline/data/postgresql_full.jsonl {postgresql_data}\n"
        )
        sys.exit(1)

    postgre_dumps = data_dir / "postgre_table_dumps"
    if not postgre_dumps.exists():
        print(f"\n❌ Error: PostgreSQL table dumps not found: {postgre_dumps}")
        print(f"\n💡 Please copy the database dumps:")
        print(f"   cp -r bird-critic/evaluation/postgre_table_dumps {postgre_dumps}\n")
        sys.exit(1)

    return True


def get_benchmark_dir() -> Path:
    """Get the benchmark root directory."""
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Get the data directory."""
    return get_benchmark_dir() / "data"


def get_outputs_dir() -> Path:
    """Get the outputs directory."""
    return get_benchmark_dir() / "outputs"


def get_logs_dir() -> Path:
    """Get the logs directory."""
    return get_benchmark_dir() / "logs"


if __name__ == "__main__":
    # Test configuration
    print("Testing configuration...")
    print(f"\nRoot directory: {ROOT_DIR}")
    print(f"Benchmark directory: {get_benchmark_dir()}")
    print(f"Data directory: {get_data_dir()}")
    print(f"\nModel configuration:")
    for key, value in MODEL_CONFIG.items():
        print(f"  {key}: {value}")

    print(f"\nLoading API keys...")
    api_keys = load_api_keys()
    print(f"✓ Loaded {len(api_keys)} API keys")

    print(f"\nValidating configuration...")
    if validate_config():
        print("✓ Configuration is valid!\n")
