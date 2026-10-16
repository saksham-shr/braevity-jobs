import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

WORKABLE_API = "https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"
# Cloudflare in front of this endpoint 302s requests with no browser User-Agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


class WorkableSource(BaseSource):
    name = "workable"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        url = WORKABLE_API.format(slug=slug)
        try:
            resp = await session.get(url, headers=HEADERS)
            if resp.status != 200:
                logger.warning("Workable %s returned %d", slug, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Workable %s returned non-JSON", slug)
                return []
            data = await resp.json()
        except Exception as e:
            logger.warning("Workable %s failed: %s", slug, e)
            return []

        jobs = []
        for posting in data.get("jobs", []):
            job_url = (posting.get("url") or posting.get("shortlink") or "").strip()
            if not job_url:
                continue
            location = ", ".join(
                part.strip() for part in (posting.get("city"), posting.get("country"))
                if part and part.strip()
            ) or None

            jobs.append(Job.from_fields(
                title=(posting.get("title") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or slug,
                location=location,
                url=job_url,
                posted_date=(posting.get("published_on") or posting.get("created_at") or "").strip() or None,
                source=self.name,
            ))
        return jobs
