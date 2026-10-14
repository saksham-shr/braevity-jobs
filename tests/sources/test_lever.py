import asyncio
import json
from unittest.mock import AsyncMock
from braevity.sources.lever import LeverSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_lever_parses_jobs():
    source = LeverSource()
    api_data = [
        {
            "text": "Backend Engineer",
            "categories": {"location": "Bangalore", "allLocations": ["Bangalore", "Remote"]},
            "hostedUrl": "https://jobs.lever.co/zepto/abc-123",
            "createdAt": 1728201600000,
        },
    ]
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(api_data))

    company = {"name": "Zepto", "org": "zepto"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Zepto"
    assert "Bangalore" in jobs[0].location
    assert jobs[0].source == "lever"


def test_lever_api_error():
    source = LeverSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response([], status=429))

    jobs = asyncio.run(source.fetch_jobs(session, {"name": "X", "org": "x"}))
    assert jobs == []
