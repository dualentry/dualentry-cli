"""HTTP client for the DualEntry public API."""
from __future__ import annotations
import os
from typing import Any
import httpx

class APIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")

class DualEntryClient:
    def __init__(self, api_url: str, api_key: str):
        self._base_url = f"{api_url.rstrip('/')}/public/v2"
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"X-API-KEY": api_key},
            timeout=30.0,
        )

    @classmethod
    def from_env(cls, api_url: str) -> DualEntryClient:
        api_key = os.environ.get("X_API_KEY", "")
        if not api_key:
            msg = "X_API_KEY environment variable is not set"
            raise ValueError(msg)
        return cls(api_url=api_url, api_key=api_key)

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise APIError(response.status_code, str(detail))
        return response.json()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        response = self._client.get(path, params=params)
        return self._handle_response(response)

    def post(self, path: str, json: dict[str, Any] | None = None) -> dict:
        response = self._client.post(path, json=json)
        return self._handle_response(response)

    def put(self, path: str, json: dict[str, Any] | None = None) -> dict:
        response = self._client.put(path, json=json)
        return self._handle_response(response)

    def close(self):
        self._client.close()
