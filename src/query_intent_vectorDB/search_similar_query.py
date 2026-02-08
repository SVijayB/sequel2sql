import sys
import os
# Add src to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
import math
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Set, Optional

import chromadb
from sentence_transformers import SentenceTransformer
import sqlglot
from pydantic import BaseModel

from ast_parsers.query_analyzer import analyze_query


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "query_intents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_PATH = Path(__file__).parents[1] / "chroma_db"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Suppress noisy libraries
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("tokenizers").setLevel(logging.WARNING)


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
    complexity_score: float
    pattern_signature: str
    clauses_present: List[str]

    # Retrieval metadata
    distance: float

    # Optional hooks for future use
    source_db: Optional[str] = None

    class Config:
        validate_assignment = True
        str_strip_whitespace = True


# ---------------------------------------------------------------------------
# Helper functions for diversity selection
# ---------------------------------------------------------------------------

def parse_signature(sig: Any) -> Set[str]:
    """Parse pattern signature string into a set of components."""
    if not sig or not isinstance(sig, str):
        return set()
    return set(sig.split("-"))


def jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard similarity between two sets."""
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
    Balances semantic relevance with structural diversity (via pattern signature).
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

            cand_sig = parse_signature(cand["meta"].get("pattern_signature"))
            max_overlap = max(
                jaccard(
                    cand_sig,
                    parse_signature(s["meta"].get("pattern_signature")),
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
    complexity_sampling: bool = True,
    max_examples: int = 6,
    candidate_pool_size: int = 40,
    diversity_lambda: float = 0.6,
) -> List[Dict[str, Any]]:
    """
    Post-process Chroma results to produce a diverse candidate set.
    Uses optional complexity stratification + MMR (on pattern signatures).
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

    # Step 1: Dynamic Stratification by complexity score
    if complexity_sampling:
        pool_scores = [float(c["meta"].get("complexity_score", 0.0)) for c in pool]
        min_s, max_s = min(pool_scores, default=0.0), max(pool_scores, default=1.0)

        if max_s - min_s > 1e-6:
            range_width = (max_s - min_s) / 3.0
            t1 = min_s + range_width
            t2 = min_s + 2 * range_width

            buckets = {"low": [], "medium": [], "high": []}
            for c in pool:
                score = float(c["meta"].get("complexity_score", 0.0))
                if score <= t1:
                    buckets["low"].append(c)
                elif score <= t2:
                    buckets["medium"].append(c)
                else:
                    buckets["high"].append(c)

            for label in ["low", "medium", "high"]:
                bucket = buckets[label]
                if bucket:
                    bucket.sort(key=lambda x: x["dist"])
                    selected.append(bucket[0])

            if len(selected) >= max_examples:
                return mmr_select(selected, max_examples, diversity_lambda)

    # Step 2: fill remaining slots via MMR
    selected_keys = {(s["doc"], s["meta"].get("sql", "")) for s in selected}
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
    #sql_query: str,
    n_results: int = 6,
) -> List[FewShotExample]:
    """
    Retrieve semantically similar but structurally diverse SQL examples.
    Returns structured Pydantic models (no printing).
    """

    # # Optional structural analysis of input query
    # try:
    #     ast = sqlglot.parse_one(sql_query, read="postgres")
    #     analyze_query(ast)
    # except Exception as e:
    #     logger.warning(f"SQL analysis failed: {e}")

    # Embed intent
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_embedding = model.encode([intent], show_progress_bar=False).tolist()

    # Query ChromaDB (persistent client)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(COLLECTION_NAME)

    pool_size = 40
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=pool_size,
        where={"document_type": "query_intent_pairs"},
        include=["documents", "metadatas", "distances"],
    )

    if not results["documents"]:
        return []

    selected = select_diverse_examples_from_chroma_results(
        results,
        complexity_sampling=True,
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
            continue

        examples.append(
            FewShotExample(
                intent=ex["doc"],
                sql=sql_text,
                complexity_score=float(meta.get("complexity_score", 0.0)),
                pattern_signature=meta.get("pattern_signature", ""),
                clauses_present=clauses,
                distance=float(ex["dist"]),
                source_db=meta.get("db_id"),
            )
        )

    return examples