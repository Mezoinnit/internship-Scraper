import asyncio
import random
from urllib.parse import urljoin, quote_plus

from utils.config import Internship
from .base import BaseScraper, _pw_lock

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class IndeedScraper(BaseScraper):
    SOURCE = "indeed"
    BASE_URL = "https://eg.indeed.com/jobs"

    async def scrape(self) -> list[Internship]:
        if not PLAYWRIGHT_AVAILABLE:
            return []
        cfg = self.config.scrapers["indeed"]
        loc = cfg["location"]
        all_jobs: list[Internship] = []
        seen_urls: set[str] = set()
        for kw in cfg["keywords"]:
            query = f"{kw} intern"
            url = f"{self.BASE_URL}?q={quote_plus(query)}&l={quote_plus(loc)}"
            jobs = await self._scrape_page(url)
            for job in jobs:
                if job.url not in seen_urls:
                    seen_urls.add(job.url)
                    all_jobs.append(job)
        return all_jobs

    async def _scrape_page(self, url: str) -> list[Internship]:
        async with _pw_lock:
            for attempt in range(3):
                try:
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        ctx = await browser.new_context(
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            viewport={"width": 1920, "height": 1080}, locale="en-US",
                        )
                        page = await ctx.new_page()
                        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        await page.wait_for_timeout(random.randint(3000, 5000))
                        data = await page.evaluate("""() => {
                            const links = document.querySelectorAll('a[href*="rc/clk"]');
                            const results = []; const seen = new Set();
                            for (const link of links) {
                                const title = link.innerText.trim();
                                const href = link.getAttribute('href') || '';
                                if (!title || !href || seen.has(href)) continue;
                                seen.add(href);
                                const card = link.closest('div[class*="card"], li, section, [data-testid]');
                                let company = '', location = 'Egypt', datePosted = '';
                                if (card) {
                                    const ce = card.querySelector('[data-testid="company-name"], .companyName');
                                    if (ce) company = ce.innerText.trim();
                                    const le = card.querySelector('[data-testid="text-location"], .companyLocation');
                                    if (le) location = le.innerText.trim();
                                    const de = card.querySelector('[data-testid="myJobsStateDate"], .date');
                                    if (de) datePosted = de.innerText.trim();
                                }
                                results.push({ title, href, company, location, datePosted });
                            }
                            return results;
                        }""")
                        await browser.close()
                        return [
                            Internship(
                                title=d["title"], company=d["company"],
                                location=d["location"] or "Egypt",
                                url=urljoin("https://eg.indeed.com", d["href"]),
                                source=self.SOURCE,
                                date_posted=d.get("datePosted", ""),
                            )
                            for d in data
                        ]
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(random.uniform(3, 5))
                    continue
        return []
