import asyncio
import re
import random

from utils.config import Internship
from .base import BaseScraper


class LinkedInScraper(BaseScraper):
    SOURCE = "linkedin"
    BASE_URL = "https://www.linkedin.com/jobs/search"

    def _is_valid_title(self, t: str) -> bool:
        if not t or t.lower() in {"linkedin", "clear text", "skip to main content", ""}:
            return False
        if len(t) > 80:
            return False
        low = t.lower()
        noise = ["sign in", "join now", "past week", "past month",
                  "past 24 hours", "any time", "done company",
                  "done experience", "clear text", "expand search"]
        for phrase in noise:
            if phrase in low:
                return False
        if re.search(r'\(\d+\)', t):
            return False
        return True

    async def scrape(self) -> list[Internship]:
        cfg = self.config.scrapers["linkedin"]
        locations_param = cfg["location"]
        days = cfg["days_posted"]
        exp = ",".join(str(e) for e in cfg["experience_level"])
        sort = cfg["sort_by"]

        jobs = []
        # dict.fromkeys dedupes while preserving order (deterministic across runs).
        all_kw = list(dict.fromkeys(cfg["keywords"] + cfg["industry_keywords"]))
        for kw in all_kw:
            params = {
                "keywords": kw, "location": locations_param,
                "f_TPR": f"r{days * 86400}", "f_E": exp,
                "sortBy": sort,
            }
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{self.BASE_URL}?{qs}"
            chunk = await self._fetch_jobs(url)
            jobs.extend(chunk)
            await asyncio.sleep(random.uniform(2, 4))
        return jobs

    def _clean_title(self, raw: str) -> str:
        t = re.sub(r'<[^>]+>', '', raw).strip()
        t = re.sub(r'\s+', ' ', t)
        t = re.sub(r'\s*\d{7,}\s*$', '', t)
        return t

    def _try_parse_v1(self, html: str) -> list[dict] | None:
        # Parse each job card as a self-contained block so href, title, company,
        # and location are read from the SAME card — never paired by global index
        # (which misaligns because sr-only spans appear all over the page).
        blocks = re.split(r'<li[^>]*>', html)
        results = []
        for block in blocks:
            m_href = re.search(r'base-card__full-link[^>]*href="([^"]+)"', block)
            if not m_href:
                continue
            href = m_href.group(1)

            m_title = re.search(r'sr-only[^>]*>\s*(.*?)\s*</span>', block, re.DOTALL)
            if not m_title:
                m_title = re.search(r'base-search-card__title[^>]*>\s*(.*?)\s*</', block, re.DOTALL)
            title = self._clean_title(m_title.group(1)) if m_title else ""

            m_company = re.search(
                r'base-search-card__subtitle[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.DOTALL)
            company = ""
            if m_company:
                company = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m_company.group(1))).strip()

            m_loc = re.search(r'job-search-card__location[^>]*>(.*?)</span>', block, re.DOTALL)
            location = ""
            if m_loc:
                location = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m_loc.group(1))).strip()

            results.append(dict(href=href, title=title, company=company, location=location))
        return results if results else None

    def _try_parse_v2(self, html: str) -> list[dict] | None:
        blocks = re.findall(
            r'<a[^>]*class="[^"]*job-card[^"]*"[^>]*href="([^"]+)"[^>]*>.*?'
            r'<span[^>]*class="[^"]*job-title[^"]*"[^>]*>(.*?)</span>.*?'
            r'<span[^>]*class="[^"]*company[^"]*"[^>]*>(.*?)</span>',
            html, re.DOTALL
        )
        if blocks:
            result = []
            for href, title, company in blocks:
                result.append(dict(href=href, title=self._clean_title(title), company=company.strip()))
            return result if result else None
        return None

    def _try_parse_v3(self, html: str) -> list[dict] | None:
        cards = re.findall(
            r'<div[^>]*class="[^"]*job-card-container[^"]*"[^>]*>.*?'
            r'href="([^"]+)"[^>]*>.*?<span[^>]*>(.*?)</span>',
            html, re.DOTALL
        )
        if cards:
            result = []
            for href, title in cards:
                t = self._clean_title(title)
                if self._is_valid_title(t):
                    result.append(dict(href=href, title=t))
            return result if result else None
        return None

    def _title_from_href(self, href: str) -> str:
        """Derive a human-readable title from the job-view URL slug."""
        slug = href.split("/")[-1].split("?")[0]
        slug = re.sub(r'-\d+$', '', slug)
        return slug.replace("-", " ").title()

    async def _fetch_jobs(self, url: str) -> list[Internship]:
        html = await self.safe_fetch(url, timeout=45)
        if not html:
            return []

        parsed = self._try_parse_v1(html)
        if parsed is None:
            parsed = self._try_parse_v2(html)
        if parsed is None:
            parsed = self._try_parse_v3(html)
        if parsed is None:
            # Last resort: collect job-view links; the title comes from the URL
            # slug per-link (never paired by global index — that misaligns).
            hrefs = re.findall(r'href="(https?://[^"]*linkedin[^"]*/jobs/view/[^"]+)"', html)
            parsed = [dict(href=h) for h in hrefs] if hrefs else None
        if parsed is None:
            return []

        default_location = self.config.scrapers["linkedin"]["location"]
        seen_ids: set[str] = set()
        results: list[Internship] = []
        for entry in parsed:
            href = entry.get("href", "")
            jid_match = re.search(r'(\d+)(?:\?|$)', href.split("-")[-1] if "-" in href else href)
            if not jid_match:
                continue
            jid = jid_match.group(1)
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            title = entry.get("title", "")
            if not self._is_valid_title(title):
                title = self._title_from_href(href)

            company = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', entry.get("company", ""))).strip()
            location = entry.get("location") or default_location
            results.append(Internship(
                title=title, company=company, location=location,
                url=href.split("?")[0], source=self.SOURCE,
            ))
        return results
