import asyncio
import re
from urllib.parse import quote_plus

from utils.config import Internship
from .base import BaseScraper


class CompanyPagesScraper(BaseScraper):
    SOURCE = "company"

    async def scrape(self) -> list[Internship]:
        cfg = self.config.scrapers["company_pages"]
        templates = cfg["query_templates"]
        targets = cfg["companies"] + cfg["universities"]

        async def search_target(name: str) -> list[Internship]:
            queries = [t.format(name=name) for t in templates]
            jobs = []
            for q in queries:
                url = f"https://www.bing.com/search?q={quote_plus(q)}&mkt=en-US&cc=EG"
                html = await self.bing_fetch(url)
                if not html:
                    continue
                jobs.extend(self._parse(html, name))
            return jobs

        tasks = [search_target(name) for name in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        jobs: list[Internship] = []
        for r in results:
            if isinstance(r, list):
                jobs.extend(r)
        return jobs

    SKIP_DOMAINS = ("linkedin.com/jobs", "wuzzuf", "indeed", "glassdoor")

    def _parse(self, html: str, name: str) -> list[Internship]:
        jobs: list[Internship] = []
        seen_urls: set[str] = set()
        for m in re.finditer(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL):
            # The result anchor precedes its <cite>; read the real href + title
            # from it rather than reconstructing a lossy URL from the cite text.
            window_start = max(m.start() - 200, 0)
            anchor = re.search(
                r'<a[^>]*href="(https?://(?!www\.bing\.com)[^"]*)"[^>]*>(.*?)</a>',
                html[window_start:m.start() + 50], re.DOTALL
            )
            if not anchor:
                continue
            url = anchor.group(1)
            if any(domain in url for domain in self.SKIP_DOMAINS):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = re.sub(r'<[^>]+>', '', anchor.group(2)).strip() or name
            jobs.append(Internship(
                title=f"{title} — {name}", company=name,
                location="Egypt", url=url, source=self.SOURCE,
            ))
        return jobs
