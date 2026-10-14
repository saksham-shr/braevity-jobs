# Braevity Jobs Collection Infrastructure

## Overview

Multi-source job collection system that harvests jobs from ATS APIs, aggregator APIs, and Schema.org structured data. Replaces fixed company catalog with auto-growing board registry fed by seed lists and cross-referencing.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  braevity CLI                    │
│       (init, watch, start, discover, boards)     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Scheduler (async, two-tier)          │
│  ┌─────────────────┐  ┌──────────────────┐      │
│  │ Fast cycle       │  │ Slow cycle        │      │
│  │ (30min)          │  │ (6hr)             │      │
│  │ Aggregator APIs  │  │ ATS boards        │      │
│  │ + cross-ref      │  │ + schema.org      │      │
│  └────────┬────────┘  └────────┬──────────┘      │
└───────────┼────────────────────┼────────────────┘
            │                    │
┌───────────▼────────────────────▼────────────────┐
│              Source Layer                         │
│                                                  │
│  ATS Sources:          Aggregator Sources:       │
│   Greenhouse            RemoteOK                 │
│   Lever                 Jobicy                   │
│   Workday               Arbeitnow                │
│   Ashby                 Himalayas                │
│                                                  │
│  Schema.org Scraper:                             │
│   JSON-LD extraction from career pages           │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Board Registry (SQLite)                         │
│  Auto-populated from seed + cross-ref            │
│  Tracks: ats, token, company, last_fetched,      │
│          job_count, active status                 │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Normalizer → Dedup Engine → Filter → Export     │
│  (cross-source dedup via content_hash)           │
└─────────────────────────────────────────────────┘
```

## Data Model

### Job (updated dataclass)

```python
@dataclass(frozen=True)
class Job:
    id: str                      # sha256(url) or sha256(title+company) for cross-source
    title: str
    company: str
    location: str | None
    url: str
    posted_date: str | None
    source: str                  # "greenhouse", "remoteok", "schema.org", etc.
    found_at: str
    salary_min: int | None       # raw value from source
    salary_max: int | None
    salary_currency: str | None  # "USD", "EUR", "INR"
    tags: list[str]              # ["python", "react", "remote"]
    description: str | None      # HTML or plain text
    remote: bool                 # True if remote position
    employment_type: str | None  # "full-time", "contract", "part-time"
    apply_url: str | None        # direct application link
    source_id: str | None        # original ID from source API
```

### Board Registry (new SQLite table)

```sql
CREATE TABLE board_registry (
    id TEXT PRIMARY KEY,         -- "greenhouse:stripe", "lever:figma"
    ats TEXT NOT NULL,           -- "greenhouse", "lever", "workday", "ashby"
    token TEXT NOT NULL,         -- board_token/org/url depending on ATS
    company_name TEXT,
    discovered_from TEXT,        -- "seed", "crossref", "aggregator"
    last_fetched TEXT,
    job_count INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,    -- 0 if 404/empty 3 consecutive times
    created_at TEXT
);
```

### Seen Jobs (updated)

```sql
CREATE TABLE seen_jobs (
    url TEXT PRIMARY KEY,
    content_hash TEXT,           -- sha256(lower(title) + lower(company))
    title TEXT,
    company TEXT,
    source TEXT,
    first_seen TEXT,
    last_seen TEXT
);
CREATE INDEX idx_content_hash ON seen_jobs(content_hash);
```

### Scheduler State

```sql
CREATE TABLE scheduler_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

## Source Layer

### Two base classes

```python
class BaseSource(ABC):
    """Per-company ATS source. Needs board token from registry."""
    name: str
    async def fetch_jobs(self, session: ClientSession, board: dict) -> list[Job]: ...

class BaseAggregator(ABC):
    """Bulk API source. Returns jobs across all companies."""
    name: str
    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]: ...
    async def fetch_paginated(self, session: ClientSession) -> list[Job]: ...
```

### ATS Sources (existing, updated for new Job fields)

| Source | Lookup key | API |
|---|---|---|
| Greenhouse | `board_token` | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` |
| Lever | `org` | `api.lever.co/v0/postings/{org}?mode=json` |
| Workday | `url` | `{url}/wday/cxs/{subdomain}/{company_id}/jobs` (POST) |
| Ashby | `org` | `jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams` |

### Aggregator Sources (new)

| Source | Endpoint | Pagination | Rate limit |
|---|---|---|---|
| RemoteOK | `remoteok.com/api` | `?offset=N` | 1 req/sec |
| Jobicy | `jobicy.com/api/v2/remote-jobs` | `?count=N` + cursor | polite |
| Arbeitnow | `arbeitnow.com/api/job-board-api` | `?page=N` via links/meta | polite |
| Himalayas | `himalayas.app/jobs/api` | `?offset=N&limit=N` + cursor | polite |

### Schema.org Scraper (new)

Extracts `<script type="application/ld+json">` with `@type: "JobPosting"` from career page HTML. Targets career pages of boards in registry that have public websites. Enrichment source — adds salary/description to ATS data.

## Cross-Reference Discovery

Aggregator results contain `apply_url` fields pointing to ATS boards. Pattern extraction:

```python
BOARD_PATTERNS = {
    "greenhouse": [
        r"boards\.greenhouse\.io/(\w+)",
        r"job-boards\.greenhouse\.io/(\w+)",
    ],
    "lever": [
        r"jobs\.lever\.co/(\w+)",
    ],
    "ashby": [
        r"jobs\.ashbyhq\.com/([\w-]+)",
    ],
    "workday": [
        r"([\w-]+)\.wd\d+\.myworkdayjobs\.com",
    ],
}
```

Flow: aggregator returns job → extract board token from apply_url → register in board_registry with `discovered_from: "crossref"` → next ATS cycle fetches it.

## Seed Data Strategy

1. Existing `companies.yaml` migrated to registry on first run
2. Large seed file `seed_boards.yaml` ships with project — token-only lists per ATS
3. Cross-referencing grows registry automatically over time

Growth loop:
```
Seed → Registry → ATS Fetch → Jobs
Aggregator Fetch → Jobs → Cross-ref → Registry (new boards) → next cycle
```

## Scheduler Design

### Two-tier scheduling

**Fast cycle (default 30min)**:
- All 4 aggregator APIs (bulk, ~4 requests total)
- Cross-reference extraction from results
- Filter + dedup + export + notify

**Slow cycle (default 6hr)**:
- All registered ATS boards (thousands of requests)
- Schema.org scraping for boards with career page URLs
- Board health check (mark inactive if 3x consecutive 404/empty)
- Registry cleanup

### Concurrency control

```python
ATS_LIMITS = {
    "greenhouse": 5,
    "lever": 5,
    "workday": 3,
    "ashby": 5,
}
AGGREGATOR_DELAY = 1.0  # seconds between aggregator requests
```

`asyncio.Semaphore` per ATS. Aggregators sequential with delay.

### Board prioritization

Boards with higher `job_count` or recent discoveries fetched first. Stale boards (no new jobs in 30 days) drop to weekly cadence.

## CLI Changes

```
braevity discover              # seed import + one aggregator cross-ref cycle
braevity start                 # runs both fast and slow tiers
braevity boards                # list registered boards, counts, last fetch
braevity boards add <ats> <token>  # manual board addition
```

Existing commands (`init`, `watch`, `list`, `remove`, `start`, `status`) unchanged.

## File Layout

```
braevity/sources/
    base.py              # BaseSource + BaseAggregator ABCs
    greenhouse.py        # existing, updated
    lever.py             # existing, updated
    workday.py           # existing, updated
    ashby.py             # existing, updated
    remoteok.py          # new
    jobicy.py            # new
    arbeitnow.py         # new
    himalayas.py         # new
    schema_org.py        # new
    crossref.py          # cross-reference discovery logic

braevity/core/
    models.py            # updated Job dataclass
    dedup.py             # updated with content_hash, cross-source merge
    registry.py          # new — BoardRegistry SQLite manager
    scheduler.py         # updated — two-tier scheduling
    filter.py            # existing, unchanged
    exporter.py          # existing, updated for new Job fields
    notifier.py          # existing, unchanged

braevity/catalog/
    seed_boards.yaml     # replaces companies.yaml — token-only lists
```

## Migration

1. `companies.yaml` auto-imported to `board_registry` on first run
2. `seen_jobs` table gets `content_hash`, `source`, `last_seen` columns via ALTER TABLE
3. `Job.source_ats` renamed to `Job.source`
4. `companies.yaml` kept as fallback seed

## Testing

- One integration test per aggregator — real API call, assert Job fields
- One unit test for cross-ref pattern extraction
- One unit test for dedup content_hash collision
- Existing tests updated for new Job fields
