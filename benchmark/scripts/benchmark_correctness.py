
import json
import time
import sys
import os
from pathlib import Path
import statistics
import logging
from transformers import AutoTokenizer

# Add src to sys.path to allow imports
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root / "src"))

from ast_parsers.llm_tool import validate_sql

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize tokenizer
MODEL_NAME = "google/gemma-2b" 
try:
    logger.info(f"Loading tokenizer for {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    logger.info(f"Initialized tokenizer: {MODEL_NAME}")
except Exception as e:
    logger.error(f"Failed to initialize tokenizer {MODEL_NAME}: {e}")
    tokenizer = None

def count_tokens(text):
    if not text:
        return 0
    if tokenizer:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        except Exception:
            return len(text) / 4
    else:
        return len(text) / 4

def run_benchmark(input_file, output_file, plot_file_prefix):
    logger.info(f"Starting correctness benchmark using data from {input_file}")
    
    results = []
    execution_times = []
    token_counts = []
    failures = []
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        total_queries = 0
        
        for idx, entry in enumerate(data):
            db_id = entry.get('db_id')
            sql = entry.get('SQL')
            
            if not sql or not isinstance(sql, str):
                continue
                
            start_time = time.time()
            try:
                # Call the tool
                validation_result = validate_sql(sql, db_name=db_id)
                end_time = time.time()
                
                duration_ms = (end_time - start_time) * 1000
                
                # Check correctness
                if not validation_result.valid:
                    failures.append({
                        'index': idx,
                        'db_id': db_id,
                        'sql': sql,
                        'errors': [e.message for e in validation_result.errors]
                    })
                    logger.warning(f"Query {idx} INVALID: {validation_result.errors[0].message}")
                
                # Serialize output
                result_dict = validation_result.model_dump(mode='json')
                result_json_str = validation_result.model_dump_json()
                
                tokens = count_tokens(result_json_str)
                
                execution_times.append(duration_ms)
                token_counts.append(tokens)
                
                results.append({
                    'query_idx': idx,
                    'db_id': db_id,
                    'sql_snippet': sql[:50] + "..." if len(sql) > 50 else sql,
                    'valid': validation_result.valid,
                    'duration_ms': duration_ms,
                    'estimated_tokens': tokens,
                    'validation_output': result_dict
                })
                
                total_queries += 1
                
            except Exception as e:
                logger.error(f"Error validating query {idx}: {e}")
                failures.append({'index': idx, 'error': str(e)})

        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
            
        # Save failures if any
        if failures:
            failure_file = str(output_file).replace('.json', '_failures.json')
            with open(failure_file, 'w', encoding='utf-8') as f:
                json.dump(failures, f, indent=2)
            logger.error(f"Found {len(failures)} invalid queries! Details saved to {failure_file}")
        else:
            logger.info("All queries validated successfully!")
            
        logger.info(f"Benchmark complete. Processed {total_queries} queries.")
        
        # Calculate statistics
        if execution_times:
            stats = {
                "count": len(execution_times),
                "failures": len(failures),
                "time_mean_ms": statistics.mean(execution_times),
                "time_median_ms": statistics.median(execution_times),
                "time_max_ms": max(execution_times),
                "tokens_mean": statistics.mean(token_counts),
                "tokens_median": statistics.median(token_counts),
                "tokens_max": max(token_counts),
            }
            
            print("\n" + "="*40)
            print("CORRECTNESS BENCHMARK STATISTICS")
            print("="*40)
            print(f"Total Queries: {stats['count']}")
            print(f"Failures:      {stats['failures']}")
            print("-" * 20)
            print("Execution Time (ms):")
            print(f"  Mean:   {stats['time_mean_ms']:.2f}")
            print(f"  Median: {stats['time_median_ms']:.2f}")
            print(f"  Max:    {stats['time_max_ms']:.2f}")
            print("-" * 20)
            print("Output Size (tokens - gemma-2b):")
            print(f"  Mean:   {stats['tokens_mean']:.2f}")
            print(f"  Median: {stats['tokens_median']:.2f}")
            print(f"  Max:    {stats['tokens_max']:.2f}")
            print("="*40 + "\n")
            
            # Use separate script for plotting if needed, or inline here
            try:
                import matplotlib.pyplot as plt
                
                plt.figure(figsize=(10, 6))
                plt.hist(execution_times, bins=30, color='orange', edgecolor='black')
                plt.title('Distribution of Query Execution Times (Mini Dev)')
                plt.xlabel('Time (ms)')
                plt.ylabel('Count')
                plt.savefig(f"{plot_file_prefix}_time_dist.png")
                
                plt.figure(figsize=(10, 6))
                plt.hist(token_counts, bins=30, color='lightcoral', edgecolor='black')
                plt.title('Distribution of Output Token Counts (Mini Dev)')
                plt.xlabel('Tokens')
                plt.ylabel('Count')
                plt.savefig(f"{plot_file_prefix}_token_dist.png")
                
            except ImportError:
                pass

    except FileNotFoundError:
        logger.error(f"Input file not found: {input_file}")

if __name__ == "__main__":
    DATA_FILE = project_root / "benchmark" / "data" / "mini_dev_pg-00000-of-00001.json"
    RESULTS_DIR = project_root / "benchmark" / "results"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    OUTPUT_FILE = RESULTS_DIR / "mini_dev_metrics.json"
    PLOT_PREFIX = RESULTS_DIR / "mini_dev"
    
    run_benchmark(DATA_FILE, OUTPUT_FILE, PLOT_PREFIX)
