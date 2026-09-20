import asyncio
import json
import os
import sys
import webbrowser
from functools import lru_cache
from pathlib import Path
from threading import Timer
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

from main import run_pipeline
import utils.config as config
from utils.config import DEFAULT_LOCATION, DEFAULT_DAYS_POSTED, ProgressEvent
from utils.logger import info, warn, error

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
PERSISTED_CONFIG = DATA_DIR / "persisted_config.json"
TEMPLATES = BASE / "templates"

# How long a finished run's event queue is retained for a late-connecting
# stream before it is dropped, so `runs` cannot grow without bound.
RUN_RETENTION_SECONDS = 300

app = FastAPI(title="Egypt Internships Scraper")
runs: dict[str, asyncio.Queue] = {}


class RunRequest(BaseModel):
    keywords: list[str]
    exclude_titles: list[str]
    include_titles: list[str]
    target_cities: list[str]
    sources: dict[str, bool]
    location: str = DEFAULT_LOCATION
    days_posted: int = DEFAULT_DAYS_POSTED


class ConfigPayload(BaseModel):
    keywords: list[str] = []
    exclude_titles: list[str] = []
    include_titles: list[str] = []
    target_cities: list[str] = []
    sources: dict[str, bool] = {}
    location: str = DEFAULT_LOCATION
    days_posted: int = DEFAULT_DAYS_POSTED


@lru_cache(maxsize=1)
def _load_options() -> dict:
    try:
        keywords = json.loads((DATA_DIR / "keywords.json").read_text(encoding="utf-8"))
        titles = json.loads((DATA_DIR / "titles.json").read_text(encoding="utf-8"))
        cities = json.loads((DATA_DIR / "cities.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to load option data files from {DATA_DIR}: {e}") from e
    return {"keywords": keywords, "titles": titles, "cities": cities}


def _expand_bilingual(en_values: list[str], items: list[dict]) -> list[str]:
    lookup = {item["en"]: item.get("ar", "") for item in items}
    result: list[str] = []
    seen: set[str] = set()
    for val in en_values:
        for token in (val, lookup.get(val, "")):
            if token and token not in seen:
                seen.add(token)
                result.append(token)
    return result


def _defaults() -> dict:
    opts = _load_options()
    return {
        "keywords":       [i["en"] for i in opts["keywords"] if i.get("default")],
        "exclude_titles": [i["en"] for i in opts["titles"]   if i.get("default_exclude")],
        "include_titles": [i["en"] for i in opts["titles"]   if i.get("default_include")],
        "target_cities":  [i["en"] for i in opts["cities"]   if i.get("default")],
        "sources": {k: v.get("enabled", True) for k, v in config.SCRAPER_CONFIG.items()},
        "location": DEFAULT_LOCATION,
        "days_posted": DEFAULT_DAYS_POSTED,
    }


def _load_config() -> dict:
    if PERSISTED_CONFIG.exists():
        try:
            stored = json.loads(PERSISTED_CONFIG.read_text())
            merged = _defaults()
            merged.update(stored)
            return merged
        except (OSError, json.JSONDecodeError) as e:
            warn("ignoring corrupt persisted config %s: %s", PERSISTED_CONFIG, e)
    return _defaults()


def _save_config(data: dict) -> None:
    keys = ("keywords", "exclude_titles", "include_titles",
            "target_cities", "sources", "location", "days_posted")
    safe = {k: data[k] for k in keys if k in data}
    PERSISTED_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    PERSISTED_CONFIG.write_text(json.dumps(safe, indent=2, ensure_ascii=False))


def _to_scraper_config(req: RunRequest) -> dict:
    opts = _load_options()
    cfg: dict = {}
    for source, enabled in req.sources.items():
        if source in config.SCRAPER_CONFIG:
            cfg[source] = {**config.SCRAPER_CONFIG[source], "enabled": enabled}
    cfg["keywords"]       = _expand_bilingual(req.keywords, opts["keywords"])
    cfg["exclude_titles"] = _expand_bilingual(req.exclude_titles, opts["titles"])
    cfg["include_titles"] = _expand_bilingual(req.include_titles, opts["titles"])
    cfg["target_cities"]  = _expand_bilingual(req.target_cities, opts["cities"])
    cfg["location"]       = req.location
    cfg["days_posted"]    = req.days_posted
    return cfg


async def _execute_run(req: RunRequest, queue: asyncio.Queue, run_id: str) -> None:
    try:
        await run_pipeline(user_config=_to_scraper_config(req), progress_queue=queue)
    except Exception as e:
        error("run %s failed: %s", run_id, e)
        queue.put_nowait({"type": ProgressEvent.ERROR, "text": str(e)})
    finally:
        queue.put_nowait(None)
        await asyncio.sleep(RUN_RETENTION_SECONDS)
        runs.pop(run_id, None)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = TEMPLATES / "index.html"
    if not html.exists():
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)
    return HTMLResponse(html.read_text(encoding="utf-8"))


@app.get("/api/options")
async def get_options() -> JSONResponse:
    return JSONResponse(_load_options())


@app.get("/api/defaults")
async def get_defaults() -> JSONResponse:
    return JSONResponse(_defaults())


@app.get("/api/config")
async def get_config() -> JSONResponse:
    return JSONResponse(_load_config())


@app.post("/api/config")
async def post_config(payload: ConfigPayload) -> JSONResponse:
    _save_config(payload.model_dump())
    return JSONResponse({"ok": True})


@app.post("/api/run")
async def start_run(req: RunRequest) -> JSONResponse:
    _save_config(req.model_dump())
    run_id = str(uuid4())[:8]
    queue: asyncio.Queue = asyncio.Queue()
    runs[run_id] = queue
    asyncio.create_task(_execute_run(req, queue, run_id))
    return JSONResponse({"run_id": run_id})


@app.get("/api/stream/{run_id}")
async def stream(run_id: str):
    queue = runs.get(run_id)
    if queue is None:
        return JSONResponse({"error": "not found"}, status_code=404)

    async def event_gen():
        try:
            while True:
                msg = await queue.get()
                if msg is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
        finally:
            runs.pop(run_id, None)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/output/{filename:path}")
async def output_file(filename: str):
    base = config.OUTPUT_DIR.resolve()
    target = (base / filename).resolve()
    # Reject anything that escapes OUTPUT_DIR (path traversal / absolute paths).
    if target != base and base not in target.parents:
        return JSONResponse({"error": "not found"}, status_code=404)
    if not target.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(target)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    url = f"http://localhost:{port}"

    info("Egypt Internships Scraper UI — %s", url)

    Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="0.0.0.0", port=port)
