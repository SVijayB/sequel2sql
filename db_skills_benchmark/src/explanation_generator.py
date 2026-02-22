import sys
from pathlib import Path

from benchmark.src.api_client import LLMClient
from db_skills_benchmark.src.config import get_model_config, DEFAULT_PROVIDER
from benchmark.src.logger_config import get_logger

def generate_fix_explanation(intent: str, error_sql: str, corrected_sql: str) -> str:
    """
    Makes a single LLM call using the benchmark API client.
    Generates a 2-3 sentence explanation of the specific fix.
    """
    logger = get_logger()
    
    prompt = f"""Given:
- User intent: {intent}
- Broken SQL: {error_sql}
- Corrected SQL: {corrected_sql}

In 2-3 sentences, explain exactly what was wrong in the broken SQL and what 
specific change was made to fix it. Be precise about column names, join 
conditions, or logic errors. Do not give generic SQL advice."""

    try:
        model_config = get_model_config("mistral")
        client = LLMClient(model_config)
        response = client.call_api(prompt)
        return response.strip()
    except Exception as e:
        logger.error(f"Failed to generate explanation natively: {e}")
        return f"Fix confirmed for: {intent[:80]}"
