# Braevity

CLI job monitor that collects listings from multiple sources — ATS platforms, job aggregator APIs, and Schema.org career pages — with automatic deduplication and Excel export.

## Features

- **9 ATS platforms**: Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, BambooHR, Recruitee, BreezyHR
- **4 aggregator APIs**: RemoteOK, Jobicy, Arbeitnow, Himalayas
- **Schema.org source**: Extracts JobPosting JSON-LD from any career page, wired into the scheduler as a real source
- **Cross-reference discovery**: Automatically finds new ATS boards from aggregator apply URLs
- **Board registry**: SQLite-backed, auto-growing catalog (56 seed boards included, all live-verified)
- **Two-tier scheduler**: Fast cycle (aggregators, 30min) + slow cycle (ATS boards, 6hr)
- **HTTP resilience layer**: shared fetch wrapper with timeout, 429/`Retry-After` cooldown (seconds or HTTP-date), bounded retry on 429/5xx/timeout
- **Terminal vs. transient failure tracking**: a confirmed-dead board (404) deactivates after repeated failures; a transient blip never does
- **Smart dedup**: URL-based fetch dedup + content hash (title + company + location) to catch cross-source duplicates without collapsing distinct postings
- **Durable delivery**: per-watch delivery tracking with a persisted retry queue — an export/notification crash can't silently lose a job
- **Filtered watches**: Match by role, experience level, location (country/city)
- **Excel export**: Daily `.xlsx` files with salary, remote status, tags, and more

## Requirements

- Python 3.10+
- No external services required (SQLite for all persistence)

## Install

```bash
pip install -e .
```

## Quick Start

```bash
# Set up config (Excel path, email notifications)
braevity init

# Add a job watch
braevity watch
# Follow prompts: role, experience, countries, cities, poll interval

# Import seed boards and run aggregator discovery
braevity discover

# Start monitoring
braevity start
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `braevity init` | Configure Excel path and SMTP settings |
| `braevity watch` | Add a new job watch (role/location/experience filter) |
| `braevity list` | Show all configured watches |
| `braevity remove <n>` | Remove a watch by index |
| `braevity start` | Start the two-tier polling scheduler |
| `braevity status` | Show config and tracked job count |
| `braevity discover` | Seed boards + run one aggregator discovery cycle |
| `braevity boards list` | List all registered boards |
| `braevity boards add <ats> <token>` | Manually add a board |

## Architecture

```
braevity/
├── cli/commands.py          # Click CLI
├── config.py                # YAML config (~/.braevity/)
├── catalog/
│   ├── companies.yaml       # Legacy catalog (migrated on first run)
│   └── seed_boards.yaml     # 56 seed boards across 7 of the 9 ATS platforms (Recruitee/BreezyHR adapters exist, seed import pending)
├── core/
│   ├── models.py            # Job dataclass (frozen, content_hash by title+company+location)
│   ├── registry.py          # SQLite board registry (terminal vs transient failure tracking)
│   ├── dedup.py             # Fetch-dedup, per-watch delivery tracking, pending-retry queue
│   ├── http.py              # Shared fetch wrapper: timeout, 429/Retry-After cooldown, bounded retry
│   ├── scheduler.py         # Two-tier async scheduler
│   ├── migration.py         # Seed import + legacy catalog migration
│   ├── filter.py            # Role/location/experience matching
│   ├── exporter.py          # Excel (.xlsx) export
│   └── notifier.py          # Email notifications
└── sources/
    ├── base.py              # BaseSource + BaseAggregator ABCs, BoardGoneError signal
    ├── greenhouse.py        # Greenhouse boards API
    ├── lever.py             # Lever postings API
    ├── workday.py           # Workday CXS API (paginated)
    ├── ashby.py             # Ashby GraphQL API
    ├── smartrecruiters.py   # SmartRecruiters postings API (paginated)
    ├── workable.py          # Workable widget API
    ├── bamboohr.py          # BambooHR careers list (undocumented endpoint)
    ├── recruitee.py         # Recruitee offers API
    ├── breezyhr.py          # BreezyHR JSON feed
    ├── remoteok.py          # RemoteOK aggregator
    ├── jobicy.py            # Jobicy aggregator (paginated)
    ├── arbeitnow.py         # Arbeitnow aggregator
    ├── himalayas.py         # Himalayas aggregator
    ├── crossref.py          # ATS board token extraction from apply URLs
    └── schema_org.py        # JSON-LD JobPosting scraper, wired as a real source
```

## How It Works

1. **Fast cycle** (every 30 min): Polls all 4 aggregator APIs, collects jobs, runs cross-reference discovery to find new ATS boards from apply URLs
2. **Slow cycle** (every 6 hrs): Polls all registered ATS boards with per-platform concurrency limits, routed through a shared HTTP layer with timeout/retry/429 cooldown
3. **Fetch dedup**: Every fetched job is marked seen once, immediately — by URL, and by a title+company+location content hash to catch the same posting surfaced by two different sources
4. **Filter**: New jobs are matched against configured watches (role, experience, location)
5. **Deliver**: Matching jobs are exported to daily Excel files and marked delivered per watch; a delivery that fails (export/notify crash) is queued and retried on the next cycle instead of being lost
6. **Board health**: a board that returns a confirmed-dead signal (404) is deactivated after repeated failures; a transient failure (timeout, 5xx, rate limit) never counts against it

## Testing

```bash
# Unit tests (no network)
pytest tests/ --ignore=tests/sources/test_remoteok.py --ignore=tests/sources/test_jobicy.py --ignore=tests/sources/test_arbeitnow.py --ignore=tests/sources/test_himalayas.py --ignore=tests/test_e2e_aggregators.py

# Full suite including live API tests
pytest tests/

# E2E smoke test (hits all 4 aggregator APIs)
pytest tests/test_e2e_aggregators.py -v -s
```

## License

MIT
