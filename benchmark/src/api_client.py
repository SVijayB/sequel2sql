"""API client with intelligent key rotation for Gemini API"""

import itertools
import threading
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from .logger_config import get_logger


class GeminiAPIClient:
    """
    Thread-safe Gemini API client with intelligent key rotation.

    Features:
    - Cyclic rotation through 8 API keys
    - 60-second wait when all keys exhausted
    - Thread-safe key management
    - Automatic retry with exponential backoff
    """

    def __init__(self, api_keys: List[str], model_config: Dict[str, Any]):
        """
        Initialize the API client.

        Args:
            api_keys: List of 8 Gemini API keys
            model_config: Model configuration dictionary
        """
        self.api_keys = api_keys
        self.model_config = model_config
        self.key_cycle = itertools.cycle(api_keys)
        self.key_index = 0
        self.key_lock = threading.Lock()

        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.key_usage = {i: 0 for i in range(len(api_keys))}
        self.invalid_keys = set()

        # Get logger
        self.logger = get_logger()

        # Configure first key and create client
        self.current_key = api_keys[0]
        self.client = genai.Client(api_key=self.current_key)

        self.logger.info(f"Initialized GeminiAPIClient with {len(api_keys)} API keys")

    def _rotate_key(self) -> str:
        """
        Rotate to the next API key (thread-safe).

        Returns:
            The new current API key
        """
        with self.key_lock:
            # Skip invalid keys
            attempts = 0
            while attempts < len(self.api_keys):
                self.current_key = next(self.key_cycle)
                self.key_index = (self.key_index + 1) % len(self.api_keys)

                if self.key_index not in self.invalid_keys:
                    # Re-create client with new API key
                    self.client = genai.Client(api_key=self.current_key)
                    self.logger.debug(
                        f"Rotated to API key {self.key_index + 1}/{len(self.api_keys)}"
                    )
                    return self.current_key

                attempts += 1

            # All keys are invalid
            raise RuntimeError("All API keys are invalid")

    def _handle_rate_limit(self, retry_count: int) -> None:
        """
        Handle rate limit by waiting if all keys have been cycled.

        Args:
            retry_count: Current retry count
        """
        if retry_count % len(self.api_keys) == 0 and retry_count > 0:
            self.logger.warning(
                f"⚠️  All {len(self.api_keys)} API keys exhausted. "
                f"Waiting 60 seconds before retrying..."
            )
            time.sleep(60)
            self.logger.info("Resuming API calls with first key...")

    def call_api(self, prompt: str, max_retries: int = 24) -> str:
        """
        Call the Gemini API with automatic retry and key rotation.

        Args:
            prompt: The prompt to send to the API
            max_retries: Maximum number of retry attempts (default: 24 = 3 full cycles)

        Returns:
            The API response text

        Raises:
            RuntimeError: If all retries fail or all keys are invalid
        """
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                with self.key_lock:
                    self.total_requests += 1
                    # Track key usage for current key
                    self.key_usage[self.key_index] += 1

                # Generate response using new SDK
                response = self.client.models.generate_content(
                    model=self.model_config["model_name"],
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=self.model_config["temperature"],
                        max_output_tokens=self.model_config["max_tokens"],
                    ),
                )

                # Extract text from response
                result = response.text

                with self.key_lock:
                    self.successful_requests += 1

                return result

            except Exception as e:
                error_str = str(e).lower()
                last_error = e
                retry_count += 1

                # Log error
                self.logger.debug(
                    f"API call failed (attempt {retry_count}/{max_retries}): {str(e)[:100]}"
                )

                # Handle different error types
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    # Rate limit error - rotate key
                    self._handle_rate_limit(retry_count)
                    self._rotate_key()

                elif (
                    "401" in error_str
                    or "unauthorized" in error_str
                    or "invalid" in error_str
                ):
                    # Invalid key - mark as invalid and rotate
                    with self.key_lock:
                        self.invalid_keys.add(self.key_index)
                        self.logger.warning(
                            f"⚠️  API key {self.key_index + 1} is invalid. Skipping..."
                        )
                    self._rotate_key()

                elif "timeout" in error_str:
                    # Timeout - rotate and retry
                    self.logger.warning("⚠️  Request timeout. Rotating key...")
                    self._rotate_key()

                elif (
                    "500" in error_str
                    or "503" in error_str
                    or "server" in error_str
                    or "disconnected" in error_str
                    or "ssl" in error_str
                ):
                    # Server/connection error - wait, rotate key and retry
                    self.logger.warning(
                        "⚠️  Server/connection error. Rotating key and waiting 2 seconds..."
                    )
                    self._rotate_key()
                    time.sleep(2)

                else:
                    # Unknown error - wait and rotate
                    self.logger.warning(
                        f"⚠️  Unknown error: {str(e)[:100]}. Rotating key..."
                    )
                    time.sleep(2)
                    self._rotate_key()

        # Max retries exceeded
        with self.key_lock:
            self.failed_requests += 1

        self.logger.error(
            f"❌ Failed to get API response after {max_retries} attempts. "
            f"Last error: {str(last_error)[:100]}"
        )
        raise RuntimeError(f"API call failed after {max_retries} retries: {last_error}")

    def get_current_key_index(self) -> int:
        """Get the current API key index (1-based for display)."""
        with self.key_lock:
            return self.key_index + 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics."""
        with self.key_lock:
            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "key_usage": self.key_usage.copy(),
                "invalid_keys": list(self.invalid_keys),
                "success_rate": (
                    self.successful_requests / self.total_requests * 100
                    if self.total_requests > 0
                    else 0
                ),
            }

    def reset_to_key(self, index: int) -> None:
        """
        Reset to a specific key index (for resume).

        Args:
            index: Key index (0-based)
        """
        with self.key_lock:
            if 0 <= index < len(self.api_keys):
                self.key_index = index
                self.current_key = self.api_keys[index]
                self.client = genai.Client(api_key=self.current_key)
                self.logger.info(f"Reset to API key {index + 1}/{len(self.api_keys)}")


if __name__ == "__main__":
    # Test API client
    from datetime import datetime

    from .config import get_model_config, load_api_keys
    from .logger_config import setup_logger

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setup_logger(timestamp)

    api_keys = load_api_keys()
    model_config = get_model_config()

    client = GeminiAPIClient(api_keys, model_config)

    # Test simple query
    try:
        response = client.call_api("Say 'Hello, SEQUEL2SQL!' in one sentence.")
        print(f"\n✓ API Response: {response}\n")

        stats = client.get_statistics()
        print("Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"\n❌ API test failed: {e}\n")
