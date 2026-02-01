import logging
import math
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Set, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import sqlglot
from pydantic import BaseModel

from src.ast_parsers.query_analyzer import analyze_query


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "query_intents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_PATH = Path(__file__).parents[1] / "chroma_db"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic model returned to callers
# ---------------------------------------------------------------------------

class FewShotExample(BaseModel):
    """
    Structured few-shot example returned by the retrieval layer.
    This is prompt-agnostic and safe to serialize / log / evaluate.
    """

    # Core content
    intent: str
    sql: str

    # Structural metadata
    difficulty: Optional[str]
    complexity_score: int
    pattern_signature: str
    clauses_present: List[str]

    # Retrieval metadata
    distance: float

    # Optional hooks for future use
    source_db: Optional[str] = None
    example_id: Optional[str] = None

    class Config:
        validate_assignment = True
        anystr_strip_whitespace = True


# ---------------------------------------------------------------------------
# Helper functions for diversity selection
# ---------------------------------------------------------------------------

def parse_clauses(meta_val: Any) -> Set[str]:
    """Normalize clause metadata into a set."""
    if meta_val is None:
        return set()
    if isinstance(meta_val, list):
        return set(map(str, meta_val))
    if isinstance(meta_val, str):
        return {s.strip() for s in meta_val.split(",") if s.strip()}
    return set()


def jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard similarity between two clause sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def mmr_select(
    candidates: List[Dict[str, Any]],
    num_select: int,
    diversity_lambda: float = 0.6,
) -> List[Dict[str, Any]]:
    """
    Greedy Maximal Marginal Relevance (MMR) selection.
    Balances semantic relevance with structural diversity.
    """
    if not candidates:
        return []

    # Convert distance → similarity
    for c in candidates:
        c["_sim"] = 1.0 / (1.0 + float(c["dist"]))

    remaining = sorted(candidates, key=lambda x: -x["_sim"])
    selected = [remaining.pop(0)]

    while remaining and len(selected) < num_select:
        best_idx, best_score = None, -math.inf

        for i, cand in enumerate(remaining):
            relevance = cand["_sim"]

            cand_clauses = parse_clauses(cand["meta"].get("clauses_present"))
            max_overlap = max(
                jaccard(
                    cand_clauses,
                    parse_clauses(s["meta"].get("clauses_present")),
                )
                for s in selected
            )

            diversity = 1.0 - max_overlap
            score = (1 - diversity_lambda) * relevance + diversity_lambda * diversity

            if score > best_score:
                best_score, best_idx = score, i

        selected.append(remaining.pop(best_idx))

    return selected


def select_diverse_examples_from_chroma_results(
    results: Dict[str, Any],
    *,
    per_difficulty: bool = True,
    max_examples: int = 6,
    candidate_pool_size: int = 40,
    diversity_lambda: float = 0.6,
) -> List[Dict[str, Any]]:
    """
    Post-process Chroma results to produce a diverse candidate set.
    Uses optional difficulty stratification + MMR.
    """
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    candidates = [
        {"doc": d, "meta": m, "dist": dist}
        for d, m, dist in zip(docs, metas, dists)
    ]

    pool = candidates[:candidate_pool_size]
    selected: List[Dict[str, Any]] = []

    # Step 1: stratify by difficulty (coverage)
    if per_difficulty:
        by_diff = defaultdict(list)
        for c in pool:
            by_diff[c["meta"].get("difficulty", "unknown")].append(c)

        for bucket in by_diff.values():
            bucket.sort(key=lambda x: x["dist"])
            selected.append(bucket[0])
            if len(selected) >= max_examples:
                return mmr_select(selected, max_examples, diversity_lambda)

    # Step 2: fill remaining slots via MMR
    selected_keys = {
        (s["doc"], s["meta"].get("sql", "")) for s in selected
    }
    remaining = [
        c for c in pool
        if (c["doc"], c["meta"].get("sql", "")) not in selected_keys
    ]

    selected.extend(
        mmr_select(
            remaining,
            max_examples - len(selected),
            diversity_lambda,
        )
    )

    return selected[:max_examples]


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------

def find_similar_examples(
    intent: str,
    sql_query: str,
    n_results: int = 6,
) -> List[FewShotExample]:
    """
    Retrieve semantically similar but structurally diverse SQL examples.
    Returns structured Pydantic models (no printing).
    """

    # Optional structural analysis of input query
    try:
        ast = sqlglot.parse_one(sql_query, read="postgres")
        analyze_query(ast)
    except Exception as e:
        logger.warning(f"SQL analysis failed: {e}")

    # Embed intent
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_embedding = model.encode([intent], show_progress_bar=False).tolist()

    # Query ChromaDB
    client = chromadb.Client(
        Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(CHROMA_PATH),
        )
    )
    collection = client.get_collection(COLLECTION_NAME)

    pool_size = 40
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=pool_size,
        include=["documents", "metadatas", "distances"],
    )

    if not results["documents"]:
        return []

    selected = select_diverse_examples_from_chroma_results(
        results,
        per_difficulty=True,
        max_examples=n_results,
        candidate_pool_size=pool_size,
        diversity_lambda=0.6,
    )

    examples: List[FewShotExample] = []

    for ex in selected:
        meta = ex["meta"]

        clauses = (
            meta.get("clauses_present", "").split(",")
            if isinstance(meta.get("clauses_present"), str)
            else meta.get("clauses_present", [])
        )

        sql_text = meta.get("sql", "").strip()
        if not sql_text:
            continue  # skip empty SQL examples

        examples.append(
            FewShotExample(
                intent=ex["doc"],
                sql=sql_text,
                difficulty=meta.get("difficulty"),
                complexity_score=int(meta.get("complexity_score", 0)),
                pattern_signature=meta.get("pattern_signature", ""),
                clauses_present=clauses,
                distance=float(ex["dist"]),
                source_db=meta.get("db_id"),
            )
        )

    return examples


# ---------------------------------------------------------------------------
# Demo entrypoint (debug only)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_intent = (
        "Find accounts with at least two transactions where the difference "
        "between max and min transaction amounts exceeds 12000."
    )

    test_sql = (
        "SELECT account_id "
        "FROM trans "
        "GROUP BY account_id "
        "HAVING COUNT(trans_id) > 1 "
        "AND (MAX(amount) - MIN(amount)) > 12000;"
    )

    examples = find_similar_examples(test_intent, test_sql)

    for i, ex in enumerate(examples, 1):
        print(f"\nExample #{i}")
        print(ex.json(indent=2))
