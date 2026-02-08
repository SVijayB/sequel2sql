import sys
import os

# Add src to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import sqlglot
from ast_parsers.query_analyzer import analyze_query
from query_intent_vectorDB.search_similar_query import find_similar_examples

if __name__ == "__main__":
    test_intent = (
        "Find accounts with at least two transactions where the difference "
        "between max and min transaction amounts exceeds 12000."
    )

    test_sql = (
        "SELECT account_id "
        "FROM trans "
        "GROUP BY account_id "
        "HAVING COUNT(trans_id) > 1 "
        "AND (MAX(amount) - MIN(amount)) > 12000;"
    )

    print(f"Searching for similar examples for intent: {test_intent}")
    
    # Analyze input query
    try:
        ast = sqlglot.parse_one(test_sql, read="postgres")
        meta = analyze_query(ast)
        print("\n--- Input Query Metadata ---")
        print(f"SQL: {test_sql}")
        print(f"Complexity Score: {meta.complexity_score}")
        print(f"Pattern Signature: {meta.pattern_signature}")
        print(f"Clauses Present: {meta.clauses_present}")
        print("----------------------------\n")
    except Exception as e:
        print(f"Error analyzing input query: {e}")

    examples = find_similar_examples(test_intent )# test_sql) #removed because sql text no longer required

    for i, ex in enumerate(examples, 1):
        print(f"\nExample #{i}")
        print(ex.model_dump_json(indent=2))
