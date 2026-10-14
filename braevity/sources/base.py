from abc import ABC, abstractmethod
from pathlib import Path
import yaml
from aiohttp import ClientSession
from braevity.core.models import Job


class BaseSource(ABC):
    name: str

    @abstractmethod
    async def fetch_jobs(self, session: ClientSession, company: dict) -> list[Job]:
        ...


class BaseAggregator(ABC):
    name: str

    @abstractmethod
    async def fetch_all_jobs(self, session: ClientSession, offset: int = 0) -> list[Job]:
        ...

    @abstractmethod
    async def fetch_paginated(self, session: ClientSession) -> list[Job]:
        ...


def load_catalog() -> dict:
    catalog_path = Path(__file__).parent.parent / "catalog" / "companies.yaml"
    with open(catalog_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
