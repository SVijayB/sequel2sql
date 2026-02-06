#!/bin/bash

# SEQUEL2SQL Benchmark Launcher Script
# This script checks prerequisites and launches the benchmark

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the directory of this script (root directory)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$ROOT_DIR/benchmark"

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   SEQUEL2SQL Benchmark Launcher${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Check if .env exists
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo ""
    echo -e "${YELLOW}Please create a .env file with your API keys:${NC}"
    echo -e "  ${CYAN}cd $ROOT_DIR${NC}"
    echo -e "  ${CYAN}cp .env.example .env${NC}"
    echo -e "  ${CYAN}# Edit .env and add your 8 Gemini API keys${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} Found .env file"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found${NC}"
    echo ""
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 is available"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker not found${NC}"
    echo ""
    echo -e "${YELLOW}Please install Docker:${NC}"
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is installed"

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not running${NC}"
    echo ""
    echo -e "${YELLOW}Please start Docker:${NC}"
    echo "  • On Linux: sudo systemctl start docker"
    echo "  • On Mac/Windows: Start Docker Desktop"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is running"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: uv not found${NC}"
    echo "Using python3 directly"
    PYTHON_CMD="python3"
else
    PYTHON_CMD="uv run python3"
    echo -e "${GREEN}✓${NC} uv is available"
fi

# Check if data directory exists
if [ ! -d "$BENCHMARK_DIR/data" ]; then
    echo -e "${RED}❌ Error: data directory not found${NC}"
    echo ""
    echo "Expected data at: $BENCHMARK_DIR/data"
    exit 1
fi

if [ ! -f "$BENCHMARK_DIR/data/postgresql_full.jsonl" ]; then
    echo -e "${RED}❌ Error: postgresql_full.jsonl not found${NC}"
    echo ""
    echo "Expected file: $BENCHMARK_DIR/data/postgresql_full.jsonl"
    exit 1
fi

echo -e "${GREEN}✓${NC} Data files found"

# Check if database dumps exist
if [ ! -d "$BENCHMARK_DIR/data/postgre_table_dumps" ]; then
    echo -e "${RED}❌ Error: PostgreSQL table dumps not found${NC}"
    echo ""
    echo "Expected directory: $BENCHMARK_DIR/data/postgre_table_dumps"
    exit 1
fi

echo -e "${GREEN}✓${NC} Database dumps found"

echo ""
echo -e "${CYAN}Starting benchmark...${NC}"
echo ""

# Change to benchmark directory
cd "$BENCHMARK_DIR"

# Run main script
exec $PYTHON_CMD main.py "$@"
