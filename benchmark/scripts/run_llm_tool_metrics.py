
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
# Using gemma-2b as a proxy for gemma-27b as they share the same tokenizer
MODEL_NAME = "google/gemma-2b" 
try:
    logger.info(f"Loading tokenizer for {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    logger.info(f"Initialized tokenizer: {MODEL_NAME}")
except Exception as e:
    logger.error(f"Failed to initialize tokenizer {MODEL_NAME}: {e}")
    tokenizer = None

def count_tokens(text):
    """Count tokens using transformers AutoTokenizer."""
    if not text:
        return 0
    
    if tokenizer:
        try:
            return len(tokenizer.encode(text, add_special_tokens=True))
        except Exception:
            return len(text) / 4
    else:
        return len(text) / 4

def run_benchmark(input_file, output_file, plot_file_prefix):
    logger.info(f"Starting benchmark using data from {input_file}")
    
    results = []
    execution_times = []
    output_token_counts = [] # AST tokens
    input_token_counts = []
    error_token_counts = []
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_queries = 0
        
        for line_idx, line in enumerate(lines):
            try:
                data = json.loads(line)
                db_id = data.get('db_id')
                issue_sqls = data.get('issue_sql', [])
                
                if not isinstance(issue_sqls, list):
                    issue_sqls = [issue_sqls]
                
                for sql in issue_sqls:
                    if not sql or not isinstance(sql, str):
                        continue
                     
                    # Count input tokens
                    input_tokens = count_tokens(sql)
                    
                    start_time = time.time()
                    try:
                        # Call the tool
                        validation_result = validate_sql(sql, db_name=db_id)
                        end_time = time.time()
                        
                        duration_ms = (end_time - start_time) * 1000
                        
                        # Serialize output to count tokens and save
                        result_dict = validation_result.model_dump(mode='json')
                        result_json_str = validation_result.model_dump_json()
                        
                        output_tokens = count_tokens(result_json_str)
                        
                        # Calculate error tokens and invalid sql tokens
                        error_tokens = 0
                        invalid_sql_tokens = 0
                        
                        if not validation_result.valid:
                            # Count tokens in the input SQL if invalid
                            invalid_sql_tokens = count_tokens(sql)
                            
                            # Count tokens in error messages
                            if validation_result.errors:
                                for err in validation_result.errors:
                                    error_tokens += count_tokens(err.message)
                        
                        execution_times.append(duration_ms)
                        output_token_counts.append(output_tokens)
                        input_token_counts.append(input_tokens)
                        error_token_counts.append(error_tokens)
                        # We only care about the distribution of invalid sql tokens where they exist (>0)
                        # But to keep alignment, we can append 0, or just filter later. 
                        # The user wants "Separate distributions".
                        
                        possible_err = None
                        if validation_result.errors:
                            possible_err = validation_result.errors[0].message

                        results.append({
                            'query_idx': total_queries,
                            'db_id': db_id,
                            'sql_snippet': sql[:50] + "..." if len(sql) > 50 else sql,
                            'valid': validation_result.valid,
                            'error': possible_err,
                            'duration_ms': duration_ms,
                            'input_sql_tokens': input_tokens,
                            'estimated_tokens': output_tokens, # AST tokens
                            'error_tokens': error_tokens,
                            'invalid_sql_tokens': invalid_sql_tokens,
                            'validation_output': result_dict
                        })
                        
                        total_queries += 1
                        
                    except Exception as e:
                        logger.error(f"Error validating query in line {line_idx}: {e}")
                        
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON at line {line_idx}")

        # Save main results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
            
        # Save error metrics separately
        error_results = []
        for r in results:
            if not r['valid']:
                error_results.append({
                    'query_idx': r['query_idx'],
                    'db_id': r['db_id'],
                    'valid': r['valid'],
                    'error_message': r['error'],
                    'error_tokens': r.get('error_tokens', 0),
                    'issue_sql_tokens': r.get('invalid_sql_tokens', 0) # User called it issue_sql tokens
                })
        
        error_output_file = str(output_file).replace('.json', '_error_stats.json')
        with open(error_output_file, 'w', encoding='utf-8') as f:
            json.dump(error_results, f, indent=2)
            
        logger.info(f"Benchmark complete. Processed {total_queries} queries.")
        logger.info(f"Main results saved to {output_file}")
        logger.info(f"Error stats saved to {error_output_file}")
        
        # Calculate statistics
        # Use strictly invalid queries for error stats
        error_tokens_list = [r['error_tokens'] for r in error_results]
        issue_sql_tokens_list = [r['issue_sql_tokens'] for r in error_results]
        
        if execution_times:
            stats = {
                "count": len(execution_times),
                "error_count": len(error_results),
                "time_mean_ms": statistics.mean(execution_times),
                "time_median_ms": statistics.median(execution_times),
                "time_max_ms": max(execution_times),
                
                "input_tokens_mean": statistics.mean(input_token_counts),
                "input_tokens_median": statistics.median(input_token_counts),
                "input_tokens_max": max(input_token_counts),
                
                "output_tokens_mean": statistics.mean(output_token_counts),
                "output_tokens_median": statistics.median(output_token_counts),
                "output_tokens_max": max(output_token_counts),
                
                "error_tokens_mean": statistics.mean(error_tokens_list) if error_tokens_list else 0,
                "error_tokens_median": statistics.median(error_tokens_list) if error_tokens_list else 0,
                "error_tokens_max": max(error_tokens_list) if error_tokens_list else 0,
                
                "invalid_sql_tokens_mean": statistics.mean(issue_sql_tokens_list) if issue_sql_tokens_list else 0,
                "invalid_sql_tokens_median": statistics.median(issue_sql_tokens_list) if issue_sql_tokens_list else 0,
                "invalid_sql_tokens_max": max(issue_sql_tokens_list) if issue_sql_tokens_list else 0,
            }
            
            print("\n" + "="*40)
            print("BENCHMARK STATISTICS")
            print("="*40)
            print(f"Total Queries: {stats['count']}")
            print(f"Invalid Queries (Errors): {stats['error_count']}")
            print("-" * 20)
            print("Execution Time (ms):")
            print(f"  Mean:   {stats['time_mean_ms']:.2f}")
            print(f"  Median: {stats['time_median_ms']:.2f}")
            print(f"  Max:    {stats['time_max_ms']:.2f}")
            print("-" * 20)
            print("Input Size (tokens - gemma-2b):")
            print(f"  Mean:   {stats['input_tokens_mean']:.2f}")
            print(f"  Median: {stats['input_tokens_median']:.2f}")
            print(f"  Max:    {stats['input_tokens_max']:.2f}")
            print("-" * 20)
            print("AST Output Size (tokens - gemma-2b):")
            print(f"  Mean:   {stats['output_tokens_mean']:.2f}")
            print(f"  Median: {stats['output_tokens_median']:.2f}")
            print(f"  Max:    {stats['output_tokens_max']:.2f}")
            print("-" * 20)
            print("Error Message Size (Invalid Queries Only):")
            print(f"  Mean:   {stats['error_tokens_mean']:.2f}")
            print(f"  Median: {stats['error_tokens_median']:.2f}")
            print(f"  Max:    {stats['error_tokens_max']:.2f}")
            print("-" * 20)
            print("Issue SQL Size (Invalid Queries Only):")
            print(f"  Mean:   {stats['invalid_sql_tokens_mean']:.2f}")
            print(f"  Median: {stats['invalid_sql_tokens_median']:.2f}")
            print(f"  Max:    {stats['invalid_sql_tokens_max']:.2f}")
            print("="*40 + "\n")
            
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_file}")

if __name__ == "__main__":
    # Define paths
    DATA_FILE = project_root / "benchmark" / "data" / "postgresql_full.jsonl"
    RESULTS_DIR = project_root / "benchmark" / "results"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    OUTPUT_FILE = RESULTS_DIR / "llm_tool_metrics.json"
    PLOT_PREFIX = RESULTS_DIR / "llm_tool"
    
    run_benchmark(DATA_FILE, OUTPUT_FILE, PLOT_PREFIX)
