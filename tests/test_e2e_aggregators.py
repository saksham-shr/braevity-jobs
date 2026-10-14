import asyncio
import aiohttp
from braevity.sources.remoteok import RemoteOKSource
from braevity.sources.jobicy import JobicySource
from braevity.sources.arbeitnow import ArbeitnowSource
from braevity.sources.himalayas import HimalayasSource
from braevity.core.dedup import DedupStore
from braevity.core.registry import BoardRegistry
from braevity.sources.crossref import discover_from_jobs


def test_full_aggregator_pipeline(tmp_path):
    """Fetch from all aggregators, dedup, cross-ref discover."""
    async def _run():
        store = DedupStore(tmp_path / "seen.db")
        registry = BoardRegistry(tmp_path / "reg.db")

        all_jobs = []
        async with aiohttp.ClientSession() as session:
            for source in [RemoteOKSource(), JobicySource(), ArbeitnowSource(), HimalayasSource()]:
                try:
                    jobs = await source.fetch_all_jobs(session)
                    all_jobs.extend(jobs)
                except Exception:
                    pass

        assert len(all_jobs) > 0, "Should fetch at least some jobs"

        new_jobs = [j for j in all_jobs if not store.is_seen(j.url)]
        assert len(new_jobs) == len(all_jobs), "First run, all should be new"

        store.mark_seen_batch(new_jobs)

        second_check = [j for j in all_jobs if not store.is_seen(j.url)]
        assert len(second_check) == 0, "After marking, none should be new"

        discovered = discover_from_jobs(all_jobs, registry)

        store.close()
        registry.close()
        return len(all_jobs), discovered

    total, discovered = asyncio.run(_run())
    assert total > 10
    print(f"Fetched {total} jobs, discovered {discovered} new boards")
