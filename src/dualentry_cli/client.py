"""HTTP client for the DualEntry public API."""

from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any

import httpx

from dualentry_cli import USER_AGENT

# Status codes that should be retried (transient errors)
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
# Transient transport failures. Deliberately excludes LocalProtocolError,
# UnsupportedProtocol, DecodingError and TooManyRedirects: those fail the same
# way every time, so retrying only delays the error the user needs to see.
_RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
_RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
_MAX_RETRIES = len(_RETRY_DELAYS)

# The API replays the original response for a repeated Idempotency-Key instead of
# running the operation again, so a retried write cannot create a duplicate record.
# https://docs.dualentry.com/developers/release-notes/2026-08-12
_IDEMPOTENCY_HEADER = "Idempotency-Key"
_IDEMPOTENCY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# 429 and the in-flight 409 both report exactly how long to wait.
# https://docs.dualentry.com/developers/guides/rate-limiting
_RETRY_AFTER_HEADER = "Retry-After"

_MAX_RETRY_AFTER = 60


def _retry_after_seconds(response: httpx.Response) -> int | None:
    """Seconds from the Retry-After header, or None if absent or unusable."""
    raw = response.headers.get(_RETRY_AFTER_HEADER)
    if raw is None:
        return None
    try:
        # RFC 9110 delay-seconds is a non-negative integer
        seconds = int(raw.strip())
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def _is_retryable(response: httpx.Response) -> bool:
    """
    Whether this response should be retried with the same idempotency key.

    409 means two different things, told apart by Retry-After:
    with the header the first request is still running and we should retry;
    without it the original response was too large to store, the write did not run again
    https://docs.dualentry.com/developers/guides/idempotency-and-write-validation
    """
    if response.status_code == 409:
        return _RETRY_AFTER_HEADER in response.headers
    return response.status_code in _RETRYABLE_STATUS_CODES


def _server_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text.strip()
    errors = payload.get("errors", payload) if isinstance(payload, dict) else payload
    if isinstance(errors, dict):
        messages = []
        for field, msgs in errors.items():
            if isinstance(msgs, list):
                messages.extend(str(msg) for msg in msgs)
            else:
                messages.append(f"{field}: {msgs}")
        return "; ".join(messages)
    return str(errors)


def _explain(message: str, detail: str) -> str:
    return f"{message} Server said: {detail}" if detail else message


class APIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class DualEntryClient:
    def __init__(self, api_url: str, *, api_key: str, retry: bool = False):
        self._api_url = api_url.rstrip("/")
        self._base_url = f"{self._api_url}/public/v2"
        self._retry = retry
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "X-API-KEY": api_key,
                "User-Agent": USER_AGENT,
            },
            timeout=30.0,
        )

    @classmethod
    def from_env(cls, api_url: str, *, retry: bool = False) -> DualEntryClient:
        api_key = os.environ.get("X_API_KEY", "")
        if not api_key:
            msg = "X_API_KEY environment variable is not set"
            raise ValueError(msg)
        return cls(api_url=api_url, api_key=api_key, retry=retry)

    def _handle_response(self, response: httpx.Response, *, sent_idempotency_key: bool = False) -> dict:
        status = response.status_code
        if status == 401:
            raise APIError(401, "API key is invalid or expired. Run: dualentry auth login")
        if status == 403:
            raise APIError(403, "API key authentication failed. Run: dualentry auth login")
        if status == 404:
            raise APIError(404, "Resource not found. Check the ID or number and try again.")
        if status == 422:
            try:
                detail = response.json()
                errors = detail.get("errors", detail)
            except Exception:
                errors = response.text
            raise APIError(422, f"Validation error: {errors}")
        if status == 409:
            detail = _server_detail(response)
            if _RETRY_AFTER_HEADER in response.headers:
                wait = _retry_after_seconds(response)
                when = f"Retry in {wait}s with the same key." if wait is not None else "Retry shortly with the same key."
                raise APIError(409, _explain(f"The first request with this idempotency key is still being processed. {when}", detail))
            if sent_idempotency_key:
                raise APIError(
                    409,
                    _explain(
                        "The original response is too large to replay (over 256 KB). "
                        "The write was not repeated - check whether the record already exists before sending it again.",
                        detail,
                    ),
                )
            raise APIError(409, detail or "Conflict.")
        if status == 429:
            wait = _retry_after_seconds(response)
            if wait is not None:
                raise APIError(429, f"Rate limited. Retry after {wait}s.")
            raise APIError(429, "Rate limited. Please wait and try again.")
        if status >= 500:
            wait = _retry_after_seconds(response)
            when = f" The server asked to retry after {wait}s." if wait is not None else ""
            raise APIError(status, f"Server error ({status}). The API may be temporarily unavailable.{when}")
        if status >= 400:
            try:
                detail = response.json()
            except Exception:
                raise APIError(status, response.text) from None
            errors = detail.get("errors", detail) if isinstance(detail, dict) else detail
            if isinstance(errors, dict):
                messages = []
                for field, msgs in errors.items():
                    if isinstance(msgs, list):
                        messages.extend(msgs)
                    else:
                        messages.append(f"{field}: {msgs}")
                raise APIError(status, "; ".join(messages) if messages else str(detail))
            raise APIError(status, str(errors))
        return response.json()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        method = method.upper()
        keyed = method in _IDEMPOTENCY_METHODS
        if keyed:
            # One key per logical request, deliberately generated here rather than
            # per attempt: reusing it across retries is what makes a retry safe.
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault(_IDEMPOTENCY_HEADER, str(uuid.uuid4()))
            kwargs["headers"] = headers

        if not self._retry:
            response = self._client.request(method, path, **kwargs)
            return self._handle_response(response, sent_idempotency_key=keyed)

        # Retry logic with visible feedback
        for attempt, backoff in enumerate(_RETRY_DELAYS):
            retry_after = None
            try:
                response = self._client.request(method, path, **kwargs)
                if not _is_retryable(response):
                    return self._handle_response(response, sent_idempotency_key=keyed)
                retry_after = _retry_after_seconds(response)
                if retry_after is not None and retry_after > _MAX_RETRY_AFTER:
                    return self._handle_response(response, sent_idempotency_key=keyed)
            except _RETRYABLE_EXCEPTIONS:
                pass

            # every retry waits, including the one after the loop
            delay = retry_after if retry_after is not None else backoff
            print(f"\033[33mRetrying in {delay}s... (attempt {attempt + 2}/{_MAX_RETRIES + 1})\033[0m", file=sys.stderr)
            time.sleep(delay)

        # Final attempt
        response = self._client.request(method, path, **kwargs)
        return self._handle_response(response, sent_idempotency_key=keyed)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        return self._request("GET", path, params=params)

    def paginate(self, path: str, params: dict[str, Any] | None = None, page_size: int = 100, max_items: int | None = None) -> dict:
        """Fetch all pages and return combined {items: [...], count: N}."""
        params = dict(params or {})
        params["limit"] = page_size
        params["offset"] = 0
        all_items = []
        max_pages = 1000

        for _ in range(max_pages):
            data = self.get(path, params=params)
            items = data.get("items", [])
            all_items.extend(items)
            total = data.get("count", len(items))
            if max_items and len(all_items) >= max_items:
                all_items = all_items[:max_items]
                break
            if len(all_items) >= total or not items:
                break
            params["offset"] += page_size

        return {"items": all_items, "count": len(all_items)}

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict:
        return self._request("POST", path, json=json)

    def put(self, path: str, json: dict[str, Any] | None = None) -> dict:
        return self._request("PUT", path, json=json)

    def patch(self, path: str, json: dict[str, Any] | None = None) -> dict:
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
