import json
import random
import re
import shutil
import sys
from pathlib import Path

from db_skills_benchmark.src.config import TARGET_DB_ID, RANDOM_SEED, get_data_dir
from db_skills_benchmark.src.explanation_generator import generate_fix_explanation
from benchmark.src.logger_config import get_logger

import sys

# Import from project root database schema handler (which is already loaded by main)
from src.db_skills.store import save_confirmed_fix, CHROMA_BASE_PATH

def load_and_split_examples(db_id: str) -> tuple[list[dict], list[dict]]:
    logger = get_logger()
    data_dir = get_data_dir()
    
    full_path = data_dir / "postgresql_full.jsonl"
    sol_path = data_dir / "pg_sol.jsonl"
    
    solutions = {}
    with open(sol_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            solutions[data["instance_id"]] = {
                "sol_sql": data.get("sol_sql", ""),
                "test_cases": data.get("test_cases", [])
            }
            
    matched = []
    with open(full_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if data.get("db_id") == db_id and data["instance_id"] in solutions:
                data["sol_sql"] = solutions[data["instance_id"]]["sol_sql"]
                data["test_cases"] = solutions[data["instance_id"]]["test_cases"]
                matched.append(data)
                
    random.Random(RANDOM_SEED).shuffle(matched)
    
    mid = len(matched) // 2
    seen = matched[:mid]
    unseen = matched[mid:]
    
    logger.info(f"Loaded {len(matched)} examples for DB '{db_id}' ({len(seen)} seen, {len(unseen)} unseen)")
    print(f"\n[Info] Data Load Summary:")
    print(f"  Target DB: {db_id}")
    print(f"  Total matched to solutions: {len(matched)}")
    print(f"  Seen subset: {len(seen)}")
    print(f"  Unseen subset: {len(unseen)}")
    print()
    
    return seen, unseen

def seed_db_skills(seen_examples: list[dict]) -> dict:
    logger = get_logger()
    logger.info(f"Seeding {len(seen_examples)} examples to Chroma...")
    
    summary = {
        "attempted": 0,
        "saved": 0,
        "duplicates": 0,
        "failed": 0,
        "seeded_instance_ids": []
    }
    
    for ex in seen_examples:
        instance_id = ex["instance_id"]
        db_id = ex["db_id"]
        intent = ex["query"]
        corrected_raw = ex.get("sol_sql", "")
        if isinstance(corrected_raw, list):
            corrected_sql = ";\n".join(corrected_raw)
        else:
            corrected_sql = str(corrected_raw)
        
        issue_raw = ex.get("issue_sql", [])
        if isinstance(issue_raw, list):
            error_sql = ";\n".join(issue_raw)
        else:
            error_sql = str(issue_raw)
            
        summary["attempted"] += 1
        
        try:
            explanation = generate_fix_explanation(intent, error_sql, corrected_sql)
            logger.debug(f">> Embedding fix for {instance_id}: Intent='{intent[:40]}...' | CorrectedSQL='{corrected_sql[:40]}...'")
                
            result = save_confirmed_fix(
                database=db_id,
                intent=intent,
                corrected_sql=corrected_sql,
                error_sql=error_sql,
                explanation=explanation
            )
            
            status = result.get("status", "unknown")
            if status == "saved":
                summary["saved"] += 1
                summary["seeded_instance_ids"].append(instance_id)
                logger.info(f"Seeded {instance_id}: Saved")
            elif status == "duplicate":
                summary["duplicates"] += 1
                logger.debug(f"Seeded {instance_id}: Duplicate skipped")
            else:
                summary["failed"] += 1
                logger.warning(f"Seeded {instance_id}: Unexpected status '{status}'")
                
        except Exception as e:
            summary["failed"] += 1
            logger.error(f"Failed to seed {instance_id}: {e}")
            
    return summary

def backup_and_clear_db_skills(db_id: str, run_output_dir: Path) -> None:
    logger = get_logger()
    sanitized_db_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", db_id)
    source_dir = CHROMA_BASE_PATH / sanitized_db_name
    
    if not source_dir.exists():
        logger.info(f"No existing Chroma store found for {db_id} at {source_dir}. Skipping cleanup.")
        return
        
    dest_dir = run_output_dir / "chroma_snapshot"
    
    try:
        shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
        print(f"\n[Info] Backed up Chroma store to: {dest_dir}")
        logger.info(f"Chroma snapshot saved to {dest_dir}")
        
        shutil.rmtree(source_dir)
        print(f"[Info] Cleared old live Chroma store from: {source_dir}\n")
        logger.info(f"Cleared {source_dir}")
    except Exception as e:
        logger.error(f"Failed to backup/clear Chroma store: {e}")
        print(f"\n[Error] Failed to clear Chroma store: {e}\n")
