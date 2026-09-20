import asyncio
import random
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp

from utils.config import (
    USER_AGENTS, REQUEST_TIMEOUT, FETCH_RETRIES, MIN_BODY_LENGTH,
    BING_CONCURRENCY, Internship, RunConfig,
)
from utils.logger import warn


try:
    from fake_useragent import UserAgent
    _ua = UserAgent()

    def _random_ua() -> str:
        try:
            return _ua.random
        except Exception:
            return random.choice(USER_AGENTS)
except ImportError:
    def _random_ua() -> str:
        return random.choice(USER_AGENTS)


# Module-level coordination primitives shared across all scraper instances:
#   _pw_lock      — only one Playwright/Chrome process runs at a time.
#   _bing_limiter — caps concurrent Bing requests to avoid rate-limiting.
_pw_lock = asyncio.Lock()
_bing_limiter = asyncio.Semaphore(BING_CONCURRENCY)


class BaseScraper(ABC):
    SOURCE: str = ""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers())
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
        }

    async def fetch(self, url: str, timeout: int = REQUEST_TIMEOUT,
                    headers: Optional[dict] = None) -> Optional[str]:
        session = await self._get_session()
        for attempt in range(FETCH_RETRIES):
            try:
                async with session.get(url, timeout=timeout, headers=headers,
                                       allow_redirects=True) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if len(text) > MIN_BODY_LENGTH:
                            return text
                        warn("fetch %s: body too short (%d chars)", url, len(text))
                    else:
                        warn("fetch %s: HTTP %d", url, resp.status)
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                warn("fetch %s attempt %d/%d failed: %s", url, attempt + 1, FETCH_RETRIES, e)
            if attempt < FETCH_RETRIES - 1:
                await asyncio.sleep((attempt + 1) * random.uniform(2, 4))
        return None

    async def bing_fetch(self, url: str, timeout: int = 25) -> Optional[str]:
        async with _bing_limiter:
            html = await self.fetch(url, timeout=timeout)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            return html

    async def safe_fetch(self, url: str, headers: Optional[dict] = None,
                         timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
        for _ in range(2):
            html = await self.fetch(url, timeout=timeout, headers=headers)
            if html:
                return html
            await asyncio.sleep(random.uniform(2, 3))
        return None

    @abstractmethod
    async def scrape(self) -> list[Internship]:
        ...
