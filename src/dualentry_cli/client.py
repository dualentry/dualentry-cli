"""HTTP client for the DualEntry public API."""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx

from dualentry_cli import USER_AGENT

# Status codes that should be retried (transient errors)
_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s


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

    def _handle_response(self, response: httpx.Response) -> dict:
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
        if status == 429:
            raise APIError(429, "Rate limited. Please wait and try again.")
        if status >= 500:
            raise APIError(status, f"Server error ({status}). The API may be temporarily unavailable.")
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
        if not self._retry:
            response = self._client.request(method, path, **kwargs)
            return self._handle_response(response)

        # Retry logic with visible feedback
        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.request(method, path, **kwargs)
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    return self._handle_response(response)
                # Retryable error - will retry
                last_error = APIError(response.status_code, f"Temporary error ({response.status_code})")
            except httpx.RequestError as e:
                last_error = e

            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                print(f"Retrying in {delay}s... (attempt {attempt + 2}/{_MAX_RETRIES})", file=sys.stderr)
                time.sleep(delay)

        # Final attempt
        response = self._client.request(method, path, **kwargs)
        return self._handle_response(response)

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

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
