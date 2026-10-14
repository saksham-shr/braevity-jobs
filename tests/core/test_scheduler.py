import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from braevity.core.scheduler import run_fast_cycle
from braevity.core.models import Job


def _job(title="SDE", url="https://x.com/1"):
    return Job.from_fields(
        title=title, company="Acme", location="Bangalore, India",
        url=url, posted_date=None, source="remoteok",
    )


@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_fast_cycle_fetches_aggregators(mock_discover, mock_aggs, tmp_path):
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[_job()])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    count, jobs = asyncio.run(run_fast_cycle({}, db_path, reg_path))
    assert count == 1
    assert len(jobs) == 1
    fake_agg.fetch_all_jobs.assert_awaited_once()
