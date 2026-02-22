import sys
import os
from pathlib import Path
import chromadb

# Add src to sys.path (optional, safe)
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

# Path to ChromaDB (persistent)
PRJ_ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = PRJ_ROOT / "src" / "db_skills" / "chroma"/"european_football_2"
COLLECTION_NAME = "db_confirmed_fixes"


def inspect_chroma():
    print(f"Connecting to ChromaDB at {CHROMA_PATH.resolve()}")

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(COLLECTION_NAME)

    count = collection.count()
    print(f"Collection '{COLLECTION_NAME}' has {count} records.")

    if count == 0:
        return

    print("\nFetching first 5 records...\n")

    results = collection.get(
        limit=min(5, count),
        include=["documents", "metadatas"],
    )

    ids = results.get("ids", [])

    for i in range(len(ids)):
        print(f"--- Record #{i + 1} ---")
        print(f"ID: {ids[i]}")
        print(f"Intent (document): {results['documents'][i]}")
        print("Metadata:")
        for k, v in results["metadatas"][i].items():
            print(f"  {k}: {v}")
        print()


if __name__ == "__main__":
    inspect_chroma()