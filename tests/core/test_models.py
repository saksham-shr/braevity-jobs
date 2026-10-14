from braevity.core.models import Job


def test_job_from_url_generates_id():
    job = Job.from_fields(
        title="Backend Engineer",
        company="Stripe",
        location="San Francisco, CA",
        url="https://boards.greenhouse.io/stripe/jobs/123",
        posted_date="2026-10-06",
        source="greenhouse",
    )
    assert job.id
    assert len(job.id) == 64
    assert job.title == "Backend Engineer"
    assert job.found_at


def test_job_id_deterministic_from_url():
    job1 = Job.from_fields(
        title="A", company="B", location=None,
        url="https://example.com/job/1",
        posted_date=None, source="lever",
    )
    job2 = Job.from_fields(
        title="C", company="D", location="NYC",
        url="https://example.com/job/1",
        posted_date="2026-01-01", source="lever",
    )
    assert job1.id == job2.id


def test_job_none_location_allowed():
    job = Job.from_fields(
        title="SDE", company="X", location=None,
        url="https://x.com/jobs/1",
        posted_date=None, source="ashby",
    )
    assert job.location is None


def test_job_new_fields():
    job = Job.from_fields(
        title="Backend Engineer",
        company="Stripe",
        location="Remote",
        url="https://boards.greenhouse.io/stripe/jobs/123",
        posted_date="2026-10-06",
        source="greenhouse",
        salary_min=120000,
        salary_max=180000,
        salary_currency="USD",
        tags=["python", "aws"],
        description="Build APIs",
        remote=True,
        employment_type="full-time",
        apply_url="https://boards.greenhouse.io/stripe/jobs/123/apply",
        source_id="gh-123",
    )
    assert job.salary_min == 120000
    assert job.salary_max == 180000
    assert job.salary_currency == "USD"
    assert job.tags == ["python", "aws"]
    assert job.description == "Build APIs"
    assert job.remote is True
    assert job.employment_type == "full-time"
    assert job.apply_url == "https://boards.greenhouse.io/stripe/jobs/123/apply"
    assert job.source_id == "gh-123"
    assert job.source == "greenhouse"


def test_job_new_fields_defaults():
    job = Job.from_fields(
        title="SDE", company="X", location=None,
        url="https://x.com/1", posted_date=None, source="lever",
    )
    assert job.salary_min is None
    assert job.tags == []
    assert job.remote is False
    assert job.apply_url is None
    assert job.source_id is None


def test_content_hash_deterministic():
    job1 = Job.from_fields(
        title="Backend Engineer", company="Stripe", location=None,
        url="https://a.com/1", posted_date=None, source="greenhouse",
    )
    job2 = Job.from_fields(
        title="Backend Engineer", company="Stripe", location="NYC",
        url="https://b.com/2", posted_date=None, source="remoteok",
    )
    assert job1.content_hash() == job2.content_hash()


def test_content_hash_separator_prevents_collision():
    job1 = Job.from_fields(
        title="Senior", company="Dev Engineer", location=None,
        url="https://a.com/1", posted_date=None, source="greenhouse",
    )
    job2 = Job.from_fields(
        title="Senior Dev", company="Engineer", location=None,
        url="https://b.com/2", posted_date=None, source="lever",
    )
    assert job1.content_hash() != job2.content_hash()
