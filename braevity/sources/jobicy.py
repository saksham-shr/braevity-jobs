import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


class JobicySource(BaseAggregator):
    name = "jobicy"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        params = {"count": 50}
        try:
            resp = await session.get(
                JOBICY_API, params=params,
                headers={"User-Agent": "braevity/0.1"},
            )
            if resp.status != 200:
                logger.warning("Jobicy returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("Jobicy failed: %s", e)
            return []

        job_list = data.get("jobs") or []
        jobs = []
        for item in job_list:
            title = (item.get("jobTitle") or "").strip()
            if not title:
                continue
            job_url = (item.get("url") or "").strip()
            if not job_url:
                continue

            industry = item.get("jobIndustry") or []
            job_type = item.get("jobType") or []
            emp_type = job_type[0].lower() if job_type else None

            jobs.append(Job.from_fields(
                title=title,
                company=(item.get("companyName") or "").strip() or "Unknown",
                location=item.get("jobGeo"),
                url=job_url,
                posted_date=item.get("pubDate"),
                source=self.name,
                salary_min=_parse_int(item.get("salaryMin")),
                salary_max=_parse_int(item.get("salaryMax")),
                salary_currency=item.get("salaryCurrency"),
                tags=industry if isinstance(industry, list) else [industry],
                description=item.get("jobDescription"),
                remote=True,
                employment_type=emp_type,
                apply_url=job_url,
                source_id=str(item.get("id", "")),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        return await self.fetch_all_jobs(session)


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
