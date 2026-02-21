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

from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "error_taxonomy"


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


