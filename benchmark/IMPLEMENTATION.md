# SEQUEL2SQL Benchmark - Implementation Documentation

## Project Overview

A clean, user-friendly console application that runs the BIRD-CRITIC PostgreSQL benchmark (531 queries) using Google Gemma 3 27B with intelligent API key rotation, full Docker-based evaluation, resume capability, and comprehensive logging.

### Core Requirements

1. **PostgreSQL Focus**: 531 queries from BIRD-CRITIC benchmark specifically for PostgreSQL
2. **Model**: Google AI's Gemma 3 27B (gemma-3-27b-it)
3. **API Key Management**: 8 API keys with intelligent cycling
4. **Rate Limiting Strategy**: 
   - Cycle through 8 API keys sequentially
   - When all 8 keys hit limits, wait 60 seconds
   - Resume from first key after wait period
5. **Evaluation**: Full Docker-based PostgreSQL evaluation (same as BIRD-CRITIC)
6. **User Experience**: Terminal UI with logo, progress tracking, and results display
7. **Reliability**: Resume capability with checkpoints every 10 queries
8. **Logging**: Dual logging (console + timestamped file in `/logs`)

## Architecture Overview

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     SEQUEL2SQL BENCHMARK                        │
│                                                                 │
│  1. Terminal UI (Logo + Config Display + Confirmation)         │
│  2. Prompt Generation (Schema + Issue SQL → Prompt)            │
│  3. LLM Inference (Multi-threaded with Key Rotation)           │
│  4. Post-Processing (Extract SQL from Markdown)                │
│  5. Docker Setup (PostgreSQL + Evaluation Container)           │
│  6. Evaluation (Test Cases + Database Validation)              │
│  7. Results Display (Metrics + Category Breakdown)             │
└─────────────────────────────────────────────────────────────────┘
```

### Phase Separation with Checkpoints

Each phase creates checkpoint files allowing independent retry:
- **Phase 1**: Prompts generated → `outputs/run_TIMESTAMP/prompts.jsonl`
- **Phase 2**: LLM responses collected → `outputs/run_TIMESTAMP/responses.jsonl` + checkpoint
- **Phase 3**: SQL extracted → `outputs/run_TIMESTAMP/final_output.jsonl`
- **Phase 4**: Evaluation completed → `outputs/run_TIMESTAMP/evaluation_results.jsonl`

## Directory Structure

```
/home/svijayb/sequel2sql/benchmark/
├── main.py                          # Main entry point and orchestrator
├── run.sh                           # Launcher script
├── docker-compose.yml               # PostgreSQL + evaluation containers
├── requirements.txt                 # Python dependencies
├── README.md                        # User-facing documentation
├── IMPLEMENTATION.md                # This file
├── .env                             # API keys (gitignored)
├── .env.example                     # Template for API keys
│
├── config/                          # Configuration files
│   └── model_config.json            # Model-specific settings
│
├── src/                             # Source code modules
│   ├── __init__.py
│   ├── config.py                    # Load .env and configuration
│   ├── api_client.py                # API key rotation + retry logic
│   ├── checkpoint_manager.py        # Save/load progress
│   ├── logger_config.py             # Dual logging setup
│   ├── ui.py                        # Terminal UI components
│   ├── prompt_generator.py          # Generate prompts from data
│   ├── inference_engine.py          # Multi-threaded LLM calls
│   ├── post_processor.py            # Extract SQL from responses
│   ├── postgresql_utils.py          # DB utilities (from bird-critic)
│   ├── wrapper_evaluation_postgresql.py  # Parallel evaluation
│   ├── single_instance_eval_postgresql.py  # Single instance eval
│   └── logger.py                    # Logger utilities (from bird-critic)
│
├── data/                            # Input data (gitignored)
│   └── postgresql_full.jsonl        # 531 PostgreSQL queries
│
├── prompts/                         # Generated prompts (gitignored)
│   └── .gitkeep
│
├── outputs/                         # Run outputs (gitignored)
│   └── run_YYYY-MM-DD_HH-MM-SS/
│       ├── prompts.jsonl            # Generated prompts
│       ├── responses.jsonl          # Raw LLM responses
│       ├── checkpoint.json          # Resume checkpoint
│       ├── final_output.jsonl       # Extracted SQL
│       ├── evaluation_results.jsonl # Evaluation with status
│       └── report.txt               # Summary report
│
├── logs/                            # Log files (gitignored)
│   └── benchmark_YYYY-MM-DD_HH-MM-SS.log
│
└── postgre_table_dumps/             # Database dumps (copied from bird-critic)
    ├── california_schools_template/
    ├── card_games_template/
    ├── codebase_community_template/
    ├── debit_card_specializing_template/
    ├── erolp_template/
    ├── esophageal_template/
    ├── european_football_2_template/
    ├── financial_template/
    ├── formula_1_template/
    ├── global_atlas_template/
    ├── spotify_template/
    ├── student_club_template/
    ├── superhero_template/
    ├── thrombosis_prediction_template/
    └── toxicology_template/
```

## Module Specifications

### 1. config.py

**Purpose**: Load and manage configuration from .env and config files

**Functions**:
- `load_api_keys()` → Returns list of 8 API keys from GEMINI_API_KEY_1 through GEMINI_API_KEY_8
- `get_model_config()` → Returns model configuration (base_url, model name, temperature, etc.)
- `validate_config()` → Checks all required keys exist and are valid

**Configuration Structure**:
```python
{
    "model_name": "models/gemma-3-27b-it",
    "base_url": "https://generativelanguage.googleapis.com/v1beta",
    "temperature": 0.0,
    "max_tokens": 2048,
    "timeout": 10,
    "max_threads": 8
}
```

**Error Handling**:
- Missing .env file → Display error message with .env.example instructions
- Invalid API keys → Test with simple request, warn about non-working keys
- Missing required fields → Exit with clear error message

---

### 2. api_client.py

**Purpose**: Handle API calls with intelligent key rotation and retry logic

**Class**: `GeminiAPIClient`

**Key Features**:
- Thread-safe key rotation using `itertools.cycle` and `threading.Lock`
- Automatic 60-second wait when all 8 keys exhausted
- Request timeout handling (10 seconds default)
- Detailed logging of key usage and errors

**Methods**:
```python
class GeminiAPIClient:
    def __init__(self, api_keys: List[str], model_config: dict)
    def call_api(self, prompt: str) -> str
    def _rotate_key(self) -> str
    def _handle_rate_limit(self) -> None
    def get_current_key_index(self) -> int
    def reset_to_key(self, index: int) -> None
```

**Rotation Logic**:
```python
# Thread-safe key cycling
with self.key_lock:
    current_key = next(self.key_cycle)
    self.key_index = (self.key_index + 1) % len(self.api_keys)
    self.total_requests += 1
    self.key_usage[self.key_index] += 1

# Rate limit handling
if retry_count % len(self.api_keys) == 0:
    logger.warning("All API keys exhausted. Waiting 60 seconds...")
    time.sleep(60)
    logger.info("Resuming API calls with first key...")
```

**Error Handling**:
- Rate limit (429) → Rotate to next key
- Timeout → Rotate and retry
- Authentication error (401) → Mark key as invalid, skip
- Other errors → Log and retry with next key

---

### 3. checkpoint_manager.py

**Purpose**: Save and restore benchmark progress for resume capability

**Class**: `CheckpointManager`

**Checkpoint Structure**:
```python
{
    "timestamp": "2026-02-02T14:30:45.123456",
    "total_queries": 531,
    "completed_queries": 245,
    "current_api_key_index": 3,
    "phase": "inference",  # prompt_generation, inference, post_processing, evaluation
    "output_directory": "outputs/run_2026-02-02_14-30-45",
    "completed_indices": [0, 1, 2, ..., 244],
    "failed_indices": [67, 123],
    "statistics": {
        "total_api_calls": 1230,
        "successful_calls": 1228,
        "failed_calls": 2,
        "key_usage": [154, 153, 154, 153, 154, 153, 154, 153]
    }
}
```

**Methods**:
```python
class CheckpointManager:
    def __init__(self, output_dir: str)
    def save_checkpoint(self, data: dict) -> None
    def load_checkpoint(self) -> Optional[dict]
    def checkpoint_exists(self) -> bool
    def get_remaining_queries(self, total_queries: int) -> List[int]
    def update_progress(self, completed_index: int) -> None
```

**Save Frequency**: Every 10 queries completed

**Resume Behavior**: 
- Detect checkpoint → Display: "Previous run detected (245/531 queries completed). Resume? (y/n/restart)"
- Yes → Continue from query 246 with same API key position
- No/Restart → Delete checkpoint and start fresh

---

### 4. logger_config.py

**Purpose**: Configure dual logging (console + file with timestamps)

**Functions**:
- `setup_logger(run_timestamp: str) -> logging.Logger`
- `get_console_handler() -> logging.Handler` (colorful with rich)
- `get_file_handler(log_path: str) -> logging.Handler` (rotating file)

**Log Format**:
```
Console: [14:30:45] INFO     Processing query 245/531 (API Key: 3/8)
File:    2026-02-02 14:30:45.123 | INFO | inference_engine.py:145 | Processing query 245/531
```

**Log Levels**:
- DEBUG: API request/response details
- INFO: Progress updates, checkpoint saves
- WARNING: API key exhaustion, retries
- ERROR: Failed queries, connection errors
- CRITICAL: Fatal errors requiring intervention

**File Rotation**: 
- Max size: 10 MB per file
- Keep last 5 files
- Compression: gzip old files

---

### 5. ui.py

**Purpose**: Terminal user interface components

**Functions**:
```python
def display_logo() -> None
def display_config_summary(config: dict) -> None
def confirm_run(checkpoint_exists: bool, checkpoint_data: Optional[dict]) -> str
def display_progress(current: int, total: int, key_index: int, passed: int, failed: int) -> None
def display_results(report_path: str) -> None
```

**Logo**:
```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ███████╗███████╗ ██████╗ ██╗   ██╗███████╗██╗          ║
║   ██╔════╝██╔════╝██╔═══██╗██║   ██║██╔════╝██║          ║
║   ███████╗█████╗  ██║   ██║██║   ██║█████╗  ██║          ║
║   ╚════██║██╔══╝  ██║▄▄ ██║██║   ██║██╔══╝  ██║          ║
║   ███████║███████╗╚██████╔╝╚██████╔╝███████╗███████╗     ║
║   ╚══════╝╚══════╝ ╚══▀▀═╝  ╚═════╝ ╚══════╝╚══════╝     ║
║                                                           ║
║   ██████╗ ███████╗ ██████╗ ██╗                           ║
║   ╚════██╗██╔════╝██╔═══██╗██║                           ║
║    █████╔╝███████╗██║   ██║██║                           ║
║   ██╔═══╝ ╚════██║██║▄▄ ██║██║                           ║
║   ███████╗███████║╚██████╔╝███████╗                      ║
║   ╚══════╝╚══════╝ ╚══▀▀═╝ ╚══════╝                      ║
║                                                           ║
║              BENCHMARK EVALUATION SYSTEM                  ║
╚═══════════════════════════════════════════════════════════╝

Configuration:
  • Dialect:       PostgreSQL 14.12
  • Model:         Google Gemma 3 27B
  • Total Queries: 531
  • API Keys:      8 configured
  • Threads:       8 workers
```

**Progress Display** (using rich.progress):
```
╭─────────────────────────────────────────────────────────────────╮
│ Generating SQL Solutions                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 46% 245/531 │
│                                                                 │
│ Current API Key: 3/8  │  Speed: 12.5 queries/min               │
│ Time Elapsed: 19m 36s │  Est. Remaining: 23m 04s               │
│                                                                 │
│ ✓ Passed: 180  │  ✗ Failed: 65  │  ⚠ Retries: 12              │
╰─────────────────────────────────────────────────────────────────╯
```

**Results Display** (parsed from report.txt):
```
╔═══════════════════════════════════════════════════════════════╗
║                    EVALUATION RESULTS                         ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Total Instances:        531                                  ║
║  Passed Instances:       423                                  ║
║  Failed Instances:       108                                  ║
║                                                               ║
║  Execution Errors:       45                                   ║
║  Timeout Errors:         23                                   ║
║  Assertion Errors:       40                                   ║
║                                                               ║
║  Overall Accuracy:       79.66%                               ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║                  CATEGORY BREAKDOWN                           ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Query:                  312/390  (80.00%)                    ║
║  Management:             89/105   (84.76%)                    ║
║  Personalization:        22/36    (61.11%)                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

Detailed results saved to:
  → outputs/run_2026-02-02_14-30-45/report.txt
  → outputs/run_2026-02-02_14-30-45/evaluation_results.jsonl
```

---

### 6. prompt_generator.py

**Purpose**: Generate prompts from dataset (adapted from bird-critic)

**Source**: `bird-critic/baseline/src/prompt_generator.py`

**Prompt Template**:
```python
baseline_v1 = """You are a SQL assistant. Your task is to understand user issue and correct their problematic SQL given the database schema. Please wrap your corrected SQL with ```sql\n[Your Fixed SQL]\n``` tags in your response.

# Database Schema:
{schema}

# User issue:
{user_issue}

# Problematic SQL:
{issue_sql}

# Corrected SQL:
"""
```

**Input**: `data/postgresql_full.jsonl` (531 entries)

**Output**: `outputs/run_TIMESTAMP/prompts.jsonl`

**Output Format**:
```json
{
  "instance_id": "PostgreSQL_0",
  "db_id": "financial",
  "dialect": "PostgreSQL",
  "prompt": "You are a SQL assistant...",
  "_index": 0
}
```

---

### 7. inference_engine.py

**Purpose**: Multi-threaded LLM inference with progress tracking

**Class**: `InferenceEngine`

**Features**:
- Multi-threaded execution (8 workers default)
- Progress bar with rich
- Checkpoint every 10 queries
- Real-time statistics
- Thread-safe file writing

**Methods**:
```python
class InferenceEngine:
    def __init__(self, api_client, checkpoint_manager, logger)
    def run_inference(self, prompts: List[dict], output_path: str) -> List[dict]
    def _worker(self, task_queue, results_dict, progress, lock)
    def _save_intermediate_results(self, results: List[dict])
```

**Worker Function**:
```python
def _worker(self, task_queue, results_dict, progress, lock):
    while True:
        try:
            task = task_queue.get_nowait()
        except queue.Empty:
            break
        
        prompt_data = task["data"]
        index = task["index"]
        
        try:
            response = self.api_client.call_api(prompt_data["prompt"])
            result = {
                **prompt_data,
                "response": response,
                "_index": index
            }
            with lock:
                results_dict[index] = result
                progress.update(task_id, advance=1)
                
                # Checkpoint every 10 queries
                if (index + 1) % 10 == 0:
                    self.checkpoint_manager.update_progress(index)
        except Exception as e:
            logger.error(f"Failed query {index}: {e}")
            with lock:
                self.failed_indices.append(index)
```

**Output**: `outputs/run_TIMESTAMP/responses.jsonl`

**Output Format**:
```json
{
  "instance_id": "PostgreSQL_0",
  "prompt": "You are a SQL assistant...",
  "response": "Based on the user issue...\n```sql\nSELECT * FROM table;\n```",
  "_index": 0
}
```

---

### 8. post_processor.py

**Purpose**: Extract SQL from markdown code blocks

**Source**: `bird-critic/baseline/src/post_process.py`

**Regex Pattern**:
```python
sql_pattern = re.compile(r"```[ \t]*sql\s*([\s\S]*?)```", re.IGNORECASE | re.DOTALL)
```

**Function**:
```python
def extract_sql_from_response(response: str) -> List[str]:
    """Extract SQL statements from markdown code blocks"""
    matches = sql_pattern.findall(response)
    return [stmt.strip() for stmt in matches if stmt.strip()]

def process_responses(input_path: str, output_path: str) -> None:
    """Process all responses and extract SQL"""
    with open(input_path) as f:
        data = [json.loads(line) for line in f]
    
    for item in data:
        item["pred_sqls"] = extract_sql_from_response(item["response"])
        # Remove large fields
        item.pop("prompt", None)
        item.pop("_index", None)
    
    with open(output_path, "w") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
```

**Output**: `outputs/run_TIMESTAMP/final_output.jsonl`

---

### 9. Evaluation Modules

**Source**: Copy from `bird-critic/evaluation/src/`

**Files to Copy**:
- `postgresql_utils.py` - Database utilities, connection pooling, test execution
- `wrapper_evaluation_postgresql.py` - Parallel evaluation with thread safety
- `single_instance_eval_postgresql.py` - Individual query evaluation
- `logger.py` - Logging configuration

**Key Functions**:

**postgresql_utils.py**:
```python
def load_jsonl(path) -> List[dict]
def save_report_and_status(...)
def generate_category_report(...)
def execute_sql(db_name, sql, timeout=60)
def compare_results(expected, actual)
```

**wrapper_evaluation_postgresql.py**:
```python
def run_instance(instance_data, instance_id, args, idx)
def get_db_lock(db_name)
def main()
```

**Database Connection**:
```python
# Connection to Docker container
{
    "host": "localhost",  # or "bird_critic_postgresql" if running inside Docker
    "port": 5432,
    "user": "root",
    "password": "123123",
    "dbname": "database_name"
}
```

**Evaluation Output**: `outputs/run_TIMESTAMP/evaluation_results.jsonl` + `report.txt`

---

### 10. main.py

**Purpose**: Main orchestrator script

**Flow**:
```python
def main():
    # 1. Setup
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = f"outputs/run_{timestamp}"
    logger = setup_logger(timestamp)
    
    # 2. Load configuration
    api_keys = load_api_keys()
    model_config = get_model_config()
    validate_config(api_keys, model_config)
    
    # 3. Display UI
    display_logo()
    display_config_summary(model_config)
    
    # 4. Check for checkpoint
    checkpoint_manager = CheckpointManager(output_dir)
    checkpoint_exists = checkpoint_manager.checkpoint_exists()
    
    # 5. Get user confirmation
    action = confirm_run(checkpoint_exists, checkpoint_manager.load_checkpoint())
    if action == "exit":
        return
    elif action == "restart":
        checkpoint_manager.clear()
    
    # 6. Phase 1: Prompt Generation
    if not checkpoint_exists or action == "restart":
        logger.info("Phase 1: Generating prompts...")
        generate_prompts(
            input_path="data/postgresql_full.jsonl",
            output_path=f"{output_dir}/prompts.jsonl"
        )
        checkpoint_manager.save_checkpoint({"phase": "prompt_generation"})
    
    # 7. Phase 2: LLM Inference
    logger.info("Phase 2: Running LLM inference...")
    api_client = GeminiAPIClient(api_keys, model_config)
    inference_engine = InferenceEngine(api_client, checkpoint_manager, logger)
    
    inference_engine.run_inference(
        prompts_path=f"{output_dir}/prompts.jsonl",
        output_path=f"{output_dir}/responses.jsonl"
    )
    checkpoint_manager.save_checkpoint({"phase": "inference"})
    
    # 8. Phase 3: Post-processing
    logger.info("Phase 3: Extracting SQL from responses...")
    process_responses(
        input_path=f"{output_dir}/responses.jsonl",
        output_path=f"{output_dir}/final_output.jsonl"
    )
    checkpoint_manager.save_checkpoint({"phase": "post_processing"})
    
    # 9. Phase 4: Docker Setup
    logger.info("Phase 4: Setting up Docker containers...")
    setup_docker()
    
    # 10. Phase 5: Evaluation
    logger.info("Phase 5: Running evaluation...")
    run_evaluation(
        jsonl_file=f"{output_dir}/final_output.jsonl",
        output_dir=output_dir,
        num_threads=8
    )
    checkpoint_manager.save_checkpoint({"phase": "evaluation"})
    
    # 11. Display Results
    logger.info("Benchmark complete!")
    display_results(f"{output_dir}/report.txt")

if __name__ == "__main__":
    main()
```

---

## Configuration Files

### .env.example

```bash
# Google Gemini API Keys (8 keys for rotation)
GEMINI_API_KEY_1=your_api_key_here
GEMINI_API_KEY_2=your_api_key_here
GEMINI_API_KEY_3=your_api_key_here
GEMINI_API_KEY_4=your_api_key_here
GEMINI_API_KEY_5=your_api_key_here
GEMINI_API_KEY_6=your_api_key_here
GEMINI_API_KEY_7=your_api_key_here
GEMINI_API_KEY_8=your_api_key_here

# Model Configuration
MODEL_NAME=models/gemma-3-27b-it
TEMPERATURE=0.0
MAX_TOKENS=2048
TIMEOUT=10

# Execution Configuration
MAX_THREADS=8
CHECKPOINT_FREQUENCY=10
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  postgresql:
    image: postgres:14.12
    container_name: sequel2sql_postgresql
    environment:
      POSTGRES_USER: root
      POSTGRES_PASSWORD: 123123
      POSTGRES_DB: postgres
    volumes:
      - ./postgre_table_dumps:/docker-entrypoint-initdb.d/postgre_table_dumps
    command:
      - "-c"
      - "max_connections=300"
      - "-c"
      - "shared_buffers=256MB"
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U root"]
      interval: 10s
      timeout: 5s
      retries: 5

  so_eval_env:
    image: python:3.10-slim
    container_name: sequel2sql_eval
    volumes:
      - ./:/app/
    working_dir: /app
    depends_on:
      postgresql:
        condition: service_healthy
    command: ["tail", "-f", "/dev/null"]
```

### requirements.txt

```
# Core dependencies
google-generativeai==0.3.2
python-dotenv==1.0.0
psycopg2-binary==2.9.9

# UI and progress
rich==13.7.0
tqdm==4.66.1
pyfiglet==1.0.2

# Utilities
tenacity==8.2.3
```

---

## Data Flow Diagram

```
┌─────────────────────┐
│ postgresql_full.jsonl│  (531 queries with schema, issue_sql, test_cases)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ prompt_generator.py │  → prompts.jsonl
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ inference_engine.py │  (Multi-threaded, 8 API keys rotation)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  responses.jsonl    │  (Raw LLM responses with markdown)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ post_processor.py   │  (Extract SQL from ```sql blocks)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ final_output.jsonl  │  (Extracted SQL in pred_sqls field)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│      Docker PostgreSQL Evaluation       │
│  (Parallel execution with DB isolation) │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│    evaluation_results.jsonl + report.txt│
│  (Status, passed/failed, error details) │
└─────────────────────────────────────────┘
```

---

## Error Handling Strategy

### Configuration Errors
- **Missing .env**: Display clear error with .env.example instructions, exit gracefully
- **Invalid API keys**: Test each key with simple request, warn about non-working keys, continue with valid ones
- **Missing data files**: Check for `data/postgresql_full.jsonl`, provide download instructions if missing

### Runtime Errors

#### API Errors
```python
Error Type              → Action
─────────────────────────────────────────────────────────
Rate Limit (429)        → Rotate to next key immediately
Timeout                 → Retry with next key (max 3 attempts)
Authentication (401)    → Mark key invalid, skip permanently
Server Error (500+)     → Wait 5 seconds, retry with same key
Network Error           → Wait 10 seconds, retry with next key
```

#### Database Errors
```python
Error Type                    → Action
─────────────────────────────────────────────────────────────
Connection Refused            → Check Docker status, retry 3 times
Database Does Not Exist       → Create from template, retry
Template Lock Timeout         → Wait for lock release (max 60s)
SQL Execution Error           → Log error, mark instance as failed
Query Timeout                 → Cancel query, mark as timeout error
```

#### Phase Recovery
```python
Phase                  → Recovery Strategy
─────────────────────────────────────────────────────────────
Prompt Generation      → If interrupted, restart from beginning (fast)
LLM Inference          → Resume from checkpoint (expensive phase)
Post-processing        → Restart from beginning (fast)
Evaluation             → Can retry independently without LLM calls
```

---

## Resume Capability Implementation

### Checkpoint Structure

**File**: `outputs/run_TIMESTAMP/checkpoint.json`

```json
{
  "created_at": "2026-02-02T14:30:45.123456",
  "last_updated": "2026-02-02T14:45:12.456789",
  "phase": "inference",
  "total_queries": 531,
  "completed_queries": 245,
  "failed_queries": 3,
  "current_api_key_index": 3,
  "completed_indices": [0, 1, 2, ..., 244],
  "failed_indices": [67, 123, 198],
  "statistics": {
    "total_api_calls": 1235,
    "successful_calls": 1232,
    "failed_calls": 3,
    "total_retries": 47,
    "key_usage": {
      "0": 154,
      "1": 155,
      "2": 153,
      "3": 154,
      "4": 155,
      "5": 153,
      "6": 154,
      "7": 157
    },
    "average_query_time": 4.7,
    "estimated_completion_time": "2026-02-02T15:15:30"
  }
}
```

### Resume Dialog

```
╔═══════════════════════════════════════════════════════════╗
║           PREVIOUS RUN DETECTED                           ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  Progress: 245/531 queries completed (46.14%)             ║
║  Started:  2026-02-02 14:30:45                           ║
║  Phase:    LLM Inference                                  ║
║                                                           ║
║  ✓ Completed: 242  │  ✗ Failed: 3                        ║
║                                                           ║
║  Options:                                                 ║
║    [Y] Resume from query 246                              ║
║    [R] Restart from beginning                             ║
║    [N] Exit                                               ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Your choice:
```

### Implementation Details

**Save Frequency**: Every 10 queries + on graceful shutdown (SIGINT/SIGTERM)

**Resume Logic**:
```python
def resume_inference(checkpoint_data, prompts):
    completed = set(checkpoint_data["completed_indices"])
    remaining_prompts = [p for i, p in enumerate(prompts) if i not in completed]
    
    # Restore API key position
    api_client.reset_to_key(checkpoint_data["current_api_key_index"])
    
    # Continue inference
    inference_engine.run_inference(remaining_prompts)
```

**Failed Queries**:
- Store failed indices in checkpoint
- At end of run, offer to retry only failed queries
- Maximum 3 retry attempts per query

---

## Docker Setup and Evaluation

### Docker Compose Services

1. **PostgreSQL Container**: Database server with 15 template databases
2. **Evaluation Container**: Python environment for running evaluation scripts

### Database Template Structure

Each database template in `postgre_table_dumps/`:
- `schema.sql` - Table definitions, indexes, constraints
- `data.sql` - Sample data for testing
- Isolated per query evaluation (clone template → run test → drop clone)

### Evaluation Process

1. **Parallel Execution**: 8 threads processing queries simultaneously
2. **Database Isolation**: Each thread gets unique database clone (`db_name_process_N`)
3. **Template Locking**: Thread-safe locks prevent concurrent template access
4. **Test Execution**:
   ```python
   # For each query:
   1. Create database clone from template
   2. Execute preprocess_sql (setup)
   3. Execute LLM-generated SQL (pred_sqls)
   4. Run test_cases (validation)
   5. Execute clean_up_sql (teardown)
   6. Drop database clone
   ```

### Test Case Types

1. **Soft EX**: Result set comparison for SELECT queries
2. **Test Functions**: Python functions validating CRUD operations
3. **Query Execution Plan**: Efficiency comparison (if `efficiency: true`)

### Evaluation Metrics

```python
Overall Accuracy = (Total - Errors) / Total * 100

Where Errors = Execution Errors + Timeout Errors + Assertion Errors

Category Breakdown:
- Query: SELECT statement issues
- Management: DDL/DML operations  
- Personalization: Complex custom requirements
```

---

## Implementation Checklist

### Phase 1: Setup and Configuration
- [ ] Create directory structure
- [ ] Create `.env.example` with 8 API key placeholders
- [ ] Update `.gitignore` with benchmark exclusions
- [ ] Copy `postgresql_full.jsonl` from bird-critic
- [ ] Copy database dumps to `postgre_table_dumps/`
- [ ] Create `docker-compose.yml`
- [ ] Create `requirements.txt`

### Phase 2: Core Modules
- [ ] Implement `config.py` - Load .env and validate
- [ ] Implement `api_client.py` - Key rotation and retry logic
- [ ] Implement `checkpoint_manager.py` - Save/load progress
- [ ] Implement `logger_config.py` - Dual logging setup

### Phase 3: UI Components
- [ ] Implement `ui.py` - Logo, config display, confirmation
- [ ] Add progress bar with rich
- [ ] Add results display parser
- [ ] Test all UI components

### Phase 4: Pipeline Modules
- [ ] Adapt `prompt_generator.py` from bird-critic
- [ ] Implement `inference_engine.py` - Multi-threaded inference
- [ ] Adapt `post_processor.py` from bird-critic
- [ ] Copy evaluation modules from bird-critic

### Phase 5: Orchestration
- [ ] Implement `main.py` - Full pipeline orchestration
- [ ] Add signal handlers for graceful shutdown
- [ ] Add phase recovery logic
- [ ] Create `run.sh` launcher script

### Phase 6: Testing
- [ ] Test API key rotation with dummy keys
- [ ] Test checkpoint save/resume
- [ ] Test with small subset (10 queries)
- [ ] Test Docker evaluation flow
- [ ] Test error handling scenarios

### Phase 7: Documentation
- [ ] Create user-facing `README.md`
- [ ] Document setup instructions
- [ ] Add troubleshooting guide
- [ ] Create usage examples

---

## Usage Guide

### Initial Setup

1. **Clone repository and navigate to benchmark directory**
   ```bash
   cd /home/svijayb/sequel2sql/benchmark
   ```

2. **Create .env file from template**
   ```bash
   cp .env.example .env
   # Edit .env and add your 8 Gemini API keys
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start Docker containers**
   ```bash
   docker compose up -d
   ```

5. **Run benchmark**
   ```bash
   ./run.sh
   # OR
   python main.py
   ```

### Running the Benchmark

```bash
$ ./run.sh

╔═══════════════════════════════════════════════════════════╗
║                   SEQUEL2SQL BENCHMARK                    ║
║              BENCHMARK EVALUATION SYSTEM                  ║
╚═══════════════════════════════════════════════════════════╝

Configuration:
  • Dialect:       PostgreSQL 14.12
  • Model:         Google Gemma 3 27B
  • Total Queries: 531
  • API Keys:      8 configured
  • Threads:       8 workers

Run benchmark? (y/n): y

Phase 1: Generating prompts... ✓ (2.3s)
Phase 2: Running LLM inference...

╭─────────────────────────────────────────────────────────────────╮
│ Generating SQL Solutions                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 46% 245/531 │
│                                                                 │
│ Current API Key: 3/8  │  Speed: 12.5 queries/min               │
│ Time Elapsed: 19m 36s │  Est. Remaining: 23m 04s               │
│                                                                 │
│ ✓ Passed: 180  │  ✗ Failed: 65  │  ⚠ Retries: 12              │
╰─────────────────────────────────────────────────────────────────╯
```

### Resuming Interrupted Run

```bash
$ ./run.sh

╔═══════════════════════════════════════════════════════════╗
║           PREVIOUS RUN DETECTED                           ║
╠═══════════════════════════════════════════════════════════╣
║  Progress: 245/531 queries completed (46.14%)             ║
║  Options: [Y] Resume  [R] Restart  [N] Exit               ║
╚═══════════════════════════════════════════════════════════╝

Your choice: y

Resuming from query 246...
```

---

## Troubleshooting

### Common Issues

#### Issue: "No module named 'google.generativeai'"
**Solution**: Install dependencies: `pip install -r requirements.txt`

#### Issue: "Failed to load .env file"
**Solution**: 
1. Check `.env` exists: `ls -la .env`
2. Copy from template: `cp .env.example .env`
3. Add your API keys to `.env`

#### Issue: "Docker connection refused"
**Solution**:
1. Check Docker is running: `docker ps`
2. Start containers: `docker compose up -d`
3. Check logs: `docker compose logs postgresql`

#### Issue: "API key rate limit exceeded"
**Solution**: This is expected. The system will automatically:
1. Rotate to next API key
2. Wait 60 seconds after all 8 keys exhausted
3. Resume with first key

#### Issue: "Database template not found"
**Solution**:
1. Check database dumps: `ls -la postgre_table_dumps/`
2. Copy from bird-critic if missing
3. Restart Docker: `docker compose restart`

---

## Performance Considerations

### Expected Timing

- **Prompt Generation**: ~2-5 seconds (fast, in-memory)
- **LLM Inference**: ~40-60 minutes (531 queries, ~12-15 queries/minute with 8 threads)
- **Post-processing**: ~2-5 seconds (regex extraction)
- **Evaluation**: ~15-30 minutes (depends on query complexity)
- **Total Runtime**: ~1-1.5 hours

### Optimization Tips

1. **Increase threads**: Set `MAX_THREADS=16` in `.env` if you have more API quota
2. **Reduce timeout**: Set `TIMEOUT=5` for faster failures
3. **Skip evaluation**: Run only inference for testing (modify main.py)
4. **Use checkpoint**: Always resume from checkpoint to avoid duplicate API calls

### Resource Usage

- **Memory**: ~2-4 GB (depends on thread count)
- **Disk**: ~500 MB for outputs per run
- **Network**: ~100-200 MB (API calls)
- **Docker**: ~1 GB (PostgreSQL + evaluation container)

---

## Future Enhancements

1. **Multiple Model Support**: Add Claude, GPT-4 alongside Gemma
2. **Custom Test Cases**: Allow user-defined validation logic
3. **Web Dashboard**: Real-time monitoring via web interface
4. **Distributed Execution**: Run across multiple machines
5. **Result Comparison**: Compare multiple model runs
6. **Fine-tuning Integration**: Use benchmark results for model improvement

---

## References

- **BIRD-CRITIC Repository**: https://github.com/bird-bench/BIRD-CRITIC-1
- **Google Gemini API**: https://ai.google.dev/docs
- **PostgreSQL 14 Documentation**: https://www.postgresql.org/docs/14/
- **Rich Library**: https://rich.readthedocs.io/

---

## Contact & Support

For issues or questions, please:
1. Check this implementation documentation
2. Review logs in `benchmark/logs/`
3. Check Docker logs: `docker compose logs`
4. Create an issue in the repository

---

**Last Updated**: 2026-02-02
**Version**: 1.0.0
**Status**: Ready for Implementation
