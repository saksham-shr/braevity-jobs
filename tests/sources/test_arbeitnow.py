import asyncio
import aiohttp
from braevity.sources.arbeitnow import ArbeitnowSource


def test_arbeitnow_fetch_real_api():
    async def _run():
        source = ArbeitnowSource()
        async with aiohttp.ClientSession() as session:
            jobs = await source.fetch_all_jobs(session)
        return jobs

    jobs = asyncio.run(_run())
    assert len(jobs) > 0
    job = jobs[0]
    assert job.title
    assert job.company
    assert job.url
    assert job.source == "arbeitnow"
