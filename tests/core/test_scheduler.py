import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from braevity.core.scheduler import run_fast_cycle, run_slow_cycle
from braevity.core.models import Job
from braevity.core.registry import BoardRegistry


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


def test_slow_cycle_empty_results_not_failure(tmp_path):
    """Empty job results should not deactivate boards (issue #9)."""
    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    registry = BoardRegistry(reg_path)
    registry.register("greenhouse", "acme-co", company_name="Acme")
    registry.close()

    fake_source = MagicMock()
    fake_source.return_value = fake_source
    fake_source.fetch_jobs = AsyncMock(return_value=[])

    with patch.dict("braevity.core.scheduler.ATS_SOURCES", {"greenhouse": fake_source}):
        count, jobs = asyncio.run(run_slow_cycle({}, db_path, reg_path))

    assert count == 0

    registry = BoardRegistry(reg_path)
    boards = registry.get_active_boards("greenhouse")
    registry.close()
    assert len(boards) == 1
    assert boards[0]["fail_count"] == 0


@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_fast_cycle_calls_progress_callback(mock_discover, mock_aggs, tmp_path):
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[_job()])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    progress_calls = []

    def on_progress(source_name, job_count):
        progress_calls.append((source_name, job_count))

    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    count, jobs = asyncio.run(run_fast_cycle({}, db_path, reg_path, on_progress=on_progress))
    assert count == 1
    assert ("fake", 1) in progress_calls


@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_fast_cycle_progress_callback_on_failure(mock_discover, mock_aggs, tmp_path):
    fake_agg = MagicMock()
    fake_agg.name = "broken"
    fake_agg.fetch_all_jobs = AsyncMock(side_effect=RuntimeError("boom"))
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    progress_calls = []

    def on_progress(source_name, job_count):
        progress_calls.append((source_name, job_count))

    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    count, jobs = asyncio.run(run_fast_cycle({}, db_path, reg_path, on_progress=on_progress))
    assert count == 0
    assert ("broken", -1) in progress_calls
