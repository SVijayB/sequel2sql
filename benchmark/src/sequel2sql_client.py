"""
Sequel2SQL pipeline client for benchmark evaluation.

Wraps the full Sequel2SQL agent (schema lookup + validation + few-shot
retrieval + LLM) as a drop-in replacement for LLMClient.

Instead of receiving a pre-built prompt string, this client receives the
raw task data dict (with db_id, query, issue_sql) and runs the agent
pipeline. The agent is instructed (via BENCHMARK_PROMPT) to return only
a single ```sql ... ``` block, which the benchmark post-processor can
extract identically to responses from Google/Mistral.
"""

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any, Dict

import logfire

# I have no idea what any of the below code below means, I did not create this import mess and I am not going to bother trying to fix it.

# Load sqlagent by absolute file path to avoid the 'src' package namespace
# conflict between benchmark/src (sys.modules['src']) and the project-root src/.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SQLAGENT_PATH = _PROJECT_ROOT / "src" / "agent" / "sqlagent.py"

if "_s2s_sqlagent" not in sys.modules:
    # Temporarily expose project root so sqlagent's own imports (src.ast_parsers,
    # src.database, etc.) can resolve. We restore sys.modules['src'] afterwards
    # so the benchmark's 'src' package stays intact for its own modules.
    _saved_src = sys.modules.pop("src", None)
    _saved_src_children = {
        k: sys.modules.pop(k) for k in list(sys.modules) if k.startswith("src.")
    }
    sys.path.insert(0, str(_PROJECT_ROOT))
    try:
        _spec = importlib.util.spec_from_file_location(
            "_s2s_sqlagent", str(_SQLAGENT_PATH)
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["_s2s_sqlagent"] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        # Restore benchmark 'src' package in sys.modules
        if _saved_src is not None:
            sys.modules["src"] = _saved_src
        sys.modules.update(_saved_src_children)

_sqlagent = sys.modules["_s2s_sqlagent"]
agent = _sqlagent.agent
get_database_deps = _sqlagent.get_database_deps

from .logger_config import get_logger


class Sequel2SQLClient:
    """
    Benchmark client that runs the full Sequel2SQL agent pipeline.

    Exposes the same interface as LLMClient:
        - call_api_with_data(task_data) -> str
        - get_statistics() -> dict

    The returned string is always a ```sql ... ``` fenced block so the
    standard post-processor can extract it without any changes.
    """

    def __init__(self, model_config: Dict[str, Any]):
        self.model_config = model_config
        self.logger = get_logger()

        # Statistics (mirrors LLMClient)
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        self.logger.info(
            f"Initialized Sequel2SQLClient: {model_config['display_name']}"
        )

    def call_api_with_data(
        self, task_data: Dict[str, Any], max_retries: int = 2
    ) -> str:
        """
        Run the Sequel2SQL agent pipeline on a single benchmark task.

        Args:
            task_data: A benchmark row dict with at minimum:
                - "db_id"    — PostgreSQL database name
                - "query"    — Natural-language question / user intent
            max_retries: Number of retry attempts on transient errors

        Returns:
            Agent response string (a ```sql ... ``` block per BENCHMARK_PROMPT)

        Raises:
            RuntimeError: If all retries fail
        """
        db_id = task_data.get("db_id", "postgres")
        query = task_data.get("query", "")
        issue_sql_raw = task_data.get("issue_sql", [])

        # issue_sql is stored as a list of SQL strings in the benchmark data
        if isinstance(issue_sql_raw, list):
            issue_sql_str = "\n".join(issue_sql_raw)
        else:
            issue_sql_str = str(issue_sql_raw)

        # Build the user message matching the baseline prompt format.
        # Schema is omitted here — the agent fetches it live via tools.
        user_message = (
            f"# User issue:\n{query}\n\n"
            f"# Problematic SQL:\n```sql\n{issue_sql_str}\n```"
        )

        last_error = None

        with logfire.span(
            "benchmark.sequel2sql",
            db_id=db_id,
            query=query,
        ) as span:
            for attempt in range(1, max_retries + 1):
                try:
                    self.total_requests += 1

                    # Build database deps for this specific database
                    deps = get_database_deps(db_id)

                    # Run the full agent pipeline (tools: schema lookup, validation,
                    # few-shot retrieval, SQL analysis)
                    result = agent.run_sync(user_message, deps=deps)

                    self.successful_requests += 1
                    span.set_attribute("attempts", attempt)
                    time.sleep(1)  # respect 1 req/sec rate limit
                    return str(result.output)

                except Exception as e:
                    last_error = e
                    self.logger.debug(
                        f"Pipeline call failed (attempt {attempt}/{max_retries}): {str(e)[:120]}"
                    )
                    error_str = str(e).lower()

                    if (
                        "429" in error_str
                        or "rate" in error_str
                        or "quota" in error_str
                    ):
                        wait = 15 * attempt
                        self.logger.warning(
                            f"⚠️  Rate limit hit. Waiting {wait}s before retry {attempt}/{max_retries}..."
                        )
                        time.sleep(wait)
                    elif (
                        "500" in error_str
                        or "503" in error_str
                        or "server" in error_str
                    ):
                        self.logger.warning(
                            f"⚠️  Server error. Waiting 5s before retry {attempt}/{max_retries}..."
                        )
                        time.sleep(5)
                    elif attempt < max_retries:
                        time.sleep(2)

            self.failed_requests += 1
            span.set_attribute("attempts", max_retries)
            span.set_attribute("error", str(last_error)[:240])
            self.logger.error(
                f"❌ Pipeline call failed after {max_retries} attempts. "
                f"Last error: {str(last_error)[:120]}"
            )
            raise RuntimeError(
                f"Pipeline call failed after {max_retries} retries: {last_error}"
            )

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics (same schema as LLMClient)."""
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
