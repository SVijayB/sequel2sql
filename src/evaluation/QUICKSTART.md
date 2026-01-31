# Quick Start Guide - Core Functionality

## What This Does

1. **Combines dataset** - Pulls from HuggingFace + merges with solution files
2. **Sets up database** - Creates PostgreSQL in Docker with all tables
3. **Tests SQL** - Test error SQL and compare with true SQL solutions

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

# Or analyze with sequel2sql
python -m src.evaluation.sequel2sql_integration
```

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
