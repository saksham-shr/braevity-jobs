import asyncio
import json
import pytest
from unittest.mock import AsyncMock
from braevity.sources.base import BoardGoneError
from braevity.sources.ashby import AshbySource


def _mock_response(data, status=200, content_type="application/json"):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=data)
    resp.headers = {"Content-Type": content_type}
    resp.text = AsyncMock(return_value=json.dumps(data))
    return resp


def test_ashby_parses_jobs():
    source = AshbySource()
    api_data = {
        "data": {
            "jobBoard": {
                "jobPostings": [
                    {
                        "id": "abc-123",
                        "title": "Product Engineer",
                        "locationName": "San Francisco",
                    },
                ]
            }
        }
    }
    session = AsyncMock()
    session.post = AsyncMock(return_value=_mock_response(api_data))

    company = {"name": "Linear", "org": "linear"}
    jobs = asyncio.run(source.fetch_jobs(session, company))

    assert len(jobs) == 1
    assert jobs[0].title == "Product Engineer"
    assert jobs[0].company == "Linear"
    assert jobs[0].location == "San Francisco"
    assert "ashbyhq.com/linear/abc-123" in jobs[0].url
    assert jobs[0].source == "ashby"


def test_ashby_graphql_error():
    """An unknown org on Ashby's shared endpoint signals via a GraphQL
    error, not an HTTP 404 — that's the real "board gone" signal here."""
    source = AshbySource()
    api_data = {"errors": [{"message": "Not found"}]}
    session = AsyncMock()
    session.post = AsyncMock(return_value=_mock_response(api_data))

    with pytest.raises(BoardGoneError):
        asyncio.run(source.fetch_jobs(session, {"name": "X", "org": "x"}))
