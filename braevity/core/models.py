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
        # Location is part of the identity on purpose: title+company alone
        # collapses genuinely distinct postings (same role, different city/
        # req) into one. A real cross-posted duplicate with a mismatched
        # location string (e.g. an aggregator saying "Remote" for a job the
        # source ATS lists as "NYC") is missed instead — a false negative
        # is far cheaper than silently dropping a real, distinct job.
        location_key = (self.location or "").strip().lower()
        key = f"{self.title.lower()}\x00{self.company.lower()}\x00{location_key}"
        return sha256(key.encode()).hexdigest()
