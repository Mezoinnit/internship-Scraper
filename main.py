import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import (
    OUTPUT_DIR, Internship, RunConfig, build_run_config,
    ProgressEvent, PHASE_TIMEOUTS,
)
from utils.filters import filter_jobs
from utils.output import save_json, save_html
from utils.logger import info, error


def _emit(queue: Optional[asyncio.Queue], kind: Optional[str], **payload: Any) -> None:
    """Push a progress event onto the SSE queue, if there is one."""
    if kind is None or queue is None:
        return
    queue.put_nowait({"type": kind, **payload})


async def run_pipeline(user_config: Optional[dict[str, Any]] = None,
                       progress_queue: Optional[asyncio.Queue] = None) -> list[Internship]:
    config = build_run_config(user_config)
    start = time.time()
    OUTPUT_DIR.mkdir(exist_ok=True)

    async def _run(name: str, scraper, timeout: int) -> list[Internship]:
        try:
            jobs = await asyncio.wait_for(scraper.scrape(), timeout=timeout)
            info("  %s: %d results", name, len(jobs))
            _emit(progress_queue, ProgressEvent.PHASE_DONE, source=name, count=len(jobs))
            return jobs
        except asyncio.TimeoutError:
            error("  %s: TIMEOUT after %ds", name, timeout)
            _emit(progress_queue, ProgressEvent.PHASE_ERROR, source=name, error="timeout")
            return []
        except Exception as e:
            error("  %s: ERROR — %s", name, e)
            _emit(progress_queue, ProgressEvent.PHASE_ERROR, source=name, error=str(e))
            return []
        finally:
            await scraper.close()

    async def _phase(cfg_key: str, name: str, scraper_cls) -> list[Internship]:
        if not config.scrapers.get(cfg_key, {}).get("enabled", True):
            info("  %s: skipped (disabled)", name)
            _emit(progress_queue, ProgressEvent.PHASE_SKIP, source=name)
            return []
        return await _run(name, scraper_cls(config), PHASE_TIMEOUTS[cfg_key])

    all_jobs: list[Internship] = []

    # Scraper imports are deferred so an optional dependency (Playwright) that is
    # missing only affects the scrapers that need it, not module import.
    msg = "Phase 1 — Playwright scrapers (serialized, retry-enabled)"
    info(msg)
    _emit(progress_queue, ProgressEvent.MESSAGE, text=msg)
    from scrapers.indeed import IndeedScraper
    from scrapers.wuzzuf import WuzzufScraper

    all_jobs.extend(await _phase("indeed", "Indeed", IndeedScraper))
    all_jobs.extend(await _phase("wuzzuf", "Wuzzuf", WuzzufScraper))

    msg = "Phase 2 — Bing-backed scrapers (rate-limited)"
    info(msg)
    _emit(progress_queue, ProgressEvent.MESSAGE, text=msg)
    from scrapers.company_pages import CompanyPagesScraper
    from utils.search_engine import SearchEngineScraper

    all_jobs.extend(await _phase("company_pages", "Company Pages", CompanyPagesScraper))
    all_jobs.extend(await _phase("search_engine", "Search Engine", SearchEngineScraper))

    msg = "Phase 3 — HTTP scrapers"
    info(msg)
    _emit(progress_queue, ProgressEvent.MESSAGE, text=msg)
    from scrapers.linkedin import LinkedInScraper

    all_jobs.extend(await _phase("linkedin", "LinkedIn", LinkedInScraper))

    msg = f"Total raw results: {len(all_jobs)}"
    info(msg)
    _emit(progress_queue, ProgressEvent.MESSAGE, text=msg)

    before = len(all_jobs)
    filtered = filter_jobs(all_jobs, config)
    removed = before - len(filtered)
    info("After dedup/filter: %d  (removed %d)", len(filtered), removed)

    elapsed = time.time() - start

    if filtered:
        json_path = save_json(filtered, "internships")
        html_path = save_html(filtered, "internships")
        info("Exported to %s", OUTPUT_DIR / "internships.json")
        info("Exported to %s", OUTPUT_DIR / "internships.html")
        _emit(progress_queue, ProgressEvent.DONE,
              total=len(filtered), removed=removed,
              json_path=json_path, html_path=html_path, elapsed=round(elapsed, 1))
    else:
        info("No results found.")
        _emit(progress_queue, ProgressEvent.DONE,
              total=0, removed=removed,
              json_path=None, html_path=None, elapsed=round(elapsed, 1))

    info("Total time: %.1fs", elapsed)
    _emit(progress_queue, None)
    return filtered


async def main() -> None:
    info("Egypt Internships Scraper")
    info("=" * 40)
    await run_pipeline()


if __name__ == "__main__":
    asyncio.run(main())
