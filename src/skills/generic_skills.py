"""Generic skills for SQL error taxonomy retrieval and update."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "error_taxonomy"

MAX_EXAMPLES_DEFAULT = 10

# Maps both internal taxonomy_category values and user-facing JSON keys
# to the markdown file stem in src/skills/error_taxonomy/
CATEGORY_TO_FILE: dict[str, str] = {
    # Internal category names (from ValidationErrorOut.taxonomy_category)
    "syntax": "syntax",
    "semantic": "schema_link",
    "logical": "others",
    "join_related": "join",
    "aggregation": "aggregation",
    "filter_conditions": "filter",
    "value_representation": "value",
    "subquery_formulation": "subquery",
    "set_operations": "set_op",
    "structural": "select",
    # User-facing JSON keys (identity mapping)
    "schema_link": "schema_link",
    "join": "join",
    "filter": "filter",
    "value": "value",
    "subquery": "subquery",
    "set_op": "set_op",
    "others": "others",
    "select": "select",
}


def get_error_taxonomy_skill(error_category: str) -> str:
    """
    Return the markdown skill file for the given error taxonomy
    category.  Pass the taxonomy_category value from a
    ValidationErrorOut (e.g. "join_related", "syntax").

    Returns full markdown text, or a short fallback message when
    no skill file exists for that category.
    """
    stem = CATEGORY_TO_FILE.get(error_category)
    if stem is None:
        return (
            f"No skill file found for category '{error_category}'. "
            "Use general SQL debugging approach."
        )
    skill_path = SKILLS_DIR / f"{stem}.md"
    if not skill_path.exists():
        return (
            f"Skill file '{stem}.md' not found on disk. "
            "Use general SQL debugging approach."
        )
    return skill_path.read_text(encoding="utf-8")


def update_taxonomy_skill(
    category: str,
    original_sql: str,
    fixed_sql: str,
    approach_description: str,
) -> bool:
    """
    Append a confirmed learned example to the skill file for
    category.  Prunes the oldest entry when MAX_EXAMPLES is
    exceeded.  Silently skips if fixed_sql is already present.

    Args:
            category: Internal or user-facing taxonomy category string.
            original_sql: The broken SQL query.
            fixed_sql: The corrected SQL query.
            approach_description: One-line description of the fix.

    Returns:
            True if the file was updated (or duplicated/skipped),
            False if category is unknown or skill file missing.
    """
    stem = CATEGORY_TO_FILE.get(category)
    if stem is None:
        return False
    skill_path = SKILLS_DIR / f"{stem}.md"
    if not skill_path.exists():
        return False

    content = skill_path.read_text(encoding="utf-8")

    # Skip if this exact fixed SQL was already recorded
    if fixed_sql.strip() in content:
        return True

    max_examples = _parse_max_examples(content)
    current_count = _count_learned_examples(content)

    while current_count >= max_examples:
        content = _prune_oldest_example(content)
        current_count = _count_learned_examples(content)

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    new_entry = (
        f"\n<!-- entry_start -->\n"
        f"### Example {current_count + 1} — {date_str}\n"
        f"**Original (broken):**\n"
        f"```sql\n{original_sql.strip()}\n```\n"
        f"**Fixed:**\n"
        f"```sql\n{fixed_sql.strip()}\n```\n"
        f"**Approach used:** {approach_description.strip()}\n\n"
        f"---\n"
        f"<!-- entry_end -->\n"
    )

    skill_path.write_text(content + new_entry, encoding="utf-8")
    return True


def _parse_max_examples(content: str) -> int:
    match = re.search(r"<!--\s*MAX_EXAMPLES=(\d+)\s*-->", content)
    return int(match.group(1)) if match else MAX_EXAMPLES_DEFAULT


def _count_learned_examples(content: str) -> int:
    return content.count("<!-- entry_start -->")


def _prune_oldest_example(content: str) -> str:
    """Remove the oldest (first) learned example entry."""
    start_marker = "<!-- entry_start -->"
    end_marker = "<!-- entry_end -->"
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return content
    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        return content
    end_idx += len(end_marker)
    if end_idx < len(content) and content[end_idx] == "\n":
        end_idx += 1
    return content[:start_idx] + content[end_idx:]
