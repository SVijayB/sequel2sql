"""Configuration management for BIRD-CRITIC evaluation setup.

This module handles loading and validating configuration for external paths
and API keys. Supports both environment variables and JSON config files.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class EvaluationConfig:
    """Configuration for BIRD-CRITIC evaluation."""
    
    # External paths (not in git)
    bird_critic_repo_path: str
    bird_solutions_path: str
    postgres_dumps_path: str
    eval_output_dir: str
    
    # API keys (optional, for baseline generation)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    
    # Model configuration
    model_name: str = "gpt-4o-2024-0806"
    gemini_model: str = "gemma-3-27b-it"  # Gemma 3 27B (same API key as Gemini)
    
    # Docker configuration
    postgres_port: int = 5432
    postgres_user: str = "root"
    postgres_password: str = "123123"
    
    def validate(self) -> None:
        """Validate that all required paths exist."""
        errors = []
        
        if not os.path.exists(self.bird_critic_repo_path):
            errors.append(f"BIRD-CRITIC repo path does not exist: {self.bird_critic_repo_path}")
        
        if not os.path.exists(self.bird_solutions_path):
            errors.append(f"Solutions path does not exist: {self.bird_solutions_path}")
        
        if not os.path.exists(self.postgres_dumps_path):
            errors.append(f"PostgreSQL dumps path does not exist: {self.postgres_dumps_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(self.eval_output_dir, exist_ok=True)
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(errors))
    
    def get_bird_critic_path(self, *parts: str) -> str:
        """Get a path relative to the BIRD-CRITIC repo."""
        return os.path.join(self.bird_critic_repo_path, *parts)
    
    def get_output_path(self, *parts: str) -> str:
        """Get a path relative to the output directory."""
        return os.path.join(self.eval_output_dir, *parts)


def load_config(config_path: Optional[str] = None) -> EvaluationConfig:
    """Load configuration from file or environment variables.
    
    Args:
        config_path: Path to JSON config file. If None, looks for config.json
                    in the evaluation directory, or uses environment variables.
    
    Returns:
        EvaluationConfig instance with loaded configuration.
    """
    # Load .env so GEMINI_API_KEY / GOOGLE_API_KEY etc. are available
    project_root = Path(__file__).resolve().parent.parent.parent
    _env_bases = [Path.cwd(), project_root]
    try:
        from dotenv import load_dotenv
        # utf-8-sig strips BOM (common on Windows); load from cwd then project root
        for base in _env_bases:
            env_path = base / ".env"
            if env_path.exists():
                load_dotenv(env_path, encoding="utf-8-sig")
    except ImportError:
        pass

    # Fallback: if key still missing, parse .env manually (handles BOM/encoding quirks)
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        for base in _env_bases:
            env_path = base / ".env"
            if not env_path.exists():
                continue
            try:
                with open(env_path, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, value = line.partition("=")
                        key, value = key.strip(), value.strip()
                        if key in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and value:
                            value = value.strip("'\"").strip()
                            if value:
                                os.environ[key] = value
                                break
            except Exception:
                continue

    # Try to load from config file first
    if config_path is None:
        # Look for config.json in the evaluation directory
        eval_dir = Path(__file__).parent
        config_path = eval_dir / "config.json"
    
    config_dict: Dict[str, Any] = {}
    
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = json.load(f)
    
    # Override with environment variables if present
    config_dict["bird_critic_repo_path"] = os.getenv(
        "BIRD_CRITIC_REPO_PATH", 
        config_dict.get("bird_critic_repo_path", "")
    )
    config_dict["bird_solutions_path"] = os.getenv(
        "BIRD_SOLUTIONS_PATH",
        config_dict.get("bird_solutions_path", "")
    )
    config_dict["postgres_dumps_path"] = os.getenv(
        "POSTGRES_DUMPS_PATH",
        config_dict.get("postgres_dumps_path", "")
    )
    config_dict["eval_output_dir"] = os.getenv(
        "EVAL_OUTPUT_DIR",
        config_dict.get("eval_output_dir", "evaluation_output")
    )
    
    # API keys from environment (preferred for security)
    config_dict["openai_api_key"] = os.getenv(
        "OPENAI_API_KEY",
        config_dict.get("openai_api_key")
    )
    config_dict["anthropic_api_key"] = os.getenv(
        "ANTHROPIC_API_KEY",
        config_dict.get("anthropic_api_key")
    )
    config_dict["google_api_key"] = os.getenv(
        "GOOGLE_API_KEY",
        config_dict.get("google_api_key")
    )
    # Gemini accepts either GEMINI_API_KEY or GOOGLE_API_KEY (same key works for both)
    config_dict["gemini_api_key"] = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or config_dict.get("gemini_api_key")
        or config_dict.get("google_api_key")
    )

    # Model configuration
    config_dict["model_name"] = os.getenv(
        "EVAL_MODEL_NAME",
        config_dict.get("model_name", "gpt-4o-2024-0806")
    )
    config_dict["gemini_model"] = os.getenv(
        "GEMINI_MODEL",
        config_dict.get("gemini_model", "gemma-3-27b-it")
    )
    
    # Docker configuration
    config_dict["postgres_port"] = int(os.getenv(
        "POSTGRES_PORT",
        config_dict.get("postgres_port", 5432)
    ))
    config_dict["postgres_user"] = os.getenv(
        "POSTGRES_USER",
        config_dict.get("postgres_user", "root")
    )
    config_dict["postgres_password"] = os.getenv(
        "POSTGRES_PASSWORD",
        config_dict.get("postgres_password", "123123")
    )
    
    # Validate required paths
    required = ["bird_critic_repo_path", "bird_solutions_path", "postgres_dumps_path"]
    missing = [key for key in required if not config_dict.get(key)]
    if missing:
        raise ValueError(
            f"Missing required configuration: {', '.join(missing)}. "
            f"Set via environment variables or config file."
        )
    
    config = EvaluationConfig(**config_dict)
    config.validate()
    
    return config
