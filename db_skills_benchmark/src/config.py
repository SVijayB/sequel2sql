"""Configuration management for DB Skills Benchmark"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables from root .env
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

# DB Skills Benchmark specific configuration
TARGET_DB_ID = "european_football_2"
SEEN_FRACTION = 0.5
SIMILARITY_THRESHOLD = 0.75
RANDOM_SEED = 42

# Supported providers (mirrored from benchmark/src/config.py)
PROVIDERS = {
    "google": {
        "model_id": "google-gla:gemini-3-flash-preview",
        "display_name": "Google Gemini 3 Flash Preview",
    },
    "mistral": {
        "model_id": "mistral:mistral-large-latest",
        "display_name": "Mistral Large Latest",
    },
    "sequel2sql": {
        "model_id": "sequel2sql:pipeline",
        "display_name": "Sequel2SQL Pipeline",
        "no_api_key": True,
    },
}

DEFAULT_PROVIDER = "mistral"

# Extracted directly from benchmark
RUN_CONFIG = {
    "timeout": 10,
    "max_threads": 8,
    "checkpoint_frequency": 10,
}

def load_api_key(provider: str) -> str:
    """Load API key for provider."""
    if PROVIDERS.get(provider, {}).get("no_api_key"):
        return ""

    if not ENV_PATH.exists():
        print(f"\n❌ Error: .env file not found at {ENV_PATH}")
        sys.exit(1)

    env_var_map = {
        "google": "GOOGLE_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }

    env_var = env_var_map.get(provider)
    if not env_var:
        print(f"\n❌ Error: Unknown provider '{provider}'")
        sys.exit(1)

    key = os.getenv(env_var)
    if not key or key.startswith("your_"):
        print(f"\n❌ Error: Missing or invalid API key in .env: {env_var}")
        sys.exit(1)

    return key

def get_model_config(provider: Optional[str] = None) -> Dict[str, Any]:
    if provider is None:
        provider = DEFAULT_PROVIDER

    if provider not in PROVIDERS:
        print(f"\n❌ Error: Unknown provider '{provider}'")
        sys.exit(1)

    provider_entry = PROVIDERS[provider]
    config = {
        **RUN_CONFIG,
        "provider": provider,
        "model_id": provider_entry["model_id"],
        "display_name": provider_entry["display_name"],
    }
    for key, value in provider_entry.items():
        if key not in ("model_id", "display_name"):
            config.setdefault(key, value)
    return config

def get_benchmark_root() -> Path:
    return ROOT_DIR / "benchmark"

def get_data_dir() -> Path:
    return get_benchmark_root() / "data"

def get_outputs_dir() -> Path:
    return ROOT_DIR / "db_skills_benchmark" / "outputs"

def get_logs_dir() -> Path:
    return ROOT_DIR / "db_skills_benchmark" / "logs"

def validate_config(provider: Optional[str] = None) -> bool:
    if provider is None:
        provider = DEFAULT_PROVIDER

    load_api_key(provider)

    data_dir = get_data_dir()
    if not data_dir.exists():
        print(f"\n❌ Error: Benchmark data directory not found: {data_dir}")
        sys.exit(1)

    postgresql_data = data_dir / "postgresql_full.jsonl"
    if not postgresql_data.exists():
        print(f"\n❌ Error: PostgreSQL dataset not found: {postgresql_data}")
        sys.exit(1)
        
    postgresql_sols = data_dir / "pg_sol.jsonl"
    if not postgresql_sols.exists():
        print(f"\n❌ Error: PostgreSQL solutions dataset not found: {postgresql_sols}")
        sys.exit(1)

    postgre_dumps = data_dir / "postgre_table_dumps"
    if not postgre_dumps.exists():
        print(f"\n❌ Error: PostgreSQL dumps not found: {postgre_dumps}")
        sys.exit(1)

    return True
