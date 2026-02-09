# Query Intent Vector Database

This module handles the semantic search and retrieval of SQL examples based on natural language query intents. It powers the few-shot prompting mechanism by finding relevant and structurally diverse examples.

## Workflow

### 1. Processing (`process_query_intent.py`)
We digest the raw dataset (BirdSQL `mini_dev_pg`) and run it through our **AST Parser (`ast_parsers`)**.
For each query, we calculate a **complexity score** and extract structural metadata.
- **Complexity Score**: A normalized float (0-1) derived from the presence of advanced SQL features (CTEs, joins, aggregations, subqueries, etc.).
- **Pattern Signature**: A string representation of the query structure (e.g., `SELECT-FROM-WHERE`).

### 2. Embedding & Storage (`embed_query_intent.py`)
Processed records are embedded using `sentence-transformers` (`all-MiniLM-L6-v2`) and stored in a local **ChromaDB**.

**Example Stored Document:**
- **ID**: `2`
- **Document (Intent)**: "What was the average monthly consumption of customers in SME for the year 2013?"
- **Embedding**: `[...]`
- **Metadata**:
  - `db_id`: `"debit_card_specializing"`
  - `sql`: `"SELECT AVG(T2.Consumption) / NULLIF(12, 0) FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID WHERE SUBSTR(T2.Date, 1, 4) = '2013' AND T1.Segment = 'SME'"`
  - `complexity_score`: `0.068`
  - `pattern_signature`: `"SELECT-FROM-JOIN-JOIN_INNER-WHERE"`
  - `clauses_present`: `"FROM, JOIN, JOIN_INNER, SELECT, WHERE"`
  - `num_joins`: `1`
  - `num_subqueries`: `0`
  - `num_ctes`: `0`
  - `num_aggregations`: `1`
  - `document_type`: `"query_intent_pairs"`

### 3. Retrieval (`search_similar_query.py`)
To find the best examples for a new user query, we employ a sophisticated retrieval strategy:

1.  **Semantic Search**: Fetch the top 40 candidates similar to the user's intent.
2.  **Complexity Sampling (Stratification)**:
    - We analyze the complexity range (min to max) of the retrieved candidates.
    - We divide this range into 3 dynamic buckets (Low, Medium, High).
    - We sample the most relevant candidates from each bucket to ensure we cover different levels of difficulty.
3.  **Structural Diversity (MMR)**:
    - We use **Maximal Marginal Relevance (MMR)** to re-rank and select the final set.
    - **Similarity Metric**: We use **Jaccard Similarity** on the **Pattern Signature**.
    - This ensures we don't just return 5 examples that all look like `SELECT * FROM table`, but instead provide a mix of patterns (e.g., one simple select, one with a JOIN, one with a GROUP BY) to help the LLM generalize better.

**Output**: Returns a list of `FewShotExample` Pydantic models.
