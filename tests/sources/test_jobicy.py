import asyncio
import aiohttp
from braevity.sources.jobicy import JobicySource


def test_jobicy_fetch_real_api():
    async def _run():
        source = JobicySource()
        async with aiohttp.ClientSession() as session:
            jobs = await source.fetch_all_jobs(session)
        return jobs

    jobs = asyncio.run(_run())
    assert len(jobs) > 0
    job = jobs[0]
    assert job.title
    assert job.company
    assert job.url
    assert job.source == "jobicy"
