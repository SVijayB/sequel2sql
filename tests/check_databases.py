#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, inspect, text

# Connect to postgres database to list all databases
engine = create_engine("postgresql://root:123123@localhost:5432/postgres")

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT datname FROM pg_database WHERE datistemplate = false;")
    )
    databases = [row[0] for row in result]
    print("Available databases:")
    for db in databases:
        print(f"  - {db}")

# Now check each database for tables
print("\n" + "=" * 70)
print("Databases with tables:")
print("=" * 70)

for db in databases:
    if db in ["postgres", "template_hashes", "template_postgis"]:
        continue
    try:
        db_engine = create_engine(f"postgresql://root:123123@localhost:5432/{db}")
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()
        if tables:
            print(f"\n✓ Database '{db}' has {len(tables)} tables:")
            for table in sorted(tables)[:15]:  # Show first 15
                row_count_result = db_engine.connect().execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                row_count = row_count_result.scalar()
                print(f"    - {table} ({row_count} rows)")
    except Exception as e:
        pass
