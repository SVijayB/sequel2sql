"""Configuration management for SEQUEL2SQL Benchmark"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables from root .env
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

# Supported providers and their model configs
PROVIDERS = {
    "google": {
        "model_id": "google-gla:models/gemma-3-27b-it",
        "display_name": "Google Gemma 3 27B",
    },
    "mistral": {
        "model_id": "mistral:mistral-large-latest",
        "display_name": "Mistral Large Latest",
    },
    "sequel2sql": {
        "model_id": "sequel2sql:pipeline",
        "display_name": "Sequel2SQL Pipeline",
        # No API key needed — uses DEFAULT_MODEL from sqlagent.py
        "no_api_key": True,
    },
}

DEFAULT_PROVIDER = "mistral"

# General run configuration
RUN_CONFIG = {
    "timeout": 10,  # seconds
    "max_threads": 8,
    "checkpoint_frequency": 10,  # Save checkpoint every N queries
}


def load_api_key(provider: str) -> str:
    """
    Load a single API key for the given provider from environment variables.

    Args:
        provider: "google", "mistral", or "sequel2sql"

    Returns:
        API key string, or empty string for providers that don't need one

    Raises:
        SystemExit: If .env file doesn't exist or the key is missing
    """
    # sequel2sql uses the agent pipeline — no external API key needed here
    if PROVIDERS.get(provider, {}).get("no_api_key"):
        return ""

    if not ENV_PATH.exists():
        print(f"\n❌ Error: .env file not found at {ENV_PATH}")
        print(f"\n💡 Please create a .env file from the template:")
        print(f"   cp {ROOT_DIR}/.env.example {ROOT_DIR}/.env")
        sys.exit(1)

    env_var_map = {
        "google": "GOOGLE_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }

    env_var = env_var_map.get(provider)
    if not env_var:
        print(f"\n❌ Error: Unknown provider '{provider}'")
        print(f"   Supported providers: {', '.join(PROVIDERS.keys())}")
        sys.exit(1)

    key = os.getenv(env_var)
    if not key or key.startswith("your_"):
        print(f"\n❌ Error: Missing or invalid API key in .env: {env_var}")
        if provider == "google":
            print(f"   Get your key from: https://aistudio.google.com/apikey")
        elif provider == "mistral":
            print(f"   Get your key from: https://console.mistral.ai/")
        print(f"   Then set it in {ENV_PATH}\n")
        sys.exit(1)

    return key


# Keep backward-compatible helper that loads 8 Gemini keys for old code paths
def load_api_keys() -> List[str]:
    """
    Load API keys from environment variables.
    For Google, loads up to 8 rotation keys (GEMINI_API_KEY_1..8) if present,
    falling back to GOOGLE_API_KEY.

    Returns:
        List of API keys (at least one)
    """
    if not ENV_PATH.exists():
        print(f"\n❌ Error: .env file not found at {ENV_PATH}")
        sys.exit(1)

    api_keys = []

    # Try numbered rotation keys first (legacy)
    for i in range(1, 9):
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if key and not key.startswith("your_"):
            api_keys.append(key)

    # Fall back to single GOOGLE_API_KEY
    if not api_keys:
        key = os.getenv("GOOGLE_API_KEY")
        if key and not key.startswith("your_"):
            api_keys.append(key)

    if not api_keys:
        print(
            "\n❌ Error: No valid Google API keys found in .env."
            "\n   Set GOOGLE_API_KEY or GEMINI_API_KEY_1..8\n"
        )
        sys.exit(1)

    return api_keys


def get_model_config(provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Get model configuration for the given provider.

    Args:
        provider: "google" or "mistral". Defaults to DEFAULT_PROVIDER.

    Returns:
        Dictionary containing model configuration
    """
    if provider is None:
        provider = DEFAULT_PROVIDER

    if provider not in PROVIDERS:
        print(f"\n❌ Error: Unknown provider '{provider}'")
        print(f"   Supported providers: {', '.join(PROVIDERS.keys())}")
        sys.exit(1)

    provider_entry = PROVIDERS[provider]
    config = {
        **RUN_CONFIG,
        "provider": provider,
        "model_id": provider_entry["model_id"],
        "display_name": provider_entry["display_name"],
    }
    # Forward any extra provider-level flags (e.g. no_api_key for sequel2sql)
    for key, value in provider_entry.items():
        if key not in ("model_id", "display_name"):
            config.setdefault(key, value)
    return config


def validate_config(provider: Optional[str] = None) -> bool:
    """
    Validate the complete configuration.

    Returns:
        True if configuration is valid

    Raises:
        SystemExit: If configuration is invalid
    """
    if provider is None:
        provider = DEFAULT_PROVIDER

    # Validate API key for the chosen provider
    load_api_key(provider)

    # Validate paths
    benchmark_dir = Path(__file__).parent.parent
    data_dir = benchmark_dir / "data"

    if not data_dir.exists():
        print(f"\n❌ Error: Data directory not found: {data_dir}")
        sys.exit(1)

    postgresql_data = data_dir / "postgresql_full.jsonl"
    if not postgresql_data.exists():
        print(f"\n❌ Error: PostgreSQL dataset not found: {postgresql_data}")
        sys.exit(1)

    postgre_dumps = data_dir / "postgre_table_dumps"
    if not postgre_dumps.exists():
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

    for provider in PROVIDERS:
        print(f"\nModel configuration [{provider}]:")
        config = get_model_config(provider)
        for key, value in config.items():
            print(f"  {key}: {value}")

    print(f"\nLoading API key for default provider ({DEFAULT_PROVIDER})...")
    key = load_api_key(DEFAULT_PROVIDER)
    print(f"✓ Loaded API key (length={len(key)})")

    print(f"\nValidating configuration...")
    if validate_config():
        print("✓ Configuration is valid!\n")
