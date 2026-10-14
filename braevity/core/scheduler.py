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

# Maps registry format to what each ATS source expects
ATS_KEY_MAP = {
    "greenhouse": "board_token",
    "lever": "org",
    "ashby": "org",
    "workday": "url",
}


def _board_to_company(board: dict) -> dict:
    ats = board["ats"]
    key = ATS_KEY_MAP.get(ats, "token")
    return {"name": board.get("company_name", ""), key: board["token"]}


def _ensure_registry(registry_path: Path) -> BoardRegistry:
    registry = BoardRegistry(registry_path)
    if registry.board_count() == 0:
        migrate_catalog(registry)
        seed_registry(registry)
    return registry


async def run_fast_cycle(
    config: dict, db_path: Path, registry_path: Path,
) -> tuple[int, list[Job]]:
    store = DedupStore(db_path)
    registry = _ensure_registry(registry_path)

    connector = TCPConnector(limit=10)
    all_jobs: list[Job] = []

    async with ClientSession(connector=connector) as session:
        for agg in AGGREGATORS:
            try:
                jobs = await agg.fetch_all_jobs(session)
                all_jobs.extend(jobs)
                logger.info("%s: fetched %d jobs", agg.name, len(jobs))
            except Exception as e:
                logger.warning("%s failed: %s", agg.name, e)
            await asyncio.sleep(AGGREGATOR_DELAY)

    discovered = discover_from_jobs(all_jobs, registry)
    if discovered:
        logger.info("Cross-ref discovered %d new boards", discovered)

    new_jobs = [j for j in all_jobs if not store.is_seen(j.url)]
    if new_jobs:
        store.mark_seen_batch(new_jobs)

    registry.close()
    store.close()
    return len(new_jobs), new_jobs


async def run_slow_cycle(
    config: dict, db_path: Path, registry_path: Path,
) -> tuple[int, list[Job]]:
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
                        company = _board_to_company(board)
                        jobs = await src.fetch_jobs(s, company)
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
    if new_jobs:
        store.mark_seen_batch(new_jobs)

    registry.close()
    store.close()
    return len(new_jobs), new_jobs


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
