import asyncio
import pytest
from unittest.mock import AsyncMock
from braevity.sources.base import BoardGoneError
from braevity.sources.personio import PersonioSource

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
<position>
    <id>1761414</id>
    <office>Dublin</office>
    <department>Technical</department>
    <recruitingCategory>Full Time</recruitingCategory>
    <name>ARCHITECT - DUBLIN</name>
    <employmentType>permanent</employmentType>
    <createdAt>2024-10-01T17:44:49+00:00</createdAt>
</position>
<position>
    <id>99</id>
    <office>Remote</office>
    <name>REMOTE ENGINEER</name>
    <employmentType>permanent</employmentType>
    <createdAt>2026-01-01T00:00:00+00:00</createdAt>
</position>
</workzag-jobs>
"""


def _mock_response(text, status=200):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    return resp


def test_personio_parses_positions():
    source = PersonioSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(SAMPLE_XML))

    company = {"name": "TODD Architects", "slug": "todd"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 2
    assert jobs[0].title == "ARCHITECT - DUBLIN"
    assert jobs[0].company == "TODD Architects"
    assert jobs[0].location == "Dublin"
    assert jobs[0].url == "https://todd.jobs.personio.com/job/1761414"
    assert jobs[0].posted_date == "2024-10-01T17:44:49+00:00"
    assert jobs[0].employment_type == "permanent"
    assert jobs[0].source == "personio"


NAMESPACED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs xmlns="https://www.personio.com/xml/job">
<position>
    <id>555</id>
    <office>Berlin</office>
    <name>NAMESPACED ROLE</name>
    <employmentType>permanent</employmentType>
    <createdAt>2026-02-01T00:00:00+00:00</createdAt>
</position>
</workzag-jobs>
"""


def test_personio_parses_namespaced_positions():
    source = PersonioSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(NAMESPACED_XML))

    company = {"name": "NSCo", "slug": "nsco"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "NAMESPACED ROLE"
    assert jobs[0].location == "Berlin"
    assert jobs[0].url == "https://nsco.jobs.personio.com/job/555"


def test_personio_skips_position_without_id():
    source = PersonioSource()
    xml = """<?xml version="1.0"?><workzag-jobs><position><name>No ID</name></position></workzag-jobs>"""
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(xml))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_personio_empty_feed():
    source = PersonioSource()
    xml = """<?xml version="1.0"?><workzag-jobs></workzag-jobs>"""
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(xml))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_personio_malformed_xml_returns_empty():
    source = PersonioSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response("not xml at all <<<"))

    company = {"name": "Acme", "slug": "acme"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_personio_api_error_returns_empty():
    source = PersonioSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response("", status=403))

    company = {"name": "Down", "slug": "down"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_personio_404_raises_board_gone():
    source = PersonioSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response("", status=404))

    company = {"name": "Gone", "slug": "gone"}
    with pytest.raises(BoardGoneError):
        asyncio.run(source.fetch_jobs(session, company))
