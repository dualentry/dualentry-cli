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
    def __init__(self, api_url: str, *, access_token: str | None = None, refresh_token: str | None = None, client_id: str | None = None, api_key: str | None = None):
        self._api_url = api_url.rstrip("/")
        self._base_url = f"{self._api_url}/public/v2"
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._api_key = api_key

        headers = self._build_headers()
        self._client = httpx.Client(base_url=self._base_url, headers=headers, timeout=30.0)

    def _build_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"X-API-KEY": self._api_key}
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    @classmethod
    def from_env(cls, api_url: str) -> DualEntryClient:
        api_key = os.environ.get("X_API_KEY", "")
        if not api_key:
            msg = "X_API_KEY environment variable is not set"
            raise ValueError(msg)
        return cls(api_url=api_url, api_key=api_key)

    def _try_refresh(self) -> bool:
        """Attempt to refresh the access token. Returns True if successful."""
        if not self._refresh_token or not self._client_id:
            return False
        try:
            from dualentry_cli.auth import refresh_access_token, store_tokens

            mcp_url = f"{self._api_url}/mcp"
            token_response = refresh_access_token(mcp_url, self._client_id, self._refresh_token)
            self._access_token = token_response["access_token"]
            self._refresh_token = token_response.get("refresh_token", self._refresh_token)
            store_tokens(self._access_token, self._refresh_token)
            self._client.headers.update({"Authorization": f"Bearer {self._access_token}"})
        except Exception:
            return False
        else:
            return True

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise APIError(response.status_code, str(detail))
        return response.json()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self._client.request(method, path, **kwargs)
        if response.status_code in (401, 403) and self._access_token and self._try_refresh():
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

        while True:
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
