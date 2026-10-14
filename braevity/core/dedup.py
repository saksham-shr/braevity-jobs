import sqlite3
from pathlib import Path
from braevity.core.models import Job


class DedupStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_jobs ("
            "url TEXT PRIMARY KEY, content_hash TEXT, title TEXT, "
            "company TEXT, source TEXT, first_seen TEXT, last_seen TEXT)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_hash "
            "ON seen_jobs(content_hash)"
        )
        self._conn.commit()

    def is_seen(self, url: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_jobs WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def is_duplicate_content(self, job: Job) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_jobs WHERE content_hash = ? AND source != ?",
            (job.content_hash(), job.source),
        ).fetchone()
        return row is not None

    def mark_seen(self, job: Job) -> None:
        self._conn.execute(
            "INSERT INTO seen_jobs (url, content_hash, title, company, source, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET last_seen = excluded.last_seen",
            (job.url, job.content_hash(), job.title, job.company,
             job.source, job.found_at, job.found_at),
        )
        self._conn.commit()

    def mark_seen_batch(self, jobs: list[Job]) -> None:
        self._conn.executemany(
            "INSERT INTO seen_jobs (url, content_hash, title, company, source, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET last_seen = excluded.last_seen",
            [(j.url, j.content_hash(), j.title, j.company,
              j.source, j.found_at, j.found_at) for j in jobs],
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
