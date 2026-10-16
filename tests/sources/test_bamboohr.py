import asyncio
import json
from unittest.mock import AsyncMock
from braevity.sources.bamboohr import BambooHRSource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_bamboohr_parses_jobs():
    source = BambooHRSource()
    data = {
        "meta": {"totalCount": 1},
        "result": [
            {
                "id": "163",
                "jobOpeningName": "Facilities & Fleet Attendant",
                "departmentLabel": "Facilities & Fleet",
                "location": {"city": "Saskatoon", "state": "Saskatchewan"},
            },
        ],
    }
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response(data))

    company = {"name": "G2", "subdomain": "g2"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Facilities & Fleet Attendant"
    assert jobs[0].company == "G2"
    assert jobs[0].location == "Saskatoon, Saskatchewan"
    assert jobs[0].url == "https://g2.bamboohr.com/careers/163"
    assert jobs[0].source == "bamboohr"


def test_bamboohr_empty_response():
    source = BambooHRSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({"result": []}))

    company = {"name": "Empty", "subdomain": "empty"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []


def test_bamboohr_api_error_returns_empty():
    source = BambooHRSource()
    session = AsyncMock()
    session.get = AsyncMock(return_value=_mock_response({}, status=404))

    company = {"name": "Gone", "subdomain": "gone"}
    jobs = asyncio.run(source.fetch_jobs(session, company))
    assert jobs == []
