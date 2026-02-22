#!/bin/bash

# SEQUEL2SQL DB Skills Benchmark Launcher Script
# Mirroring execution from benchmark.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$ROOT_DIR/db_skills_benchmark"

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   DB SKILLS BENCHMARK LAUNCHER${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Check .env
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Found .env file"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python 3 is available"

# Check uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: uv not found${NC}"
    PYTHON_CMD="python3"
else
    PYTHON_CMD="uv run python3"
    echo -e "${GREEN}✓${NC} uv is available"
fi

# Check Docker Environment
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker not found${NC}"
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker is ready and running"

# Check PostgreSQL solutions payload
if [ ! -f "$ROOT_DIR/benchmark/data/pg_sol.jsonl" ]; then
    echo -e "${RED}❌ Error: postgresql_full.jsonl not found${NC}"
    echo "Expected file: $ROOT_DIR/benchmark/data/pg_sol.jsonl"
    exit 1
fi
echo -e "${GREEN}✓${NC} PostgreSQL Solution Payload is available"

# Verify store functionality implemented
if [ ! -f "$ROOT_DIR/src/db_skills/store.py" ]; then
  echo -e "${RED}❌ Error: src/db_skills/store.py not found${NC}"
  echo "The db_skills feature must be implemented before running this benchmark."
  exit 1
fi
echo -e "${GREEN}✓${NC} Advanced DB Skills module confirmed available"

echo ""
echo -e "${CYAN}Launching DB Skills benchmark...${NC}"
echo ""

# Launch application
cd "$BENCH_DIR"
exec $PYTHON_CMD main.py "$@"
