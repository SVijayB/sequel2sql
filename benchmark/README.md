# SEQUEL2SQL Benchmark

A clean, user-friendly console application for running the BIRD-CRITIC PostgreSQL benchmark (531 queries) using Google Gemma 3 27B with intelligent API key rotation and full Docker-based evaluation.

## Features

- 🚀 **PostgreSQL Focus**: 531 real-world SQL debugging queries
- 🤖 **Gemma 3 27B**: Google's latest AI model for SQL generation  
- 🔄 **Smart API Key Rotation**: Automatic cycling through 8 API keys with rate limit handling
- 📊 **Progress Tracking**: Real-time progress bars with statistics
- 💾 **Resume Capability**: Checkpoint every 10 queries to resume interrupted runs
- 🐳 **Docker Evaluation**: Full PostgreSQL database validation
- 📝 **Dual Logging**: Console output + detailed file logs

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
# You'll be prompted:
# 1. Do you want to run a subset? [y/N]
# 2. If yes, how many queries? [default: 20]
```

**Command-Line Mode** (for automation):
```bash
# Test with 20 queries
./benchmark.sh --limit 20

# Test with 100 queries
./benchmark.sh --limit 100

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
    "model_name": "models/gemma-3-27b-it",
    "timeout": 10,
    "max_threads": 8,
    "checkpoint_frequency": 10
}
```