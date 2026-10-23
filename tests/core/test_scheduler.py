import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from braevity.core.scheduler import run_fast_cycle, run_slow_cycle, run_scheduler, run_scan_cycle
from braevity.core.models import Job
from braevity.core.registry import BoardRegistry
from braevity.core.dedup import DedupStore
from braevity.sources.base import BoardGoneError


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

    with patch.dict("braevity.core.scheduler.ATS_SOURCES", {"greenhouse": fake_source}), \
         patch("braevity.core.scheduler.seed_registry", return_value=0):
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


class _StopLoop(Exception):
    pass


@patch("braevity.core.scheduler.asyncio.sleep", new_callable=AsyncMock)
@patch("braevity.config.config_dir")
@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_two_watches_same_job_both_delivered(mock_discover, mock_aggs, mock_config_dir, mock_sleep, tmp_path):
    """Two watches matching the same job in one cycle must both get it
    exported — gating export on per-watch delivered_jobs instead of the
    global seen_jobs must not block a second watch (issue #19, Task 1)."""
    from braevity.core.scheduler import run_scheduler

    mock_config_dir.return_value = tmp_path
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[_job(title="SDE")])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])
    mock_sleep.side_effect = [None, _StopLoop()]

    config = {
        "excel_path": str(tmp_path),
        "watches": [
            {"role": "SDE", "experience": "any", "locations": {}},
            {"role": "sde", "experience": "any", "locations": {}},
        ],
    }
    try:
        asyncio.run(run_scheduler(config))
    except _StopLoop:
        pass

    store = DedupStore(tmp_path / "seen.db")
    assert store.is_delivered("https://x.com/1", "SDE")
    assert store.is_delivered("https://x.com/1", "sde")
    store.close()


@patch("braevity.config.config_dir")
@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_same_watch_not_redelivered(mock_discover, mock_aggs, mock_config_dir, tmp_path):
    """Same watch scanning again after a job was already delivered must
    not re-export it a second time."""
    from braevity.core.scheduler import run_scan_cycle
    mock_config_dir.return_value = tmp_path

    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[_job(title="SDE")])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    db_path = tmp_path / "seen.db"
    watch = {"role": "SDE", "experience": "any", "locations": {}}

    first = asyncio.run(run_scan_cycle(watch, {"excel_path": str(tmp_path)}, db_path))
    store = DedupStore(db_path)
    assert store.is_delivered("https://x.com/1", "SDE")
    store.close()
    assert first == 1


def test_board_gone_error_deactivates_after_three_terminal_failures(tmp_path):
    """A source raising BoardGoneError (confirmed-dead board, e.g. 404)
    must count toward deactivation — unlike a generic/transient exception,
    which does not (issue #30 review: terminal status wasn't wired through,
    so a dead board stayed active forever)."""
    reg_path = tmp_path / "reg.db"
    registry = BoardRegistry(reg_path)
    registry.register("greenhouse", "gone", company_name="Gone")
    registry.close()

    fake_source = MagicMock()
    fake_source.return_value = fake_source
    fake_source.fetch_jobs = AsyncMock(side_effect=BoardGoneError("404"))

    db_path = tmp_path / "seen.db"
    with patch.dict("braevity.core.scheduler.ATS_SOURCES", {"greenhouse": fake_source}, clear=True), \
         patch.dict("braevity.core.scheduler.ATS_LIMITS", {"greenhouse": 5}, clear=True), \
         patch("braevity.core.scheduler.seed_registry", return_value=0):
        asyncio.run(run_slow_cycle({}, db_path, reg_path))
        asyncio.run(run_slow_cycle({}, db_path, reg_path))
        registry = BoardRegistry(reg_path)
        assert len(registry.get_active_boards()) == 1
        registry.close()
        asyncio.run(run_slow_cycle({}, db_path, reg_path))

    registry = BoardRegistry(reg_path)
    assert len(registry.get_active_boards()) == 0
    registry.close()


def test_generic_exception_does_not_deactivate_board(tmp_path):
    """A plain exception (network blip, bug) stays transient — it must
    not count toward deactivation the way a confirmed-dead board does."""
    reg_path = tmp_path / "reg.db"
    registry = BoardRegistry(reg_path)
    registry.register("greenhouse", "flaky", company_name="Flaky")
    registry.close()

    fake_source = MagicMock()
    fake_source.return_value = fake_source
    fake_source.fetch_jobs = AsyncMock(side_effect=RuntimeError("boom"))

    db_path = tmp_path / "seen.db"
    with patch.dict("braevity.core.scheduler.ATS_SOURCES", {"greenhouse": fake_source}, clear=True), \
         patch.dict("braevity.core.scheduler.ATS_LIMITS", {"greenhouse": 5}, clear=True), \
         patch("braevity.core.scheduler.seed_registry", return_value=0):
        for _ in range(5):
            asyncio.run(run_slow_cycle({}, db_path, reg_path))

    registry = BoardRegistry(reg_path)
    assert len(registry.get_active_boards()) == 1
    registry.close()


@patch("braevity.config.config_dir")
@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_export_failure_persists_job_for_retry(mock_discover, mock_aggs, mock_config_dir, tmp_path):
    """If export/notify crashes, the job must not be lost — it's already
    marked seen (fetch-dedup) so it won't come back from a future fetch.
    It must be retried on the next scan instead (issue #30 review)."""
    mock_config_dir.return_value = tmp_path
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[_job(title="SDE")])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    db_path = tmp_path / "seen.db"
    watch = {"role": "SDE", "experience": "any", "locations": {}}

    with patch("braevity.core.scheduler.export_jobs", side_effect=OSError("disk full")):
        count = asyncio.run(run_scan_cycle(watch, {"excel_path": str(tmp_path)}, db_path))
    assert count == 0

    store = DedupStore(db_path)
    assert not store.is_delivered("https://x.com/1", "SDE")
    pending = store.get_pending("SDE")
    assert len(pending) == 1
    assert pending[0].url == "https://x.com/1"
    store.close()

    # Next scan (export working again) must retry and deliver the pending job.
    second = asyncio.run(run_scan_cycle(watch, {"excel_path": str(tmp_path)}, db_path))
    assert second == 1
    store = DedupStore(db_path)
    assert store.is_delivered("https://x.com/1", "SDE")
    assert store.get_pending("SDE") == []
    store.close()
