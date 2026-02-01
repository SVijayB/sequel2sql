import json
import logging
from pathlib import Path

from datasets import load_dataset
import sqlglot

from src.ast_parsers.query_analyzer import analyze_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_FILE = Path(__file__).parent / "query_intent_metadata.jsonl"


def process_dataset():
    logger.info("Loading BirdSQL mini_dev_pg dataset...")
    dataset = load_dataset("birdsql/bird_mini_dev", split="mini_dev_pg")

    count = 0  # ✅ FIX: initialize counter

    logger.info(f"Writing {len(dataset)} records to {OUTPUT_FILE}")

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for item in dataset:
            sql_query = item.get("SQL")
            intent = item.get("question")

            if not sql_query or not intent:
                continue

            try:
                ast = sqlglot.parse_one(sql_query, read="postgres")
                metadata = analyze_query(ast)
            except Exception as e:
                logger.debug(f"Skipping query due to parse error: {e}")
                continue

            record = {
                "db_id": item.get("db_id"),
                "difficulty": item.get("difficulty"),
                "intent": intent,
                "sql": sql_query,
                # --- metadata fields (from QueryMetadata dataclass) ---
                "complexity_score": metadata.complexity_score,
                "pattern_signature": metadata.pattern_signature,
                "clauses_present": metadata.clauses_present,
                "num_joins": metadata.num_joins,
                "num_subqueries": metadata.num_subqueries,
                "num_ctes": metadata.num_ctes,
                "num_aggregations": metadata.num_aggregations,
            }

            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 100 == 0:
                logger.info(f"Processed {count} queries...")

    logger.info(f"Completed. Total queries processed: {count}")


if __name__ == "__main__":
    process_dataset()
