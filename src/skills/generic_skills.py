# -*- coding: utf-8 -*-
"""
Generic skills for SQL error taxonomy retrieval and feedback-loop updates.

Skill files live in src/skills/error_taxonomy/{category}.md, where {category}
is the taxonomy_category value from a ValidationError (e.g. "join_related",
"syntax", "aggregation", "semantic").

The CATEGORY_TO_FILE translation table has been removed.  Skill file names now
match taxonomy categories 1-to-1, so adding a new category only requires:
  1. Adding the new tags to ErrorTag in ast_parsers/tags.py
  2. Creating src/skills/error_taxonomy/{new_category}.md
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "error_taxonomy"

MAX_EXAMPLES_DEFAULT = 10


def get_error_taxonomy_skill(error_category: str) -> str:
    """
    Return the markdown skill file for the given taxonomy category.

    Args:
        error_category: Taxonomy category string from ValidationError.taxonomy_category
                        (e.g. ``"join_related"``, ``"syntax"``, ``"aggregation"``).

    Returns:
        Full markdown text of the skill file, or a short fallback message when
        no skill file exists for that category.
    """
    skill_path = SKILLS_DIR / f"{error_category}.md"
    if not skill_path.exists():
        return (
            f"No skill file found for category '{error_category}'. "
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
    Append a confirmed learned example to the skill file for *category*.

    Prunes the oldest entry when MAX_EXAMPLES is exceeded.
    Silently skips when *fixed_sql* is already present in the file.

    Args:
        category:             Taxonomy category (e.g. ``"join_related"``).
        original_sql:         The broken SQL query.
        fixed_sql:            The corrected SQL query.
        approach_description: One-line description of the fix.

    Returns:
        ``True`` if the file was updated (or the example was already present),
        ``False`` if the skill file for this category does not exist.
    """
    skill_path = SKILLS_DIR / f"{category}.md"
    if not skill_path.exists():
        return False

    content = skill_path.read_text(encoding="utf-8")
    if fixed_sql.strip() in content:
        return True  # Already recorded — idempotent

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


# ─── Private helpers ──────────────────────────────────────────────────────────


def _parse_max_examples(content: str) -> int:
    match = re.search(r"<!--\s*MAX_EXAMPLES=(\d+)\s*-->", content)
    return int(match.group(1)) if match else MAX_EXAMPLES_DEFAULT


def _count_learned_examples(content: str) -> int:
    return content.count("<!-- entry_start -->")


def _prune_oldest_example(content: str) -> str:
    """Remove the oldest (first) learned example entry from the file content."""
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
