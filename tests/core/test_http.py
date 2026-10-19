import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock, patch
from braevity.core.http import fetch, _parse_retry_after


def _resp(status, headers=None):
    r = AsyncMock()
    r.status = status
    r.headers = headers or {}
    return r


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_404_returns_immediately_no_retry(mock_sleep):
    session = AsyncMock()
    session.get = AsyncMock(return_value=_resp(404))

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp.status == 404
    session.get.assert_awaited_once()
    mock_sleep.assert_not_awaited()


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_200_returns_immediately_no_retry(mock_sleep):
    session = AsyncMock()
    session.get = AsyncMock(return_value=_resp(200))

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp.status == 200
    session.get.assert_awaited_once()
    mock_sleep.assert_not_awaited()


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_429_reads_retry_after_and_retries_once(mock_sleep):
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[
        _resp(429, headers={"Retry-After": "2"}),
        _resp(200),
    ])

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp.status == 200
    assert session.get.await_count == 2
    mock_sleep.assert_awaited_once_with(2.0)


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_429_without_retry_after_uses_backoff(mock_sleep):
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[
        _resp(429),
        _resp(200),
    ])

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp.status == 200
    mock_sleep.assert_awaited_once_with(1.0)


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_500_retries_then_returns_failing_response(mock_sleep):
    session = AsyncMock()
    session.get = AsyncMock(return_value=_resp(500))

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp.status == 500
    assert session.get.await_count == 3  # initial + 2 retries
    assert mock_sleep.await_count == 2


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_timeout_exception_retries_then_returns_none(mock_sleep):
    session = AsyncMock()
    session.get = AsyncMock(side_effect=asyncio.TimeoutError())

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp is None
    assert session.get.await_count == 3
    assert mock_sleep.await_count == 2


@patch("braevity.core.http.asyncio.sleep", new_callable=AsyncMock)
def test_429_retry_after_http_date(mock_sleep):
    future = datetime.now(timezone.utc) + timedelta(seconds=5)
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[
        _resp(429, headers={"Retry-After": format_datetime(future, usegmt=True)}),
        _resp(200),
    ])

    resp = asyncio.run(fetch(session, "GET", "https://x.com/jobs"))

    assert resp.status == 200
    assert mock_sleep.await_count == 1
    delay = mock_sleep.await_args[0][0]
    assert 0 <= delay <= 6


def test_parse_retry_after_malformed_falls_back():
    assert _parse_retry_after("not a date or number", fallback=1.0) == 1.0


def test_parse_retry_after_caps_huge_value():
    assert _parse_retry_after("999999", fallback=1.0) == 60.0


def test_parse_retry_after_none_uses_fallback():
    assert _parse_retry_after(None, fallback=1.0) == 1.0


def test_post_method_routes_to_session_post():
    session = AsyncMock()
    session.post = AsyncMock(return_value=_resp(200))

    resp = asyncio.run(fetch(session, "POST", "https://x.com/jobs", json={"a": 1}))

    assert resp.status == 200
    session.post.assert_awaited_once_with("https://x.com/jobs", json={"a": 1}, timeout=15)
