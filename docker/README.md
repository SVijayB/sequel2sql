# Docker: SQL engines for BIRD-Critic, Spider 1.0, Spider 2.0 + dbdex

This directory provides a Docker Compose stack with the SQL engine versions used by **BIRD-Critic**, **Spider 1.0**, and **Spider 2.0**, and a **dbdex**-compatible client so you can use [dbdex](https://github.com/Finndersen/dbdex) to query these databases.

## SQL versions

| Benchmark     | Engine     | Version in this stack |
|-------------|------------|------------------------|
| BIRD-Critic | PostgreSQL | 14.12 (same as [BIRD-CRITIC-1/evaluation](https://github.com/taoyds/spider)) |
| BIRD-Critic | MySQL      | 8.4.0                  |
| Spider 1.0  | SQLite     | File-based (see below) |
| Spider 2.0  | PostgreSQL | 14.12                  |
| Spider 2.0  | SQLite     | Same volume as Spider 1.0 |

## Quick start

From the **repo root**:

```bash
# Copy env and start Postgres + MySQL
cp docker/.env.example docker/.env
docker compose -f docker/docker-compose.yml up -d postgres mysql sqlite-mount
```

Then use dbdex **from your host** (recommended) or from the `dbdex` service.

## Testing the containers

From the **repo root**, run the test script to start Postgres and MySQL and verify connections:

```bash
chmod +x docker/test-containers.sh
./docker/test-containers.sh
```

Or test manually:

```bash
# Start databases
docker compose -f docker/docker-compose.yml up -d postgres mysql

# Check they're running (wait until "healthy")
docker compose -f docker/docker-compose.yml ps

# Test PostgreSQL
docker compose -f docker/docker-compose.yml exec postgres psql -U root -d postgres -c "SELECT 1, version();"

# Test MySQL
docker compose -f docker/docker-compose.yml exec mysql mysql -uroot -p123123 -e "SELECT 1, VERSION();"
```

If both commands return a row with `1` and the server version, the containers are working.

## Using dbdex with this stack

[dbdex](https://github.com/Finndersen/dbdex) supports PostgreSQL, MySQL, and SQLite. Install it locally and point it at the running containers.

### 1. From your host (recommended)

Install dbdex:

```bash
pip install "git+https://github.com/Finndersen/dbdex.git[postgres,mysql]"
```

Start the databases:

```bash
docker compose -f docker/docker-compose.yml up -d postgres mysql
```

**Connection strings** (default credentials from `.env.example`):

- **PostgreSQL** (BIRD-Critic, Spider 2.0):
  ```text
  postgresql://root:123123@localhost:5432/postgres
  ```

- **MySQL** (BIRD-Critic):
  ```text
  mysql+pymysql://root:123123@localhost:3306/mysql
  ```

- **SQLite** (Spider 1.0): after placing Spider 1.0 `.sqlite` files in a folder (e.g. `./spider1_databases`):
  ```text
  sqlite:///./spider1_databases/department_management.sqlite
  ```

Run dbdex:

```bash
python -m dbdex \
  --model openai:gpt-4o \
  --api-key "$OPENAI_API_KEY" \
  --db-uri postgresql://root:123123@localhost:5432/postgres
```

### 2. From the dbdex Docker service

Build and run dbdex inside the stack (uses `postgres` / `mysql` hostnames):

```bash
docker compose -f docker/docker-compose.yml --profile client up -d postgres mysql
docker compose -f docker/docker-compose.yml run --rm -e OPENAI_API_KEY="$OPENAI_API_KEY" dbdex \
  python -m dbdex \
  --model openai:gpt-4o \
  --api-key "$OPENAI_API_KEY" \
  --db-uri postgresql://root:123123@postgres:5432/postgres
```

## Spider 1.0 SQLite databases

Spider 1.0 uses **SQLite** databases (200 DBs). They are not included in this repo.

1. Download the Spider 1.0 dataset from [Yale LILY](https://yale-lily.github.io/spider) (link to the zip with `database/` containing `.sqlite` files).
2. Either:
   - **Host:** Copy the `.sqlite` files into a directory and use:
     ```text
     sqlite:///path/to/database/db_id.sqlite
     ```
   - **Docker:** Copy files into the `spider1_databases` volume, then run dbdex with the volume mounted and use a path inside the container (e.g. `/data/spider1/department_management.sqlite`).

## BIRD-Critic evaluation

For full BIRD-Critic evaluation (with table dumps and init scripts), use the existing setup:

```bash
cd BIRD-CRITIC-1/evaluation
# Uncomment postgresql/mysql in docker-compose.yml and add your table dumps
docker compose up -d postgresql mysql
```

The Postgres/MySQL **versions** (14.12 and 8.4.0) in `docker/docker-compose.yml` match BIRD-Critic so you can reuse the same engine versions for development and dbdex.

## Compose reference

- **postgres** – PostgreSQL 14.12, port 5432  
- **mysql** – MySQL 8.4.0, port 3306  
- **sqlite-mount** – Holds volume `spider1_databases` for Spider 1.0 SQLite files  
- **dbdex** (profile `client`) – Image with dbdex + sequel2sql; run with `--profile client`

Files:

- `docker-compose.yml` – Service definitions  
- `.env.example` – Copy to `.env` and set credentials  
- `Dockerfile.dbdex` – Client image for dbdex  
- `README.md` – This file  
