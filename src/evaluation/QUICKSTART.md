# Quick Start Guide - Core Functionality

## When is Docker required?

**You do not need Docker for the baseline pipeline.** The flow that produces the eval-ready file is:

1. **Data preparation** (no Docker) → **Gemini baseline** (no Docker) → **Copy to BIRD-CRITIC** (no Docker)

Docker is only needed if you want to:

- **Run our local PostgreSQL** (`database_setup`) to load BIRD-CRITIC dumps and test SQL locally.
- **Use `sql_tester` or `database_checker`** to run SQL against that local DB.

The **official BIRD-CRITIC evaluation** (run_eval.sh) uses **their** Docker setup inside the BIRD-CRITIC repo, not ours. We only generate the baseline file; you run their eval in their environment.

To verify our Docker DB (when you use it) is working:  
`python -m src.evaluation.check_docker_db`

---

## What This Does

1. **Combines dataset** - Pulls from HuggingFace + merges with solution files
2. **Sets up database** (optional, needs Docker) - Creates PostgreSQL in Docker with all tables
3. **Tests SQL** (optional, needs Docker) - Test error SQL and compare with true SQL solutions

## Setup (One-time)

1. **Configure paths**:
   ```bash
   cp src/evaluation/config.example.json src/evaluation/config.json
   # Edit config.json with your paths
   ```

2. **Install dependencies**:
   ```bash
   pip install datasets psycopg2
   ```

## Running the Pipeline

### Step 1: Prepare Dataset
```bash
python -m src.evaluation.data_preparation
```
Output: `{eval_output_dir}/data/combined/postgresql_combined.jsonl`

### Step 2: Setup Database
```bash
python -m src.evaluation.database_setup
```
Sets up PostgreSQL in Docker with all tables loaded.

### Step 3: Test SQL
```bash
# Test a single instance
python -m src.evaluation.sql_tester \
  --instance_id PostgreSQL_1 \
  --dataset evaluation_output/data/combined/postgresql_combined.jsonl
```

### Step 4: Run Gemini baseline
Set `GEMINI_API_KEY` in a `.env` file at the project root, then run:
```bash
python -m src.evaluation.sequel2sql_integration
```
This loads the combined dataset, prompts Gemini (query + issue_sql) per instance, extracts `pred_sqls` from ```sql...``` blocks, and saves an **eval-ready** file to `{eval_output_dir}/data/results/baseline_gemini_final_output.jsonl` (each row has `pred_sqls` and all fields BIRD-CRITIC evaluation expects).

### Interpreting baseline results

Each line in `baseline_gemini_final_output.jsonl` is one instance with:
- **instance_id**, **db_id**, **query**, **issue_sql** (buggy SQL), **sol_sql** (gold fix), **pred_sqls** (model prediction).

**Streamlit dashboard** (select instance, view query/intent, compare pred_sql vs sol_sql):
```bash
streamlit run src/evaluation/baseline_dashboard.py
```

**Quick summary (no DB required):**
```bash
python -m src.evaluation.interpret_baseline_results
```
This reports: total instances, how many have non-empty **pred_sqls** (coverage), and a strict **exact string match** rate (pred_sqls vs sol_sql, normalized). Exact match is very strict; many correct fixes differ in formatting, so 0% exact match does not mean 0% correct.

**Real performance (execution accuracy):** BIRD-CRITIC runs **pred_sqls** and **sol_sql** against the real databases and compares results (and runs **test_cases** where present). To get pass rate / execution accuracy, run the official evaluation (see “End-to-end evaluation” below).

---

## End-to-end evaluation (BIRD-CRITIC)

To run the official BIRD-CRITIC evaluation on the baseline output:

1. **Prepare data and run baseline** (in this repo):
   ```bash
   python -m src.evaluation.data_preparation
   python -m src.evaluation.sequel2sql_integration
   ```
   Output: `{eval_output_dir}/data/results/baseline_gemini_final_output.jsonl`

2. **Copy baseline to BIRD-CRITIC repo** (optional script):
   ```bash
   python -m src.evaluation.copy_baseline_to_bird
   ```
   This copies the file to `{bird_critic_repo_path}/evaluation/data/postgresql_300.jsonl` and prints the exact commands for step 4. Or copy manually: create `evaluation/data/` in the BIRD-CRITIC repo if needed, then copy `baseline_gemini_final_output.jsonl` to `evaluation/data/postgresql_300.jsonl`.

3. **In the BIRD-CRITIC repo**: Enable the PostgreSQL service in `evaluation/docker-compose.yml` (uncomment the postgresql service and its dependency in so_eval_env).

4. **Run evaluation** (from BIRD-CRITIC repo):
   ```bash
   cd evaluation
   docker compose up --build
   ```
   Then in another terminal:
   ```bash
   docker compose exec so_eval_env bash
   cd run
   # Ensure dialect=postgresql and mode=pred in run_eval.sh
   bash run_eval.sh
   ```
   The report and status file are written next to the JSONL (e.g. `*_output_with_status.jsonl`).

## Configuration

Required paths in `config.json`:
- `bird_critic_repo_path` - Path to BIRD-CRITIC repository
- `bird_solutions_path` - Path to solution files (contains pg_sol.zip)
- `postgres_dumps_path` - Path to PostgreSQL database dumps
- `eval_output_dir` - Output directory (default: "evaluation_output")

Optional:
- `postgres_port` - PostgreSQL port (default: 5432)
- `postgres_user` - PostgreSQL user (default: "root")
- `postgres_password` - PostgreSQL password (default: "123123")

For baseline (sequel2sql_integration):
- Put `GEMINI_API_KEY=your_key` in a `.env` file at the project root (or set the environment variable). Config loads `.env` automatically.
- Default model is **Gemma 3 27B** (`gemma-3-27b-it`); same API key works. To use a smaller Gemma (e.g. 4B) or Gemini, set `GEMINI_MODEL=gemma-3-4b-it` or `GEMINI_MODEL=gemini-3-flash-preview` in `.env` or config.

## Usage in Code

```python
from src.evaluation.sql_tester import load_instance, get_error_sql, get_true_sql, test_instance

# Load an instance
instance = load_instance("PostgreSQL_1", "evaluation_output/data/combined/postgresql_combined.jsonl")

# Get SQL statements
error_sql = get_error_sql(instance)  # The buggy SQL
true_sql = get_true_sql(instance)    # The correct SQL
db_name = instance["db_id"]          # Database name

# Test against database
result = test_instance("PostgreSQL_1", "evaluation_output/data/combined/postgresql_combined.jsonl")
print(result["error_sql_result"])  # Result of error SQL execution
print(result["true_sql_result"])   # Result of true SQL execution
```

## Troubleshooting

- **File not found**: Check all paths in config.json
- **Docker errors**: Ensure Docker is running
- **Database connection errors**: Wait for database to be ready (takes ~1-2 minutes)

For detailed documentation, see `README.md`
