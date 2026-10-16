import asyncio
import json
from unittest.mock import AsyncMock
from braevity.sources.workable import WorkableSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_workable_parses_jobs():
    source = WorkableSource()
    data = {
        "name": "Hugging Face",
        "jobs": [
            {
                "title": "ML Engineer",
                "shortcode": "ABC123",
                "url": "https://apply.workable.com/huggingface/j/ABC123/",
                "city": "Paris",
                "country": "France",
                "published_on": "2026-10-01",
            },
        ],
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Hugging Face", "slug": "huggingface"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "ML Engineer"
    assert jobs[0].company == "Hugging Face"
    assert jobs[0].location == "Paris, France"
    assert jobs[0].source == "workable"


def test_workable_empty_response():
    source = WorkableSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({"jobs": []}))

    company = {"name": "Empty", "slug": "empty"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_workable_api_error_returns_empty():
    source = WorkableSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "slug": "gone"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_workable_cloudflare_redirect_returns_empty():
    source = WorkableSource()
    resp = AsyncMock()
    resp.status = 200
    resp.headers = {"Content-Type": "text/html"}
    resp.text = AsyncMock(return_value="<html>Checking your browser</html>")
    session = AsyncMock()
    session.get = AsyncMock(return_value=resp)

    company = {"name": "Blocked", "slug": "blocked"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []
