import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from braevity.sources.base import BoardGoneError
from braevity.sources.breezyhr import BreezyHRSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_breezyhr_parses_postings():
    source = BreezyHRSource()
    data = [
        {
            "id": "cb1851c03788",
            "name": "Bilingual Accounts Payable Virtual Assistant",
            "url": "https://20four7va.breezy.hr/p/cb1851c03788",
            "published_date": "2026-10-02T11:03:03.789Z",
            "type": {"id": "fullTime", "name": "Full-Time"},
            "location": {"name": "Worldwide", "is_remote": True, "country": {"name": "Worldwide"}},
        },
    ]
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "20four7VA", "slug": "20four7va"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Bilingual Accounts Payable Virtual Assistant"
    assert jobs[0].company == "20four7VA"
    assert jobs[0].location == "Worldwide"
    assert jobs[0].url == "https://20four7va.breezy.hr/p/cb1851c03788"
    assert jobs[0].posted_date == "2026-10-02T11:03:03.789Z"
    assert jobs[0].employment_type == "Full-Time"
    assert jobs[0].remote is True
    assert jobs[0].source == "breezyhr"


def test_breezyhr_skips_posting_without_url():
    source = BreezyHRSource()
    data = [{"id": "1", "name": "No URL"}]
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_breezyhr_empty_response():
    source = BreezyHRSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response([]))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_breezyhr_api_error_returns_empty():
    source = BreezyHRSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=403))

    company = {"name": "Down", "slug": "down"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_breezyhr_404_raises_board_gone():
    source = BreezyHRSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "slug": "gone"}
    with pytest.raises(BoardGoneError):
        asyncio.run(source.fetch_jobs(session, company))


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_breezyhr_network_failure_returns_empty(mock_sleep):
    source = BreezyHRSource()
    session = AsyncMock()
    session.get = AsyncMock(side_effect=ConnectionError("boom"))

    company = {"name": "Down", "slug": "down"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_breezyhr_non_remote_location_name():
    source = BreezyHRSource()
    data = [
        {
            "id": "1",
            "name": "Office Manager",
            "url": "https://acme.breezy.hr/p/1",
            "location": {"name": "Austin, TX", "is_remote": False},
        },
    ]
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs[0].location == "Austin, TX"
    assert jobs[0].remote is False
