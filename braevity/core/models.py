from dataclasses import dataclass
from hashlib import sha256
from datetime import datetime, timezone

@dataclass(frozen=True)
class Job:
    id: str
    title: str
    company: str
    location: str | None
    url: str
    posted_date: str | None
    source_ats: str
    found_at: str

    @classmethod
    def from_fields(cls, title, company, location, url, posted_date, source_ats) -> "Job":
        job_id = sha256(url.encode()).hexdigest()
        found_at = datetime.now(timezone.utc).isoformat()
        return cls(
            id=job_id,
            title=title,
            company=company,
            location=location,
            url=url,
            posted_date=posted_date,
            source_ats=source_ats,
            found_at=found_at
        )   