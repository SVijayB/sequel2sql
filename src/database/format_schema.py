"""
Schema formatting utilities for human-readable database schema output.

Formats SQLAlchemy Table objects into readable text DDL-like representations
optimized for LLM consumption.
"""

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.sql.schema import ForeignKeyConstraint


def format_table_schema(table: Table) -> str:
    """Format a SQLAlchemy Table object into a readable schema string.

    Returns a text representation like:
        TABLE table_name (
            COLUMNS
                column_name column_type [PRIMARY KEY] [NOT NULL] [DEFAULT value] [UNIQUE]
            ---
            INDEXES
                INDEX index_name (column_name [ASC|DESC])
            ---
            CONSTRAINTS
                FOREIGN KEY (column_name) REFERENCES target_table (target_column)
                UNIQUE (column1, column2)
        )

    Args:
        table: SQLAlchemy Table object from metadata

    Returns:
        Human-readable text representation of table schema
    """
    schema_lines = [f"TABLE {table.name} ("]

    # Format column definitions
    schema_lines.append("    COLUMNS")
    for column in table.columns:
        column_definition = f"        {column.name} {column.type}"
        if column.primary_key:
            column_definition += " PRIMARY KEY"
        if not column.nullable:
            column_definition += " NOT NULL"
        if column.default:
            column_definition += f" DEFAULT {column.default.arg}"  # type: ignore
        if column.unique:
            column_definition += " UNIQUE"
        schema_lines.append(column_definition + ",")

    schema_lines.append("    ---")

    # Format indexes
    schema_lines.append("    INDEXES")
    for index in table.indexes:
        index_columns = []
        for column in index.columns:
            # Handle special PostgreSQL index types (GIN, GIST)
            if index.dialect_options.get("postgresql_using", "") in ("gin", "gist"):
                index_columns.append(f"{column.name}")
            elif column.name in index.kwargs.get("descending_cols", []):
                index_columns.append(f"{column.name} DESC")
            else:
                index_columns.append(f"{column.name} ASC")
        index_columns_str = ", ".join(index_columns)
        schema_lines.append(f"        INDEX {index.name} ({index_columns_str}),")

    schema_lines.append("    ---")

    # Format constraints
    schema_lines.append("    CONSTRAINTS")

    # Format foreign keys
    for fk_constraint in table.constraints:
        if isinstance(fk_constraint, ForeignKeyConstraint):
            for fk in fk_constraint.elements:
                schema_lines.append(
                    f"        FOREIGN KEY ({fk.parent.name}) REFERENCES {fk.column.table.name} ({fk.column.name}),"
                )

    # Format unique constraints (if not already handled inline)
    for unique_constraint in table.constraints:
        if isinstance(unique_constraint, UniqueConstraint):
            uc_cols = ", ".join(uc_col.name for uc_col in unique_constraint.columns)
            schema_lines.append(f"        UNIQUE ({uc_cols}),")

    # Remove trailing comma from the last line in each section
    sections = ["COLUMNS", "INDEXES", "CONSTRAINTS"]
    for i in range(len(schema_lines) - 1, 0, -1):
        line = schema_lines[i].strip()
        if line.startswith("---"):
            continue
        if any(line.startswith(section) for section in sections):
            continue
        if schema_lines[i].endswith(","):
            schema_lines[i] = schema_lines[i].rstrip(",")
            break

    schema_lines.append(")")
    return "\n".join(schema_lines)
