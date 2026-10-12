import logging
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

class GreenhouseSource(BaseSource):
    name = "greenhouse"

    async def fetch_jobs(self, session, company) -> list[Job]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company['token']}/jobs?content=true"
        try:
             resp = await session.get(url)
             if resp.status != 200:
                 logger.warning("Greenhouse %s returned %d", company["name"], resp.status)
                 return []
             if "json" not in resp.headers.get("Content-Type", ""):
                 logger.warning("Greenhouse %s returned non-JSON", company["name"])
                 return []
             data = await resp.json()
        except Exception as e:
            logger.warning("Greenhouse %s failed: %s", company["name"], e)
            return []

        jobs = []
        for item in data.get("jobs", []):
            loc = item.get("location")
            if isinstance(loc, dict):
                loc = loc.get("name")

            jobs.append(Job.from_fields(
                title=item.get("title", "Untitled"),
                company=company["name"],
                location=loc,
                url=item.get("absolute_url", ""),
                posted_date=item.get("updated_at"),
                source_ats=self.name,
            ))
        return jobs