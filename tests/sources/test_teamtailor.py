import asyncio
import json
import pytest
from unittest.mock import AsyncMock
from braevity.sources.base import BoardGoneError
from braevity.sources.teamtailor import TeamtailorSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_teamtailor_parses_embedded_jobposting():
    source = TeamtailorSource()
    data = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "2Care",
        "items": [
            {
                "id": "6cd48327",
                "title": "Nurse",
                "url": "https://2care.teamtailor.com/jobs/1",
                "date_published": "2026-09-30T11:37:34+02:00",
                "content_html": "<p>...</p>",
                "_jobposting": {
                    "@type": "JobPosting",
                    "title": "Nurse",
                    "hiringOrganization": {"name": "2Care"},
                    "jobLocation": [
                        {"address": {"addressLocality": "Lillestrøm", "addressCountry": "NO"}},
                    ],
                    "datePosted": "2026-09-30T11:37:34+02:00",
                    "url": "https://2care.teamtailor.com/jobs/1",
                },
            },
        ],
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "2Care", "slug": "2care"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Nurse"
    assert jobs[0].company == "2Care"
    assert jobs[0].location == "Lillestrøm, NO"
    assert jobs[0].url == "https://2care.teamtailor.com/jobs/1"
    assert jobs[0].source == "teamtailor"


def test_teamtailor_falls_back_without_embedded_jobposting():
    """If _jobposting is ever missing, fall back to the plain feed fields
    instead of silently dropping the posting."""
    source = TeamtailorSource()
    data = {
        "items": [
            {
                "id": "1",
                "title": "Support Engineer",
                "url": "https://acme.teamtailor.com/jobs/1",
                "date_published": "2026-10-01T00:00:00+00:00",
            },
        ],
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert len(jobs) == 1
    assert jobs[0].title == "Support Engineer"
    assert jobs[0].location is None
    assert jobs[0].source == "teamtailor"


def test_teamtailor_skips_item_without_url():
    source = TeamtailorSource()
    data = {"items": [{"id": "1", "title": "No URL"}]}
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_teamtailor_empty_response():
    source = TeamtailorSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({"items": []}))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_teamtailor_api_error_returns_empty():
    source = TeamtailorSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=403))

    company = {"name": "Down", "slug": "down"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_teamtailor_404_raises_board_gone():
    source = TeamtailorSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "slug": "gone"}
    with pytest.raises(BoardGoneError):
        asyncio.run(source.fetch_jobs(session, company))
