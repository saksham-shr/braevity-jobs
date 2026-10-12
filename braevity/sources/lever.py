import logging
from datetime import datetime, timezone
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)


class LeverSource(BaseSource):
    name = "lever"

    async def fetch_jobs(self, session, company) -> list[Job]:
        org = company["org"]
        url = f"https://api.lever.co/v0/postings/{org}?mode=json"

        try:
            resp = await session.get(url)
            if resp.status != 200:
                logger.warning("Lever %s returned %d", company["name"], resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Lever %s returned non-JSON", company["name"])
                return []
            data = await resp.json()
        except Exception as e:
            logger.warning("Lever %s failed: %s", company["name"], e)
            return []

        jobs = []
        for item in data:
            locations = item.get("categories", {}).get("allLocations", [])
            location = " / ".join(locations) if locations else None

            created = item.get("createdAt")
            posted_date = None
            if created:
                posted_date = datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat()

            jobs.append(Job.from_fields(
                title=item.get("text", "Untitled"),
                company=company["name"],
                location=location,
                url=item.get("hostedUrl", ""),
                posted_date=posted_date,
                source_ats=self.name,
            ))
        return jobs
