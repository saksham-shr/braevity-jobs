import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError
from braevity.sources.schema_org import SchemaOrgScraper

logger = logging.getLogger(__name__)

TEAMTAILOR_API = "https://{slug}.teamtailor.com/jobs.json"
# api.teamtailor.com/v1 needs OAuth (confirmed 406 unauthenticated) — do not use.


class TeamtailorSource(BaseSource):
    name = "teamtailor"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        url = TEAMTAILOR_API.format(slug=slug)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status == 404:
                raise BoardGoneError(f"Teamtailor {slug} returned 404")
            if resp.status != 200:
                logger.warning("Teamtailor %s returned %d", slug, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Teamtailor %s returned non-JSON", slug)
                return []
            data = await resp.json()
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("Teamtailor %s failed: %s", slug, e)
            return []

        if not isinstance(data, dict):
            logger.warning("Teamtailor %s returned unexpected payload shape", slug)
            return []
        items = data.get("items", [])
        if not isinstance(items, list):
            logger.warning("Teamtailor %s items field is not a list", slug)
            return []

        scraper = SchemaOrgScraper()
        jobs = []
        for item in items:
            if not isinstance(item, dict):
                continue
            job_url = (item.get("url") or "").strip()
            if not job_url:
                continue

            posting = item.get("_jobposting")
            job = scraper._parse_posting(posting, job_url, source=self.name) if posting else None
            if job is None:
                job = Job.from_fields(
                    title=(item.get("title") or "").strip() or "Untitled",
                    company=company.get("name") or company.get("company_name") or slug,
                    location=None,
                    url=job_url,
                    posted_date=(item.get("date_published") or "").strip() or None,
                    source=self.name,
                )
            jobs.append(job)
        return jobs
