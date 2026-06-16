"""Shared text helpers for parsing job titles.

Centralizes the company-extraction logic that previously lived (duplicated and
divergent) in both ``utils/filters.py`` and ``utils/search_engine.py``.
"""

import re
from typing import Optional

from .config import MIN_COMPANY_LEN, MAX_COMPANY_LEN

# Patterns that read the company from the *suffix* of a title,
# e.g. "Backend Intern - Acme", "QA @ Acme", "Data Intern at Acme".
SUFFIX_COMPANY_PATTERNS: list[tuple[str, int]] = [
    (r"\s+[-–|]\s+(.+)$", 1),
    (r"\s+@\s+(.+)$", 1),
    (r"\s+at\s+(.+)$", 1),
]

# Reads the company from the *prefix*, e.g. "Acme - Backend Intern".
PREFIX_COMPANY_PATTERN: tuple[str, int] = (r"^(.+?)\s+[-–|]\s+", 1)

# Tokens that mean the captured text is a role, not a company name.
_COMPANY_STOPWORDS: tuple[str, ...] = (
    "intern", "trainee", "graduate", "summer",
    "training", "entry", "fresh", "program",
)


def extract_company_from_title(
    title: str,
    patterns: list[tuple[str, int]],
    stopwords: tuple[str, ...] = _COMPANY_STOPWORDS,
) -> Optional[str]:
    """Return a plausible company name pulled from ``title``, or ``None``.

    ``patterns`` is an ordered list of ``(regex, capture_group)`` pairs; the
    first capture that survives the stopword and length checks wins.
    """
    stripped = title.strip()
    for pattern, group in patterns:
        match = re.search(pattern, stripped, re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(group).strip()
        candidate = re.sub(r"\s*\([^)]*\)\s*$", "", candidate)
        if any(word in candidate.lower() for word in stopwords):
            continue
        if MIN_COMPANY_LEN < len(candidate) < MAX_COMPANY_LEN:
            return candidate
    return None
