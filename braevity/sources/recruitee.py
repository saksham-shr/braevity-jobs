import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

RECRUITEE_API = "https://{slug}.recruitee.com/api/offers/"


class RecruiteeSource(BaseSource):
    name = "recruitee"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        url = RECRUITEE_API.format(slug=slug)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status != 200:
                logger.warning("Recruitee %s returned %d", slug, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Recruitee %s returned non-JSON", slug)
                return []
            data = await resp.json()
        except Exception as e:
            logger.warning("Recruitee %s failed: %s", slug, e)
            return []

        jobs = []
        for offer in data.get("offers", []):
            job_url = (offer.get("careers_url") or "").strip()
            if not job_url:
                continue

            jobs.append(Job.from_fields(
                title=(offer.get("title") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or slug,
                location=(offer.get("location") or offer.get("city") or "").strip() or None,
                url=job_url,
                posted_date=(offer.get("published_at") or "").strip() or None,
                source=self.name,
            ))
        return jobs
