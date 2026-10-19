import logging
from datetime import datetime, timezone
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

RECRUITEE_API = "https://{slug}.recruitee.com/api/offers/"


def _normalize_published_at(raw: str) -> str | None:
    """published_at comes back as "2026-10-08 08:03:01 UTC", not ISO 8601
    — datetime.fromisoformat() raises on the trailing " UTC"."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.removesuffix(" UTC"), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return raw


class RecruiteeSource(BaseSource):
    name = "recruitee"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        url = RECRUITEE_API.format(slug=slug)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status == 401:
                logger.warning(
                    "Recruitee %s returned 401 — likely needs X-Careers-Sites-Token "
                    "(unauthenticated access ends 2027-02-10 per Recruitee docs)", slug,
                )
                return []
            if resp.status == 404:
                raise BoardGoneError(f"Recruitee {slug} returned 404")
            if resp.status != 200:
                logger.warning("Recruitee %s returned %d", slug, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Recruitee %s returned non-JSON", slug)
                return []
            data = await resp.json()
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("Recruitee %s failed: %s", slug, e)
            return []

        jobs = []
        for offer in data.get("offers", []):
            job_url = (offer.get("careers_url") or "").strip()
            if not job_url:
                continue

            is_remote = bool(offer.get("remote"))
            city = (offer.get("city") or "").strip()
            loc = (offer.get("location") or "").strip()
            # Remote postings put "Remote job" in location; city holds the real place.
            location = (city or loc) if is_remote else (loc or city)
            location = location or None

            jobs.append(Job.from_fields(
                title=(offer.get("title") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or slug,
                location=location,
                url=job_url,
                posted_date=_normalize_published_at((offer.get("published_at") or "").strip()),
                source=self.name,
                remote=is_remote,
            ))
        return jobs
