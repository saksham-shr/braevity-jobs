import json
import logging
import re
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class SchemaOrgScraper:
    name = "schema.org"

    async def scrape_page(self, session: ClientSession, url: str) -> list[Job]:
        try:
            resp = await fetch(session, "GET", url, headers={"User-Agent": "braevity/0.1"})
            if resp is None or resp.status != 200:
                return []
            html = await resp.text()
        except Exception as e:
            logger.warning("Schema.org scrape failed for %s: %s", url, e)
            return []
        return self.parse_jsonld(html, url)

    def parse_jsonld(self, html: str, page_url: str) -> list[Job]:
        matches = JSONLD_RE.findall(html)
        jobs = []
        for raw in matches:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, list):
                for item in data:
                    job = self._parse_posting(item, page_url)
                    if job:
                        jobs.append(job)
            elif isinstance(data, dict):
                if data.get("@graph"):
                    for item in data["@graph"]:
                        job = self._parse_posting(item, page_url)
                        if job:
                            jobs.append(job)
                else:
                    job = self._parse_posting(data, page_url)
                    if job:
                        jobs.append(job)
        return jobs

    def _parse_posting(self, data: dict, page_url: str) -> Job | None:
        if not isinstance(data, dict):
            return None
        if data.get("@type", "") != "JobPosting":
            return None

        title = (data.get("title") or "").strip()
        if not title:
            return None

        org = data.get("hiringOrganization") or {}
        company = (org.get("name") or "").strip() if isinstance(org, dict) else str(org).strip()
        company = company or "Unknown"

        url = data.get("url") or page_url
        location = self._extract_location(data)
        salary_min, salary_max, currency = self._extract_salary(data)
        remote = data.get("jobLocationType") == "TELECOMMUTE"
        emp_type = (data.get("employmentType") or "").lower() or None

        return Job.from_fields(
            title=title,
            company=company,
            location=location,
            url=url,
            posted_date=data.get("datePosted"),
            source=self.name,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            description=data.get("description"),
            remote=remote,
            employment_type=emp_type,
            apply_url=data.get("directApply") if isinstance(data.get("directApply"), str) else url,
        )

    def _extract_location(self, data: dict) -> str | None:
        loc = data.get("jobLocation")
        if not loc:
            return None
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality"),
                    addr.get("addressRegion"),
                    addr.get("addressCountry"),
                ]
                return ", ".join(p for p in parts if p) or None
            return (loc.get("name") or "").strip() or None
        if isinstance(loc, str):
            return loc.strip() or None
        return None

    def _extract_salary(self, data: dict) -> tuple[int | None, int | None, str | None]:
        salary = data.get("baseSalary")
        if not salary or not isinstance(salary, dict):
            return None, None, None
        currency = salary.get("currency")
        value = salary.get("value")
        if isinstance(value, dict):
            return (
                _parse_int(value.get("minValue")),
                _parse_int(value.get("maxValue")),
                currency,
            )
        if isinstance(value, (int, float)):
            return int(value), int(value), currency
        return None, None, currency


class SchemaOrgSource(BaseSource):
    name = "schema_org"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        url = company.get("url") or company.get("token", "")
        if not url:
            return []
        return await SchemaOrgScraper().scrape_page(session, url)


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
