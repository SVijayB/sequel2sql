# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sequel2SQL is an agentic LLM + RAG framework for SQL error diagnosis, optimization, and correction. While most LLMs excel at generating SQL from natural language (NL2SQL), they struggle with fixing erroneous queries. This project addresses that gap using retrieval-augmented generation and agent-based workflows, leveraging database schemas, official documentation, and past correction examples.

**Project Context:**
- Capstone project for MS in Data Science, University of Washington
- Sponsored by Microsoft
- Python 3.12+ required

## Development Commands

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management.

### Initial Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Set up LogFire (optional, for logging and monitoring):**
   ```bash
   uv run logfire auth
   uv run logfire projects new
   ```
   Then uncomment LogFire configuration in [src/agent/sqlagent.py](src/agent/sqlagent.py)

3. **Configure Google API Key:**
   - Visit [Google AI Studio](https://aistudio.google.com/apikey)
   - Create a new API key
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Add your API key to `.env`:
     ```
     GOOGLE_API_KEY=your_actual_api_key_here
     ```

### Running the Application

```bash
# Run the web interface (main application)
uv run python sequel2sql.py
```

Then open http://localhost:8000 in your browser to access the chat interface.

```bash
# Run the agent pipeline directly with test cases
uv run python src/agent/sqlagent.py
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_validator.py

# Run tests with verbose output
uv run pytest -v

# Run tests and inspect ChromaDB
uv run python tests/inspect_chroma_db.py
```

### Benchmarking

Run the BIRD-CRITIC PostgreSQL benchmark (530 queries):

```bash
# Interactive mode (recommended for first-time users)
./benchmark.sh

# Command-line mode - test with limited queries
./benchmark.sh --limit 20

# Run full benchmark
./benchmark.sh
```

See [benchmark/README.md](benchmark/README.md) for detailed setup instructions, data downloads, and configuration.

### Docker Setup for Testing

```bash
# Start PostgreSQL container
docker compose -f docker/docker-compose.yml up -d postgres

# Check container status
docker compose -f docker/docker-compose.yml ps

# Test PostgreSQL connection
docker compose -f docker/docker-compose.yml exec postgres psql -U root -d postgres -c "SELECT 1, version();"

# Stop containers
docker compose -f docker/docker-compose.yml down
```

See [docker/README.md](docker/README.md) for engine versions and connection strings.

### Managing Dependencies

```bash
# Add a new dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Update dependencies
uv sync
```

## Code Architecture

### System Overview

Sequel2SQL uses a **deterministic orchestration pipeline** that combines AST-based validation, semantic retrieval, and LLM reasoning to fix SQL queries. The workflow (see [assets/flowchart.jpg](assets/flowchart.jpg)):

1. **Syntax Validation** - Parse query through AST validator to detect syntax/schema errors
2. **Syntax Fixing** - If errors found, use syntax fixer agent (up to 3 retries)
3. **Semantic Retrieval** - Embed query and retrieve top 6 similar examples from ChromaDB
4. **LLM Reasoning** - Main agent generates corrected query with few-shot context
5. **Validation** - Return corrected query with explanation

### Core Components

**Agent Layer** ([src/agent/](src/agent/)):
- **sqlagent.py**: Main orchestration pipeline with two Pydantic AI agents:
  - `agent`: Main SQL assistant using `gemini-3-flash-preview`
  - `syntax_fixer_agent`: Dedicated syntax error fixer
- **prompts/db_agent_prompt.py**: System prompts for agents
- Tools: `validate_query()` and `similar_examples_tool()` available to main agent

**AST Parser & Validation** ([src/ast_parsers/](src/ast_parsers/)):
- **validator.py**: SQL syntax and schema validation using sqlglot
- **query_analyzer.py**: AST-based query analysis for structural patterns
- **llm_tool.py**: Simplified validation interface for agent tool calls
- **error_codes.py**, **error_context.py**: Structured error handling with canonical tags
- **models.py**: Pydantic models for validation results

**Vector Database RAG** ([src/query_intent_vectorDB/](src/query_intent_vectorDB/)):
- **search_similar_query.py**: Semantic search over training examples using ChromaDB
- **embed_query_intent.py**: Query embedding using sentence-transformers
- **process_query_intent.py**: AST-based query intent extraction
- Uses `all-MiniLM-L6-v2` for embeddings, stored in [src/chroma_db/](src/chroma_db/)

**Entry Points:**
- **sequel2sql.py**: Web interface via `agent.to_web()` (http://localhost:8000)
- **src/agent/sqlagent.py**: Direct pipeline execution with test cases

**Benchmarking** ([benchmark/](benchmark/)):
- BIRD-CRITIC PostgreSQL benchmark runner (530 queries)
- Smart API key rotation, checkpointing, Docker-based evaluation
- See [benchmark/README.md](benchmark/README.md) for details

### Key Dependencies

- **pydantic-ai**: Agent framework and LLM orchestration
- **google-genai**: Gemini API access (`gemini-3-flash-preview` model)
- **chromadb**: Vector database for semantic search
- **sentence-transformers**: Query embedding (`all-MiniLM-L6-v2`)
- **sqlglot**: SQL parsing and AST analysis
- **logfire**: Optional observability and monitoring
- **uvicorn**: ASGI server for web interface

### Important Implementation Details

**Pipeline Execution Flow** ([src/agent/sqlagent.py](src/agent/sqlagent.py)):
- `run_pipeline()` is the main async orchestration function
- Validation happens deterministically BEFORE agent calls (not as agent tool)
- Syntax fixing uses a separate agent with up to 3 retries
- Few-shot examples retrieved using AST-based semantic search
- Final agent call includes: query intent, validated SQL, and similar examples

**Validation Strategy**:
- Schema files stored in [benchmark/data/schemas/](benchmark/data/schemas/) as JSON
- Validation uses sqlglot parser with PostgreSQL dialect
- Returns structured errors with canonical tags (e.g., `SYNTAX_ERROR`, `SCHEMA_ERROR`)
- See [src/ast_parsers/llm_tool.py](src/ast_parsers/llm_tool.py) for validation interface

**Vector Database**:
- ChromaDB collection: `query_intents`
- Documents indexed by AST-based query structure, not just raw SQL text
- Semantic search uses query intent + structural similarity
- Database persisted in [src/chroma_db/](src/chroma_db/)

## Code Style Guidelines

From [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md):

- **Indentation**: Use tabs (not spaces)
- **Line length**: Maximum 80 characters
- **Braces**: Opening braces on next line for class/method declarations
- **Spacing**: One space between operators and operands
- **Variable naming**: Descriptive names (avoid single-letter variables like `a` or `x`)
- **Commits**: Must be atomic - one logical change per commit
- **Testing**: Add tests for any new functionality

## Project-Specific Notes

- This project focuses on PostgreSQL specifically, not general SQL
- The goal is error correction and optimization, not initial query generation
- RAG context includes database schemas, official PostgreSQL docs, and past corrections
- Agent-based approach means queries go through multi-step reasoning, not single-shot generation
