import httpx
import pytest
import respx

class TestDualEntryClient:
    def test_sets_api_key_header(self):
        from dualentry_cli.client import DualEntryClient
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="org_live_xxxx_secret")
        assert client._client.headers["X-API-KEY"] == "org_live_xxxx_secret"

    @respx.mock
    def test_get_request(self):
        from dualentry_cli.client import DualEntryClient
        route = respx.get("https://api.dualentry.com/public/v2/invoices/").mock(
            return_value=httpx.Response(200, json={"items": [], "count": 0})
        )
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        data = client.get("/invoices/")
        assert data == {"items": [], "count": 0}
        assert route.called

    @respx.mock
    def test_post_request(self):
        from dualentry_cli.client import DualEntryClient
        route = respx.post("https://api.dualentry.com/public/v2/invoices/").mock(
            return_value=httpx.Response(201, json={"id": 1, "number": "INV-001"})
        )
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        data = client.post("/invoices/", json={"customer_id": 1})
        assert data == {"id": 1, "number": "INV-001"}

    @respx.mock
    def test_handles_error_response(self):
        from dualentry_cli.client import APIError, DualEntryClient
        respx.get("https://api.dualentry.com/public/v2/invoices/").mock(
            return_value=httpx.Response(403, json={"success": False, "errors": {"__all__": ["Access denied"]}})
        )
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        with pytest.raises(APIError, match="403"):
            client.get("/invoices/")

    def test_from_env_uses_api_key_env_var(self, monkeypatch):
        from dualentry_cli.client import DualEntryClient
        monkeypatch.setenv("X_API_KEY", "env_key_123")
        client = DualEntryClient.from_env(api_url="https://api.dualentry.com")
        assert client._client.headers["X-API-KEY"] == "env_key_123"
