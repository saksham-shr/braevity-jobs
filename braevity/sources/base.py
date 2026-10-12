import yaml
from pathlib import Path
from braevity.core.models import Job 

class BaseSource:
    name = ""

    async def fetch_jobs(self, session, company) -> list[Job]:
        raise NotImplementedError 


def load_catalog() -> dict: 
    companies_path = Path(__file__).parent.parent /"catalog" / "companies.yaml"
    if not companies_path.exists():
        return {}
    with open(companies_path, "r") as f:
        return yaml.safe_load(f) or {}

        