import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

BREEZYHR_API = "https://{slug}.breezy.hr/json"


class BreezyHRSource(BaseSource):
    name = "breezyhr"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        url = BREEZYHR_API.format(slug=slug)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status == 404:
                raise BoardGoneError(f"BreezyHR {slug} returned 404")
            if resp.status != 200:
                logger.warning("BreezyHR %s returned %d", slug, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("BreezyHR %s returned non-JSON", slug)
                return []
            data = await resp.json()
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("BreezyHR %s failed: %s", slug, e)
            return []

        if not isinstance(data, list):
            return []

        jobs = []
        for posting in data:
            job_url = (posting.get("url") or "").strip()
            if not job_url:
                continue

            location = posting.get("location") or {}

            jobs.append(Job.from_fields(
                title=(posting.get("name") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or slug,
                location=(location.get("name") or "").strip() or None,
                url=job_url,
                posted_date=(posting.get("published_date") or "").strip() or None,
                source=self.name,
                employment_type=(posting.get("type") or {}).get("name"),
                remote=bool(location.get("is_remote")),
            ))
        return jobs
