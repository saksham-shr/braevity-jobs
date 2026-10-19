import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


class GreenhouseSource(BaseSource):
    name = "greenhouse"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        token = company.get("board_token") or company.get("token", "")
        url = GREENHOUSE_API.format(token=token)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status != 200:
                logger.warning("Greenhouse %s returned %d", token, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Greenhouse %s returned non-JSON", token)
                return []
            data = await resp.json()
        except Exception as e:
            logger.warning("Greenhouse %s failed: %s", token, e)
            return []

        jobs = []
        for posting in data.get("jobs", []):
            job_url = (posting.get("absolute_url") or "").strip()
            if not job_url:
                continue
            location_obj = posting.get("location")
            location = None
            if isinstance(location_obj, dict):
                location = (location_obj.get("name") or "").strip() or None
            elif isinstance(location_obj, str):
                location = location_obj.strip() or None

            jobs.append(Job.from_fields(
                title=(posting.get("title") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or token,
                location=location,
                url=job_url,
                posted_date=(posting.get("updated_at") or "").strip() or None,
                source=self.name,
            ))
        return jobs
