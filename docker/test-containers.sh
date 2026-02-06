#!/usr/bin/env bash
# Test the Docker stack (Postgres + MySQL). Run from repo root:
#   ./docker/test-containers.sh
# Or: bash docker/test-containers.sh

set -e
COMPOSE_FILE="docker/docker-compose.yml"
export POSTGRES_USER="${POSTGRES_USER:-root}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-123123}"
export MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-123123}"

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running. Please start Docker and try again."
  exit 1
fi

echo "=== Starting Postgres and MySQL ==="
docker compose -f "$COMPOSE_FILE" up -d postgres mysql

echo ""
echo "=== Waiting for health (up to 30s) ==="
for i in {1..30}; do
  if docker compose -f "$COMPOSE_FILE" ps postgres mysql 2>/dev/null | grep -q "healthy"; then
    sleep 2
  fi
  PG_OK=$(docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$POSTGRES_USER" -d postgres 2>/dev/null || true)
  MYSQL_OK=$(docker compose -f "$COMPOSE_FILE" exec -T mysql mysqladmin ping -h localhost -uroot -p"$MYSQL_ROOT_PASSWORD" 2>/dev/null || true)
  if [[ "$PG_OK" == *"accepting"* && "$MYSQL_OK" == *"alive"* ]]; then
    echo "Both databases are ready."
    break
  fi
  echo "  waiting... ($i)"
  sleep 1
done

echo ""
echo "=== Test PostgreSQL ==="
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "SELECT 1 AS one, current_database(), version();"
echo "PostgreSQL: OK"

echo ""
echo "=== Test MySQL ==="
docker compose -f "$COMPOSE_FILE" exec -T mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1 AS one, DATABASE(), VERSION();"
echo "MySQL: OK"

echo ""
echo "=== All container tests passed ==="
echo "Connection strings for dbdex:"
echo "  PostgreSQL: postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/postgres"
echo "  MySQL:     mysql+pymysql://root:$MYSQL_ROOT_PASSWORD@localhost:3306/mysql"
