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
