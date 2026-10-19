import logging
from aiohttp import ClientSession
from braevity.core.http import fetch
from braevity.core.models import Job
from braevity.sources.base import BaseSource, BoardGoneError

logger = logging.getLogger(__name__)

ASHBY_API = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"

ASHBY_QUERY = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
  jobBoard: jobBoardWithTeams(
    organizationHostedJobsPageName: $organizationHostedJobsPageName
  ) {
    jobPostings {
      id
      title
      locationName
      employmentType
    }
  }
}
"""


class AshbySource(BaseSource):
    name = "ashby"

    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        org = company.get("org") or company.get("token", "")
        try:
            resp = await fetch(
                session, "POST", ASHBY_API,
                json={
                    "operationName": "ApiJobBoardWithTeams",
                    "variables": {"organizationHostedJobsPageName": org},
                    "query": ASHBY_QUERY,
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            if resp is None:
                return []
            if resp.status != 200:
                logger.warning("Ashby %s returned %d", org, resp.status)
                return []
            if "json" not in resp.headers.get("Content-Type", ""):
                logger.warning("Ashby %s returned non-JSON", org)
                return []
            data = await resp.json()
        except BoardGoneError:
            raise
        except Exception as e:
            logger.warning("Ashby %s failed: %s", org, e)
            return []

        if data.get("errors"):
            # Ashby signals an unknown org via a GraphQL error on this
            # shared endpoint, not an HTTP 404 — that's the real "board
            # gone" signal here.
            logger.warning("Ashby %s GraphQL error: %s", org, data["errors"][0].get("message"))
            raise BoardGoneError(f"Ashby {org}: {data['errors'][0].get('message')}")

        postings = (
            data.get("data", {}).get("jobBoard", {}).get("jobPostings") or []
        )

        jobs = []
        for posting in postings:
            job_id = (posting.get("id") or "").strip()
            if not job_id:
                continue
            job_url = f"https://jobs.ashbyhq.com/{org}/{job_id}"
            location = (posting.get("locationName") or "").strip() or None

            jobs.append(Job.from_fields(
                title=(posting.get("title") or "").strip() or "Untitled",
                company=company.get("name") or company.get("company_name") or org,
                location=location,
                url=job_url,
                posted_date=None,
                source=self.name,
            ))
        return jobs
