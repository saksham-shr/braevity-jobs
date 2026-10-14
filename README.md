# Braevity

CLI job monitor that collects listings from multiple sources — ATS platforms, job aggregator APIs, and Schema.org career pages — with automatic deduplication and Excel export.

## Features

- **4 ATS platforms**: Greenhouse, Lever, Ashby, Workday
- **4 aggregator APIs**: RemoteOK, Jobicy, Arbeitnow, Himalayas
- **Schema.org scraper**: Extracts JobPosting JSON-LD from any career page
- **Cross-reference discovery**: Automatically finds new ATS boards from aggregator apply URLs
- **Board registry**: SQLite-backed, auto-growing catalog (66 seed boards included)
- **Two-tier scheduler**: Fast cycle (aggregators, 30min) + slow cycle (ATS boards, 6hr)
- **Smart dedup**: URL-based + content hash (title + company) to catch cross-source duplicates
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
│   └── seed_boards.yaml     # 66 seed boards across 4 ATS platforms
├── core/
│   ├── models.py            # Job dataclass (frozen, content_hash)
│   ├── registry.py          # SQLite board registry
│   ├── dedup.py             # URL + content-hash dedup store
│   ├── scheduler.py         # Two-tier async scheduler
│   ├── migration.py         # Seed import + legacy catalog migration
│   ├── filter.py            # Role/location/experience matching
│   ├── exporter.py          # Excel (.xlsx) export
│   └── notifier.py          # Email notifications
└── sources/
    ├── base.py              # BaseSource + BaseAggregator ABCs
    ├── greenhouse.py        # Greenhouse boards API
    ├── lever.py             # Lever postings API
    ├── workday.py           # Workday CXS API (paginated)
    ├── ashby.py             # Ashby GraphQL API
    ├── remoteok.py          # RemoteOK aggregator
    ├── jobicy.py            # Jobicy aggregator (paginated)
    ├── arbeitnow.py         # Arbeitnow aggregator
    ├── himalayas.py         # Himalayas aggregator
    ├── crossref.py          # ATS board token extraction from apply URLs
    └── schema_org.py        # JSON-LD JobPosting scraper
```

## How It Works

1. **Fast cycle** (every 30 min): Polls all 4 aggregator APIs, collects jobs, runs cross-reference discovery to find new ATS boards from apply URLs
2. **Slow cycle** (every 6 hrs): Polls all registered ATS boards with per-platform concurrency limits
3. **Dedup**: Each job is checked by URL and content hash before export
4. **Filter**: New jobs are matched against configured watches (role, experience, location)
5. **Export**: Matching jobs are appended to daily Excel files

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
