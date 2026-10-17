import asyncio
import json
from unittest.mock import AsyncMock, patch
from braevity.sources.recruitee import RecruiteeSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_recruitee_parses_offers():
    source = RecruiteeSource()
    data = {
        "offers": [
            {
                "title": "Backend Engineer",
                "careers_url": "https://11bitstudios.recruitee.com/o/backend-engineer",
                "location": "Warszawa, Mazowieckie, Poland",
                "city": "Warszawa",
                "published_at": "2026-10-08 10:12:16 UTC",
            },
        ]
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "11 Bit Studios", "slug": "11bitstudios"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "11 Bit Studios"
    assert jobs[0].location == "Warszawa, Mazowieckie, Poland"
    assert jobs[0].url == "https://11bitstudios.recruitee.com/o/backend-engineer"
    assert jobs[0].posted_date == "2026-10-08 10:12:16 UTC"
    assert jobs[0].source == "recruitee"


def test_recruitee_falls_back_to_city_when_no_location():
    source = RecruiteeSource()
    data = {"offers": [{"title": "PM", "careers_url": "https://x/1", "city": "Remote"}]}
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs[0].location == "Remote"


def test_recruitee_skips_offer_without_url():
    source = RecruiteeSource()
    data = {"offers": [{"title": "No URL"}]}
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_recruitee_empty_response():
    source = RecruiteeSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({"offers": []}))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_recruitee_api_error_returns_empty():
    source = RecruiteeSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "slug": "gone"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_recruitee_network_failure_returns_empty(mock_sleep):
    source = RecruiteeSource()
    session = AsyncMock()
    session.get = AsyncMock(side_effect=ConnectionError("boom"))

    company = {"name": "Down", "slug": "down"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []
