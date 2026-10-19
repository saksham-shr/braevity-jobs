import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from aiohttp import ClientResponse, ClientSession

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
MAX_RETRIES = 2
BACKOFF_SECONDS = [1.0, 2.0]
MAX_RETRY_AFTER = 60.0


def _parse_retry_after(raw: str | None, fallback: float) -> float:
    """Retry-After is either delay-seconds or an HTTP-date (RFC 7231) —
    handle both, and cap the result so a malformed or huge value can't
    block a fetch for an unreasonable time."""
    if not raw:
        return fallback
    try:
        return min(float(raw), MAX_RETRY_AFTER)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        delay = (when - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delay, MAX_RETRY_AFTER))
    except (TypeError, ValueError):
        return fallback


async def fetch(
    session: ClientSession, method: str, url: str, **kwargs
) -> ClientResponse | None:
    """Shared fetch wrapper: timeout, 429 Retry-After cooldown, bounded
    retry on 429/5xx/timeout. A 404 or other 4xx is a terminal result —
    returned immediately, never retried."""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    call = session.get if method.upper() == "GET" else session.post

    attempt = 0
    while True:
        try:
            resp = await call(url, **kwargs)
        except Exception as e:
            if attempt >= MAX_RETRIES:
                logger.warning("%s %s failed after %d retries: %s", method, url, attempt, e)
                return None
            await asyncio.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
            attempt += 1
            continue

        if resp.status == 429:
            if attempt >= MAX_RETRIES:
                return resp
            fallback = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
            delay = _parse_retry_after(resp.headers.get("Retry-After"), fallback)
            await asyncio.sleep(delay)
            attempt += 1
            continue

        if 500 <= resp.status < 600:
            if attempt >= MAX_RETRIES:
                return resp
            await asyncio.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
            attempt += 1
            continue

        return resp
