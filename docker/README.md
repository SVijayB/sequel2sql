# Docker: SQL engines for BIRD-Critic, Spider 1.0, Spider 2.0

This directory provides a Docker Compose stack with the SQL engine versions used by **BIRD-Critic**, **Spider 1.0**, and **Spider 2.0**. After review, only **PostgreSQL** is enabled by default; other services are commented out and can be enabled as needed.

## SQL versions

| Benchmark     | Engine     | Version in this stack |
|-------------|------------|------------------------|
| BIRD-Critic | PostgreSQL | 14.12 (same as BIRD-Critic evaluation) |
| BIRD-Critic | MySQL      | 8.4.0 (commented out)  |
| BIRD-Critic | SQL Server | 2022 (commented out)   |
| BIRD-Critic | Oracle     | 19c (commented out)    |
| Spider 1.0  | SQLite     | File-based (commented out) |
| Spider 2.0  | PostgreSQL | 14.12                  |
| Spider 2.0  | SQLite     | Same volume as Spider 1.0 (commented out) |

## Testing the containers

From the **repo root**, test PostgreSQL manually:

```bash
# Start database
docker compose -f docker/docker-compose.yml up -d postgres

# Check they're running (wait until "healthy")
docker compose -f docker/docker-compose.yml ps

# Test PostgreSQL
docker compose -f docker/docker-compose.yml exec postgres psql -U root -d postgres -c "SELECT 1, version();"

```

If the command returns a row with `1` and the server version, the container is working.

## Spider 1.0 SQLite databases

Spider 1.0 uses **SQLite** databases (200 DBs). They are not included in this repo.

1. Download the Spider 1.0 dataset from [Yale LILY](https://yale-lily.github.io/spider) (link to the zip with `database/` containing `.sqlite` files).
2. Either:
   - **Host:** Copy the `.sqlite` files into a directory and use:
     ```text
     sqlite:///path/to/database/db_id.sqlite
     ```
  - **Docker:** Copy files into the `spider1_databases` volume and use a path inside the container (e.g. `/data/spider1/department_management.sqlite`).