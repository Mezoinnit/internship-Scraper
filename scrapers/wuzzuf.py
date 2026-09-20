import asyncio
import random
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup

from utils.config import Internship
from .base import BaseScraper, _pw_lock

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class WuzzufScraper(BaseScraper):
    SOURCE = "wuzzuf"
    BASE_URL = "https://wuzzuf.net/search/jobs/"

    async def scrape(self) -> list[Internship]:
        cfg = self.config.scrapers["wuzzuf"]
        loc = cfg["location"]
        all_jobs: list[Internship] = []
        seen_urls: set[str] = set()
        for kw in cfg["keywords"]:
            query = f"{kw} intern"
            url = f"{self.BASE_URL}?q={quote_plus(query)}&location={quote_plus(loc)}"
            if PLAYWRIGHT_AVAILABLE:
                jobs = await self._scrape_pw(url)
            else:
                html = await self.safe_fetch(url)
                jobs = self._parse(html) if html else []
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
        return all_jobs

    async def _scrape_pw(self, url: str) -> list[Internship]:
        async with _pw_lock:
            for attempt in range(3):
                try:
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        ctx = await browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            viewport={"width": 1920, "height": 1080},
                        )
                        page = await ctx.new_page()
                        await page.goto(url, timeout=25000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)
                        html = await page.content()
                        await browser.close()
                        return self._parse(html)
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(random.uniform(2, 4))
                    continue
        return []

    def _parse(self, html: str) -> list[Internship]:
        jobs = []
        soup = BeautifulSoup(html, "html.parser")
        seen = set()
        for card in soup.select("div.css-pkv5jc"):
            try:
                link = card.select_one("a.css-o171kl")
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if href and href.startswith("/"):
                    href = urljoin("https://wuzzuf.net", href)
                if not href or href in seen:
                    continue
                seen.add(href)
                detail = card.select_one("div.css-1k5ee52")
                company, location = "", "Egypt"
                if detail:
                    ce = detail.select_one("a.css-ipsyv7")
                    if ce:
                        company = ce.get_text(strip=True).rstrip(" -")
                    le = detail.select_one("span.css-16x61xq")
                    if le:
                        location = le.get_text(strip=True)
                date_posted = ""
                date_el = card.select_one("div.css-4c4ojb, time, [class*='date']")
                if date_el:
                    date_posted = date_el.get_text(strip=True)
                jobs.append(Internship(
                    title=title, company=company, location=location,
                    url=href, source=self.SOURCE, date_posted=date_posted,
                ))
            except Exception:
                continue
        return jobs
