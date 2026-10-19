import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

# Undocumented endpoint (BambooHR's own public API needs a company API key).
# May change without notice.
BAMBOOHR_API = "https://{subdomain}.bamboohr.com/careers/list"
HEADERS = {"Accept": "application/json"}


class BambooHRSource(BaseSource):
    name = "bamboohr"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        subdomain = company.get("subdomain") or company.get("token", "")
        url = BAMBOOHR_API.format(subdomain=subdomain)
        try:
            resp = await fetch(session, "GET", url, headers=HEADERS)
            if resp is None:
                return []
            if resp.status == 404:
                raise BoardGoneError(f"BambooHR {subdomain} returned 404")
            if resp.status != 200:
                logger.warning("BambooHR %s returned %d", subdomain, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("BambooHR %s returned non-JSON", subdomain)
                return []
            data = await resp.json()
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("BambooHR %s failed: %s", subdomain, e)
            return []

        jobs = []
        for posting in data.get("result", []):
            job_id = posting.get("id")
            if not job_id:
                continue
            job_url = f"https://{subdomain}.bamboohr.com/careers/{job_id}"

            loc = posting.get("location") or {}
            location = ", ".join(
                part.strip() for part in (loc.get("city"), loc.get("state")) if part and part.strip()
            ) or None

            jobs.append(Job.from_fields(
                title=(posting.get("jobOpeningName") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or subdomain,
                location=location,
                url=job_url,
                posted_date=None,
                source=self.name,
            ))
        return jobs
