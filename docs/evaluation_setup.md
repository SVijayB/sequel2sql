# BIRD-CRITIC Evaluation Setup Guide

This guide explains how to set up and run the BIRD-CRITIC evaluation pipeline for testing sequel2sql on real-world SQL debugging tasks.

## Overview

The evaluation setup integrates with the BIRD-CRITIC benchmark to:
1. Combine the complete dataset (HuggingFace + solution files)
2. Set up PostgreSQL database in Docker with all tables
3. Test error SQL and compare with true SQL solutions

**Important:** BIRD-CRITIC repository and dataset files are NOT tracked in git. You must download and configure paths to external files.

## Prerequisites

1. **Python 3.12+** with required packages:
   ```bash
   pip install datasets psycopg2
   ```

2. **Docker and Docker Compose** installed and running

3. **External files** (see Setup section below):
   - BIRD-CRITIC repository
   - Solution files (pg_sol.zip)
   - PostgreSQL database dumps

## Setup

### Step 1: Download BIRD-CRITIC Repository

1. Clone or download the BIRD-CRITIC repository:
   ```bash
   git clone https://github.com/bird-bench/BIRD-CRITIC-1.git
   # Or download from: https://huggingface.co/datasets/birdsql/bird-critic-1.0-open
   ```

2. Note the path to the repository (e.g., `/path/to/BIRD-CRITIC-1-main/BIRD-CRITIC-1-main`)

### Step 2: Download Solution Files

1. Request solution files by emailing: bird.bench23@gmail.com or bird.bench25@gmail.com
   (These are not included in the public dataset to prevent data leakage)

2. Extract the solution files to a directory (e.g., `/path/to/bird_critic_tc/BIRD-Critic-sol`)

3. Ensure `pg_sol.zip` is present in this directory

### Step 3: Download Database Dumps

1. Download PostgreSQL database dumps from [Google Drive](https://drive.google.com/drive/folders/1nJReLrvZVVrnfgBYwwNEgYvLroPGbcPD?usp=sharing)

2. Extract the dumps to a directory (e.g., `/path/to/BIRD-CRITIC-1-main/BIRD-CRITIC-1-main/evaluation/postgre_table_dumps`)

### Step 4: Configure Paths

1. Copy the example configuration:
   ```bash
   cp src/evaluation/config.example.json src/evaluation/config.json
   ```

2. Edit `src/evaluation/config.json` and fill in the paths to your downloaded files:
   ```json
   {
     "bird_critic_repo_path": "/path/to/BIRD-CRITIC-1-main/BIRD-CRITIC-1-main",
     "bird_solutions_path": "/path/to/bird_critic_tc/BIRD-Critic-sol",
     "postgres_dumps_path": "/path/to/BIRD-CRITIC-1-main/BIRD-CRITIC-1-main/evaluation/postgre_table_dumps",
     "eval_output_dir": "evaluation_output",
     "postgres_port": 5432,
     "postgres_user": "root",
     "postgres_password": "123123"
   }
   ```

   **Required paths:**
   - `bird_critic_repo_path`: Path to the BIRD-CRITIC repository you downloaded
   - `bird_solutions_path`: Path to the directory containing `pg_sol.zip` (solution files)
   - `postgres_dumps_path`: Path to the PostgreSQL database dumps directory
   - `eval_output_dir`: Directory where output files will be saved (default: "evaluation_output")

   **Note:** `config.json` is in `.gitignore` and will not be committed to git.

3. Alternatively, set environment variables:
   ```bash
   export BIRD_CRITIC_REPO_PATH="/path/to/BIRD-CRITIC-1-main/BIRD-CRITIC-1-main"
   export BIRD_SOLUTIONS_PATH="/path/to/bird_critic_tc/BIRD-Critic-sol"
   export POSTGRES_DUMPS_PATH="/path/to/BIRD-CRITIC-1-main/BIRD-CRITIC-1-main/evaluation/postgre_table_dumps"
   export EVAL_OUTPUT_DIR="evaluation_output"
   ```

## Usage

### Step 1: Data Preparation

Pull the dataset from HuggingFace and combine with solution files:

```bash
python -m src.evaluation.data_preparation
```

This will:
- Download the BIRD-CRITIC dataset from HuggingFace
- Filter for PostgreSQL instances only
- Extract and merge solution files
- Save combined dataset to `{EVAL_OUTPUT_DIR}/data/combined/postgresql_combined.jsonl`

### Step 2: Baseline Generation (Optional)

Generate baseline predictions using LLM APIs:

```bash
python -m src.evaluation.baseline_generator
```

This will:
- Generate prompts using BIRD-CRITIC baseline templates
- Call LLM API to generate predictions
- Post-process responses to extract SQL statements
- Save predictions to `{EVAL_OUTPUT_DIR}/data/predictions/{model_name}_postgresql_predictions.jsonl`

**Note:** This step requires API keys and may incur costs.

### Step 3: Evaluation

Run evaluation in Docker environment:

```bash
python -m src.evaluation.evaluator
```

This will:
- Generate Docker Compose configuration
- Build and start PostgreSQL and evaluation containers
- Run evaluation script on predictions
- Save results to `{EVAL_OUTPUT_DIR}/data/results/`

### Step 4: Sequel2SQL Integration

Test sequel2sql on the BIRD-CRITIC dataset:

```bash
python -m src.evaluation.sequel2sql_integration
```

This will:
- Load BIRD-CRITIC instances
- Analyze each instance using sequel2sql's validator and analyzers
- Compare results with baseline predictions (if available)
- Generate comparison reports

## Output Files

All output files are saved in the configured `eval_output_dir`:

```
evaluation_output/
├── data/
│   ├── combined/
│   │   └── postgresql_combined.jsonl      # Combined dataset with solutions
│   ├── prompts/
│   │   └── postgresql_prompts.jsonl       # Generated prompts
│   ├── predictions/
│   │   └── {model_name}_postgresql_predictions.jsonl  # Model predictions
│   └── results/
│       ├── postgresql_evaluation_report.json           # Evaluation report
│       ├── postgresql_status.jsonl                     # Per-instance status
│       ├── sequel2sql_analysis.jsonl                   # Sequel2SQL analysis
│       └── sequel2sql_baseline_comparison.json         # Comparison report
└── docker-compose.yml                    # Generated Docker Compose file
```

## Troubleshooting

### Docker Issues

- **Containers not starting**: Check Docker is running and has enough resources
- **PostgreSQL not ready**: Wait longer or check container logs: `docker logs bird_critic_postgresql`
- **Permission errors**: Ensure Docker has access to mounted directories

### Path Issues

- **File not found errors**: Verify all paths in config are correct and files exist
- **Permission errors**: Check read/write permissions on all configured paths

### API Issues

- **API key errors**: Verify API keys are set correctly in config or environment
- **Rate limiting**: The API client includes retry logic, but you may need to wait between runs

### Dataset Issues

- **HuggingFace download fails**: Check internet connection and HuggingFace access
- **Solution file missing**: Ensure `pg_sol.zip` is in the solutions directory
- **Database dumps missing**: Download from Google Drive link

## Advanced Usage

### Custom Configuration

You can specify a custom config file:

```bash
python -m src.evaluation.data_preparation --config /path/to/custom_config.json
```

### Running Individual Steps

Each module can be run independently:

```python
from src.evaluation.config import load_config
from src.evaluation.data_preparation import prepare_data

config = load_config("path/to/config.json")
prepare_data("path/to/config.json")
```

### Docker Management

The Docker manager can be used programmatically:

```python
from src.evaluation.config import load_config
from src.evaluation.docker_manager import DockerManager

config = load_config()
docker_manager = DockerManager(config)
compose_file = docker_manager.generate_docker_compose("docker-compose.yml")
docker_manager.build_containers(compose_file)
docker_manager.start_containers(compose_file)
```

## References

- [BIRD-CRITIC Repository](https://github.com/bird-bench/BIRD-CRITIC-1)
- [BIRD-CRITIC Dataset](https://huggingface.co/datasets/birdsql/bird-critic-1.0-open)
- [BIRD-CRITIC Paper](https://arxiv.org/abs/2506.18951)

## Support

For issues with:
- **BIRD-CRITIC dataset**: Contact bird.bench23@gmail.com or bird.bench25@gmail.com
- **sequel2sql evaluation**: Open an issue in the sequel2sql repository
