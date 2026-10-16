import asyncio
import json
from unittest.mock import AsyncMock
from braevity.sources.workday import WorkdaySource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_workday_parses_jobs():
    source = WorkdaySource()
    page1 = {
        "jobPostings": [
            {
                "title": "SDE-2",
                "externalPath": "/en/job/Bangalore/SDE-2/123",
                "postedOn": "Posted Today",
            },
        ]
    }
    session = AsyncMock()
    session.post = AsyncMock(return_value=_mock_response(page1))

    company = {
        "name": "NVIDIA",
        "url": "https://nvidia.wd5.myworkdayjobs.com#NVIDIAExternalCareerSite",
    }
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "SDE-2"
    assert jobs[0].company == "NVIDIA"
    assert jobs[0].source == "workday"
    assert "nvidia.wd5.myworkdayjobs.com" in jobs[0].url


def test_workday_pagination_stops_on_empty():
    source = WorkdaySource()
    page1 = {"jobPostings": [{"title": f"Job {i}", "externalPath": f"/job/{i}", "postedOn": "Today"} for i in range(20)]}
    page2 = {"jobPostings": []}
    session = AsyncMock()
    session.post = AsyncMock(side_effect=[_mock_response(page1), _mock_response(page2)])

    company = {"name": "Test", "url": "https://test.myworkdayjobs.com#ExternalCareerSite"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert len(jobs) == 20
    assert session.post.call_count == 2


def test_workday_nonstandard_url_with_override():
    source = WorkdaySource()
    page1 = {
        "jobPostings": [
            {"title": "PM", "externalPath": "/job/123", "postedOn": "Today"},
        ]
    }
    session = AsyncMock()
    session.post = AsyncMock(return_value=_mock_response(page1))

    company = {
        "name": "Microsoft",
        "url": "https://jobs.careers.microsoft.com",
        "subdomain": "microsoft",
        "company_id": "microsoft",
    }
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert len(jobs) == 1
    call_url = session.post.call_args[0][0]
    assert "/wday/cxs/microsoft/microsoft/jobs" in call_url


def test_workday_bare_token_no_crash():
    """A token with no '#site_name' suffix and no company_id override can't
    be resolved to Workday's real career-site id (it's an arbitrary name
    the company picked, not derivable from the subdomain) — must return []
    without crashing rather than guess and silently 404."""
    source = WorkdaySource()
    session = AsyncMock()
    session.post = AsyncMock()

    company = {"name": "NVIDIA", "url": "nvidia"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []
    session.post.assert_not_called()
