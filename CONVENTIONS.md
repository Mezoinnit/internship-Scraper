# CONVENTIONS.md

How this codebase is actually written. Read this before adding or changing code so
your work stays consistent with what's already here. These rules are derived from
the real code, not generic best practice.

The project is a Python 3.12 async web scraper: FastAPI UI + CLI, Playwright +
aiohttp scrapers, regex/BeautifulSoup parsing, self-contained HTML report output.

---

## 1. Folder structure

```
app.py                 FastAPI server: routes, SSE streaming, config persistence
main.py                Pipeline orchestrator (run_pipeline) + CLI entry point
utils/
  config.py            Single source of truth: constants, dataclasses, SCRAPER_CONFIG, ProgressEvent
  logger.py            The only logging entry point (debug/info/warn/error)
  filters.py           filter_jobs pipeline: dedup, relevance, location, staleness
  text.py              Shared text helpers (company extraction from titles)
  output.py            JSON + self-contained HTML report writers
  search_engine.py     SearchEngineScraper (Bing organic results) — a scraper that lives in utils/
scrapers/
  __init__.py          Barrel: re-exports the board/company scrapers
  base.py              BaseScraper (ABC) + _pw_lock + _bing_limiter primitives
  indeed.py            Playwright scraper
  wuzzuf.py            Playwright scraper (HTTP fallback)
  linkedin.py          HTTP scraper with 4 regex fallback parsers
  company_pages.py     Bing-backed scraper
templates/index.html   Dark-mode control UI (single self-contained file)
data/                  Option data: keywords.json, titles.json, cities.json (+ persisted_config.json, gitignored)
output/                Generated reports (gitignored)
```

Rules:
- **Shared helpers go in `utils/`.** When logic is needed by 2+ modules (e.g. company
  extraction was once duplicated in `filters.py` and `search_engine.py`), extract it
  into a `utils/` module — see `utils/text.py`.
- **Constants and magic numbers go in `utils/config.py`**, never inline at call sites.
  Example: `BING_CONCURRENCY = 5`, `MIN_LOCATION_RESULTS = 5`, `STALE_AFTER_DAYS = 30`,
  `PHASE_TIMEOUTS`. If a number has meaning, name it there with a comment.
- `utils/search_engine.py` lives under `utils/` (not `scrapers/`) but is a `BaseScraper`
  subclass; it's imported directly in `main.py`, not via the `scrapers/__init__.py` barrel.

---

## 2. Naming & style

- **Modules / files:** `snake_case.py` (`company_pages.py`, `search_engine.py`).
- **Classes:** `PascalCase` (`IndeedScraper`, `RunConfig`, `BaseScraper`, `Internship`).
- **Functions / variables:** `snake_case` (`run_pipeline`, `filter_jobs`, `build_run_config`).
- **Constants:** `SCREAMING_SNAKE_CASE` at module top (`SCRAPER_CONFIG`, `PHASE_TIMEOUTS`,
  `USER_AGENTS`, `EXCLUDE_TITLES`).
- **Private/internal helpers:** leading underscore (`_emit`, `_phase`, `_run`,
  `_propagate_shared`, `_build_role_pattern`, `_parse`). Module-level shared primitives
  too: `_pw_lock`, `_bing_limiter`.
- **Class constants** for scraper identity: `SOURCE` and `BASE_URL` as class attributes
  (`SOURCE = "indeed"`, `BASE_URL = "https://eg.indeed.com/jobs"`). The `source` string
  on each `Internship` MUST match the scraper's `SOURCE`, because filters branch on it
  (`source == "company"`, `source == "search"`).
- **Type hints on every function signature**, including return types. Use
  `Optional[...]`, `list[...]`, `dict[str, dict]`, `list[Internship]`. Prefer the
  builtin-generic `X | None` style for new code.
- **Docstrings** are triple-quoted and explain *why*, not *what* — see the module
  docstrings in `logger.py`, `text.py` and the inline comments in `filters.py`
  ("Built once per run (not per job)"). Match this: comment the non-obvious decision.
- No `print()` anywhere (see logging rule below).

### Import ordering

Three groups, blank-line separated, stdlib → third-party → local, as in `filters.py`:

```python
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from .config import Internship, RunConfig, ROLE_GROUPS
from .text import extract_company_from_title, SUFFIX_COMPANY_PATTERNS
```

- Inside `utils/`, import siblings with **relative** imports (`from .config import ...`).
- Inside `scrapers/`, import the base with relative (`from .base import BaseScraper, _pw_lock`)
  but import config/utils with **absolute** imports (`from utils.config import Internship`).
- `app.py` and `main.py` use absolute imports and do `sys.path.insert(0, ...)` at the top
  so the project root is importable; keep that line when adding new top-level entry points.
- **Scraper imports in `main.py` are deferred inside `run_pipeline`** (imported at the
  point of use, not module top). This is intentional: a missing optional dependency
  (Playwright) only breaks the scrapers that need it, not module import. Keep new
  scraper imports deferred the same way.

---

## 3. The config flow — never mutate module globals

This is the single most important rule. The old design mutated `SCRAPER_CONFIG`
globally at runtime; that has been deliberately removed.

- `SCRAPER_CONFIG`, `EXCLUDE_TITLES`, `INCLUDE_TITLES`, `TARGET_CITIES`, `KEYWORDS` in
  `utils/config.py` are **immutable DEFAULT templates**. Treat them as read-only.
- Per-run settings live in a `RunConfig` dataclass, built fresh by
  `build_run_config(user_config)` which **deep-copies** the defaults
  (`RunConfig.default()` uses `copy.deepcopy(SCRAPER_CONFIG)`).
- `RunConfig` is threaded **explicitly as a parameter** through the whole pipeline:
  `run_pipeline` → `scraper_cls(config)` → `self.config` → `filter_jobs(jobs, config)`.
  No layer reaches back to module globals for run state.

**To add a new run-level setting (e.g. a new toggle or limit):**
1. Add a field to the `RunConfig` dataclass (with a default).
2. Set it in `RunConfig.default()`.
3. Parse it from `user_config` in `build_run_config` (with `isinstance` validation —
   unknown/invalid keys are ignored).
4. If scrapers need it pushed into their sub-config, add it to `_propagate_shared`
   (that's how `location`/`days_posted` reach the per-scraper dicts).
5. If it comes from the UI, add it to `RunRequest`/`ConfigPayload` in `app.py` and to
   `_to_scraper_config`.

**Never** introduce run state via `global` rebinding or by mutating a `config.py` constant.

---

## 4. Logging — use `utils/logger.py`, never `print`

- The Logger wraps stdlib `logging`. Four functions: `debug`, `info`, `warn`, `error`.
- `debug`/`info` are **silenced in production** (when `ENV` is `prod`/`production`);
  `warn`/`error` always emit. Import only what you use:
  `from utils.logger import info, error`.
- Use **`%`-style lazy formatting**, not f-strings, at call sites:
  `info("  %s: %d results", name, len(jobs))` — not `info(f"...")`. This matches every
  existing call and defers string building until the level is actually emitted.
- `warn` for recoverable problems (short body, HTTP non-200, corrupt persisted config);
  `error` for failures that abort a unit of work (scraper timeout/exception, failed run).
- When telemetry is added later, only `logger.py` changes — keep all logging behind it.

---

## 5. Scrapers — the BaseScraper contract

Yes, this project uses **classes** for scrapers. This is an intentional, accepted
exception to a "functional only" preference (see §10). The hierarchy gives a shared
session/fetch/retry surface and a uniform `scrape()` entry point; do not "refactor"
it into free functions.

Every scraper:
- Subclasses `BaseScraper(ABC)` and is constructed with a `RunConfig`
  (`scraper_cls(config)` — `__init__` is inherited from the base; don't override unless
  you also call `super().__init__(config)`).
- Sets class attributes `SOURCE` (required — it's the `Internship.source` value) and
  usually `BASE_URL`.
- Implements `async def scrape(self) -> list[Internship]`.
- Reads its settings from `self.config.scrapers["<name>"]` and shared run values from
  `self.config` (`self.config.target_cities`, etc.).
- Returns a `list[Internship]`; never raises out of `scrape()` for an expected failure —
  the orchestrator's `_run` catches exceptions, but scrapers should degrade gracefully
  (return `[]` for a failed keyword/page, like LinkedIn's fallback chain).

Fetching:
- Use `self.fetch(url)` for plain HTTP (3 retries, exponential-ish backoff, rejects
  bodies < `MIN_BODY_LENGTH`).
- Use `self.bing_fetch(url)` for **any Bing / rate-limited HTTP** — it holds the
  `_bing_limiter` semaphore (`BING_CONCURRENCY = 5`) and sleeps 1–2s. All Bing queries
  go through this (`company_pages.py`, `search_engine.py`).
- Use `self.safe_fetch(url)` for a lighter 2-attempt retry (LinkedIn, Wuzzuf fallback).
- Wrap **all Playwright / Chrome usage in `async with _pw_lock:`** so only one Chrome
  process runs at a time (`indeed.py`, `wuzzuf._scrape_pw`). Optional Playwright is
  guarded with `try: import ... PLAYWRIGHT_AVAILABLE = True / except ImportError`.

**To add a new scraper, do all of these:**
1. Create `scrapers/<name>.py` with a `BaseScraper` subclass and a unique `SOURCE`.
2. Add a `"<name>"` entry to `SCRAPER_CONFIG` in `utils/config.py` (with `"enabled": True`
   and its keywords/settings).
3. Add a `"<name>"` entry to `PHASE_TIMEOUTS` (overall `scrape()` timeout in seconds).
4. Register it in `scrapers/__init__.py` (`__all__` + import) — unless, like
   `SearchEngineScraper`, it lives under `utils/` and is imported directly.
5. Wire an `all_jobs.extend(await _phase("<name>", "Display Name", ScraperCls))` call
   into the correct phase in `run_pipeline` (Phase 1 Playwright, Phase 2 Bing, Phase 3 HTTP).
6. If the UI should toggle it, it appears automatically: `_defaults()` derives `sources`
   from `SCRAPER_CONFIG.items()`.

---

## 6. The `Internship` dataclass — the single inter-layer type

- `Internship` (`utils/config.py`) is the only object passed between scrapers, filters,
  and output. Don't introduce a parallel job type.
- `clean_title` and `is_stale` are **runtime-only** fields populated by `filter_jobs`.
- `to_dict()` deliberately drops `clean_title` from JSON output. If you add a runtime-only
  field, pop it in `to_dict()` the same way; if you add a real output field, leave it in.

---

## 7. SSE progress events — keep the three sides in sync

`ProgressEvent` (a constants holder class in `utils/config.py`) is the single source of
truth for SSE `type` strings. Three parties must agree on these literals:

- **Producer:** `main.py` emits them via `_emit(queue, ProgressEvent.PHASE_DONE, ...)`.
- **Relay:** `app.py` re-emits `ProgressEvent.ERROR` on run failure.
- **Consumer:** `templates/index.html` switches on `m.type === 'phase_done'` etc.

Current contract: `message`, `phase_done` (`source`, `count`), `phase_error`
(`source`, `error`), `phase_skip` (`source`), `done` (`total`, `removed`, `json_path`,
`html_path`, `elapsed`), `error` (`text`). A `None` queue item ends the stream
(`data: [DONE]`).

**To add or change an event:** add/rename the constant in `ProgressEvent`, update the
emitter in `main.py`, and update the `m.type === '...'` branch in `index.html` — all three
in the same change. The string literals in the template must equal the constant values.

---

## 8. API routes (app.py)

- Keep handlers **thin**: validate input, call into `main.run_pipeline` / helpers, return
  a response. No business logic in the route — heavy work lives in `main.py` / `utils/`.
- **Validate request bodies with a Pydantic model** (`RunRequest`, `ConfigPayload`).
  Defaults pull from config constants (`location: str = DEFAULT_LOCATION`).
- **Return a concrete `Response` subclass** (`JSONResponse`, `HTMLResponse`,
  `FileResponse`, `StreamingResponse`) — and annotate the handler with that single type.
  Do **not** annotate a route return type with a union (e.g. `-> JSONResponse | FileResponse`)
  — FastAPI tries to build a `response_model` from it and breaks. Streaming/file routes are
  left unannotated on purpose (`async def stream(run_id: str):`). Follow that.
- Long-running work runs as a background task (`asyncio.create_task(_execute_run(...))`)
  and reports via the SSE queue, never by blocking the request.
- File-serving routes must guard against path traversal (see `output_file`: resolve and
  verify the target stays under `OUTPUT_DIR`).

---

## 9. Error handling

- Every scraper `scrape()` is run under `asyncio.wait_for(..., timeout=PHASE_TIMEOUTS[key])`
  inside `_run`, which catches `asyncio.TimeoutError` and `Exception`, logs via the Logger,
  emits a `phase_error` event, and always `await scraper.close()` in `finally`. New
  orchestration must preserve: timeout, catch, log, emit, close.
- Inside scrapers, catch narrow exceptions where possible (`aiohttp.ClientError`,
  `asyncio.TimeoutError` in `base.fetch`) and degrade to `[]` rather than propagating.
  Do not write bare `except Exception: pass` — log via the Logger before degrading.
- File / JSON loading catches `(OSError, json.JSONDecodeError)` and either re-raises with
  context (`_load_options`) or warns and falls back (`_load_config`).
- `app._execute_run` wraps the whole run, emits `ProgressEvent.ERROR` with the message on
  failure, and always closes the stream (`queue.put_nowait(None)`).

---

## 10. Accepted project-level exceptions

These override the global "Ibrahim standards" on purpose. Do not "fix" them:
- **Classes are used for the scraper hierarchy** (`BaseScraper` + subclasses). This is the
  one place OOP is correct here; everything else is functions/modules.
- **The HTML report (`utils/output.py`) and the UI (`templates/index.html`) use inline
  `<style>` / self-contained CSS**, not Tailwind. There is no build step and the report
  must be a single portable file with zero external dependencies. Keep styling inline and
  driven by the CSS custom-property tokens in `DESIGN_SYSTEM.md`.

---

## 11. Testing

There is **no test suite and no linter configured** yet. If you add tests:
- Pure, deterministic functions are the natural first targets: `utils/text.py`
  (`extract_company_from_title`), `utils/filters.py` (`normalize`, `similarity`,
  `_parse_date`, `_build_role_pattern`, `deduplicate`), `utils/config.py`
  (`build_run_config` override/validation behavior).
- Prefer `pytest`; name files `test_*.py`. Keep network/Playwright out of unit tests —
  test parsers by feeding saved HTML strings to `_parse` methods.

---

## 12. Tooling & ops

- Python 3.12 (`Dockerfile` base `python:3.12-slim`). Dependencies in `requirements.txt`
  with `>=` lower bounds; install Playwright Chromium separately (`playwright install chromium`).
- `.gitignore` excludes `output/`, `data/persisted_config.json`, `__pycache__/`, venvs.
  Never commit generated reports or persisted config.
- The container runs as a non-root `scraper` user. `PORT` env var overrides the default 8000;
  `ENV=production` silences `debug`/`info` logging.
