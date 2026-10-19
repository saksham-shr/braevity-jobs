import logging
from urllib.parse import urlparse
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
MAX_PAGES = 25


class WorkdaySource(BaseSource):
    name = "workday"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        raw = (company.get("url") or company.get("token", "")).rstrip("/")
        # Workday's CXS API path needs the tenant's "career site" identifier,
        # which is an arbitrary name the company picked (e.g. NVIDIA's is
        # "NVIDIAExternalCareerSite", not "nvidia") — it cannot be derived
        # from the subdomain. Registry tokens carry it as "url#site_name";
        # without that suffix there is no reliable way to guess it, so we
        # refuse rather than silently querying a URL that 404s as "0 jobs".
        if "#" in raw:
            base_url, company_id = raw.split("#", 1)
        else:
            base_url, company_id = raw, company.get("company_id")
        base_url = base_url.rstrip("/")

        if not company_id:
            logger.warning(
                "Workday %s has no career-site id (expected token format "
                "'url#site_name') — skipping rather than guessing",
                company.get("name", base_url),
            )
            return []

        parsed = urlparse(base_url)
        hostname = parsed.hostname
        if not hostname:
            logger.warning("Workday %s has no valid URL: %s", company.get("name", ""), base_url)
            return []
        subdomain = company.get("subdomain") or hostname.split(".")[0]

        cxs_url = f"{parsed.scheme}://{hostname}/wday/cxs/{subdomain}/{company_id}/jobs"

        all_jobs: list[Job] = []
        offset = 0

        for _ in range(MAX_PAGES):
            try:
                resp = await fetch(
                    session, "POST", cxs_url,
                    json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                if resp is None:
                    break
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
