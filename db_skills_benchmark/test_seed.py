import sys
from pathlib import Path

# Setup paths (simulating main.py)
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from db_skills_benchmark.src.config import TARGET_DB_ID
from db_skills_benchmark.src.seeder import load_and_split_examples, seed_db_skills, backup_and_clear_db_skills

print("=== DB SKILLS BENCHMARK HEADLESS SEEDER ===")
seen, unseen = load_and_split_examples(TARGET_DB_ID)

if seen:
    # Just do a small batch of 3 to prove the pipeline correctly uses Mistral to generate explanations
    # and Chroma correctly accepts the embeddings.
    batch = seen[:3]
    print(f"\n[Run] Seeding {len(batch)} examples into Chroma...")
    summary = seed_db_skills(batch)
    print("\n[Result] Seeding Summary:", summary)
else:
    print("No examples found to seed.")
