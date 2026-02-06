import sys
import os
from pathlib import Path
import chromadb
from chromadb.config import Settings

# Add src to sys.path to ensure we can import any src modules if needed (though mostly using chromadb directly here)
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Path to ChromaDB - it is in src/chroma_db
PRJ_ROOT = Path(__file__).parent.parent
CHROMA_PATH = PRJ_ROOT / "src" / "chroma_db"
COLLECTION_NAME = "query_intents"

def inspect_chroma():
    print(f"Connecting to ChromaDB at {CHROMA_PATH}...")
    
    # Use the same settings as in src/query_intent_vectorDB/search_similar_query.py
    client = chromadb.Client(
        Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(CHROMA_PATH),
        )
    )
    
    try:
        collection = client.get_collection(COLLECTION_NAME)
        count = collection.count()
        print(f"Collection '{COLLECTION_NAME}' has {count} documents.")
        
        if count == 0:
            print("Collection is empty.")
            return

        # Fetch first 5 items
        # collection.peek() is often the easiest way to see top N
        print("\nFetching first 5 records...")
        results = collection.peek(limit=5)
        
        ids = results['ids']
        metadatas = results['metadatas']
        documents = results['documents']
        
        for i in range(len(ids)):
            print(f"\n--- Record #{i+1} ---")
            print(f"ID: {ids[i]}")
            print(f"Intent (Document): {documents[i]}")
            print("Metadata:")
            # Pretty print metadata dict
            for k, v in metadatas[i].items():
                print(f"  {k}: {v}")
                
    except Exception as e:
        print(f"Error inspecting collection: {e}")
        # If collection doesn't exist, it raises ValueError
        print(f"(Did you run embed_query_intent.py?)")

if __name__ == "__main__":
    inspect_chroma()
