# DB Skills Benchmark

Evaluation harness for measuring how effectively the Sequel2SQL agent leverages **confirmed SQL fixes** (db_skills) during query correction. Compares agent performance on **seen** queries (fixes pre-seeded into ChromaDB) vs **unseen** queries (no prior knowledge).

## Quick Start

```bash
# From project root
./db_skills_benchmark.sh
```

This runs the `pipeline_seeded` mode on the `european_football_2` database by default.

## Modes

| Mode | Description |
|---|---|
| `pipeline` | Runs the full agent pipeline as-is on a single database (no seen/unseen split) |
| `pipeline_seeded` | Splits examples into seen/unseen halves; seeds the seen fixes into ChromaDB, then runs the agent on both halves |
| `pipeline_control` | Splits examples into seen/unseen halves but does **not** seed anything into ChromaDB — acts as a control group for comparison |

## How It Works

1. **Split** — Benchmark examples are split into **seen** (seeded) and **unseen** subsets
2. **Seed** — Seen examples' correct SQL fixes are embedded into ChromaDB via `save_confirmed_fix()`
3. **Run** — The full Sequel2SQL agent pipeline processes all examples (seen + unseen)
4. **Evaluate** — Predicted SQL is evaluated for execution correctness via Docker PostgreSQL containers
5. **Report** — CLI report shows accuracy delta between seen and unseen subsets

## Key Metrics

- **Execution Accuracy** — Does the predicted SQL produce the same result as the gold SQL?
- **Retrieval Rate** — How often did the agent retrieve a relevant fix from ChromaDB?
- **Top Retrieved Similarity** — Cosine similarity of the best-matching fix
- **Accuracy Delta** — `seen_accuracy - unseen_accuracy` (positive = db_skills helps)

## Directory Structure

```
db_skills_benchmark/
├── main.py                    # Entry point and orchestration
├── db_skills_benchmark.sh     # Shell wrapper (in project root)
├── src/
│   ├── config.py              # Paths, model config, dataset loading
│   ├── cli.py                 # CLI argument parsing
│   ├── seeder.py              # ChromaDB seeding and backup/restore
│   ├── runner.py              # Agent inference + Docker evaluation
│   ├── stats_reporter.py      # Metrics calculation and CLI output
│   ├── explanation_generator.py  # LLM-generated fix explanations
│   └── logger.py              # Rich console + file logging setup
├── outputs/                   # Run results (timestamped directories)
│   └── run_YYYY-MM-DD_HH-MM-SS/
│       ├── results_seen.json
│       ├── results_unseen.json
│       └── metrics.json
└── logs/                      # Debug logs
```

## Configuration

Key settings in `src/config.py`:

- **`TARGET_DB_ID`** — Database to benchmark against (default: `european_football_2`)
- **`SEEN_COUNT` / `UNSEEN_COUNT`** — Number of examples per subset
- **`SUBSET_LIMIT`** — Total examples cap (set to `None` for full dataset)
- **Model** — Configured via `.env` (`LLM_PROVIDER`, `LLM_MODEL`)
