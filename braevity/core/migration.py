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
                    token, url = entry.split(":", 1)
                    if registry.register(ats, url, company_name=token, discovered_from="seed"):
                        count += 1
                else:
                    if registry.register(ats, entry, company_name=entry, discovered_from="seed"):
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
            elif ats in ("lever", "ashby"):
                token = company.get("org", "")
            elif ats == "workday":
                token = company.get("url", "")
            else:
                continue
            if token and registry.register(ats, token, company_name=name, discovered_from="seed"):
                count += 1
    return count
