import logging
from urllib.parse import urlparse
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
MAX_PAGES = 25


class WorkdaySource(BaseSource):
    name = "workday"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        base_url = (company.get("url") or company.get("token", "")).rstrip("/")
        parsed = urlparse(base_url)
        hostname = parsed.hostname

        if "myworkdayjobs.com" in hostname:
            # ponytail: standard pattern nvidia.wd5.myworkdayjobs.com
            subdomain = hostname.split(".")[0]
            company_id = subdomain
        else:
            # ponytail: non-standard like jobs.careers.microsoft.com — use catalog override or hostname parts
            subdomain = company.get("subdomain", hostname.split(".")[0])
            company_id = company.get("company_id", subdomain)

        cxs_url = f"{parsed.scheme}://{hostname}/wday/cxs/{subdomain}/{company_id}/jobs"

        all_jobs: list[Job] = []
        offset = 0

        for _ in range(MAX_PAGES):
            try:
                resp = await session.post(
                    cxs_url,
                    json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                if resp.status != 200:
                    logger.warning("Workday %s returned %d", company.get("name", subdomain), resp.status)
                    break
                if "json" not in resp.headers.get("Content-Type", ""):
                    logger.warning("Workday %s returned non-JSON", company.get("name", subdomain))
                    break
                data = await resp.json()
            except Exception as e:
                logger.warning("Workday %s failed: %s", company.get("name", subdomain), e)
                break

            postings = data.get("jobPostings") or []
            if not postings:
                break

            for posting in postings:
                ext_path = (posting.get("externalPath") or "").strip()
                if not ext_path:
                    continue
                if not ext_path.startswith("/"):
                    ext_path = "/" + ext_path
                job_url = f"{base_url}{ext_path}"

                all_jobs.append(Job.from_fields(
                    title=(posting.get("title") or "").strip() or "Untitled",
                    company=company.get("name") or company.get("company_name") or subdomain,
                    location=None,
                    url=job_url,
                    posted_date=(posting.get("postedOn") or "").strip() or None,
                    source=self.name,
                ))

            if len(postings) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        return all_jobs
