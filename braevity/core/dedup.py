import json
import sqlite3
from dataclasses import asdict
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
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS delivered_jobs ("
            "url TEXT, watch_role TEXT, delivered_at TEXT, "
            "PRIMARY KEY(url, watch_role))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS pending_delivery ("
            "url TEXT, watch_role TEXT, job_json TEXT, created_at TEXT, "
            "PRIMARY KEY(url, watch_role))"
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

    def is_delivered(self, url: str, watch_role: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM delivered_jobs WHERE url = ? AND watch_role = ?",
            (url, watch_role),
        ).fetchone()
        return row is not None

    def mark_delivered_batch(self, jobs: list[Job], watch_role: str) -> None:
        self._conn.executemany(
            "INSERT OR IGNORE INTO delivered_jobs (url, watch_role, delivered_at) VALUES (?, ?, ?)",
            [(j.url, watch_role, j.found_at) for j in jobs],
        )
        self._conn.commit()

    def add_pending_batch(self, jobs: list[Job], watch_role: str) -> None:
        """A job was already marked seen (fetch-dedup) but failed to export
        or notify — persist it so a crash doesn't lose it permanently, since
        it won't come back from a future fetch cycle once seen."""
        self._conn.executemany(
            "INSERT OR REPLACE INTO pending_delivery (url, watch_role, job_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            [(j.url, watch_role, json.dumps(asdict(j)), j.found_at) for j in jobs],
        )
        self._conn.commit()

    def get_pending(self, watch_role: str) -> list[Job]:
        rows = self._conn.execute(
            "SELECT job_json FROM pending_delivery WHERE watch_role = ?", (watch_role,),
        ).fetchall()
        return [Job(**json.loads(row[0])) for row in rows]

    def clear_pending_batch(self, jobs: list[Job], watch_role: str) -> None:
        self._conn.executemany(
            "DELETE FROM pending_delivery WHERE url = ? AND watch_role = ?",
            [(j.url, watch_role) for j in jobs],
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
