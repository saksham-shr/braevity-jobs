import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


class RemoteOKSource(BaseAggregator):
    name = "remoteok"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        url = REMOTEOK_API
        if offset:
            url = f"{url}?offset={offset}"
        try:
            resp = await session.get(
                url, headers={"User-Agent": "braevity/0.1"}
            )
            if resp.status != 200:
                logger.warning("RemoteOK returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("RemoteOK failed: %s", e)
            return []

        if not isinstance(data, list):
            return []

        jobs = []
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            position = (item.get("position") or "").strip()
            if not position:
                continue
            company = (item.get("company") or "").strip() or "Unknown"
            slug = item.get("slug", "")
            job_url = f"https://remoteok.com/remote-jobs/{slug}" if slug else item.get("url", "")
            if not job_url:
                continue

            tags = item.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]

            jobs.append(Job.from_fields(
                title=position,
                company=company,
                location=item.get("location") or "Remote",
                url=job_url,
                posted_date=item.get("date"),
                source=self.name,
                salary_min=_parse_int(item.get("salary_min")),
                salary_max=_parse_int(item.get("salary_max")),
                salary_currency="USD",
                tags=tags,
                description=item.get("description"),
                remote=True,
                employment_type=None,
                apply_url=item.get("apply_url") or item.get("url"),
                source_id=str(item.get("id", "")),
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
