from pathlib import Path
from braevity.core.dedup import DedupStore
from braevity.core.models import Job


def _make_job(url: str = "https://example.com/job/1") -> Job:
    return Job.from_fields(
        title="SDE", company="Acme", location="NYC",
        url=url, posted_date="2026-10-06", source="greenhouse",
    )


def test_new_url_not_seen(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    assert not store.is_seen("https://example.com/job/1")


def test_mark_seen_then_is_seen(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_seen(job)
    assert store.is_seen(job.url)


def test_mark_seen_idempotent(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_seen(job)
    store.mark_seen(job)
    assert store.is_seen(job.url)


def test_mark_seen_batch(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    jobs = [_make_job(f"https://example.com/job/{i}") for i in range(5)]
    store.mark_seen_batch(jobs)
    for j in jobs:
        assert store.is_seen(j.url)


def test_different_urls_independent(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    store.mark_seen(_make_job("https://a.com/1"))
    assert not store.is_seen("https://a.com/2")


def test_content_hash_stored(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_seen(job)
    row = store._conn.execute(
        "SELECT content_hash, source FROM seen_jobs WHERE url = ?", (job.url,)
    ).fetchone()
    assert row is not None
    assert row[0] == job.content_hash()
    assert row[1] == "greenhouse"
    store.close()


def test_is_duplicate_content_cross_source(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job1 = Job.from_fields(
        title="SDE", company="Acme", location="NYC",
        url="https://greenhouse.io/acme/1", posted_date=None, source="greenhouse",
    )
    job2 = Job.from_fields(
        title="SDE", company="Acme", location="Remote",
        url="https://remoteok.com/jobs/sde-acme", posted_date=None, source="remoteok",
    )
    store.mark_seen(job1)
    assert store.is_duplicate_content(job2) is True
    store.close()


def test_is_duplicate_content_same_source_not_duplicate(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_seen(job)
    assert store.is_duplicate_content(job) is False
    store.close()


def test_not_delivered_until_marked(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    assert not store.is_delivered("https://example.com/job/1", "backend")


def test_mark_delivered_then_is_delivered(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_delivered_batch([job], "backend")
    assert store.is_delivered(job.url, "backend")


def test_delivered_is_per_watch_role(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_delivered_batch([job], "backend")
    assert not store.is_delivered(job.url, "frontend")


def test_mark_delivered_batch_idempotent(tmp_path):
    store = DedupStore(tmp_path / "test.db")
    job = _make_job()
    store.mark_delivered_batch([job], "backend")
    store.mark_delivered_batch([job], "backend")
    assert store.is_delivered(job.url, "backend")
