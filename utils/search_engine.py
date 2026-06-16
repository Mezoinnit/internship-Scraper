import re
from urllib.parse import urlparse, quote_plus

from .config import Internship
from .text import (
    extract_company_from_title,
    SUFFIX_COMPANY_PATTERNS,
    PREFIX_COMPANY_PATTERN,
)
from scrapers.base import BaseScraper

BOARD_DOMAINS = {"linkedin.com", "wuzzuf.net", "indeed.com",
    "eg.indeed.com", "glassdoor.com", "tanqeeb.com", "bayt.com",
    "naukrigulf.com", "gulftalent.com", "monster.com",
    "careerjet.com", "jobstreet.com", "jooble.org", "bing.com"}

_SEARCH_PATTERNS = SUFFIX_COMPANY_PATTERNS + [PREFIX_COMPANY_PATTERN]


class SearchEngineScraper(BaseScraper):
    SOURCE = "search"

    async def scrape(self) -> list[Internship]:
        cfg = self.config.scrapers["search_engine"]
        jobs: list[Internship] = []
        for kw in cfg["keywords"]:
            query = quote_plus(f"{kw} internship Egypt 2026")
            url = f"https://www.bing.com/search?q={query}&mkt=en-US&cc=EG"
            html = await self.bing_fetch(url)
            if not html:
                continue
            jobs.extend(self._parse(html))
        return jobs

    def _parse(self, html: str) -> list[Internship]:
        jobs: list[Internship] = []
        seen: set[str] = set()

        # Read each organic result from its real result anchor, so the URL is
        # the actual href (not a lossy reconstruction of the <cite> breadcrumb).
        pattern = re.compile(
            r'<h2[^>]*>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )

        for m in pattern.finditer(html):
            url = m.group(1)
            domain = urlparse(url).netloc.lower().removeprefix("www.")
            if any(board in domain for board in BOARD_DOMAINS):
                continue
            if url in seen:
                continue
            seen.add(url)

            title = re.sub(r'<[^>]+>', '', m.group(2))
            title = re.sub(r'\s+', ' ', title).strip()
            title = re.sub(r'\.{2,}$', '', title).strip()  # drop trailing ellipsis
            if not title:
                continue

            desc = self._extract_description(html, m.end())

            location = ""
            text_lower = f"{title} {desc}".lower()
            if "egypt" in text_lower or "مصر" in text_lower:
                location = "Egypt"
            for city in self.config.target_cities:
                if city in text_lower:
                    location = f"{city.title()}, Egypt"
                    break

            company = extract_company_from_title(title, _SEARCH_PATTERNS) or ""
            if company:
                title = re.sub(r'\s+[-–|]\s+.*$', '', title).strip()

            jobs.append(Internship(
                title=title, company=company, location=location,
                url=url, source=self.SOURCE, description=desc,
            ))

        return jobs

    @staticmethod
    def _extract_description(html: str, start: int) -> str:
        window = html[start:min(start + 600, len(html))]
        match = re.search(
            r'<p[^>]*class="[^"]*b_lineclamp2[^"]*"[^>]*>(.*?)</p>',
            window, re.DOTALL,
        )
        if not match:
            return ""
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', match.group(1))).strip()
