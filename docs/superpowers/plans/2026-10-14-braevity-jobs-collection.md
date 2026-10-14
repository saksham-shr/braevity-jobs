# Braevity Jobs Collection Infrastructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend braevity from a fixed-catalog ATS poller into a multi-source job collection system with auto-growing board registry, 4 aggregator APIs, cross-reference discovery, and Schema.org scraping.

**Architecture:** Two-tier async scheduler — fast cycle (30min) polls aggregator APIs and runs cross-ref discovery, slow cycle (6hr) polls all registered ATS boards and scrapes Schema.org. Board registry (SQLite) replaces `companies.yaml`, seeded from existing catalog and grown via cross-referencing apply_urls from aggregator results.

**Tech Stack:** Python 3.10+, aiohttp, sqlite3, click, openpyxl, pyyaml (all existing dependencies — no new deps)

**Spec:** `docs/superpowers/specs/2026-10-14-braevity-jobs-collection-design.md`

## Global Constraints

- Python >=3.10, no new dependencies beyond what `pyproject.toml` already lists
- All HTTP requests use `aiohttp.ClientSession` with `TCPConnector(limit=10)`
- Rate limiting: 1 req/sec for aggregators, `asyncio.Semaphore` per ATS (greenhouse=5, lever=5, workday=3, ashby=5)
- All source `fetch_*` methods must catch exceptions and return `[]` on failure (never crash the scheduler)
- `Job` dataclass stays `frozen=True`
- SQLite for all persistence (no external DB)
- `source_ats` field renamed to `source` everywhere — covers both ATS and aggregator names

## Review Focus

1. **Empty/malformed aggregator response**: aggregator returns `[]`, `null`, HTML instead of JSON, or truncated JSON — each source must handle gracefully without crashing scheduler
2. **Cross-ref pattern extraction with malformed URLs**: `apply_url` contains unexpected format (relative URL, fragment-only, `javascript:void(0)`) — `crossref.py` must not register garbage board tokens
3. **SQLite concurrent access during two-tier scheduling**: fast and slow cycles may write to `seen_jobs` or `board_registry` simultaneously — ensure each cycle uses its own `DedupStore`/`BoardRegistry` instance (SQLite WAL mode or separate connections)
4. **Board registry deactivation edge case**: board returns 404 once due to transient issue, should not be deactivated — needs `fail_count` tracking, deactivate only at 3
5. **Dedup content_hash collision**: two different jobs at different companies could collide if `sha256(lower(title) + lower(company))` matches due to concatenation ambiguity (e.g., title="Senior" company="Dev Engineer" vs title="Senior Dev" company="Engineer") — use separator in hash input

---

### Task 1: Update Job Model

**Files:**
- Modify: `braevity/core/models.py`
- Modify: `tests/core/test_models.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `Job` dataclass with new fields: `salary_min: int | None`, `salary_max: int | None`, `salary_currency: str | None`, `tags: list[str]`, `description: str | None`, `remote: bool`, `employment_type: str | None`, `apply_url: str | None`, `source_id: str | None`. Field `source_ats` renamed to `source`. `Job.from_fields()` updated with new params (all optional with defaults). `Job.content_hash() -> str` class method added.

- [ ] **Step 1: Write failing test for new Job fields**

In `tests/core/test_models.py`, add:

```python
def test_job_new_fields():
    job = Job.from_fields(
        title="Backend Engineer",
        company="Stripe",
        location="Remote",
        url="https://boards.greenhouse.io/stripe/jobs/123",
        posted_date="2026-10-06",
        source="greenhouse",
        salary_min=120000,
        salary_max=180000,
        salary_currency="USD",
        tags=["python", "aws"],
        description="Build APIs",
        remote=True,
        employment_type="full-time",
        apply_url="https://boards.greenhouse.io/stripe/jobs/123/apply",
        source_id="gh-123",
    )
    assert job.salary_min == 120000
    assert job.salary_max == 180000
    assert job.salary_currency == "USD"
    assert job.tags == ["python", "aws"]
    assert job.description == "Build APIs"
    assert job.remote is True
    assert job.employment_type == "full-time"
    assert job.apply_url == "https://boards.greenhouse.io/stripe/jobs/123/apply"
    assert job.source_id == "gh-123"
    assert job.source == "greenhouse"


def test_job_new_fields_defaults():
    job = Job.from_fields(
        title="SDE", company="X", location=None,
        url="https://x.com/1", posted_date=None, source="lever",
    )
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.salary_currency is None
    assert job.tags == []
    assert job.description is None
    assert job.remote is False
    assert job.employment_type is None
    assert job.apply_url is None
    assert job.source_id is None


def test_content_hash_deterministic():
    job1 = Job.from_fields(
        title="Backend Engineer", company="Stripe", location=None,
        url="https://a.com/1", posted_date=None, source="greenhouse",
    )
    job2 = Job.from_fields(
        title="Backend Engineer", company="Stripe", location="NYC",
        url="https://b.com/2", posted_date=None, source="remoteok",
    )
    assert job1.content_hash() == job2.content_hash()


def test_content_hash_separator_prevents_collision():
    job1 = Job.from_fields(
        title="Senior", company="Dev Engineer", location=None,
        url="https://a.com/1", posted_date=None, source="greenhouse",
    )
    job2 = Job.from_fields(
        title="Senior Dev", company="Engineer", location=None,
        url="https://b.com/2", posted_date=None, source="lever",
    )
    assert job1.content_hash() != job2.content_hash()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_models.py -v`
Expected: FAIL — `from_fields()` does not accept new params, no `content_hash` method

- [ ] **Step 3: Update Job dataclass and from_fields**

Replace `braevity/core/models.py` with:

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    company: str
    location: str | None
    url: str
    posted_date: str | None
    source: str
    found_at: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    remote: bool = False
    employment_type: str | None = None
    apply_url: str | None = None
    source_id: str | None = None

    @classmethod
    def from_fields(
        cls,
        title: str,
        company: str,
        location: str | None,
        url: str,
        posted_date: str | None,
        source: str,
        salary_min: int | None = None,
        salary_max: int | None = None,
        salary_currency: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        remote: bool = False,
        employment_type: str | None = None,
        apply_url: str | None = None,
        source_id: str | None = None,
    ) -> "Job":
        job_id = sha256(url.encode()).hexdigest()
        found_at = datetime.now(timezone.utc).isoformat()
        return cls(
            id=job_id,
            title=title,
            company=company,
            location=location,
            url=url,
            posted_date=posted_date,
            source=source,
            found_at=found_at,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            tags=tags or [],
            description=description,
            remote=remote,
            employment_type=employment_type,
            apply_url=apply_url,
            source_id=source_id,
        )

    def content_hash(self) -> str:
        key = f"{self.title.lower()}\x00{self.company.lower()}"
        return sha256(key.encode()).hexdigest()
```

- [ ] **Step 4: Update existing tests — rename source_ats to source**

In `tests/core/test_models.py`, change all `source_ats=` to `source=` in existing tests:

```python
# test_job_from_url_generates_id: source_ats="greenhouse" → source="greenhouse"
# test_job_id_deterministic_from_url: source_ats="lever" → source="lever"
# test_job_none_location_allowed: source_ats="ashby" → source="ashby"
```

Also update `tests/core/test_dedup.py` `_make_job` helper: `source_ats="greenhouse"` → `source="greenhouse"`.

- [ ] **Step 5: Update all source files — rename source_ats to source**

In each of these files, change `source_ats=self.name` to `source=self.name`:
- `braevity/sources/greenhouse.py` (line 42)
- `braevity/sources/lever.py` (line 56)
- `braevity/sources/workday.py` (line 66)
- `braevity/sources/ashby.py` (line 68)

In `braevity/core/exporter.py` line 43, change `job.source_ats` to `job.source`.

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add braevity/core/models.py braevity/sources/greenhouse.py braevity/sources/lever.py braevity/sources/workday.py braevity/sources/ashby.py braevity/core/exporter.py tests/core/test_models.py tests/core/test_dedup.py
git commit -m "feat: extend Job model with salary, tags, description, remote fields

Rename source_ats to source. Add content_hash() for cross-source dedup.
New optional fields: salary_min/max, salary_currency, tags, description,
remote, employment_type, apply_url, source_id."
```

---

### Task 2: Board Registry

**Files:**
- Create: `braevity/core/registry.py`
- Create: `tests/core/test_registry.py`

**Interfaces:**
- Consumes: `braevity.config.config_dir() -> Path`
- Produces: `BoardRegistry` class with methods:
  - `__init__(self, db_path: Path) -> None`
  - `register(self, ats: str, token: str, company_name: str | None = None, discovered_from: str = "seed") -> bool` — returns True if new
  - `get_active_boards(self, ats: str | None = None) -> list[dict]` — returns `[{"id": ..., "ats": ..., "token": ..., "company_name": ..., ...}]`
  - `update_after_fetch(self, board_id: str, job_count: int) -> None` — updates last_fetched, job_count, resets fail tracking
  - `record_failure(self, board_id: str) -> None` — increments fail count, deactivates at 3
  - `board_count(self, ats: str | None = None) -> int`
  - `close(self) -> None`

- [ ] **Step 1: Write failing tests**

Create `tests/core/test_registry.py`:

```python
from braevity.core.registry import BoardRegistry


def test_register_new_board(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    assert reg.register("greenhouse", "stripe", "Stripe", "seed") is True
    assert reg.board_count() == 1
    reg.close()


def test_register_duplicate_ignored(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "stripe", "Stripe", "seed")
    assert reg.register("greenhouse", "stripe", "Stripe", "seed") is False
    assert reg.board_count() == 1
    reg.close()


def test_get_active_boards(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "stripe", "Stripe", "seed")
    reg.register("lever", "figma", "Figma", "seed")
    boards = reg.get_active_boards()
    assert len(boards) == 2
    gh_boards = reg.get_active_boards("greenhouse")
    assert len(gh_boards) == 1
    assert gh_boards[0]["token"] == "stripe"
    reg.close()


def test_update_after_fetch(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "stripe", "Stripe", "seed")
    reg.update_after_fetch("greenhouse:stripe", 42)
    boards = reg.get_active_boards()
    assert boards[0]["job_count"] == 42
    assert boards[0]["last_fetched"] is not None
    reg.close()


def test_record_failure_deactivates_at_three(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "gone", "Gone Co", "seed")
    reg.record_failure("greenhouse:gone")
    reg.record_failure("greenhouse:gone")
    assert len(reg.get_active_boards()) == 1
    reg.record_failure("greenhouse:gone")
    assert len(reg.get_active_boards()) == 0
    reg.close()


def test_update_after_fetch_resets_fail_count(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "flaky", "Flaky", "seed")
    reg.record_failure("greenhouse:flaky")
    reg.record_failure("greenhouse:flaky")
    reg.update_after_fetch("greenhouse:flaky", 10)
    reg.record_failure("greenhouse:flaky")
    assert len(reg.get_active_boards()) == 1
    reg.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'braevity.core.registry'`

- [ ] **Step 3: Implement BoardRegistry**

Create `braevity/core/registry.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_registry.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add braevity/core/registry.py tests/core/test_registry.py
git commit -m "feat: add BoardRegistry for auto-growing ATS board tracking"
```

---

### Task 3: Updated DedupStore with Content Hash

**Files:**
- Modify: `braevity/core/dedup.py`
- Modify: `tests/core/test_dedup.py`

**Interfaces:**
- Consumes: `Job.content_hash() -> str` from Task 1
- Produces: Updated `DedupStore` with:
  - `mark_seen(self, job: Job) -> None` — now stores `content_hash`, `source`, `last_seen`
  - `mark_seen_batch(self, jobs: list[Job]) -> None` — same
  - `is_duplicate_content(self, job: Job) -> bool` — True if same `content_hash` exists from different source
  - `is_seen(self, url: str) -> bool` — unchanged

- [ ] **Step 1: Write failing tests for content hash dedup**

Add to `tests/core/test_dedup.py`:

```python
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
    from braevity.core.models import Job

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_dedup.py -v`
Expected: FAIL — `seen_jobs` table missing new columns, no `is_duplicate_content` method

- [ ] **Step 3: Update DedupStore**

Replace `braevity/core/dedup.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_dedup.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full suite to check nothing broke**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add braevity/core/dedup.py tests/core/test_dedup.py
git commit -m "feat: add content_hash cross-source dedup to DedupStore"
```

---

### Task 4: BaseAggregator ABC and Aggregator Sources

**Files:**
- Modify: `braevity/sources/base.py`
- Create: `braevity/sources/remoteok.py`
- Create: `braevity/sources/jobicy.py`
- Create: `braevity/sources/arbeitnow.py`
- Create: `braevity/sources/himalayas.py`
- Create: `tests/sources/test_remoteok.py`
- Create: `tests/sources/test_jobicy.py`
- Create: `tests/sources/test_arbeitnow.py`
- Create: `tests/sources/test_himalayas.py`

**Interfaces:**
- Consumes: `Job.from_fields()` from Task 1
- Produces: `BaseAggregator` ABC with `fetch_all_jobs(session, offset) -> list[Job]` and `fetch_paginated(session) -> list[Job]`. Four concrete implementations: `RemoteOKSource`, `JobicySource`, `ArbeitnowSource`, `HimalayasSource`.

- [ ] **Step 1: Add BaseAggregator to base.py**

Add after `BaseSource` class in `braevity/sources/base.py`:

```python
class BaseAggregator(ABC):
    name: str

    @abstractmethod
    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        ...

    @abstractmethod
    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        ...
```

- [ ] **Step 2: Write integration test for RemoteOK**

Create `tests/sources/test_remoteok.py`:

```python
import asyncio
import aiohttp
from braevity.sources.remoteok import RemoteOKSource


def test_remoteok_fetch_real_api():
    async def _run():
        source = RemoteOKSource()
        async with aiohttp.ClientSession() as session:
            jobs = await source.fetch_all_jobs(session)
        return jobs

    jobs = asyncio.run(_run())
    assert len(jobs) > 0
    job = jobs[0]
    assert job.title
    assert job.company
    assert job.url
    assert job.source == "remoteok"
```

- [ ] **Step 3: Implement RemoteOKSource**

Create `braevity/sources/remoteok.py`:

```python
import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


class RemoteOKSource(BaseAggregator):
    name = "remoteok"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        url = REMOTEOK_API
        if offset:
            url = f"{url}?offset={offset}"
        try:
            resp = await session.get(
                url, headers={"User-Agent": "braevity/0.1"}
            )
            if resp.status != 200:
                logger.warning("RemoteOK returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("RemoteOK failed: %s", e)
            return []

        if not isinstance(data, list):
            return []

        jobs = []
        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            position = (item.get("position") or "").strip()
            if not position:
                continue
            company = (item.get("company") or "").strip() or "Unknown"
            slug = item.get("slug", "")
            job_url = f"https://remoteok.com/remote-jobs/{slug}" if slug else item.get("url", "")
            if not job_url:
                continue

            tags = item.get("tags") or []
            if isinstance(tags, str):
                tags = [tags]

            jobs.append(Job.from_fields(
                title=position,
                company=company,
                location=item.get("location") or "Remote",
                url=job_url,
                posted_date=item.get("date"),
                source=self.name,
                salary_min=_parse_int(item.get("salary_min")),
                salary_max=_parse_int(item.get("salary_max")),
                salary_currency="USD",
                tags=tags,
                description=item.get("description"),
                remote=True,
                employment_type=None,
                apply_url=item.get("apply_url") or item.get("url"),
                source_id=str(item.get("id", "")),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        all_jobs = []
        offset = 0
        while True:
            batch = await self.fetch_all_jobs(session, offset)
            if not batch:
                break
            all_jobs.extend(batch)
            if len(batch) < 50:
                break
            offset += len(batch)
        return all_jobs


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run RemoteOK test**

Run: `pytest tests/sources/test_remoteok.py -v`
Expected: PASS (hits real API)

- [ ] **Step 5: Write integration test for Jobicy**

Create `tests/sources/test_jobicy.py`:

```python
import asyncio
import aiohttp
from braevity.sources.jobicy import JobicySource


def test_jobicy_fetch_real_api():
    async def _run():
        source = JobicySource()
        async with aiohttp.ClientSession() as session:
            jobs = await source.fetch_all_jobs(session)
        return jobs

    jobs = asyncio.run(_run())
    assert len(jobs) > 0
    job = jobs[0]
    assert job.title
    assert job.company
    assert job.url
    assert job.source == "jobicy"
```

- [ ] **Step 6: Implement JobicySource**

Create `braevity/sources/jobicy.py`:

```python
import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


class JobicySource(BaseAggregator):
    name = "jobicy"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        params = {"count": 50}
        try:
            resp = await session.get(
                JOBICY_API, params=params,
                headers={"User-Agent": "braevity/0.1"},
            )
            if resp.status != 200:
                logger.warning("Jobicy returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("Jobicy failed: %s", e)
            return []

        job_list = data.get("jobs") or []
        jobs = []
        for item in job_list:
            title = (item.get("jobTitle") or "").strip()
            if not title:
                continue
            job_url = (item.get("url") or "").strip()
            if not job_url:
                continue

            industry = item.get("jobIndustry") or []
            job_type = item.get("jobType") or []
            emp_type = job_type[0].lower() if job_type else None

            jobs.append(Job.from_fields(
                title=title,
                company=(item.get("companyName") or "").strip() or "Unknown",
                location=item.get("jobGeo"),
                url=job_url,
                posted_date=item.get("pubDate"),
                source=self.name,
                salary_min=_parse_int(item.get("salaryMin")),
                salary_max=_parse_int(item.get("salaryMax")),
                salary_currency=item.get("salaryCurrency"),
                tags=industry if isinstance(industry, list) else [industry],
                description=item.get("jobDescription"),
                remote=True,
                employment_type=emp_type,
                apply_url=job_url,
                source_id=str(item.get("id", "")),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        return await self.fetch_all_jobs(session)


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 7: Run Jobicy test**

Run: `pytest tests/sources/test_jobicy.py -v`
Expected: PASS

- [ ] **Step 8: Write integration test for Arbeitnow**

Create `tests/sources/test_arbeitnow.py`:

```python
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
```

- [ ] **Step 9: Implement ArbeitnowSource**

Create `braevity/sources/arbeitnow.py`:

```python
import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(BaseAggregator):
    name = "arbeitnow"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        params = {}
        if offset:
            params["page"] = (offset // 300) + 1
        try:
            resp = await session.get(
                ARBEITNOW_API, params=params,
                headers={"User-Agent": "braevity/0.1"},
            )
            if resp.status != 200:
                logger.warning("Arbeitnow returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("Arbeitnow failed: %s", e)
            return []

        job_list = data.get("data") or []
        jobs = []
        for item in job_list:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            job_url = (item.get("url") or "").strip()
            if not job_url:
                continue

            tags = item.get("tags") or []
            remote = bool(item.get("remote"))

            jobs.append(Job.from_fields(
                title=title,
                company=(item.get("company_name") or "").strip() or "Unknown",
                location=item.get("location"),
                url=job_url,
                posted_date=item.get("created_at"),
                source=self.name,
                tags=tags,
                description=item.get("description"),
                remote=remote,
                employment_type=_first_or_none(item.get("job_types")),
                apply_url=job_url,
                source_id=item.get("slug"),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        return await self.fetch_all_jobs(session)


def _first_or_none(val) -> str | None:
    if isinstance(val, list) and val:
        return val[0].lower()
    return None
```

- [ ] **Step 10: Run Arbeitnow test**

Run: `pytest tests/sources/test_arbeitnow.py -v`
Expected: PASS

- [ ] **Step 11: Write integration test for Himalayas**

Create `tests/sources/test_himalayas.py`:

```python
import asyncio
import aiohttp
from braevity.sources.himalayas import HimalayasSource


def test_himalayas_fetch_real_api():
    async def _run():
        source = HimalayasSource()
        async with aiohttp.ClientSession() as session:
            jobs = await source.fetch_all_jobs(session)
        return jobs

    jobs = asyncio.run(_run())
    assert len(jobs) > 0
    job = jobs[0]
    assert job.title
    assert job.company
    assert job.url
    assert job.source == "himalayas"
```

- [ ] **Step 12: Implement HimalayasSource**

Create `braevity/sources/himalayas.py`:

```python
import logging
from aiohttp import ClientSession
from braevity.core.models import Job
from braevity.sources.base import BaseAggregator

logger = logging.getLogger(__name__)

HIMALAYAS_API = "https://himalayas.app/jobs/api"


class HimalayasSource(BaseAggregator):
    name = "himalayas"

    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        params = {"limit": 50, "offset": offset}
        try:
            resp = await session.get(
                HIMALAYAS_API, params=params,
                headers={"User-Agent": "braevity/0.1"},
            )
            if resp.status != 200:
                logger.warning("Himalayas returned %d", resp.status)
                return []
            data = await resp.json(content_type=None)
        except Exception as e:
            logger.warning("Himalayas failed: %s", e)
            return []

        job_list = data.get("jobs") or []
        jobs = []
        for item in job_list:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            job_url = (item.get("guid") or item.get("applicationLink") or "").strip()
            if not job_url:
                continue

            categories = item.get("categories") or []
            if isinstance(categories, str):
                categories = [categories]

            jobs.append(Job.from_fields(
                title=title,
                company=(item.get("companyName") or "").strip() or "Unknown",
                location=_format_location(item.get("locationRestrictions")),
                url=job_url,
                posted_date=item.get("pubDate"),
                source=self.name,
                salary_min=_parse_int(item.get("minSalary")),
                salary_max=_parse_int(item.get("maxSalary")),
                salary_currency=item.get("currency"),
                tags=categories,
                description=item.get("description"),
                remote=True,
                employment_type=(item.get("employmentType") or "").lower() or None,
                apply_url=item.get("applicationLink"),
                source_id=item.get("guid"),
            ))
        return jobs

    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        all_jobs = []
        offset = 0
        while True:
            batch = await self.fetch_all_jobs(session, offset)
            if not batch:
                break
            all_jobs.extend(batch)
            if len(batch) < 50:
                break
            offset += len(batch)
        return all_jobs


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _format_location(restrictions) -> str | None:
    if not restrictions:
        return "Remote"
    if isinstance(restrictions, list):
        return ", ".join(str(r) for r in restrictions) or "Remote"
    return str(restrictions)
```

- [ ] **Step 13: Run Himalayas test**

Run: `pytest tests/sources/test_himalayas.py -v`
Expected: PASS

- [ ] **Step 14: Run full suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 15: Commit**

```bash
git add braevity/sources/base.py braevity/sources/remoteok.py braevity/sources/jobicy.py braevity/sources/arbeitnow.py braevity/sources/himalayas.py tests/sources/test_remoteok.py tests/sources/test_jobicy.py tests/sources/test_arbeitnow.py tests/sources/test_himalayas.py
git commit -m "feat: add 4 aggregator sources (RemoteOK, Jobicy, Arbeitnow, Himalayas)"
```

---

### Task 5: Cross-Reference Discovery

**Files:**
- Create: `braevity/sources/crossref.py`
- Create: `tests/sources/test_crossref.py`

**Interfaces:**
- Consumes: `Job` from Task 1 (reads `apply_url` and `url` fields), `BoardRegistry.register()` from Task 2
- Produces: `extract_board_tokens(jobs: list[Job]) -> list[dict]` returning `[{"ats": "greenhouse", "token": "stripe"}]`, and `discover_from_jobs(jobs: list[Job], registry: BoardRegistry) -> int` returning count of new boards registered

- [ ] **Step 1: Write failing tests**

Create `tests/sources/test_crossref.py`:

```python
from braevity.core.models import Job
from braevity.sources.crossref import extract_board_tokens, discover_from_jobs
from braevity.core.registry import BoardRegistry


def _job_with_apply_url(apply_url: str) -> Job:
    return Job.from_fields(
        title="SDE", company="Acme", location=None,
        url="https://remoteok.com/jobs/1", posted_date=None,
        source="remoteok", apply_url=apply_url,
    )


def test_extract_greenhouse_token():
    jobs = [_job_with_apply_url("https://boards.greenhouse.io/stripe/jobs/123")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "greenhouse", "token": "stripe", "company": "Acme"} in tokens


def test_extract_lever_token():
    jobs = [_job_with_apply_url("https://jobs.lever.co/figma/abc-123")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "lever", "token": "figma", "company": "Acme"} in tokens


def test_extract_ashby_token():
    jobs = [_job_with_apply_url("https://jobs.ashbyhq.com/linear/job-id")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "ashby", "token": "linear", "company": "Acme"} in tokens


def test_extract_workday_token():
    jobs = [_job_with_apply_url("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/123")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "workday", "token": "nvidia", "company": "Acme"} in tokens


def test_extract_no_match():
    jobs = [_job_with_apply_url("https://company.com/careers/apply")]
    tokens = extract_board_tokens(jobs)
    assert tokens == []


def test_extract_skips_none_apply_url():
    job = Job.from_fields(
        title="SDE", company="Acme", location=None,
        url="https://remoteok.com/1", posted_date=None, source="remoteok",
    )
    tokens = extract_board_tokens([job])
    assert tokens == []


def test_extract_malformed_url_no_crash():
    jobs = [_job_with_apply_url("javascript:void(0)")]
    tokens = extract_board_tokens(jobs)
    assert tokens == []


def test_discover_from_jobs_registers(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    jobs = [_job_with_apply_url("https://boards.greenhouse.io/newco/jobs/1")]
    count = discover_from_jobs(jobs, reg)
    assert count == 1
    boards = reg.get_active_boards("greenhouse")
    assert len(boards) == 1
    assert boards[0]["token"] == "newco"
    assert boards[0]["discovered_from"] == "crossref"
    reg.close()


def test_discover_from_jobs_skips_existing(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "existing", "Existing Co", "seed")
    jobs = [_job_with_apply_url("https://boards.greenhouse.io/existing/jobs/1")]
    count = discover_from_jobs(jobs, reg)
    assert count == 0
    reg.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sources/test_crossref.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement crossref.py**

Create `braevity/sources/crossref.py`:

```python
import re
import logging
from braevity.core.models import Job
from braevity.core.registry import BoardRegistry

logger = logging.getLogger(__name__)

BOARD_PATTERNS: dict[str, list[re.Pattern]] = {
    "greenhouse": [
        re.compile(r"boards\.greenhouse\.io/(\w+)"),
        re.compile(r"job-boards\.greenhouse\.io/(\w+)"),
    ],
    "lever": [
        re.compile(r"jobs\.lever\.co/([\w-]+)"),
    ],
    "ashby": [
        re.compile(r"jobs\.ashbyhq\.com/([\w-]+)"),
    ],
    "workday": [
        re.compile(r"([\w-]+)\.wd\d+\.myworkdayjobs\.com"),
    ],
}


def extract_board_tokens(jobs: list[Job]) -> list[dict]:
    seen = set()
    results = []
    for job in jobs:
        for url_field in (job.apply_url, job.url):
            if not url_field or not url_field.startswith("http"):
                continue
            for ats, patterns in BOARD_PATTERNS.items():
                for pattern in patterns:
                    match = pattern.search(url_field)
                    if match:
                        token = match.group(1).lower()
                        key = f"{ats}:{token}"
                        if key not in seen:
                            seen.add(key)
                            results.append({
                                "ats": ats,
                                "token": token,
                                "company": job.company,
                            })
    return results


def discover_from_jobs(jobs: list[Job], registry: BoardRegistry) -> int:
    tokens = extract_board_tokens(jobs)
    new_count = 0
    for entry in tokens:
        if registry.register(
            entry["ats"], entry["token"],
            company_name=entry["company"],
            discovered_from="crossref",
        ):
            logger.info(
                "Discovered %s:%s from cross-ref (%s)",
                entry["ats"], entry["token"], entry["company"],
            )
            new_count += 1
    return new_count
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/sources/test_crossref.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add braevity/sources/crossref.py tests/sources/test_crossref.py
git commit -m "feat: add cross-reference discovery — extract ATS board tokens from aggregator apply_urls"
```

---

### Task 6: Seed Import and Migration

**Files:**
- Create: `braevity/catalog/seed_boards.yaml`
- Modify: `braevity/sources/base.py` (update `load_catalog` to also seed registry)
- Create: `braevity/core/migration.py`
- Create: `tests/core/test_migration.py`

**Interfaces:**
- Consumes: `BoardRegistry.register()` from Task 2, `braevity.config.config_dir()`, existing `braevity/catalog/companies.yaml`
- Produces:
  - `seed_registry(registry: BoardRegistry) -> int` — imports `seed_boards.yaml` into registry, returns count of new boards
  - `migrate_catalog(registry: BoardRegistry) -> int` — imports old `companies.yaml` format into registry, returns count

- [ ] **Step 1: Create seed_boards.yaml**

Create `braevity/catalog/seed_boards.yaml` — combine existing companies.yaml tokens with additional well-known boards:

```yaml
greenhouse:
  - razorpay
  - cred
  - phonepe
  - meesho
  - paytm
  - atlassian
  - stripe
  - vercel
  - cloudflare
  - gitlab
  - datadoghq
  - snowflake
  - databricks
  - notion
  - asana
  - twilio
  - mongodb
  - hashicorp
  - confluent
  - mensabrands
  - airbnb
  - coinbase
  - doordash
  - instacart
  - gusto
  - brex
  - plaid
  - airtable
  - figma
  - discord
  - canva
  - ramp

lever:
  - zepto
  - swiggy
  - postman
  - figma
  - unacademy
  - coinswitch
  - chargebee
  - curefit
  - urbancompany
  - coindcx
  - netflix
  - nerdwallet
  - lucidmotors

ashby:
  - linear
  - setu
  - plum
  - ramp
  - notion

workday:
  - microsoft:https://jobs.careers.microsoft.com
  - netflix:https://jobs.netflix.com
  - nvidia:https://nvidia.wd5.myworkdayjobs.com
  - salesforce:https://salesforce.wd12.myworkdayjobs.com
  - adobe:https://adobe.wd5.myworkdayjobs.com
  - cisco:https://cisco.wd1.myworkdayjobs.com
  - intel:https://intel.wd1.myworkdayjobs.com
  - dell:https://dell.wd1.myworkdayjobs.com
  - vmware:https://vmware.wd1.myworkdayjobs.com
  - hp:https://hp.wd5.myworkdayjobs.com
  - amd:https://amd.wd1.myworkdayjobs.com
  - deloitte:https://deloitte.wd5.myworkdayjobs.com
  - kpmg:https://kpmg.wd5.myworkdayjobs.com
  - accenture:https://accenture.wd3.myworkdayjobs.com
  - elastic:https://elastic.wd3.myworkdayjobs.com
  - okta:https://okta.wd1.myworkdayjobs.com
```

- [ ] **Step 2: Write failing tests**

Create `tests/core/test_migration.py`:

```python
from pathlib import Path
from braevity.core.migration import seed_registry, migrate_catalog
from braevity.core.registry import BoardRegistry


def test_seed_registry(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    count = seed_registry(reg)
    assert count > 30
    boards = reg.get_active_boards()
    assert len(boards) > 30
    gh = reg.get_active_boards("greenhouse")
    assert any(b["token"] == "stripe" for b in gh)
    reg.close()


def test_seed_registry_idempotent(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    count1 = seed_registry(reg)
    count2 = seed_registry(reg)
    assert count2 == 0
    reg.close()


def test_migrate_catalog(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    count = migrate_catalog(reg)
    assert count > 0
    boards = reg.get_active_boards("greenhouse")
    assert any(b["token"] == "razorpay" for b in boards)
    assert any(b["company_name"] == "Razorpay" for b in boards)
    reg.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/core/test_migration.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Implement migration.py**

Create `braevity/core/migration.py`:

```python
import logging
from pathlib import Path
import yaml
from braevity.core.registry import BoardRegistry

logger = logging.getLogger(__name__)


def _seed_path() -> Path:
    return Path(__file__).parent.parent / "catalog" / "seed_boards.yaml"


def _catalog_path() -> Path:
    return Path(__file__).parent.parent / "catalog" / "companies.yaml"


def seed_registry(registry: BoardRegistry) -> int:
    path = _seed_path()
    if not path.exists():
        logger.warning("Seed file not found: %s", path)
        return 0

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    count = 0
    for ats, tokens in data.items():
        for entry in tokens:
            if isinstance(entry, str):
                if ats == "workday" and ":" in entry:
                    token, _ = entry.split(":", 1)
                    url = entry.split(":", 1)[1]
                    if registry.register(ats, url, company_name=token, discovered_from="seed"):
                        count += 1
                else:
                    if registry.register(ats, entry, discovered_from="seed"):
                        count += 1
    return count


def migrate_catalog(registry: BoardRegistry) -> int:
    path = _catalog_path()
    if not path.exists():
        logger.warning("Catalog file not found: %s", path)
        return 0

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    count = 0
    for ats, companies in data.items():
        for company in companies:
            if not isinstance(company, dict):
                continue
            name = company.get("name", "")
            if ats == "greenhouse":
                token = company.get("board_token", "")
            elif ats == "lever":
                token = company.get("org", "")
            elif ats == "ashby":
                token = company.get("org", "")
            elif ats == "workday":
                token = company.get("url", "")
            else:
                continue
            if token and registry.register(ats, token, company_name=name, discovered_from="seed"):
                count += 1
    return count
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_migration.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add braevity/catalog/seed_boards.yaml braevity/core/migration.py tests/core/test_migration.py
git commit -m "feat: add seed_boards.yaml and migration from companies.yaml to board registry"
```

---

### Task 7: Schema.org Scraper

**Files:**
- Create: `braevity/sources/schema_org.py`
- Create: `tests/sources/test_schema_org.py`

**Interfaces:**
- Consumes: `Job.from_fields()` from Task 1
- Produces: `SchemaOrgScraper` with:
  - `scrape_page(self, session: ClientSession, url: str) -> list[Job]` — fetches HTML, extracts JSON-LD JobPosting(s)
  - `parse_jsonld(self, html: str, page_url: str) -> list[Job]` — pure parsing, no network (for testing)

- [ ] **Step 1: Write failing test for JSON-LD parsing**

Create `tests/sources/test_schema_org.py`:

```python
from braevity.sources.schema_org import SchemaOrgScraper


SAMPLE_HTML = '''
<html><head><title>Careers</title></head><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "Senior Backend Engineer",
  "hiringOrganization": {"@type": "Organization", "name": "Acme Corp"},
  "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": "San Francisco"}},
  "datePosted": "2026-10-01",
  "description": "Build cool stuff",
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "USD",
    "value": {"@type": "QuantitativeValue", "minValue": 150000, "maxValue": 220000}
  },
  "employmentType": "FULL_TIME",
  "jobLocationType": "TELECOMMUTE",
  "url": "https://acme.com/careers/senior-backend"
}
</script>
</body></html>
'''


def test_parse_jsonld_single_posting():
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(SAMPLE_HTML, "https://acme.com/careers")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Acme Corp"
    assert job.salary_min == 150000
    assert job.salary_max == 220000
    assert job.salary_currency == "USD"
    assert job.remote is True
    assert job.employment_type == "full_time"
    assert job.source == "schema.org"


def test_parse_jsonld_no_posting():
    html = '<html><body><script type="application/ld+json">{"@type": "Organization"}</script></body></html>'
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(html, "https://example.com")
    assert jobs == []


def test_parse_jsonld_malformed_json():
    html = '<html><body><script type="application/ld+json">NOT JSON</script></body></html>'
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(html, "https://example.com")
    assert jobs == []


SAMPLE_LIST_HTML = '''
<html><body>
<script type="application/ld+json">
[
  {"@type": "JobPosting", "title": "Job A", "hiringOrganization": {"name": "Co"}, "url": "https://co.com/a"},
  {"@type": "JobPosting", "title": "Job B", "hiringOrganization": {"name": "Co"}, "url": "https://co.com/b"}
]
</script>
</body></html>
'''


def test_parse_jsonld_array():
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(SAMPLE_LIST_HTML, "https://co.com/careers")
    assert len(jobs) == 2
    assert jobs[0].title == "Job A"
    assert jobs[1].title == "Job B"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/sources/test_schema_org.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement SchemaOrgScraper**

Create `braevity/sources/schema_org.py`:

```python
import json
import logging
import re
from aiohttp import ClientSession
from braevity.core.models import Job

logger = logging.getLogger(__name__)

JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class SchemaOrgScraper:
    name = "schema.org"

    async def scrape_page(self, session: ClientSession, url: str) -> list[Job]:
        try:
            resp = await session.get(
                url, headers={"User-Agent": "braevity/0.1"}, timeout=15
            )
            if resp.status != 200:
                return []
            html = await resp.text()
        except Exception as e:
            logger.warning("Schema.org scrape failed for %s: %s", url, e)
            return []
        return self.parse_jsonld(html, url)

    def parse_jsonld(self, html: str, page_url: str) -> list[Job]:
        matches = JSONLD_RE.findall(html)
        jobs = []
        for raw in matches:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, list):
                for item in data:
                    job = self._parse_posting(item, page_url)
                    if job:
                        jobs.append(job)
            elif isinstance(data, dict):
                if data.get("@graph"):
                    for item in data["@graph"]:
                        job = self._parse_posting(item, page_url)
                        if job:
                            jobs.append(job)
                else:
                    job = self._parse_posting(data, page_url)
                    if job:
                        jobs.append(job)
        return jobs

    def _parse_posting(self, data: dict, page_url: str) -> Job | None:
        if not isinstance(data, dict):
            return None
        schema_type = data.get("@type", "")
        if schema_type != "JobPosting":
            return None

        title = (data.get("title") or "").strip()
        if not title:
            return None

        org = data.get("hiringOrganization") or {}
        company = (org.get("name") or "").strip() if isinstance(org, dict) else str(org).strip()
        company = company or "Unknown"

        url = data.get("url") or page_url

        location = self._extract_location(data)
        salary_min, salary_max, currency = self._extract_salary(data)
        remote = data.get("jobLocationType") == "TELECOMMUTE"
        emp_type = (data.get("employmentType") or "").lower() or None

        return Job.from_fields(
            title=title,
            company=company,
            location=location,
            url=url,
            posted_date=data.get("datePosted"),
            source=self.name,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            description=data.get("description"),
            remote=remote,
            employment_type=emp_type,
            apply_url=data.get("directApply") if isinstance(data.get("directApply"), str) else url,
        )

    def _extract_location(self, data: dict) -> str | None:
        loc = data.get("jobLocation")
        if not loc:
            return None
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality"),
                    addr.get("addressRegion"),
                    addr.get("addressCountry"),
                ]
                return ", ".join(p for p in parts if p) or None
            return (loc.get("name") or "").strip() or None
        if isinstance(loc, str):
            return loc.strip() or None
        return None

    def _extract_salary(self, data: dict) -> tuple[int | None, int | None, str | None]:
        salary = data.get("baseSalary")
        if not salary or not isinstance(salary, dict):
            return None, None, None
        currency = salary.get("currency")
        value = salary.get("value")
        if isinstance(value, dict):
            return (
                _parse_int(value.get("minValue")),
                _parse_int(value.get("maxValue")),
                currency,
            )
        if isinstance(value, (int, float)):
            return int(value), int(value), currency
        return None, None, currency


def _parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/sources/test_schema_org.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add braevity/sources/schema_org.py tests/sources/test_schema_org.py
git commit -m "feat: add Schema.org JSON-LD scraper for JobPosting extraction"
```

---

### Task 8: Two-Tier Scheduler and Updated Exporter

**Files:**
- Modify: `braevity/core/scheduler.py`
- Modify: `braevity/core/exporter.py`

**Interfaces:**
- Consumes: `BoardRegistry` from Task 2, `DedupStore` from Task 3, all aggregator sources from Task 4, `discover_from_jobs()` from Task 5, `seed_registry()` and `migrate_catalog()` from Task 6, `SchemaOrgScraper` from Task 7, all existing ATS sources
- Produces:
  - `run_fast_cycle(config: dict, db_path: Path, registry_path: Path) -> int` — polls aggregators + cross-ref
  - `run_slow_cycle(config: dict, db_path: Path, registry_path: Path) -> int` — polls ATS boards from registry
  - `run_scheduler(config: dict) -> None` — two-tier loop
  - Updated `HEADERS` and `export_jobs` in exporter to include new Job fields

- [ ] **Step 1: Update exporter for new fields**

In `braevity/core/exporter.py`, update `HEADERS` and the `ws.append` call:

```python
HEADERS = [
    "Title", "Company", "Location", "Posted Date", "URL",
    "Source", "Salary Min", "Salary Max", "Currency",
    "Remote", "Type", "Tags", "Found At",
]
```

Update the `for job in jobs:` loop:

```python
    for job in jobs:
        ws.append([
            job.title,
            job.company,
            job.location or "",
            job.posted_date or "",
            job.url,
            job.source,
            job.salary_min or "",
            job.salary_max or "",
            job.salary_currency or "",
            "Yes" if job.remote else "No",
            job.employment_type or "",
            ", ".join(job.tags) if job.tags else "",
            job.found_at,
        ])
```

- [ ] **Step 2: Rewrite scheduler.py**

Replace `braevity/core/scheduler.py` with:

```python
import asyncio
import logging
from pathlib import Path
from aiohttp import ClientSession, TCPConnector
from braevity.core.models import Job
from braevity.core.dedup import DedupStore
from braevity.core.registry import BoardRegistry
from braevity.core.filter import filter_jobs
from braevity.core.exporter import export_jobs
from braevity.core.migration import seed_registry, migrate_catalog
from braevity.sources.crossref import discover_from_jobs
from braevity.sources.greenhouse import GreenhouseSource
from braevity.sources.lever import LeverSource
from braevity.sources.workday import WorkdaySource
from braevity.sources.ashby import AshbySource
from braevity.sources.remoteok import RemoteOKSource
from braevity.sources.jobicy import JobicySource
from braevity.sources.arbeitnow import ArbeitnowSource
from braevity.sources.himalayas import HimalayasSource

logger = logging.getLogger(__name__)

ATS_SOURCES = {
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "workday": WorkdaySource,
    "ashby": AshbySource,
}

AGGREGATORS = [
    RemoteOKSource(),
    JobicySource(),
    ArbeitnowSource(),
    HimalayasSource(),
]

ATS_LIMITS = {
    "greenhouse": 5,
    "lever": 5,
    "workday": 3,
    "ashby": 5,
}

AGGREGATOR_DELAY = 1.0
NOTIFICATION_BATCH = 50


def _ensure_registry(registry_path: Path) -> BoardRegistry:
    registry = BoardRegistry(registry_path)
    if registry.board_count() == 0:
        migrate_catalog(registry)
        seed_registry(registry)
    return registry


async def run_fast_cycle(
    config: dict, db_path: Path, registry_path: Path,
) -> int:
    store = DedupStore(db_path)
    registry = _ensure_registry(registry_path)

    connector = TCPConnector(limit=10)
    all_jobs: list[Job] = []

    async with ClientSession(connector=connector) as session:
        for agg in AGGREGATORS:
            try:
                jobs = await agg.fetch_paginated(session)
                all_jobs.extend(jobs)
                logger.info("%s: fetched %d jobs", agg.name, len(jobs))
            except Exception as e:
                logger.warning("%s failed: %s", agg.name, e)
            await asyncio.sleep(AGGREGATOR_DELAY)

    discovered = discover_from_jobs(all_jobs, registry)
    if discovered:
        logger.info("Cross-ref discovered %d new boards", discovered)

    new_jobs = [j for j in all_jobs if not store.is_seen(j.url)]
    registry.close()
    store.mark_seen_batch(new_jobs) if new_jobs else None
    store.close()
    return len(new_jobs), new_jobs


async def run_slow_cycle(
    config: dict, db_path: Path, registry_path: Path,
) -> int:
    store = DedupStore(db_path)
    registry = _ensure_registry(registry_path)

    semaphores = {ats: asyncio.Semaphore(limit) for ats, limit in ATS_LIMITS.items()}
    all_jobs: list[Job] = []

    connector = TCPConnector(limit=10)
    async with ClientSession(connector=connector) as session:
        for ats_name, source_cls in ATS_SOURCES.items():
            source = source_cls()
            boards = registry.get_active_boards(ats_name)
            sem = semaphores[ats_name]

            async def fetch_board(src, board, s, sem):
                async with sem:
                    try:
                        jobs = await src.fetch_jobs(s, board)
                        if jobs:
                            registry.update_after_fetch(board["id"], len(jobs))
                        else:
                            registry.record_failure(board["id"])
                        return jobs
                    except Exception as e:
                        logger.warning("ATS %s board %s failed: %s", board["ats"], board["token"], e)
                        registry.record_failure(board["id"])
                        return []

            tasks = [fetch_board(source, b, session, sem) for b in boards]
            results = await asyncio.gather(*tasks)
            for result in results:
                all_jobs.extend(result)

    new_jobs = [j for j in all_jobs if not store.is_seen(j.url)]
    store.mark_seen_batch(new_jobs) if new_jobs else None

    registry.close()
    store.close()
    return len(new_jobs), new_jobs


async def _process_results(new_jobs: list[Job], config: dict) -> None:
    if not new_jobs:
        return

    watches = config.get("watches", [])
    for watch in watches:
        filtered = filter_jobs(new_jobs, watch)
        if filtered:
            excel_path = config.get("excel_path", ".")
            export_jobs(filtered, excel_path)
            logger.info("Found %d new jobs matching '%s'", len(filtered), watch.get("role"))


async def run_scan_cycle(
    watch: dict, config: dict, db_path: Path,
) -> int:
    from braevity.config import config_dir
    registry_path = config_dir() / "registry.db"
    _, new_jobs = await run_fast_cycle(config, db_path, registry_path)
    filtered = filter_jobs(new_jobs, watch)
    if filtered:
        excel_path = config.get("excel_path", ".")
        export_jobs(filtered, excel_path)
    return len(filtered)


async def run_scheduler(config: dict) -> None:
    from braevity.config import config_dir

    db_path = config_dir() / "seen.db"
    registry_path = config_dir() / "registry.db"

    watches = config.get("watches", [])
    if not watches:
        logger.error("No watches configured. Run 'braevity watch' first.")
        return

    fast_interval = min(w.get("poll_interval", 30) for w in watches)
    slow_interval = 360
    cycles_per_slow = max(1, slow_interval // fast_interval)
    cycle_count = 0

    while True:
        cycle_count += 1
        total_new = 0

        _, fast_jobs = await run_fast_cycle(config, db_path, registry_path)
        for watch in watches:
            filtered = filter_jobs(fast_jobs, watch)
            if filtered:
                excel_path = config.get("excel_path", ".")
                export_jobs(filtered, excel_path)
                total_new += len(filtered)

        if cycle_count % cycles_per_slow == 0:
            _, slow_jobs = await run_slow_cycle(config, db_path, registry_path)
            for watch in watches:
                filtered = filter_jobs(slow_jobs, watch)
                if filtered:
                    excel_path = config.get("excel_path", ".")
                    export_jobs(filtered, excel_path)
                    total_new += len(filtered)
            logger.info("Slow cycle complete.")

        if total_new == 0:
            logger.info("No new jobs. Next fast scan in %d min.", fast_interval)
        else:
            logger.info("%d new jobs this cycle. Next fast scan in %d min.", total_new, fast_interval)

        await asyncio.sleep(fast_interval * 60)
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS (existing scheduler tests may need updates — fix any `source_ats` references or import changes)

- [ ] **Step 4: Commit**

```bash
git add braevity/core/scheduler.py braevity/core/exporter.py
git commit -m "feat: two-tier scheduler (fast=aggregators, slow=ATS boards) and updated exporter"
```

---

### Task 9: CLI Commands (discover, boards)

**Files:**
- Modify: `braevity/cli/commands.py`

**Interfaces:**
- Consumes: `BoardRegistry` from Task 2, `seed_registry()` and `migrate_catalog()` from Task 6, `run_fast_cycle()` from Task 8
- Produces: Two new CLI commands: `braevity discover` and `braevity boards` (with `boards add` subcommand)

- [ ] **Step 1: Add `discover` command**

Add to `braevity/cli/commands.py`:

```python
@cli.command()
def discover():
    """Import seed boards and run one cross-reference discovery cycle."""
    import asyncio
    from braevity.core.registry import BoardRegistry
    from braevity.core.migration import seed_registry, migrate_catalog

    config = load_config()
    db_path = config_dir() / "seen.db"
    registry_path = config_dir() / "registry.db"

    registry = BoardRegistry(registry_path)
    migrated = migrate_catalog(registry)
    seeded = seed_registry(registry)
    click.echo(f"Migrated {migrated} boards from catalog, seeded {seeded} new boards.")
    click.echo(f"Total boards: {registry.board_count()}")

    from braevity.core.scheduler import run_fast_cycle

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M")

    count, _ = asyncio.run(run_fast_cycle(config, db_path, registry_path))
    click.echo(f"Discovery complete. {count} new jobs found via aggregators.")
    registry.close()
```

- [ ] **Step 2: Add `boards` command group**

Add to `braevity/cli/commands.py`:

```python
@cli.group()
def boards():
    """Manage the board registry."""
    pass


@boards.command("list")
@click.option("--ats", default=None, help="Filter by ATS (greenhouse, lever, workday, ashby)")
def boards_list(ats):
    """List all registered boards."""
    from braevity.core.registry import BoardRegistry

    registry_path = config_dir() / "registry.db"
    registry = BoardRegistry(registry_path)
    board_list = registry.get_active_boards(ats)

    if not board_list:
        click.echo("No boards registered. Run 'braevity discover' first.")
        registry.close()
        return

    click.echo(f"{'ATS':<12} {'Token':<25} {'Company':<20} {'Jobs':<6} {'Last Fetched':<22} {'From'}")
    click.echo("-" * 95)
    for b in board_list:
        click.echo(
            f"{b['ats']:<12} {b['token']:<25} {(b['company_name'] or ''):<20} "
            f"{b['job_count']:<6} {(b['last_fetched'] or 'never'):<22} {b['discovered_from'] or ''}"
        )

    click.echo(f"\nTotal: {len(board_list)} active boards")
    registry.close()


@boards.command("add")
@click.argument("ats")
@click.argument("token")
@click.option("--name", default=None, help="Company name")
def boards_add(ats, token, name):
    """Manually add a board to the registry."""
    from braevity.core.registry import BoardRegistry

    if ats not in ("greenhouse", "lever", "workday", "ashby"):
        click.echo(f"Unknown ATS: {ats}. Use greenhouse, lever, workday, or ashby.")
        return

    registry_path = config_dir() / "registry.db"
    registry = BoardRegistry(registry_path)
    if registry.register(ats, token, company_name=name, discovered_from="manual"):
        click.echo(f"Added {ats}:{token}")
    else:
        click.echo(f"Already registered: {ats}:{token}")
    registry.close()
```

- [ ] **Step 3: Test CLI manually**

Run: `python -m braevity discover --help`
Run: `python -m braevity boards --help`
Run: `python -m braevity boards list --help`
Run: `python -m braevity boards add --help`
Expected: help text shows for all commands

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add braevity/cli/commands.py
git commit -m "feat: add 'discover' and 'boards' CLI commands"
```

---

### Task 10: Update ATS Sources for Registry-Based Lookup

**Files:**
- Modify: `braevity/sources/greenhouse.py`
- Modify: `braevity/sources/lever.py`
- Modify: `braevity/sources/workday.py`
- Modify: `braevity/sources/ashby.py`
- Modify: existing source tests

**Interfaces:**
- Consumes: `Job.from_fields()` with `source=` from Task 1
- Produces: ATS sources accept `board: dict` from registry (with keys `id`, `ats`, `token`, `company_name`) instead of old catalog format. Greenhouse uses `board["token"]` as board_token, Lever uses `board["token"]` as org, etc.

- [ ] **Step 1: Update GreenhouseSource**

In `braevity/sources/greenhouse.py`, change `fetch_jobs` to accept registry board dict:

```python
    async def fetch_jobs(self, session: ClientSession, board: dict) -> list[Job]:
        token = board.get("board_token") or board.get("token", "")
        company_name = board.get("name") or board.get("company_name") or token
```

Change the rest to use `token` and `company_name` instead of `company["board_token"]` and `company["name"]`.

- [ ] **Step 2: Update LeverSource**

In `braevity/sources/lever.py`, change `fetch_jobs`:

```python
    async def fetch_jobs(self, session: ClientSession, board: dict) -> list[Job]:
        org = board.get("org") or board.get("token", "")
        company_name = board.get("name") or board.get("company_name") or org
```

Replace `company["name"]` with `company_name` in `Job.from_fields()` call.

- [ ] **Step 3: Update WorkdaySource**

In `braevity/sources/workday.py`, change `fetch_jobs`:

```python
    async def fetch_jobs(self, session: ClientSession, board: dict) -> list[Job]:
        base_url = (board.get("url") or board.get("token", "")).rstrip("/")
        company_name = board.get("name") or board.get("company_name") or "Unknown"
```

Replace `company["name"]` with `company_name` and `company["url"]` with the local variable.

- [ ] **Step 4: Update AshbySource**

In `braevity/sources/ashby.py`, change `fetch_jobs`:

```python
    async def fetch_jobs(self, session: ClientSession, board: dict) -> list[Job]:
        org = board.get("org") or board.get("token", "")
        company_name = board.get("name") or board.get("company_name") or org
```

Replace `company["name"]` with `company_name`.

- [ ] **Step 5: Update source tests**

In each test file (`test_greenhouse.py`, `test_lever.py`, etc.), update mock board dicts to include both old and new key formats so tests pass with either. Example for greenhouse:

```python
company = {"board_token": "test", "name": "Test Co", "token": "test", "company_name": "Test Co"}
```

- [ ] **Step 6: Run full suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add braevity/sources/greenhouse.py braevity/sources/lever.py braevity/sources/workday.py braevity/sources/ashby.py tests/sources/
git commit -m "feat: update ATS sources to accept registry board dicts"
```

---

### Task 11: End-to-End Smoke Test

**Files:**
- Create: `tests/test_e2e_aggregators.py`

**Interfaces:**
- Consumes: all aggregator sources from Task 4, `DedupStore` from Task 3, `BoardRegistry` from Task 2, `discover_from_jobs` from Task 5

- [ ] **Step 1: Write e2e test**

Create `tests/test_e2e_aggregators.py`:

```python
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
```

- [ ] **Step 2: Run e2e test**

Run: `pytest tests/test_e2e_aggregators.py -v -s`
Expected: PASS, prints job and board counts

- [ ] **Step 3: Run full suite one final time**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_aggregators.py
git commit -m "test: add end-to-end smoke test for aggregator pipeline"
```
