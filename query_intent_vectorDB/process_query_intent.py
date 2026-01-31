
import os
import sys
import json
import logging
from datasets import load_dataset
import sqlglot
from sqlglot import exp

# Add the project root and src directory to sys.path
# Assuming this script is located in query_intent_vectorDB/ and src is in the root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')

if project_root not in sys.path:
    sys.path.append(project_root)
if src_path not in sys.path:
    sys.path.append(src_path)

try:
    # Try importing as if src is in path (codebase style)
    from ast_parsers.query_analyzer import analyze_query, QueryMetadata
except ImportError:
    try:
        # Fallback to src.ast_parsers
        from src.ast_parsers.query_analyzer import analyze_query, QueryMetadata
    except ImportError as e:
        print(f"Error: Could not import analyze_query: {e}")
        sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_dataset():
    """
    Load BirdSQL dataset, analyze queries, and save metadata to JSONL.
    """
    logger.info("Loading BirdSQL dataset (split: mini_dev_pg)...")
    try:
        dataset = load_dataset("birdsql/bird_mini_dev", split="mini_dev_pg")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        return

    logger.info(f"Loaded {len(dataset)} examples.")

    output_file = os.path.join(os.path.dirname(__file__), "query_intent_metadata.jsonl")
    
    logger.info(f"Processing queries and saving to {output_file}...")
    
    count = 0
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in dataset:
            try:
                db_id = item.get('db_id')
                sql_query = item.get('SQL')
                question = item.get('question')
                difficulty = item.get('difficulty')
                
                if not sql_query:
                    continue

                # Parse the query using sqlglot to get the AST
                # We use read="postgres" since the split is mini_dev_pg
                try:
                    ast = sqlglot.parse_one(sql_query, read="postgres")
                except Exception as parse_err:
                    logger.warning(f"Failed to parse query for db_id {db_id}: {parse_err}")
                    # Even if parsing fails, we might still want to record the item with empty metadata or skip it.
                    # For now, let's analyze None which returns empty metadata.
                    ast = None

                # Analyze the query
                metadata: QueryMetadata = analyze_query(ast)
                metadata_dict = metadata.to_dict()
                metadata_dict['difficulty'] = difficulty
                
                # Construct the output record
                record = {
                    "db_id": db_id,
                    "query": sql_query,
                    "intent": question,
                    "metadata": metadata_dict
                }
                
                # Write to JSONL
                f.write(json.dumps(record) + '\n')
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Processed {count} queries...")
                    
            except Exception as e:
                logger.error(f"Error processing item: {e}")
                continue

    logger.info(f"Finished processing. Total queries saved: {count}")

if __name__ == "__main__":
    process_dataset()
