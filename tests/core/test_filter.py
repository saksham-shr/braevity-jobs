from braevity.core.models import Job
from braevity.core.filter import matches_role, matches_location, matches_experience, filter_jobs


def _job(title: str = "Backend Engineer", location: str | None = "Bangalore, India") -> Job:
    return Job.from_fields(
        title=title, company="Acme", location=location,
        url=f"https://x.com/{title}", posted_date=None, source="greenhouse",
    )


# Role matching
def test_role_exact_substring():
    assert matches_role(_job("Backend Engineer"), "Backend Engineer")

def test_role_case_insensitive():
    assert matches_role(_job("BACKEND ENGINEER"), "backend engineer")

def test_role_partial_match():
    assert matches_role(_job("Senior Backend Engineer"), "Backend Engineer")

def test_role_developer_engineer_synonym():
    assert matches_role(_job("Backend Developer"), "Backend Engineer")

def test_role_no_match():
    assert not matches_role(_job("Frontend Designer"), "Backend Engineer")

def test_role_sde_expansion():
    assert matches_role(_job("Software Development Engineer"), "SDE")

def test_role_sde2_match():
    assert matches_role(_job("SDE-2"), "SDE")


# Location matching
def test_location_city_match():
    assert matches_location(_job(location="Bangalore, India"), [], ["Bangalore"])

def test_location_country_match():
    assert matches_location(_job(location="Mumbai, India"), ["India"], [])

def test_location_bengaluru_alias():
    assert matches_location(_job(location="Bengaluru, KA"), [], ["Bangalore"])

def test_location_remote_variants():
    assert matches_location(_job(location="Work from home"), [], ["Remote"])

def test_location_none_included():
    assert matches_location(_job(location=None), ["India"], ["Bangalore"])

def test_location_no_match():
    assert not matches_location(_job(location="London, UK"), ["India"], ["Bangalore"])

def test_location_empty_filters_match_all():
    assert matches_location(_job(location="Anywhere"), [], [])


# Experience matching
def test_experience_senior():
    assert matches_experience(_job("Senior Backend Engineer"), "senior")

def test_experience_junior():
    assert matches_experience(_job("Junior Developer"), "junior")

def test_experience_mid_no_prefix():
    assert matches_experience(_job("Backend Engineer"), "mid")

def test_experience_any():
    assert matches_experience(_job("Staff Engineer"), "any")

def test_experience_senior_rejects_junior():
    assert not matches_experience(_job("Junior Developer"), "senior")


# Combined filter
def test_filter_jobs_applies_all():
    jobs = [
        _job("Senior Backend Engineer", "Bangalore, India"),
        _job("Frontend Designer", "Bangalore, India"),
        _job("Backend Developer", "London, UK"),
    ]
    watch = {
        "role": "Backend Engineer",
        "experience": "any",
        "locations": {"countries": ["India"], "cities": ["Bangalore"]},
    }
    result = filter_jobs(jobs, watch)
    assert len(result) == 1
    assert result[0].title == "Senior Backend Engineer"
