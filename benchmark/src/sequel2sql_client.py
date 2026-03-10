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

import asyncio
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any, Dict

import logfire
import psycopg2
from pydantic_ai.usage import UsageLimits

from .logger_config import get_logger

# ---------------------------------------------------------------------------
# Benchmark agent limits — prevent runaway tool-calling loops
# ---------------------------------------------------------------------------
BENCHMARK_REQUEST_LIMIT = 25  # max LLM round-trips per query
BENCHMARK_TOOL_CALLS_LIMIT = 25  # max successful tool invocations per query

# Per-query wall-clock timeout for the agent run (seconds).
# Prevents a single query from hanging the whole benchmark run.
AGENT_RUN_TIMEOUT = 300  # 5 minutes


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

# invalidate_schema_cache is available now because _PROJECT_ROOT is in sys.path
# from the module loading block above and ast_parsers is already in sys.modules.
from ast_parsers.validator import invalidate_schema_cache  # noqa: E402

# psycopg2 connection config — same host/port as get_database_deps
_PG_HOST = "localhost"
_PG_PORT = 5534
_PG_USER = "root"
_PG_PASSWORD = "123123"


def _run_psycopg2_statements(db_id: str, statements: list, logger) -> None:
    """
    Execute a list of raw SQL statements via a plain psycopg2 connection.

    Using psycopg2 directly (not SQLAlchemy) keeps this completely isolated
    from the SQLAlchemy connection pool that Database.__init__ creates during
    metadata.reflect(). A pooled connection left open in autobegin state would
    hold a relation-level lock and block any subsequent DELETE/DDL.

    Each statement is committed and the connection is closed before returning,
    so there are zero open transactions when the agent runs.
    """
    conn = psycopg2.connect(
        dbname=db_id,
        user=_PG_USER,
        password=_PG_PASSWORD,
        host=_PG_HOST,
        port=_PG_PORT,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
    finally:
        conn.close()


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

        # Persistent event loop — keeps the agent's internal HTTP client
        # alive across sequential benchmark queries.  asyncio.run() would
        # close the loop after each call, killing the shared client.
        self._loop = asyncio.new_event_loop()

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
        schema = task_data.get("preprocess_schema", "")
        preprocess_sql = task_data.get("preprocess_sql", [])
        clean_up_sql = task_data.get("clean_up_sql", [])

        # issue_sql is stored as a list of SQL strings in the benchmark data
        if isinstance(issue_sql_raw, list):
            issue_sql_str = "\n".join(issue_sql_raw)
        else:
            issue_sql_str = str(issue_sql_raw)

        # Build the user message matching the baseline prompt format,
        # including the pre-processed schema from the benchmark data.
        user_message = (
            f"# Database Schema:\n{schema}\n\n"
            f"# User issue:\n{query}\n\n"
            f"# Problematic SQL:\n```sql\n{issue_sql_str}\n```"
        )

        last_error = None
        usage_limits = UsageLimits(
            request_limit=BENCHMARK_REQUEST_LIMIT,
            tool_calls_limit=BENCHMARK_TOOL_CALLS_LIMIT,
        )

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

                    # Run preprocess_sql via psycopg2 — fully independent from
                    # the SQLAlchemy pool so there are no lock conflicts.
                    # Then invalidate the validator's per-engine schema cache
                    # so EXPLAIN sees the post-preprocess table state.
                    if preprocess_sql:
                        self.logger.debug(
                            f"Running {len(preprocess_sql)} preprocess_sql"
                            f" statement(s) for {db_id}"
                        )
                        _run_psycopg2_statements(db_id, preprocess_sql, self.logger)
                        invalidate_schema_cache(deps.database.engine)

                    try:
                        # Run the agent with a wall-clock timeout.
                        # Using asyncio.run + wait_for keeps everything
                        # in a single fresh event loop per call, avoiding
                        # the "bound to a different event loop" errors
                        # that the old ThreadPoolExecutor approach caused.
                        async def _run_agent():
                            return await asyncio.wait_for(
                                agent.run(
                                    user_message,
                                    deps=deps,
                                    usage_limits=usage_limits,
                                ),
                                timeout=AGENT_RUN_TIMEOUT,
                            )

                        result = self._loop.run_until_complete(
                            _run_agent()
                        )
                    finally:
                        # Restore DB state via psycopg2 — same reasoning as above.
                        if clean_up_sql:
                            try:
                                _run_psycopg2_statements(
                                    db_id, clean_up_sql, self.logger
                                )
                            except Exception as cleanup_err:
                                self.logger.warning(
                                    f"clean_up_sql failed (non-fatal): {cleanup_err}"
                                )

                    self.successful_requests += 1
                    span.set_attribute("attempts", attempt)
                    time.sleep(2)  # respect rate limits
                    sql_text = result.output.sql.strip()
                    return f"```sql\n{sql_text}\n```"

                except Exception as e:
                    last_error = e
                    self.logger.debug(
                        f"Pipeline call failed (attempt {attempt}/{max_retries}): {str(e)[:120]}"
                    )
                    error_str = str(e).lower()

                    # Exponential backoff: base 2s, doubles each attempt,
                    # capped at 60s
                    backoff = min(2**attempt, 60)

                    if (
                        "429" in error_str
                        or "rate" in error_str
                        or "quota" in error_str
                    ):
                        wait = min(60 * attempt, 240)
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
                            f"⚠️  Server error. Waiting {backoff}s before retry {attempt}/{max_retries}..."
                        )
                        time.sleep(backoff)
                    elif attempt < max_retries:
                        time.sleep(backoff)

            self.failed_requests += 1
            span.set_attribute("attempts", attempt)
            span.set_attribute("error", str(last_error)[:240])
            self.logger.error(
                f"❌ Pipeline call failed after {attempt} attempt(s). "
                f"Last error: {str(last_error)[:120]}"
            )
            raise RuntimeError(
                f"Pipeline call failed after {attempt} attempt(s): {last_error}"
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
