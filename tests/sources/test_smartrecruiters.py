import asyncio
import json
from unittest.mock import AsyncMock
from braevity.sources.smartrecruiters import SmartRecruitersSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_smartrecruiters_parses_jobs():
    source = SmartRecruitersSource()
    page1 = {
        "totalFound": 1,
        "content": [
            {
                "name": "Personal Trainer",
                "ref": "https://api.smartrecruiters.com/v1/companies/Equinox/postings/abc123",
                "location": {"city": "New York", "fullLocation": "New York, NY, US"},
                "releasedDate": "2026-10-01",
            },
        ],
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(page1))

    company = {"name": "Equinox", "slug": "Equinox"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Personal Trainer"
    assert jobs[0].company == "Equinox"
    assert jobs[0].location == "New York, NY, US"
    assert jobs[0].source == "smartrecruiters"


def test_smartrecruiters_pagination_stops_on_partial_page():
    source = SmartRecruitersSource()
    page1 = {"content": [{"name": f"Job {i}", "ref": f"https://x/{i}"} for i in range(100)]}
    page2 = {"content": [{"name": "Last", "ref": "https://x/last"}]}
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[_mock_response(page1), _mock_response(page2)])

    company = {"name": "Big", "slug": "big"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert len(jobs) == 101
    assert session.get.call_count == 2


def test_smartrecruiters_empty_response():
    source = SmartRecruitersSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({"content": []}))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_smartrecruiters_api_error_returns_empty():
    source = SmartRecruitersSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "slug": "gone"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []
