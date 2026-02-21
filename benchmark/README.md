# SEQUEL2SQL Benchmark

A clean, user-friendly console application for running the BIRD-CRITIC PostgreSQL benchmark (530 queries) using various models and full Docker-based evaluation.

This benchmark tool was built with a lot of code being reused from the [BIRD-CRITIC-1](https://github.com/bird-bench/BIRD-CRITIC-1) repository. 
You can refer to it for more details on the benchmark dataset and evaluation methodology along with data sources.

## Features

- **Smart API Key Rotation**: Automatic cycling through 8 API keys with rate limit handling
- **Progress Tracking**: Real-time progress bars with statistics
- **Resume Capability**: Checkpoint every 10 queries to resume interrupted runs
- **Docker Evaluation**: Full PostgreSQL database validation
- **Dual Logging**: Console output + detailed file logs

## Quick Start

### 1. Setup Environment

```bash
# Navigate to benchmark directory
cd /home/svijayb/sequel2sql/benchmark

# Create .env file with your API keys
cp ../.env.example ../.env

# Edit .env and add your 8 Gemini API keys
# Get keys from: https://ai.google.dev/
nano ../.env
```

Your `.env` should look like:
```bash
GEMINI_API_KEY_1=AIza...your_key_1
GEMINI_API_KEY_2=AIza...your_key_2
# ... (8 keys total)
```

### 2. Install Dependencies

Dependencies are already installed at the repository root via UV. If you need to reinstall:

```bash
cd /home/svijayb/sequel2sql
uv sync
```

### 3. Download Dataset

All of the datasets required are to be downloaded, extracted and placed inside the `/benchmark/data` directory.

1) Download and extract postgre_table_dumps.zip from here: [Google drive link](https://drive.google.com/drive/folders/1nJReLrvZVVrnfgBYwwNEgYvLroPGbcPD).
2) You can download both the full question and schema file along with the ground truth solution through this [Google drive link](https://drive.google.com/drive/folders/1-nD5nyt_9tutnqP1eudEDimRfW1c39Na?usp=sharing)

Exact structure of `/benchmark/data` should be:

```
data/
├── postgre_table_dumps/
│   ├── california_schools_template/
│   ├── card_games_template/
│   ├── codebase_community_template/
│   ├── debit_card_specializing_template/
│   ├── ... 
├── pg_sol.jsonl
└── postgresql_full.jsonl
```

### 3. Start Docker

Make sure Docker is running:
```bash
# Check Docker status
docker ps

# On Linux, if Docker isn't running:
sudo systemctl start docker

# On Mac/Windows: Start Docker Desktop
```

### 4. Run Benchmark

```bash
cd /home/svijayb/sequel2sql
./benchmark.sh
```

The benchmark supports two modes:

**Interactive Mode** (recommended for first-time users):
```bash
./benchmark.sh
```

**Command-Line Mode** (for automation):
```bash
# Test with 20 queries
./benchmark.sh --limit 20

# Run all 531 queries
./benchmark.sh
```

## Output Structure

Each run creates a timestamped directory:

```
benchmark/
├── outputs/
│   └── run_2026-02-02_14-30-45/
│       ├── prompts.jsonl              # Generated prompts
│       ├── responses.jsonl            # Raw LLM responses
│       ├── checkpoint.json            # Progress checkpoint
│       ├── final_output.jsonl         # Extracted SQL
│       └── final_output_report.txt    # Evaluation results
│
└── logs/
    └── benchmark_2026-02-02_14-30-45.log  # Detailed logs
```

## Configuration

All configuration is in [src/config.py](src/config.py):

```python
MODEL_CONFIG = {
    "model_name": "models/google-gla:gemini-3-flash-preview",
    "timeout": 10,
    "max_threads": 8,
    "checkpoint_frequency": 10
}
```