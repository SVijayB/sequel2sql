"""LLM API client backed by pydantic-ai (Google Gemini 3 Preview / Mistral Large)"""

import os
import time
from typing import Any, Dict

from pydantic_ai import Agent
from pydantic_ai.models import Model

from .logger_config import get_logger


class LLMClient:
    """
    LLM client backed by pydantic-ai.

    Supports:
    - Google Gemini 3 Preview  (provider="google")
    - Mistral Large Latest (provider="mistral")

    No key rotation — one API key per provider, retries handled by pydantic-ai.
    """

    def __init__(self, model_config: Dict[str, Any]):
        """
        Initialize the LLM client.

        Args:
            model_config: Model configuration dictionary from config.get_model_config()
        """
        self.model_config = model_config
        self.provider = model_config["provider"]
        self.model_id = model_config["model_id"]
        self.logger = get_logger()

        # Set API key env var expected by pydantic-ai provider
        self._configure_env()

        # Create a simple text agent with no tools
        self.agent: Agent[None, str] = Agent(self.model_id)

        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        self.logger.info(
            f"Initialized LLMClient: {model_config['display_name']} ({self.model_id})"
        )

    def _configure_env(self) -> None:
        """Ensure the right env var is set for the pydantic-ai provider."""
        from pathlib import Path

        from dotenv import load_dotenv

        root = Path(__file__).parent.parent.parent.parent
        load_dotenv(root / ".env", override=False)

        if self.provider == "google":
            # pydantic-ai google provider reads GEMINI_API_KEY
            key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if key:
                os.environ.setdefault("GEMINI_API_KEY", key)
        elif self.provider == "mistral":
            # pydantic-ai mistral provider reads MISTRAL_API_KEY
            # .env.example has a typo (MISTAL_API_KEY) — support both
            key = os.getenv("MISTRAL_API_KEY") or os.getenv("MISTAL_API_KEY")
            if key:
                os.environ["MISTRAL_API_KEY"] = key

    def call_api(self, prompt: str, max_retries: int = 3) -> str:
        """
        Call the LLM with automatic retry via pydantic-ai.

        Args:
            prompt: The prompt to send to the model
            max_retries: Maximum number of retry attempts on transient errors

        Returns:
            The model response text

        Raises:
            RuntimeError: If all retries fail
        """
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self.total_requests += 1
                result = self.agent.run_sync(prompt)
                self.successful_requests += 1
                time.sleep(1)  # respect 1 req/sec rate limit
                return str(result.output)

            except Exception as e:
                last_error = e
                self.logger.debug(
                    f"API call failed (attempt {attempt}/{max_retries}): {str(e)[:120]}"
                )
                error_str = str(e).lower()

                if "429" in error_str or "rate" in error_str or "quota" in error_str:
                    wait = 15 * attempt
                    self.logger.warning(
                        f"⚠️  Rate limit hit. Waiting {wait}s before retry {attempt}/{max_retries}..."
                    )
                    time.sleep(wait)
                elif "500" in error_str or "503" in error_str or "server" in error_str:
                    self.logger.warning(
                        f"⚠️  Server error. Waiting 5s before retry {attempt}/{max_retries}..."
                    )
                    time.sleep(5)
                elif attempt < max_retries:
                    time.sleep(2)

        self.failed_requests += 1
        self.logger.error(
            f"❌ API call failed after {max_retries} attempts. Last error: {str(last_error)[:120]}"
        )
        raise RuntimeError(f"API call failed after {max_retries} retries: {last_error}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests * 100
                if self.total_requests > 0
                else 0.0
            ),
        }


if __name__ == "__main__":
    from datetime import datetime

    from .config import DEFAULT_PROVIDER, get_model_config
    from .logger_config import setup_logger

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setup_logger(timestamp)

    for provider in ["google", "mistral"]:
        print(f"\nTesting provider: {provider}")
        try:
            config = get_model_config(provider)
            client = LLMClient(config)
            response = client.call_api("Say 'Hello, SEQUEL2SQL!' in one sentence.")
            print(f"✓ Response: {response}")
            print(f"  Stats: {client.get_statistics()}")
        except Exception as e:
            print(f"❌ Failed: {e}")
