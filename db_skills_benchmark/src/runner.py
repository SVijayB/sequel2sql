import sys
from pathlib import Path

import json
import shutil
import subprocess
from datetime import datetime
from json.decoder import JSONDecodeError
from benchmark.src.api_client import LLMClient
from benchmark.src.sequel2sql_client import Sequel2SQLClient

from db_skills_benchmark.src.logger import get_logger
from db_skills_benchmark.src.config import get_model_config

# Import from project root db_skills (available since main injects root to sys.path)
from src.db_skills.store import find_similar_confirmed_fixes

def run_benchmark(examples: list[dict], mode: str, use_db_skills: bool, run_output_dir: Path) -> list[dict]:
    """
    Evaluates a set of examples.
    mode: "simple" (Mistral directly) or "pipeline" (Sequel2SQL)
    """
    logger = get_logger()
    results = []
    
    if mode == "pipeline":
        config = get_model_config("sequel2sql")
        client = Sequel2SQLClient(config)
    else:
        config = get_model_config("mistral")
        client = LLMClient(config)
        
    logger.info(f"Starting execution run through {len(examples)} datasets in mode: '{mode}' - (db_skills: {use_db_skills})")
        
        
    batch_payload = []
    metadata_map = {}
        
    for i, ex in enumerate(examples, 1):
        instance_id = ex["instance_id"]
        db_id = ex["db_id"]
        intent = ex["query"]
        issue_raw = ex.get("issue_sql", [])
        issue_sql = "\n".join(issue_raw) if isinstance(issue_raw, list) else str(issue_raw)
        
        retrieved_fixes = []
        if use_db_skills:
            try:
                retrieved_fixes = find_similar_confirmed_fixes(
                    intent=intent,
                    database=db_id
                )
            except Exception as e:
                logger.warning(f"Error fetching fixes for {instance_id}: {e}")
                
        top_sim = None
        top_intent = None
        
        if retrieved_fixes:
            top_fix = retrieved_fixes[0]
            top_sim = top_fix.get("similarity")
            top_intent = top_fix.get("intent")
            
        predicted_sql = ""
        error_msg = None
        
        try:
            if mode == "pipeline":
                predicted_sql = client.call_api_with_data(ex)
            else:
                prompt_str = f"Fix this SQL for {db_id}:\nIntent: {intent}\nBroken: {issue_sql}"
                predicted_sql = client.call_api(prompt_str)
                
            import re
            m = re.search(r"```[^\n]*\n(.*?)```", predicted_sql, re.DOTALL | re.IGNORECASE)
            if m:
                predicted_sql = m.group(1).strip()
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Inference failed for {instance_id}: {e}")
            
        
        # Save retrieval metadata mapped by instance ID for later recombination
        metadata_map[instance_id] = {
            "retrieved_fixes": retrieved_fixes,
            "top_retrieved_similarity": top_sim,
            "top_retrieved_intent": top_intent,
            "benchmark_subgroup": ex.get("benchmark_subgroup"),
            "error": error_msg
        }

        # Setup expected JSON scheme for wrapper
        payload = {
            "instance_id": instance_id,
            "db_id": db_id,
            "query": intent,
            "preprocess_sql": ex.get("preprocess_sql", []),
            "issue_sql": ex.get("issue_sql", []),
            "sol_sql": ex.get("sol_sql", ""),
            "clean_up_sql": ex.get("clean_up_sql", []),
            "test_cases": ex.get("test_cases", []),
            "pred_sqls": [predicted_sql],
            "difficulty": ex.get("difficulty", "intermediate")
        }
        batch_payload.append(payload)
        
        # Appending native tracking JSONLs
        prompt_payload = {
            "instance_id": instance_id,
            "prompt": prompt_str if mode != "pipeline" else str(ex)
        }
        with open(run_output_dir / "prompts.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(prompt_payload, ensure_ascii=False) + "\n")
            
        resp_payload = {
            "instance_id": instance_id,
            "response": predicted_sql
        }
        with open(run_output_dir / "responses.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(resp_payload, ensure_ascii=False) + "\n")
            
        # Log to `final_output.jsonl` identical to the benchmark structure
        with open(run_output_dir / "final_output.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        
        sim_msg = f" (Sim: {top_sim:.3f})" if top_sim is not None else ""
        logger.info(f"[{i:02d}/{len(examples)}] ✅ Processed {instance_id}{sim_msg}")
    
    # Phase 2: Execute wrapper evaluated natively in docker container
    benchmark_dir = run_output_dir.parent.parent.parent / "benchmark"
    eval_temp_dir = benchmark_dir / "outputs" / "db_skills_temp"
    eval_temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Write the batch jsonl file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    temp_jsonl_name = f"final_output_temp_{timestamp}"
    temp_jsonl_path = eval_temp_dir / f"{temp_jsonl_name}.jsonl"
    with open(temp_jsonl_path, "w", encoding="utf-8") as f:
        for payload in batch_payload:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            
    logger.info(f"Triggering wrapper evaluation inside Docker container...")
    eval_cmd = [
        "docker", "exec", "sequel2sql_eval", "python",
        "src/wrapper_evaluation_postgresql.py",
        "--jsonl_file", str(temp_jsonl_path.relative_to(benchmark_dir)),
        "--num_threads", "8",
        "--mode", "pred",
        "--report", "true",
        "--logging", "false"
    ]
    
    try:
        eval_res = subprocess.run(
            eval_cmd,
            cwd=benchmark_dir,
            capture_output=True,
            text=True,
            timeout=7200,
        )
        for line in eval_res.stdout.splitlines():
            if line.strip():
                logger.info(f"Docker Evaluation: {line}")
        if eval_res.stderr:
            for line in eval_res.stderr.splitlines():
                if line.strip():
                    logger.error(f"Docker Error: {line}")
                    
    except Exception as e:
        logger.error(f"Docker evaluation failed: {e}")
        
    # Phase 3: Hydrate Combined Results & Cleanup Temp Objects
    output_with_status_path = eval_temp_dir / f"{temp_jsonl_name}_output_with_status.jsonl"
    report_path = eval_temp_dir / f"{temp_jsonl_name}_report.txt"
    wrapper_log = eval_temp_dir / f"{temp_jsonl_name}_wrapper.log"
    
    if output_with_status_path.exists():
        with open(output_with_status_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    output_obj = json.loads(line)
                except JSONDecodeError:
                    continue
                i_id = output_obj.get("instance_id")
                exec_correct = output_obj.get("status") == "success"
                
                # Combine native metadata
                run_metadata = metadata_map.get(i_id, {})
                comb = {
                    "instance_id": i_id,
                    "benchmark_subgroup": run_metadata.get("benchmark_subgroup"),
                    "db_id": output_obj.get("db_id"),
                    "intent": output_obj.get("query"),
                    "issue_sql": output_obj.get("issue_sql"),
                    "correct_sql": output_obj.get("sol_sql"),
                    "predicted_sql": output_obj.get("pred_sqls", [""])[0] if output_obj.get("pred_sqls") else "",
                    "execution_correct": exec_correct,
                    "retrieved_fixes": run_metadata.get("retrieved_fixes", []),
                    "top_retrieved_similarity": run_metadata.get("top_retrieved_similarity"),
                    "top_retrieved_intent": run_metadata.get("top_retrieved_intent"),
                    "error": output_obj.get("error_message") or run_metadata.get("error")
                }
                results.append(comb)
                logger.info(f"[{i_id}] Hydrated correctly. Success: {exec_correct}")
                
        # Migrate Docker generated files into execution run dir and clean up standard naming conventions
        shutil.move(output_with_status_path, run_output_dir / "final_output_output_with_status.jsonl")
        if report_path.exists():
            shutil.move(report_path, run_output_dir / "final_output_report.txt")
        if wrapper_log.exists():
            shutil.move(wrapper_log, run_output_dir / "final_output_wrapper.log")
            
        temp_jsonl_path.unlink(missing_ok=True)
    else:
        logger.error(f"Wrapper execution crashed - output jsonl is missing.")
        
    return results
