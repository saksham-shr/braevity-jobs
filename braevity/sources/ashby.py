import logging
from braevity.core.models import Job
from braevity.sources.base import BaseSource

logger = logging.getLogger(__name__)

ASHBY_QUERY = """
query ApiJobBoardWithTeams {
    jobBoard {
        teams {
            name
            jobs {
                id
                title
                locationName
                publishedAt
            }
        }
    }
}
"""


class AshbySource(BaseSource):
    name = "ashby"

    async def fetch_jobs(self, session, company) -> list[Job]:
        org = company["org"]
        url = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"

        try:
            resp = await session.post(
                url,
                json={"operationName": "ApiJobBoardWithTeams", "query": ASHBY_QUERY},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "apollographql-client-name": "non-user",
                },
            )
            if resp.status != 200:
                logger.warning("Ashby %s returned %d", company["name"], resp.status)
                return []
            data = await resp.json()
        except Exception as e:
            logger.warning("Ashby %s failed: %s", company["name"], e)
            return []

        if data.get("errors"):
            logger.warning("Ashby %s GraphQL errors: %s", company["name"], data["errors"])
            return []

        jobs = []
        teams = (data.get("data") or {}).get("jobBoard", {}).get("teams") or []
        for team in teams:
            for item in team.get("jobs", []):
                job_id = item.get("id", "")
                job_url = f"https://jobs.ashbyhq.com/{org}/{job_id}"

                jobs.append(Job.from_fields(
                    title=item.get("title", "Untitled"),
                    company=company["name"],
                    location=item.get("locationName"),
                    url=job_url,
                    posted_date=item.get("publishedAt"),
                    source_ats=self.name,
                ))
        return jobs
