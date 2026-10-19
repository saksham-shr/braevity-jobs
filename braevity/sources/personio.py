import logging
import xml.etree.ElementTree as ET
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

PERSONIO_API = "https://{slug}.jobs.personio.com/xml"


class PersonioSource(BaseSource):
    name = "personio"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        slug = company.get("slug") or company.get("token", "")
        url = PERSONIO_API.format(slug=slug)
        try:
            resp = await fetch(session, "GET", url)
            if resp is None:
                return []
            if resp.status == 404:
                raise BoardGoneError(f"Personio {slug} returned 404")
            if resp.status != 200:
                logger.warning("Personio %s returned %d", slug, resp.status)
                return []
            text = await resp.text()
            root = ET.fromstring(text)
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("Personio %s failed: %s", slug, e)
            return []

        jobs = []
        for position in root.findall("position"):
            job_id = (position.findtext("id") or "").strip()
            if not job_id:
                continue

            jobs.append(Job.from_fields(
                title=(position.findtext("name") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or slug,
                location=(position.findtext("office") or "").strip() or None,
                url=f"https://{slug}.jobs.personio.com/job/{job_id}",
                posted_date=(position.findtext("createdAt") or "").strip() or None,
                source=self.name,
                employment_type=(position.findtext("employmentType") or "").strip() or None,
            ))
        return jobs
