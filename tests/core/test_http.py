import asyncio
from unittest.mock import AsyncMock, patch
from braevity.core.http import fetch


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


def test_post_method_routes_to_session_post():
    session = AsyncMock()
    session.post = AsyncMock(return_value=_resp(200))

    resp = asyncio.run(fetch(session, "POST", "https://x.com/jobs", json={"a": 1}))

    assert resp.status == 200
    session.post.assert_awaited_once_with("https://x.com/jobs", json={"a": 1}, timeout=15)
