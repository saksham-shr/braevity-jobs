import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(BaseAggregator):
    name = "arbeitnow"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        params = {}
        if offset:
            params["page"] = (offset // 300) + 1
        try:
            resp = await session.get(
                ARBEITNOW_API, params=params,
                headers={"User-Agent": "braevity/0.1"},
            )
            if resp.status != 200:
                logger.warning("Arbeitnow returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("Arbeitnow failed: %s", e)
            return []

        job_list = data.get("data") or []
        jobs = []
        for item in job_list:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            job_url = (item.get("url") or "").strip()
            if not job_url:
                continue

            tags = item.get("tags") or []
            remote = bool(item.get("remote"))

            jobs.append(Job.from_fields(
                title=title,
                company=(item.get("company_name") or "").strip() or "Unknown",
                location=item.get("location"),
                url=job_url,
                posted_date=item.get("created_at"),
                source=self.name,
                tags=tags,
                description=item.get("description"),
                remote=remote,
                employment_type=_first_or_none(item.get("job_types")),
                apply_url=job_url,
                source_id=item.get("slug"),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        return await self.fetch_all_jobs(session)


def _first_or_none(val) -> str | None:
    if isinstance(val, list) and val:
        return val[0].lower()
    return None
