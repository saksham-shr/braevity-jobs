import logging
from datetime import datetime, timezone
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

LEVER_API = "https://api.lever.co/v0/postings/{org}?mode=json"


class LeverSource(BaseSource):
    name = "lever"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        org = company.get("org") or company.get("token", "")
        url = LEVER_API.format(org=org)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status == 404:
                raise BoardGoneError(f"Lever {org} returned 404")
            if resp.status != 200:
                logger.warning("Lever %s returned %d", org, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Lever %s returned non-JSON", org)
                return []
            data = await resp.json()
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("Lever %s failed: %s", org, e)
            return []

        if not isinstance(data, list):
            return []

        jobs = []
        for posting in data:
            job_url = (posting.get("hostedUrl") or "").strip()
            if not job_url:
                continue

            categories = posting.get("categories") or {}
            all_locations = categories.get("allLocations") or []
            if all_locations:
                location = " / ".join(
                    loc.strip() for loc in all_locations if loc and loc.strip()
                ) or None
            else:
                location = (categories.get("location") or "").strip() or None

            created_at = posting.get("createdAt")
            posted_date = None
            if isinstance(created_at, (int, float)) and created_at > 0:
                posted_date = datetime.fromtimestamp(
                    created_at / 1000, tz=timezone.utc
                ).isoformat()

            jobs.append(Job.from_fields(
                title=(posting.get("text") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or org,
                location=location,
                url=job_url,
                posted_date=posted_date,
                source=self.name,
            ))
        return jobs
