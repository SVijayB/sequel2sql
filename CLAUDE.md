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

2. **Set up LogFire (for logging and monitoring):**
   ```bash
   uv run logfire auth
   uv run logfire projects new
   ```

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
# Run the web interface
uv run python sequel2sql.py
```

Then open http://localhost:8000 in your browser to access the chat interface.

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

### Current Implementation (v0.1.0)

**Core Components:**
- **src/sqlagent.py**: Pydantic AI agent using Google Gemma 3 27B (`gemma-3-27b-it`) via Gemini API
- **sequel2sql.py**: Main entry point that creates a web interface using `agent.to_web()`
- **LogFire**: Integrated logging and monitoring for agent traces

**Planned Components (Coming Soon):**
- **RAG Pipeline**: Will retrieve context from database schemas, PostgreSQL documentation, and historical query corrections
- **AST Parser**: Will parse and embed user queries to database for semantic search
- **Error Diagnosis Flow**: Will analyze SQL errors, retrieve relevant context, and generate corrections

The planned system workflow (see [assets/flowchart.jpg](assets/flowchart.jpg)):
1. Receive erroneous SQL query
2. Parse query through AST and embed to vector DB
3. Retrieve top 5 relevant examples from training data
4. Agent-based reasoning to diagnose the issue with RAG context
5. Generate and validate corrected query

**Key Dependencies:**
- **pydantic-ai**: Agent framework for LLM-based workflows
- **logfire**: Observability and monitoring for agent execution
- **uvicorn**: ASGI server for the web interface
- **python-dotenv**: Environment variable management
- **Google Gemini API**: Access to Gemma 3 27B model

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
