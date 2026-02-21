import sys
import os

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import json
import logging
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


DATA_FILE = Path(__file__).parent / "query_intent_metadata.jsonl"
CHROMA_PATH = Path(__file__).parents[1] / "chroma_db"
COLLECTION_NAME = "query_intents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def embed_and_store() -> None:
    logger.info("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing *persistent* ChromaDB...")
    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    with DATA_FILE.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            record = json.loads(line)

            documents.append(record["intent"])

            meta = {k: v for k, v in record.items() if k != "intent"}
            for k, v in meta.items():
                if isinstance(v, list):
                    meta[k] = ", ".join(map(str, v))

            metadatas.append(meta)
            ids.append(str(idx))

    logger.info(f"Embedding {len(documents)} intents...")
    embeddings = model.encode(
        documents,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).tolist()

    collection.add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

    logger.info(f"Final collection count: {collection.count()}")
    logger.info("Embeddings persisted to disk successfully.")


if __name__ == "__main__":
    embed_and_store()