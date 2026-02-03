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
uv add python-dotenv rich tqdm psycopg2-binary pyfiglet google-generativeai
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

📖 **See [TESTING_GUIDE.md](../TESTING_GUIDE.md) for detailed testing workflows and recommendations.**

The benchmark will:
1. Display the SEQUEL2SQL logo and configuration
2. Ask how many queries to run (or use --limit)
3. Generate prompts for your selected queries
4. Call Gemma 3 27B with intelligent key rotation
5. Extract SQL from responses
6. Start Docker containers
7. Run evaluation against PostgreSQL
8. Display comprehensive results

## Testing Recommendations

Before running the full 531-query benchmark (~5-6 hours), **start with a small subset**:

1. **Quick Test** (5-10 queries): `./benchmark.sh --limit 10` → ~10 minutes
2. **Small Test** (20-50 queries): `./benchmark.sh --limit 20` → ~30 minutes
3. **Medium Test** (100 queries): `./benchmark.sh --limit 100` → ~1-2 hours
4. **Full Benchmark** (531 queries): `./benchmark.sh` → ~5-6 hours

See [TESTING_GUIDE.md](../TESTING_GUIDE.md) for complete testing workflow.

## Usage Examples

### Testing with Subset (Interactive)

```bash
$ ./benchmark.sh

╔═══════════════════════════════════════════════════════════╗
║                   SEQUEL2SQL                              ║
║              BENCHMARK EVALUATION SYSTEM                  ║
║     PostgreSQL SQL Generation Benchmark using Gemma 3     ║
╚═══════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────┐
│           Query Selection                   │
│                                            │
│  Total available queries: 531              │
│                                            │
│  You can either run all queries or test   │
│  with a subset.                           │
└────────────────────────────────────────────┘

Do you want to run a subset (for testing)? [y/N]: y
How many queries do you want to run? (1-531) [20]: 20
✓ Running subset of 20 queries

Configuration:
  • Dialect:       PostgreSQL 14.12
  • Model:         Google Gemma 3 27B
  • Total Queries: 20              ← Updated!
  • API Keys:      8 configured
  • Threads:       8 workers

Run benchmark? (y/n): y
```

### Resume Interrupted Run

If your run gets interrupted, just run `./benchmark.sh` again:

```bash
$ ./run.sh

╔═══════════════════════════════════════════════════════════╗
║           PREVIOUS RUN DETECTED                           ║
╠═══════════════════════════════════════════════════════════╣
║  Progress: 245/531 queries completed (46.14%)             ║
║  Options: [Y] Resume  [R] Restart  [N] Exit               ║
╚═══════════════════════════════════════════════════════════╝

Your choice: resume
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
    "temperature": 0.0,
    "max_tokens": 2048,
    "timeout": 10,
    "max_threads": 8,
    "checkpoint_frequency": 10
}
```

Modify these values if needed (e.g., increase `max_threads` for faster processing).

## Troubleshooting

### Issue: "❌ Error: .env file not found"

**Solution**: Create .env file at repository root:
```bash
cd /home/svijayb/sequel2sql
cp .env.example .env
# Edit .env and add your 8 API keys
```

### Issue: "❌ Error: Docker is not running"

**Solution**:
```bash
# Linux
sudo systemctl start docker

# Mac/Windows
# Start Docker Desktop application
```

### Issue: "Failed to start Docker containers"

**Solution**:
```bash
# Check Docker logs
docker compose logs

# Rebuild containers
docker compose up -d --build

# If stuck, reset:
docker compose down
docker compose up -d --build
```

### Issue: API Rate Limits

**Solution**: This is expected! The system automatically:
1. Rotates through your 8 API keys
2. Waits 60 seconds when all keys are exhausted
3. Resumes with the first key

Make sure all 8 API keys are valid and have quota.

### Issue: Evaluation Fails

**Solution**:
```bash
# Check if PostgreSQL is healthy
docker exec sequel2sql_postgresql pg_isready -U root

# Check container status
docker ps

# View evaluation container logs
docker logs sequel2sql_eval

# Restart evaluation only (without re-running LLM):
# Just re-run ./run.sh and it will skip to evaluation phase
```

### Issue: Out of Memory

**Solution**:
1. Reduce `max_threads` in `src/config.py` (try 4 instead of 8)
2. Close other applications
3. Increase Docker memory limit (in Docker Desktop settings)

## Performance

### Expected Timing
- **Prompt Generation**: ~2-5 seconds
- **LLM Inference**: ~40-60 minutes (531 queries)
- **Post-processing**: ~2-5 seconds
- **Evaluation**: ~15-30 minutes
- **Total Runtime**: ~1-1.5 hours

### Speed Tips
1. Use all 8 API keys for best throughput
2. Increase `max_threads` if you have quota (e.g., 16)
3. Use SSD storage for faster Docker I/O
4. Run on a machine with good network connection

## Docker Containers

The benchmark uses two containers:

1. **sequel2sql_postgresql**: PostgreSQL 14.12 database server
   - Port: 5432
   - User: root
   - Password: 123123
   - Contains 15 template databases

2. **sequel2sql_eval**: Python evaluation environment
   - Runs test cases against generated SQL
   - Handles database isolation and cleanup

### Managing Containers

```bash
# Start containers
docker compose up -d

# Stop containers
docker compose down

# View logs
docker compose logs

# Restart containers
docker compose restart

# Remove everything (including data)
docker compose down -v
```

## Evaluation Metrics

The benchmark reports:

- **Overall Accuracy**: Percentage of queries that pass all test cases
- **Execution Errors**: SQL syntax or runtime errors
- **Timeout Errors**: Queries that exceed time limits
- **Assertion Errors**: Queries that produce wrong results

### Category Breakdown

- **Query** (~390 queries): SELECT statement issues
- **Management** (~105 queries): DDL/DML operations
- **Personalization** (~36 queries): Complex custom requirements

## Advanced Usage

### Test with Subset

To test with only 10 queries (faster):

```python
# Edit main.py, line 281:
num_generated = generate_prompts_from_file(
    data_file,
    prompts_file,
    schema_field="preprocess_schema",
    limit=10  # Add this line
)
```

### Retry Failed Queries

The checkpoint system tracks failed queries. To retry them:

```bash
# The system will automatically retry failed queries
# when you resume from a checkpoint
./run.sh
# Choose "resume"
```

### Clean Start

To clear everything and start fresh:

```bash
# Remove outputs and logs
rm -rf outputs/* logs/*

# Run benchmark
./run.sh
```

## Project Structure

```
benchmark/
├── main.py                    # Main orchestrator
├── run.sh                     # Launcher script
├── docker-compose.yml         # Docker configuration
├── IMPLEMENTATION.md          # Detailed implementation docs
├── README.md                  # This file
│
├── src/                       # Source code
│   ├── config.py              # Configuration and .env loading
│   ├── logger_config.py       # Logging setup
│   ├── api_client.py          # Gemini API with key rotation
│   ├── checkpoint_manager.py  # Save/resume functionality
│   ├── ui.py                  # Terminal UI components
│   ├── prompt_generator.py    # Prompt creation
│   ├── inference_engine.py    # Multi-threaded LLM calls
│   ├── post_processor.py      # SQL extraction
│   ├── postgresql_utils.py    # Database utilities
│   ├── wrapper_evaluation_postgresql.py    # Evaluation runner
│   └── single_instance_eval_postgresql.py  # Single query evaluation
│
├── data/                      # Input data
│   ├── postgresql_full.jsonl # 531 queries
│   └── postgre_table_dumps/  # Database templates
│
├── env/                       # Docker build files
│   ├── Dockerfile.postgresql
│   └── Dockerfile.so_eval
│
├── outputs/                   # Generated outputs (gitignored)
└── logs/                      # Log files (gitignored)
```

## API Key Rotation

The system uses intelligent key rotation:

```
Request 1 → Key 1
Request 2 → Key 2
...
Request 8 → Key 8
Request 9 → Key 1  (back to start)

If all 8 keys hit rate limits:
  ⏱️  Wait 60 seconds
  🔄 Resume with Key 1
```

### Getting API Keys

1. Go to https://ai.google.dev/
2. Sign in with Google account
3. Create API key
4. Repeat 8 times (you can use different Google accounts)
5. Add all keys to `.env`

## Contributing

This benchmark is part of the SEQUEL2SQL project. For detailed implementation information, see [IMPLEMENTATION.md](IMPLEMENTATION.md).

## References

- **BIRD-CRITIC**: https://github.com/bird-bench/BIRD-CRITIC-1
- **Google Gemini API**: https://ai.google.dev/docs
- **PostgreSQL 14**: https://www.postgresql.org/docs/14/

## License

See repository root for license information.

---

**Need Help?**

1. Check [IMPLEMENTATION.md](IMPLEMENTATION.md) for detailed technical docs
2. Review logs in `benchmark/logs/`
3. Check Docker logs: `docker compose logs`
4. Open an issue in the repository

Happy benchmarking! 🚀
