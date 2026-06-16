import copy
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"

# --- Tunable constants (no magic numbers at call sites) ---------------------
DEFAULT_LOCATION = "Egypt"
DEFAULT_DAYS_POSTED = 7
REQUEST_TIMEOUT = 30
FETCH_RETRIES = 3
MIN_BODY_LENGTH = 1000          # bodies shorter than this are treated as failures
BING_CONCURRENCY = 5            # max simultaneous Bing requests
MIN_LOCATION_RESULTS = 5        # below this, the location filter is dropped
MIN_COMPANY_LEN = 3             # exclusive lower bound for an inferred company name
MAX_COMPANY_LEN = 60            # exclusive upper bound for an inferred company name
STALE_AFTER_DAYS = 30
SEARCH_PAGES = 1

# Per-source overall timeouts (seconds) for a full scrape() call.
PHASE_TIMEOUTS: dict[str, int] = {
    "indeed": 180,
    "wuzzuf": 180,
    "company_pages": 90,
    "search_engine": 90,
    "linkedin": 120,
}

KEYWORDS = [
    "software developer", "software engineering", "software engineer",
    "data science", "business development", "marketing", "finance",
    "sustainable interior design", "environmental interior design"
]

# Single source of truth for Egyptian employer names — used both to seed
# company-page searches and as positive Egypt-location evidence in filtering.
COMPANIES_EGYPT = [
    "Siemens Egypt", "IBM Egypt", "Microsoft Egypt", "Google Egypt",
    "Amazon Egypt", "Valeo Egypt", "PwC Egypt", "Deloitte Egypt",
    "EY Egypt", "KPMG Egypt", "Procter & Gamble Egypt", "Unilever Egypt",
    "PepsiCo Egypt", "Coca-Cola Egypt", "Oracle Egypt", "SAP Egypt",
    "Huawei Egypt", "Intel Egypt", "Vodafone Egypt", "Orange Egypt",
    "Telecom Egypt", "Etisalat Egypt", "Aramex Egypt", "Majid Al Futtaim Egypt",
    "EFG Hermes", "CIB Egypt", "QNB Egypt", "HSBC Egypt",
    "JPMorgan Egypt", "Flat6Labs Cairo", "Falak Startups",
    "ITWORX", "Raya Holding", "Elsewedy Electric",
    "Talabat Egypt", "Careem Egypt", "Uber Egypt", "swvl",
    "Juhayna", "RATP Dev", "Dsquares", "Henkel", "Giza Systems",
    "Heineken", "Dubizzle", "Lesaffre", "Pentavalue", "IACC",
    "Al Ahram", "Mansour Automotive", "Abou Ghaly", "Al-Mansour",
    "Talaat Moustafa", "Emirates NBD", "Fairmont", "Marriott",
    "Air Liquide", "AUC",
]

UNIVERSITIES_EGYPT = [
    "Cairo University", "Alexandria University", "Ain Shams University",
    "GUC", "Zewail City", "EJUST", "Nile University",
    "British University in Egypt", "American University in Cairo",
    "German University in Cairo", "MSA University",
    "Helwan University", "Mansoura University", "Assiut University",
]

# Each group: "keywords" = phrases that activate this domain from KEYWORDS,
# "match" = tokens checked (word-boundary) against the job title.
ROLE_GROUPS: dict[str, dict] = {
    "software": {
        "keywords": [
            "software developer", "software engineering", "software engineer",
        ],
        "match": [
            "developer", "software engineer", "software engineering",
            "software development", "sde", "software developer",
            "backend", "back end", "front end", "frontend", "full stack", "fullstack",
            "web developer", "web engineer", "mobile developer", "mobile engineer",
            "android", "ios", "flutter", "react native",
            "devops", "sre", "site reliability",
            "qa engineer", "quality assurance", "test engineer", "automation engineer",
            "programmer", "software",
            ".net", "java", "python", "node", "golang", "rust", "c++",
        ],
    },
    "data": {
        "keywords": ["data science"],
        "match": [
            "data scientist", "data science", "data analyst", "data engineer",
            "machine learning", "ml engineer", "ai engineer", "deep learning",
            "business intelligence", "bi analyst", "analytics", "data",
            "nlp", "computer vision",
        ],
    },
    "business_development": {
        "keywords": ["business development"],
        "match": [
            "business development", "partnerships", "bd ",
        ],
    },
    "marketing": {
        "keywords": ["marketing"],
        "match": [
            "marketing", "digital marketing", "social media", "content",
            "seo", "growth", "brand", "media buyer", "campaign",
        ],
    },
    "finance": {
        "keywords": ["finance"],
        "match": [
            "finance", "financial", "accounting", "accountant",
            "audit", "investment", "banking", "treasury", "tax",
        ],
    },
    "interior_design": {
        "keywords": [
            "sustainable interior design", "environmental interior design",
        ],
        "match": [
            "interior design", "interior designer", "sustainable design",
            "environmental design",
        ],
    },
}

# Broad terms used by Indeed/Wuzzuf (one search per term + "intern").
BOARD_KEYWORDS = [
    "software", "data science", "marketing", "finance",
    "business development", "interior design",
]

SCRAPER_CONFIG: dict[str, dict] = {
    "linkedin": {
        "enabled": True,
        "keywords": KEYWORDS,
        "industry_keywords": [
            "software developer", "software engineering", "software engineer",
            "data science", "business development", "marketing", "finance",
            "sustainable interior design", "environmental interior design"
        ],
        "location": DEFAULT_LOCATION,
        "days_posted": DEFAULT_DAYS_POSTED,
        "experience_level": [1, 2],
        "sort_by": "DD",
    },
    "indeed": {
        "enabled": True,
        "keywords": BOARD_KEYWORDS,
        "location": DEFAULT_LOCATION,
    },
    "wuzzuf": {
        "enabled": True,
        "keywords": BOARD_KEYWORDS,
        "location": DEFAULT_LOCATION,
    },
    "search_engine": {
        "enabled": True,
        "keywords": KEYWORDS,
    },
    "company_pages": {
        "enabled": True,
        "query_templates": [
            "{name} internship careers 2026",
            "{name} فرص تدريب مصر",
        ],
        "companies": COMPANIES_EGYPT,
        "universities": UNIVERSITIES_EGYPT,
    },
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

TARGET_CITIES = ["cairo", "alexandria", "giza", "hurghada", "luxor",
    "mansoura", "sharm el-sheikh", "ismailia", "asyut", "port said", "suez"]

EXCLUDE_TITLES = ["senior", "sr.", " sr ", "lead", "manager", "director", "head of",
    "principal", "5+ years", "7+ years", "10+ years", "staff", "vp ", "vice president"]

INCLUDE_TITLES = ["intern", "trainee", "graduate", "تدريب", "متدر",
    "طالب", "fresh grad", "junior"]


class ProgressEvent:
    """Canonical ``type`` values for SSE progress events.

    Producers (``main.py``) and consumers (``app.py`` / the browser) must agree
    on these strings; this is the single source of truth.
    """

    MESSAGE = "message"
    PHASE_DONE = "phase_done"
    PHASE_ERROR = "phase_error"
    PHASE_SKIP = "phase_skip"
    DONE = "done"
    ERROR = "error"


@dataclass
class Internship:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    date_posted: str = ""
    job_type: str = ""
    clean_title: str = ""
    is_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("clean_title", None)  # runtime-only field, excluded from output
        return d


@dataclass
class RunConfig:
    """Immutable-per-run configuration threaded through the whole pipeline.

    Replaces the previous pattern of mutating module-level globals, so
    concurrent or sequential runs never leak settings into one another.
    """

    scrapers: dict[str, dict]
    exclude_titles: list[str]
    include_titles: list[str]
    target_cities: list[str]
    active_keywords: list[str]
    location: str = DEFAULT_LOCATION
    days_posted: int = DEFAULT_DAYS_POSTED

    @classmethod
    def default(cls) -> "RunConfig":
        return cls(
            scrapers=copy.deepcopy(SCRAPER_CONFIG),
            exclude_titles=list(EXCLUDE_TITLES),
            include_titles=list(INCLUDE_TITLES),
            target_cities=list(TARGET_CITIES),
            active_keywords=list(KEYWORDS),
        )


def build_run_config(user_config: Optional[dict[str, Any]] = None) -> RunConfig:
    """Build a fresh :class:`RunConfig` from a user-supplied override dict.

    Unknown keys are ignored. The returned config is independent of the module
    defaults (deep-copied), so callers may use it freely without side effects.
    """
    config = RunConfig.default()
    if not user_config:
        return config

    for key, value in user_config.items():
        if key in config.scrapers and isinstance(value, dict):
            config.scrapers[key].update(value)
        elif key == "exclude_titles" and isinstance(value, list):
            config.exclude_titles = value
        elif key == "include_titles" and isinstance(value, list):
            config.include_titles = value
        elif key == "target_cities" and isinstance(value, list):
            config.target_cities = value
        elif key == "keywords" and isinstance(value, list) and value:
            config.active_keywords = value
        elif key == "location" and isinstance(value, str) and value:
            config.location = value
        elif key == "days_posted" and isinstance(value, int):
            config.days_posted = value

    _propagate_shared(config)
    return config


def _propagate_shared(config: RunConfig) -> None:
    """Push run-level ``location``/``days_posted`` into the scraper sub-configs."""
    for scraper_cfg in config.scrapers.values():
        if "location" in scraper_cfg:
            scraper_cfg["location"] = config.location
    if "linkedin" in config.scrapers:
        config.scrapers["linkedin"]["days_posted"] = config.days_posted
