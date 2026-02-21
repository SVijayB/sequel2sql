import difflib
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import sqlglot
from sqlglot import exp

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLLECTION_NAME = "db_confirmed_fixes"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_BASE_PATH = Path(__file__).parent / "chroma"

# ---------------------------------------------------------------------------
# Global Cache for Collections
# ---------------------------------------------------------------------------

_COLLECTION_CACHE: Dict[str, chromadb.Collection] = {}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def extract_skeleton(sql: str) -> str:
    """
    Parse SQL into an AST, walk the tree, and replace:
    - All string and numeric literals with `?`
    - All table and column identifiers with `?`
    - Keep all SQL keywords, functions, operators, and structural elements.
    Returns a compact structural fingerprint string.
    Returns empty string if sqlglot parsing fails.
    """
    try:
        ast = sqlglot.parse_one(sql, read="postgres", error_level=sqlglot.ErrorLevel.RAISE)
    except Exception:
        return ""

    if not ast:
        return ""

    def transform_node(node: exp.Expression) -> exp.Expression:
        # Replace Literals (strings, numbers, booleans, nulls)
        if isinstance(node, exp.Literal):
            return exp.Literal.string("?")

        if isinstance(node, exp.Boolean):
            return exp.Literal.string("?")

        if isinstance(node, exp.Null):
            return exp.Literal.string("?")

        # Replace Identifiers (table names, column names)
        # Note: We don't want to replace function names, but sqlglot separates Function
        # from the identifiers used inside it.
        if isinstance(node, exp.Identifier):
            # If this identifier is the name of a function, keep it.
            # Usually exp.Func has a name attribute which is a string, but if an
            # Identifier is a direct child of an anonymous function it might be tricky.
            # In sqlglot, most function calls will have string names, and arguments as children.
            return exp.Identifier(this="?", quoted=False)

        # Do not transform the node itself if it's not a literal or identifier,
        # but let sqlglot traverse its children.
        return node

    # Transform the AST inplace using sqlglot's transform
    # The transform function recursively applies the mapping to all nodes.
    try:
        # We need to make a copy to avoid mutating any cached trees if applicable
        transformed_ast = ast.copy().transform(transform_node)
        return transformed_ast.sql(dialect="postgres")
    except Exception:
        return ""


def _skeleton_similarity(s1: str, s2: str) -> float:
    """
    Normalized edit distance between two skeleton strings.
    Returns float 0.0-1.0, where 1.0 is identical.
    Returns 0.0 if either string is empty.
    """
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def _get_collection(database_name: str) -> chromadb.Collection:
    """
    Lazily initializes and caches a ChromaDB persistent client for the given database.
    """
    if database_name in _COLLECTION_CACHE:
        return _COLLECTION_CACHE[database_name]

    # Sanitize database name for directory use
    sanitized_db_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", database_name)
    db_path = CHROMA_BASE_PATH / sanitized_db_name

    # Create directory if it doesn't exist
    db_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(db_path))

    # We rely on ChromaDB's default embedding function, which under the hood
    # uses sentence-transformers all-MiniLM-L6-v2. Thus, passing nothing defaults to it.
    # To be explicit and handle it exactly as search_similar_query does:
    from chromadb.utils import embedding_functions

    # Initialize the specific model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, 
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"}
    )

    _COLLECTION_CACHE[database_name] = collection
    return collection


def save_confirmed_fix(
    *,
    database: str,
    intent: str,
    corrected_sql: str,
    error_sql: str,
    explanation: str,
    tables: List[str],
    confirmed_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Saves a confirmed SQL fix to the database-specific ChromaDB store.
    Deduplicates using intent similarity and skeleton similarity thresholds (0.8).
    Returns {"status": "saved", "id": doc_id} or {"status": "duplicate", "matched_id": id}.
    """
    collection = _get_collection(database)
    new_skeleton = extract_skeleton(corrected_sql)

    # 1. Deduplication Gate
    # Ask for top 5 most similar items by intent embedding
    try:
        fetch_count = min(5, collection.count())
        if fetch_count > 0:
            results = collection.query(
                query_texts=[intent],
                n_results=fetch_count,
                include=["documents", "metadatas", "distances"],
            )

        if results and results["documents"] and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]
            ids = results["ids"][0]

            for doc, meta, dist, doc_id in zip(docs, metas, dists, ids):
                # distance is typically 1 - cosine_similarity for sentence transformers in chroma
                # Some versions might return just distance (L2 or cosine).
                # Assuming cosine distance where similarity = 1 - distance
                similarity = 1.0 - dist
                
                # Check thresholds
                if similarity >= 0.8:
                    candidate_skeleton = meta.get("skeleton", "") if meta else ""
                    skel_sim = _skeleton_similarity(new_skeleton, candidate_skeleton)

                    if skel_sim >= 0.8:
                        return {"status": "duplicate", "matched_id": doc_id}
    except Exception:
        # Ignore query errors on an empty collection or during deduplication
        pass

    # 2. Save Item
    doc_id = hashlib.sha256(
        f"{database}::{intent}::{corrected_sql}".encode("utf-8")
    ).hexdigest()[:16]

    if not confirmed_at:
        confirmed_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "intent": intent,
        "corrected_sql": corrected_sql,
        "error_sql": error_sql,
        "explanation": explanation,
        "skeleton": new_skeleton,
        "tables": ",".join(tables),
        "confirmed_at": confirmed_at,
        "usage_count": 0,
    }

    collection.upsert(
        documents=[intent],
        metadatas=[metadata],
        ids=[doc_id],
    )

    # 3. Prune if needed
    try:
        count = collection.count()
        if count > 500:
            prune_confirmed_fixes(database, max_items=500)
    except Exception:
        pass

    return {"status": "saved", "id": doc_id}


def find_similar_confirmed_fixes(
    intent: str, database: str, tables: Optional[List[str]] = None, n_results: int = 4
) -> List[Dict[str, Any]]:
    """
    Query the collection for the top candidates by intent similarity.
    Returns reranked results based on intent similarity and table overlap.
    """
    try:
        collection = _get_collection(database)
        
        # Check if collection is empty
        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[intent],
            n_results=min(n_results * 2, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return []

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]
        ids = results["ids"][0]

        candidates = []
        for doc, meta, dist, doc_id in zip(docs, metas, dists, ids):
            similarity = 1.0 - dist
            if similarity >= 0.75:
                candidates.append(
                    {
                        "id": doc_id,
                        "doc": doc,
                        "meta": meta,
                        "similarity": similarity,
                    }
                )

        if not candidates:
            return []

        # Reranking
        current_tables = set(tables or [])
        scored_candidates = []

        for c in candidates:
            meta = c["meta"]
            similarity = c["similarity"]
            
            stored_tables_str = meta.get("tables", "")
            stored_tables = set(stored_tables_str.split(",")) if stored_tables_str else set()

            if current_tables or stored_tables:
                table_overlap = len(stored_tables & current_tables) / max(
                    len(stored_tables | current_tables), 1
                )
                combined_score = similarity * 0.70 + table_overlap * 0.30
            else:
                combined_score = similarity

            scored_candidates.append(
                {
                    "candidate": c,
                    "combined_score": combined_score,
                }
            )

        # Sort descending by combined_score
        scored_candidates.sort(key=lambda x: x["combined_score"], reverse=True)
        top_candidates = scored_candidates[:n_results]

        # Prepare return format
        final_results = []
        ids_to_increment = []
        metadatas_to_update = []

        for sc in top_candidates:
            c = sc["candidate"]
            meta = c["meta"]
            
            stored_tables_str = meta.get("tables", "")
            tables_list = stored_tables_str.split(",") if stored_tables_str else []

            final_results.append(
                {
                    "intent": meta.get("intent", ""),
                    "corrected_sql": meta.get("corrected_sql", ""),
                    "explanation": meta.get("explanation", ""),
                    "tables": tables_list,
                    "similarity": round(c["similarity"], 3),
                    "combined_score": round(sc["combined_score"], 3),
                    "confirmed_at": meta.get("confirmed_at", ""),
                }
            )

            # Prepare for batch increment
            ids_to_increment.append(c["id"])
            
            # Create a new metadata dict to avoid modifying the one from Chroma directly
            # which could cause issues if it's cached or frozen in some versions
            updated_meta = dict(meta)
            updated_meta["usage_count"] = int(updated_meta.get("usage_count", 0)) + 1
            metadatas_to_update.append(updated_meta)

        # Best-effort increment usage_count
        try:
            if ids_to_increment:
                collection.update(
                    ids=ids_to_increment,
                    metadatas=metadatas_to_update,
                )
        except Exception:
            pass

        return final_results

    except Exception:
        # Wrap all in try/except and return safe defaults (empty list)
        return []


def prune_confirmed_fixes(database: str, max_items: int = 500) -> int:
    """
    Deletes items according to tiers to bring count down to max_items.
    Returns number of items deleted.
    """
    try:
        collection = _get_collection(database)
        count = collection.count()

        if count <= max_items:
            return 0

        # Need to fetch everything to sort by age
        # This could be memory intensive for huge collections,
        # but max_items is small (~500) so it's fine.
        results = collection.get(include=["metadatas"])
        if not results or not results["metadatas"]:
            return 0

        ids = results["ids"]
        metas = results["metadatas"]

        now = datetime.now(timezone.utc)

        items = []
        for doc_id, meta in zip(ids, metas):
            usage_count = int(meta.get("usage_count", 0))
            confirmed_at_str = meta.get("confirmed_at", "")
            
            age_days = 0.0
            if confirmed_at_str:
                try:
                    # Parse ISO format. Handle Z explicitly if needed.
                    if confirmed_at_str.endswith("Z"):
                        confirmed_at_str = confirmed_at_str[:-1] + "+00:00"
                    
                    confirmed_at = datetime.fromisoformat(confirmed_at_str)
                    
                    # Ensure timezone awareness
                    if confirmed_at.tzinfo is None:
                        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
                        
                    delta = now - confirmed_at
                    age_days = delta.total_seconds() / (24 * 3600)
                except Exception:
                    # Treat ambiguous age as 0
                    pass
            
            items.append({
                "id": doc_id,
                "usage_count": usage_count,
                "age_days": age_days,
            })

        # Priority 1: usage_count == 0 AND age_days >= 30
        tier_1 = [item for item in items if item["usage_count"] == 0 and item["age_days"] >= 30]
        # Priority 2: usage_count == 0 AND age_days >= 7
        tier_2 = [item for item in items if item["usage_count"] == 0 and item["age_days"] >= 7]
        # Priority 3: usage_count == 1 AND age_days >= 90
        tier_3 = [item for item in items if item["usage_count"] == 1 and item["age_days"] >= 90]

        # Order of deletion
        seen_ids = set()
        candidates = []
        
        # Add tier 1 (sort older first)
        tier_1.sort(key=lambda x: x["age_days"], reverse=True)
        for item in tier_1:
            if item["id"] not in seen_ids:
                candidates.append(item)
                seen_ids.add(item["id"])
        
        # Add tier 2 (sort older first, exclude already in list)
        tier_2.sort(key=lambda x: x["age_days"], reverse=True)
        for item in tier_2:
            if item["id"] not in seen_ids:
                candidates.append(item)
                seen_ids.add(item["id"])
        
        # Add tier 3 (sort older first, exclude already in list)
        tier_3.sort(key=lambda x: x["age_days"], reverse=True)
        for item in tier_3:
            if item["id"] not in seen_ids:
                candidates.append(item)
                seen_ids.add(item["id"])

        to_delete_count = count - max_items
        actual_delete_count = min(to_delete_count, len(candidates))

        if actual_delete_count > 0:
            ids_to_delete = [item["id"] for item in candidates[:actual_delete_count]]
            collection.delete(ids=ids_to_delete)
            return actual_delete_count

        return 0

    except Exception:
        # Wrap in try/except, return safe default
        return 0
