# -*- coding: utf-8 -*-
"""PostgreSQL SQLSTATE to taxonomy mapping and error code extraction."""

import re
import json
import os
from typing import Optional, Dict, List, Any


def load_error_data() -> Dict[str, Any]:
    """Load error data from JSON file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data", "error_data.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback empty structure if file missing
        return {
            "postgres_error_code_map": {},
            "taxonomy_categories": {},
            "error_patterns": {},
            "postgres_sqlstate_to_tag": {}
        }


_ERROR_DATA = load_error_data()

POSTGRES_ERROR_CODE_MAP: Dict[str, str] = _ERROR_DATA["postgres_error_code_map"]
TAXONOMY_CATEGORIES: Dict[str, List[str]] = _ERROR_DATA["taxonomy_categories"]
ERROR_PATTERNS: Dict[str, str] = _ERROR_DATA["error_patterns"]
POSTGRES_SQLSTATE_TO_TAG: Dict[str, str] = _ERROR_DATA["postgres_sqlstate_to_tag"]


# Class fallback when exact SQLSTATE unknown (first two chars).
SQLSTATE_CLASS_FALLBACK: Dict[str, str] = {
    "42": "semantic", "22": "semantic", "23": "logical", "28": "semantic",
    "2B": "semantic", "2D": "logical", "2F": "semantic", "34": "semantic",
    "38": "semantic", "39": "semantic", "3B": "logical", "3D": "semantic",
    "3F": "semantic", "40": "logical", "44": "logical", "53": "semantic",
    "54": "semantic", "55": "semantic", "57": "semantic", "58": "semantic",
    "72": "semantic", "0A": "semantic", "XX": "semantic", "F0": "semantic",
    "HV": "semantic", "P0": "semantic",
}


def extract_error_code(error_message: str) -> Optional[str]:
    """Extract SQLSTATE from message; None if not found."""
    sqlstate_pattern = r'(?:SQLSTATE|ERROR)[\s:]*([0-9][0-9A-Z]{4})|\[([0-9][0-9A-Z]{4})\]'
    match = re.search(sqlstate_pattern, error_message, re.IGNORECASE)
    if match:
        return (match.group(1) or match.group(2)).upper()
    
    error_lower = error_message.lower()
    for pattern, code in ERROR_PATTERNS.items():
        if re.search(pattern, error_lower, re.IGNORECASE):
            return code
    
    return None


def get_taxonomy_category(error_code: Optional[str]) -> Optional[str]:
    """
    Map PostgreSQL error code to taxonomy category.
    
    Args:
        error_code: PostgreSQL SQLSTATE error code (e.g., "42703", "42P01")
    
    Returns:
        Taxonomy category ("syntax", "semantic", "logical", etc.) or None
    """
    if error_code is None:
        return None
    
    return POSTGRES_ERROR_CODE_MAP.get(error_code)


def get_tags_for_category(category: Optional[str]) -> List[str]:
    """Tags for a taxonomy category; [] if unknown."""
    if category is None:
        return []
    
    return TAXONOMY_CATEGORIES.get(category, [])


def get_taxonomy_category_with_fallback(error_code: Optional[str]) -> Optional[str]:
    """Map SQLSTATE to category; use class fallback if exact code unknown."""
    if error_code is None:
        return None
    specific = POSTGRES_ERROR_CODE_MAP.get(error_code)
    if specific is not None:
        return specific
    if len(error_code) >= 2:
        return SQLSTATE_CLASS_FALLBACK.get(error_code[:2])
    return None


def get_tag_for_sqlstate(sqlstate: Optional[str]) -> Optional[str]:
    """Return single best tag for a SQLSTATE, or None."""
    if sqlstate is None:
        return None
    return POSTGRES_SQLSTATE_TO_TAG.get(sqlstate)


# Build reverse lookup map: Tag -> Category
TAG_TO_CATEGORY: Dict[str, str] = {}
for category, tags in TAXONOMY_CATEGORIES.items():
    for tag in tags:
        TAG_TO_CATEGORY[tag] = category


def get_category_for_tag(tag: str) -> Optional[str]:
    """Taxonomy category for a tag, or None."""
    # 1. Direct lookup
    if tag in TAG_TO_CATEGORY:
        return TAG_TO_CATEGORY[tag]
    
    # 2. Pattern matching based on category keys
    # Optimization: Check if tag starts with any known category + "_"
    for category in TAXONOMY_CATEGORIES:
        if tag.startswith(category + "_"):
            return category
            
    return None
