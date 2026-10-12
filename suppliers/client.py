"""Fetch a complete supplier snapshot before opening a database transaction."""

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from django.conf import settings

from core.errors import APIError


def unavailable():
    return APIError(
        "SUPPLIER_UNAVAILABLE",
        "Could not fetch the complete supplier feed. No catalogue changes were applied.",
        502,
    )


def retry_delay(header):
    try:
        return max(0, float(header))
    except (TypeError, ValueError):
        try:
            return max(
                0, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
            )
        except (TypeError, ValueError, OverflowError):
            return 1.0


def fetch_feed():
    deadline = time.monotonic() + 105
    url = settings.SUPPLIER_API_URL.rstrip("/") + "/v1/products"
    if not settings.SUPPLIER_API_KEY:
        raise unavailable()
    items, seen, cursor = [], set(), None
    pages = requests_made = 0
    with requests.Session() as session:
        while True:
            params = {"limit": 20}
            if cursor is not None:
                params["cursor"] = cursor
            body = None
            for attempt in range(5):
                remaining = deadline - time.monotonic()
                if remaining < 1:
                    raise unavailable()
                delay = min(0.25 * (2**attempt), 2)
                requests_made += 1
                try:
                    response = session.get(
                        url,
                        headers={"X-Api-Key": settings.SUPPLIER_API_KEY},
                        params=params,
                        timeout=(min(3, remaining / 4), min(12, remaining / 2)),
                        allow_redirects=False,
                    )
                    if response.status_code == 200:
                        body = response.json()
                        if (
                            not isinstance(body, dict)
                            or not isinstance(body.get("items"), list)
                            or "next_cursor" not in body
                        ):
                            raise unavailable()
                        break
                    if response.status_code == 429:
                        delay = retry_delay(response.headers.get("Retry-After"))
                    elif not 500 <= response.status_code <= 599:
                        raise unavailable()
                except requests.RequestException:
                    pass
                except ValueError:
                    raise unavailable()
                if attempt == 4 or delay >= deadline - time.monotonic():
                    raise unavailable()
                time.sleep(delay)
            if body is None:
                raise unavailable()
            pages += 1
            items.extend(body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise unavailable()
            seen.add(cursor)
    return items, {"pages_fetched": pages, "requests_made": requests_made}
