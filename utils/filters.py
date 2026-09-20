import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urlparse

from .config import (
    Internship, RunConfig, ROLE_GROUPS, STALE_AFTER_DAYS,
    COMPANIES_EGYPT, MIN_LOCATION_RESULTS,
)
from .text import extract_company_from_title, SUFFIX_COMPANY_PATTERNS

EXCLUDE_COUNTRIES = [
    "usa", "united states", "uk", "united kingdom", "london", "germany",
    "france", "canada", "australia", "dubai", "uae", "qatar", "saudi",
    "kuwait", "oman", "bahrain", "jordan", "lebanon", "tunisia", "morocco",
    "algeria", "pakistan", "india", "china", "japan", "singapore", "america",
]

BOGUS_DOMAINS = [
    "facebook.com", "instagram.com", "twitter.com", "youtube.com",
    "merriam-webster.com", "dictionary.com", "cambridge.org",
    "wikipedia.org", "reddit.com", "pinterest.com",
    "vocabulary.com", "thesaurus.com", "britannica.com",
]

_COMPANIES_EGYPT_LOWER = [c.lower() for c in COMPANIES_EGYPT]


def _build_role_pattern(active_keywords: list[str]) -> Optional[re.Pattern]:
    """Compile a single word-boundary regex of all active role-match tokens.

    Built once per run (not per job). Returns ``None`` when no role tokens are
    active, in which case the role gate is treated as "don't filter".
    """
    active: set[str] = set()
    for group in ROLE_GROUPS.values():
        if any(kw in active_keywords for kw in group["keywords"]):
            active.update(group["match"])
    # Include any active keyword not covered by a role group.
    covered = {kw for g in ROLE_GROUPS.values() for kw in g["keywords"]}
    for kw in active_keywords:
        if kw not in covered:
            active.add(kw)
    if not active:
        return None
    tokens = sorted(active, key=len, reverse=True)  # longest first for specificity
    alternation = "|".join(re.escape(token) for token in tokens)
    # Word-boundary match that still handles .net, c++, etc.
    return re.compile(r"(?<![a-z0-9])(?:" + alternation + r")(?![a-z0-9])")


def matches_role(title_lower: str, role_pattern: Optional[re.Pattern]) -> bool:
    """Return True if the title contains an active role token (or no gate is set)."""
    if role_pattern is None:
        return True
    return role_pattern.search(title_lower) is not None


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date_posted into a datetime. Returns None if unparseable."""
    if not date_str:
        return None
    s = date_str.strip().lower()
    # Relative: "2 days ago", "1 week ago", "3 weeks ago", "1 month ago"
    m = re.match(r"(\d+)\s*(day|week|month)s?\s*ago", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "day":
            return datetime.now() - timedelta(days=n)
        if unit == "week":
            return datetime.now() - timedelta(weeks=n)
        if unit == "month":
            return datetime.now() - timedelta(days=n * 30)
    # ISO / common formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _compute_staleness(jobs: list[Internship]) -> None:
    cutoff = datetime.now() - timedelta(days=STALE_AFTER_DAYS)
    for job in jobs:
        dt = _parse_date(job.date_posted)
        if dt is not None:
            job.is_stale = dt < cutoff


def extract_job_title(raw_title: str) -> str:
    title = raw_title.strip()
    for pat in [r"^Internship\s+", r"^Paid\s+Internship\s*[–\-]\s*", r"^تدريب\s+", r"^Intern\s+"]:
        title = re.sub(pat, "", title, flags=re.IGNORECASE)
    for pat in [r"\s+[–\-]\s+Paid\s+Internship$", r"\s+[–\-]\s+Internship$",
                r"\s+[–\-]\s+intern$", r"\s+Internship$", r"-internship-$",
                r"\s*-\s*تدريب$", r"\s+تدريب$"]:
        title = re.sub(pat, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+[–\-]\s+(Intern|Trainee|Graduate)\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+[–\-]\s+[A-Z][a-z]+\s*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\b(egypt|cairo|alexandria|giza|luxor|internship|intern|training)\b', '', text)
    return text.strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _has_egypt_evidence(internship: Internship, config: RunConfig) -> bool:
    texts = [
        internship.title, internship.description,
        internship.company, internship.location, internship.url,
    ]
    combined = " ".join(t.lower() for t in texts if t)
    if "egypt" in combined or "مصر" in combined:
        return True
    if any(city in combined for city in config.target_cities):
        return True
    if any(company in combined for company in _COMPANIES_EGYPT_LOWER):
        return True
    return False


def deduplicate(jobs: list[Internship]) -> list[Internship]:
    seen_urls: set[str] = set()
    kept: list[Internship] = []

    for job in jobs:
        if job.url in seen_urls:
            continue
        seen_urls.add(job.url)

        norm_company = normalize(job.company) if job.company else ""

        is_dup = False
        if norm_company:
            for existing in kept:
                if not existing.company:
                    continue
                if existing.source != job.source:
                    continue
                if normalize(existing.company) != norm_company:
                    continue
                if similarity(existing.title, job.title) > 0.85:
                    is_dup = True
                    break

        if not is_dup:
            kept.append(job)

    return kept


def is_relevant(internship: Internship, config: RunConfig,
                role_pattern: Optional[re.Pattern]) -> bool:
    if internship.source == "company":
        return True

    title_lower = internship.title.lower()
    desc_lower = internship.description.lower()
    company_lower = internship.company.lower() if internship.company else ""
    url_lower = internship.url.lower()
    search_scope = f"{title_lower} {desc_lower} {company_lower} {url_lower}"

    for exclude in config.exclude_titles:
        if exclude in title_lower or exclude in desc_lower or exclude in company_lower:
            return False

    # Role gate: title must match an active role domain.
    if not matches_role(title_lower, role_pattern):
        return False

    if internship.source == "search":
        return any(include in search_scope for include in config.include_titles)

    return True


def is_egypt_location(internship: Internship, config: RunConfig) -> bool:
    if internship.source == "company":
        return True

    loc = internship.location.lower()
    if not loc or loc in ("egypt", "مصر"):
        if internship.source == "search":
            return _has_egypt_evidence(internship, config)
        return True
    if "egypt" in loc or "مصر" in loc:
        return True
    if any(city in loc for city in config.target_cities):
        return True
    if any(country in loc for country in EXCLUDE_COUNTRIES):
        return False
    # Unknown location: keep only if there is positive Egypt evidence elsewhere.
    return _has_egypt_evidence(internship, config)


def filter_jobs(jobs: list[Internship], config: RunConfig) -> list[Internship]:
    role_pattern = _build_role_pattern(config.active_keywords)

    for job in jobs:
        if not job.clean_title:
            job.clean_title = extract_job_title(job.title)
        if not job.company:
            inferred = extract_company_from_title(job.title, SUFFIX_COMPANY_PATTERNS)
            if inferred:
                job.company = inferred

    domain_blocked = [j for j in jobs if not any(b in _domain(j.url) for b in BOGUS_DOMAINS)]
    deduped = deduplicate(domain_blocked)
    relevant = [j for j in deduped if is_relevant(j, config, role_pattern)]
    located = [j for j in relevant if is_egypt_location(j, config)]

    result = located if len(located) >= MIN_LOCATION_RESULTS else relevant
    _compute_staleness(result)
    return result
