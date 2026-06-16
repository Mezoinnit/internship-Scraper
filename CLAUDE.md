# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conventions & References

- For code style, folder structure, the config/logging/scraper/route rules, and the
  "how to add a scraper / route / run-setting / SSE event" guides, see `CONVENTIONS.md`.
- When building or modifying the control UI (`templates/index.html`) or the generated
  HTML report (`utils/output.py`), consult `DESIGN_SYSTEM.md` for the dark-mode color
  tokens, typography, spacing, and component patterns.
- Accepted exceptions to the global standards (classes for the scraper hierarchy;
  self-contained inline CSS instead of Tailwind) are documented in `CONVENTIONS.md` §10.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Run (web UI — recommended)
python3 app.py          # opens http://localhost:8000

# Run (CLI — uses utils/config.py defaults directly)
python3 main.py

# Docker
docker build -t scraper . && docker run -p 8000:8000 scraper
```

No test suite or linter is configured. `ENV=production` silences `debug`/`info` logging.

## Architecture

The pipeline has three entry points that converge on the same `run_pipeline()` async function in `main.py`:

- **`app.py`** — FastAPI server. Accepts a `POST /api/run` with a `RunRequest`, spawns `run_pipeline()` as a background task, and streams progress events via SSE at `GET /api/stream/{run_id}` using an `asyncio.Queue`. Persists the last-used UI config to `data/persisted_config.json`; loads option lists from `data/{keywords,titles,cities}.json`.
- **`main.py`** — CLI entry point. Calls `run_pipeline()` directly with no user config, so `build_run_config(None)` falls back to the `utils/config.py` defaults.
- **`utils/config.py`** — Single source of truth for constants, the `Internship` and `RunConfig` dataclasses, `SCRAPER_CONFIG`, and `ProgressEvent`. `SCRAPER_CONFIG` and the title/city/keyword lists are **immutable default templates**.

### Config flow — no global mutation

Per-run settings are **not** applied by mutating globals. `build_run_config(user_config)` deep-copies the defaults into a fresh `RunConfig`, which is threaded explicitly as a parameter: `run_pipeline → scraper_cls(config) → self.config → filter_jobs(jobs, config)`. See `CONVENTIONS.md` §3 before adding any run-level setting.

### Three-phase pipeline (`main.py: run_pipeline`)

| Phase | Sources | Mechanism |
|-------|---------|-----------|
| 1 | Indeed, Wuzzuf | Playwright (headless Chrome), serialized via `_pw_lock` to avoid Chrome conflicts |
| 2 | Company Pages, Search Engine | Bing HTTP requests, rate-limited via `_bing_limiter` (semaphore = `BING_CONCURRENCY`) |
| 3 | LinkedIn | Direct HTTP with 4 regex-based fallback parsers |

Each `scrape()` runs under `asyncio.wait_for(..., timeout=PHASE_TIMEOUTS[key])`. After all phases, results pass through `filter_jobs()` in `utils/filters.py`.

### Filter pipeline (`utils/filters.py: filter_jobs(jobs, config)`)

1. **Bogus domain removal** — drops social/dictionary sites
2. **URL dedup** — exact URL match
3. **Fuzzy dedup** — same source + same company + title similarity > 0.85 (uses `difflib.SequenceMatcher`)
4. **Relevance** — `config.exclude_titles` applied to title/desc/company; the role-token regex (built once per run from `config.active_keywords`) gates titles; `config.include_titles` applied only to `source == "search"`; `source == "company"` bypasses relevance entirely
5. **Location** — Egypt evidence check; unknown locations require positive Egypt evidence; `source == "company"` bypasses location entirely

If fewer than `MIN_LOCATION_RESULTS` (5) jobs pass location filtering, the location filter is dropped and the relevance-filtered set is returned instead.

### Logging (`utils/logger.py`)

All output goes through the Logger (`debug`/`info`/`warn`/`error`) — **never `print()`**. `debug`/`info` are dev-only; `warn`/`error` always emit. Use `%`-style lazy formatting at call sites.

### Scraper base (`scrapers/base.py`)

`BaseScraper(ABC)` is constructed with a `RunConfig` and provides:
- Lazy `aiohttp.ClientSession` with randomized user agents
- `fetch()` — 3 retries (`FETCH_RETRIES`) with exponential-ish backoff; rejects bodies < `MIN_BODY_LENGTH`
- `bing_fetch()` — wraps `fetch()` with the Bing semaphore + 1–2s sleep
- `safe_fetch()` — lighter 2-attempt retry
- `_pw_lock` / `_bing_limiter` (module-level) — only one Chrome process at a time; capped Bing concurrency

### LinkedIn scraper (`scrapers/linkedin.py`)

LinkedIn's HTML structure changes frequently. The scraper tries 3 regex parsers in order (v1 → v2 → v3), then a job-view-link fallback whose titles come from the URL slug per-link. If all fail, returns an empty list for that keyword.

### Output (`utils/output.py`)

Writes two files to `output/`:
- `internships.json` — structured data
- `internships.html` — self-contained dark-mode report with JS search, source filtering, and sortable columns (no external dependencies). See `DESIGN_SYSTEM.md`.

## Key data flow

```
utils/config.py defaults
    ↓  build_run_config(user_config)  →  RunConfig (deep-copied, passed as a parameter)
    ↓
Phase 1 (Playwright)  →  list[Internship]
Phase 2 (Bing HTTP)   →  list[Internship]  ── all_jobs
Phase 3 (LinkedIn)    →  list[Internship]
    ↓
utils.filters.filter_jobs(all_jobs, config)
    ↓
utils.output.save_json / save_html → output/
```

The `Internship` dataclass (`utils/config.py`) is the single type passed between all layers. `clean_title` is a runtime-only field populated by `filter_jobs()`; it is excluded from `to_dict()` / JSON output.
