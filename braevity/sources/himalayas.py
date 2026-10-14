import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

HIMALAYAS_API = "https://himalayas.app/jobs/api"


class HimalayasSource(BaseAggregator):
    name = "himalayas"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        params = {"limit": 50, "offset": offset}
        try:
            resp = await session.get(
                HIMALAYAS_API, params=params,
                headers={"User-Agent": "braevity/0.1"},
            )
            if resp.status != 200:
                logger.warning("Himalayas returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("Himalayas failed: %s", e)
            return []

        job_list = data.get("jobs") or []
        jobs = []
        for item in job_list:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            job_url = (item.get("guid") or item.get("applicationLink") or "").strip()
            if not job_url:
                continue

            categories = item.get("categories") or []
            if isinstance(categories, str):
                categories = [categories]

            jobs.append(Job.from_fields(
                title=title,
                company=(item.get("companyName") or "").strip() or "Unknown",
                location=_format_location(item.get("locationRestrictions")),
                url=job_url,
                posted_date=item.get("pubDate"),
                source=self.name,
                salary_min=_parse_int(item.get("minSalary")),
                salary_max=_parse_int(item.get("maxSalary")),
                salary_currency=item.get("currency"),
                tags=categories,
                description=item.get("description"),
                remote=True,
                employment_type=(item.get("employmentType") or "").lower() or None,
                apply_url=item.get("applicationLink"),
                source_id=item.get("guid"),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        all_jobs = []
        offset = 0
        while True:
            batch = await self.fetch_all_jobs(session, offset)
            if not batch:
                break
            all_jobs.extend(batch)
            if len(batch) < 50:
                break
            offset += len(batch)
        return all_jobs


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _format_location(restrictions) -> str | None:
    if not restrictions:
        return "Remote"
    if isinstance(restrictions, list):
        return ", ".join(str(r) for r in restrictions) or "Remote"
    return str(restrictions)
