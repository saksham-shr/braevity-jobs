import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE_SIZE = 100
MAX_PAGES = 25


class SmartRecruitersSource(BaseSource):
    name = "smartrecruiters"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        all_jobs: list[Job] = []
        offset = 0

        for _ in range(MAX_PAGES):
            url = f"{SMARTRECRUITERS_API.format(slug=slug)}?limit={PAGE_SIZE}&offset={offset}"
            try:
                resp = await fetch(session, "GET", url)
                if resp is None:
                    break
                if resp.status == 404 and offset == 0:
                    raise BoardGoneError(f"SmartRecruiters {slug} returned 404")
                if resp.status != 200:
                    logger.warning("SmartRecruiters %s returned %d", slug, resp.status)
                    break
                if "json" not in resp.headers.get("Content-Type", ""):
                    logger.warning("SmartRecruiters %s returned non-JSON", slug)
                    break
                data = await resp.json()
            except BoardGoneError:
                raise
            except Exception as e:
                logger.warning("SmartRecruiters %s failed: %s", slug, e)
                break

            postings = data.get("content") or []
            if not postings:
                break

            for posting in postings:
                job_url = (posting.get("ref") or "").strip()
                if not job_url:
                    continue
                location_obj = posting.get("location") or {}
                location = (location_obj.get("fullLocation") or location_obj.get("city") or "").strip() or None

                all_jobs.append(Job.from_fields(
                    title=(posting.get("name") or "").strip() or "Untitled",
                    company=company.get("name") or company.get("company_name") or slug,
                    location=location,
                    url=job_url,
                    posted_date=(posting.get("releasedDate") or "").strip() or None,
                    source=self.name,
                ))

            if len(postings) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        return all_jobs
