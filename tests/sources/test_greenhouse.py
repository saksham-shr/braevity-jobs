import asyncio
import json
from unittest.mock import AsyncMock
from braevity.sources.greenhouse import GreenhouseSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_greenhouse_parses_jobs():
    source = GreenhouseSource()
    api_data = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "location": {"name": "Bangalore, India"},
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/123",
                "updated_at": "2026-10-06T10:00:00Z",
            },
            {
                "title": "Frontend Engineer",
                "location": {"name": "San Francisco"},
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/456",
                "updated_at": "2026-10-05T10:00:00Z",
            },
        ]
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(api_data))

    company = {"name": "Stripe", "board_token": "stripe"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 2
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Stripe"
    assert jobs[0].location == "Bangalore, India"
    assert jobs[0].source == "greenhouse"


def test_greenhouse_empty_response():
    source = GreenhouseSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({"jobs": []}))

    company = {"name": "Acme", "board_token": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_greenhouse_api_error_returns_empty():
    source = GreenhouseSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "board_token": "gone"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_greenhouse_html_error_page_returns_empty():
    source = GreenhouseSource()
    resp = AsyncMock()
    resp.status = 200
    resp.headers = {"Content-Type": "text/html"}
    resp.text = AsyncMock(return_value="<html>Error</html>")
    session = AsyncMock()
    session.get = AsyncMock(return_value=resp)

    company = {"name": "Waf", "board_token": "waf"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []
