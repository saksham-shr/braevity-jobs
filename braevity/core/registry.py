import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class BoardRegistry:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS board_registry ("
            "id TEXT PRIMARY KEY,"
            "ats TEXT NOT NULL,"
            "token TEXT NOT NULL,"
            "company_name TEXT,"
            "discovered_from TEXT,"
            "last_fetched TEXT,"
            "job_count INTEGER DEFAULT 0,"
            "fail_count INTEGER DEFAULT 0,"
            "active INTEGER DEFAULT 1,"
            "created_at TEXT"
            ")"
        )
        self._conn.commit()

    def register(
        self, ats: str, token: str,
        company_name: str | None = None,
        discovered_from: str = "seed",
    ) -> bool:
        board_id = f"{ats}:{token}"
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._conn.execute(
                "INSERT INTO board_registry "
                "(id, ats, token, company_name, discovered_from, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (board_id, ats, token, company_name, discovered_from, now),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_active_boards(self, ats: str | None = None) -> list[dict]:
        if ats:
            rows = self._conn.execute(
                "SELECT * FROM board_registry WHERE active = 1 AND ats = ? "
                "ORDER BY job_count DESC",
                (ats,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM board_registry WHERE active = 1 "
                "ORDER BY job_count DESC",
            ).fetchall()
        return [dict(r) for r in rows]

    def update_after_fetch(self, board_id: str, job_count: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE board_registry SET last_fetched = ?, job_count = ?, "
            "fail_count = 0 WHERE id = ?",
            (now, job_count, board_id),
        )
        self._conn.commit()

    def record_failure(self, board_id: str) -> None:
        self._conn.execute(
            "UPDATE board_registry SET fail_count = fail_count + 1 WHERE id = ?",
            (board_id,),
        )
        self._conn.execute(
            "UPDATE board_registry SET active = 0 WHERE id = ? AND fail_count >= 3",
            (board_id,),
        )
        self._conn.commit()

    def board_count(self, ats: str | None = None) -> int:
        if ats:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM board_registry WHERE ats = ?", (ats,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM board_registry",
            ).fetchone()
        return row[0]

    def close(self) -> None:
        self._conn.close()
