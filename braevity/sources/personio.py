import logging
import xml.etree.ElementTree as ET
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

PERSONIO_API = "https://{slug}.jobs.personio.com/xml"


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text(elem: ET.Element, name: str) -> str:
    for child in elem:
        if _local_tag(child.tag) == name:
            return (child.text or "").strip()
    return ""


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
        for position in root.iter():
            if _local_tag(position.tag) != "position":
                continue
            job_id = _find_text(position, "id")
            if not job_id:
                continue

            jobs.append(Job.from_fields(
                title=_find_text(position, "name") or "Untitled",
                company=company.get("name") or company.get("company_name") or slug,
                location=_find_text(position, "office") or None,
                url=f"https://{slug}.jobs.personio.com/job/{job_id}",
                posted_date=_find_text(position, "createdAt") or None,
                source=self.name,
                employment_type=_find_text(position, "employmentType") or None,
            ))
        return jobs
