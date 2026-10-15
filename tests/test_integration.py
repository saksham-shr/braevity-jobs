import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner
from braevity.cli.commands import cli
from braevity.core.models import Job
from braevity.core.scheduler import run_fast_cycle


def _job(title="Backend Engineer", company="Stripe", url="https://x.com/1"):
    return Job.from_fields(
        title=title, company=company, location="Bangalore, India",
        url=url, posted_date="2026-10-06", source="remoteok",
    )


def test_init_watch_list_remove_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAEVITY_HOME", str(tmp_path / ".braevity"))
    runner = CliRunner()

    r = runner.invoke(cli, ["init"], input="D:/Jobs\nN\n")
    assert r.exit_code == 0

    r = runner.invoke(cli, ["watch"], input="SDE\nany\nIndia\nBangalore\n30\n")
    assert r.exit_code == 0
    assert "Watch added" in r.output

    r = runner.invoke(cli, ["list"])
    assert "SDE" in r.output

    r = runner.invoke(cli, ["remove", "1"])
    assert "Removed" in r.output

    r = runner.invoke(cli, ["list"])
    assert "No watches" in r.output


@patch("braevity.core.scheduler.AGGREGATORS")
@patch("braevity.core.scheduler.discover_from_jobs", return_value=0)
def test_scan_cycle_end_to_end(mock_discover, mock_aggs, tmp_path):
    fake_agg = MagicMock()
    fake_agg.name = "fake"
    fake_agg.fetch_all_jobs = AsyncMock(return_value=[
        _job("Backend Engineer", "Stripe", "https://stripe.com/jobs/1"),
        _job("Frontend Engineer", "Stripe", "https://stripe.com/jobs/2"),
    ])
    mock_aggs.__iter__ = lambda s: iter([fake_agg])

    db_path = tmp_path / "seen.db"
    reg_path = tmp_path / "reg.db"

    count, jobs = asyncio.run(run_fast_cycle({}, db_path, reg_path))
    assert count == 2

    # Dedup moved to caller — fast_cycle returns same jobs until caller marks seen
    count2, jobs2 = asyncio.run(run_fast_cycle({}, db_path, reg_path))
    assert count2 == 2

    # After marking seen, dedup kicks in
    from braevity.core.dedup import DedupStore
    store = DedupStore(db_path)
    store.mark_seen_batch(jobs)
    store.close()

    count3, jobs3 = asyncio.run(run_fast_cycle({}, db_path, reg_path))
    assert count3 == 0
