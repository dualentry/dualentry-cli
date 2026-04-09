import httpx
import pytest
import respx


class TestDualEntryClient:
    def test_sets_api_key_header(self):
        from dualentry_cli.client import DualEntryClient

        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="org_live_xxxx_secret")
        assert client._client.headers["X-API-KEY"] == "org_live_xxxx_secret"

    def test_sets_user_agent_header(self):
        from dualentry_cli import USER_AGENT
        from dualentry_cli.client import DualEntryClient

        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        assert client._client.headers["User-Agent"] == USER_AGENT

    @respx.mock
    def test_get_request(self):
        from dualentry_cli.client import DualEntryClient

        route = respx.get("https://api.dualentry.com/public/v2/invoices/").mock(return_value=httpx.Response(200, json={"items": [], "count": 0}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        data = client.get("/invoices/")
        assert data == {"items": [], "count": 0}
        assert route.called

    @respx.mock
    def test_post_request(self):
        from dualentry_cli.client import DualEntryClient

        respx.post("https://api.dualentry.com/public/v2/invoices/").mock(return_value=httpx.Response(201, json={"id": 1, "number": "INV-001"}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        data = client.post("/invoices/", json={"customer_id": 1})
        assert data == {"id": 1, "number": "INV-001"}

    @respx.mock
    def test_handles_error_response(self):
        from dualentry_cli.client import APIError, DualEntryClient

        respx.get("https://api.dualentry.com/public/v2/invoices/").mock(return_value=httpx.Response(403, json={"success": False, "errors": {"__all__": ["Access denied"]}}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        with pytest.raises(APIError, match="403"):
            client.get("/invoices/")

    def test_from_env_uses_api_key_env_var(self, monkeypatch):
        from dualentry_cli.client import DualEntryClient

        monkeypatch.setenv("X_API_KEY", "env_key_123")
        client = DualEntryClient.from_env(api_url="https://api.dualentry.com")
        assert client._client.headers["X-API-KEY"] == "env_key_123"


class TestErrorMessages:
    """Test that error responses produce helpful messages."""

    @respx.mock
    def test_401_suggests_login(self):
        from dualentry_cli.client import APIError, DualEntryClient

        respx.get("https://api.dualentry.com/public/v2/test/").mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="bad_key")
        with pytest.raises(APIError) as exc:
            client.get("/test/")
        assert "dualentry auth login" in exc.value.detail

    @respx.mock
    def test_404_says_not_found(self):
        from dualentry_cli.client import APIError, DualEntryClient

        respx.get("https://api.dualentry.com/public/v2/invoices/999/").mock(return_value=httpx.Response(404, json={"error": "not found"}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        with pytest.raises(APIError) as exc:
            client.get("/invoices/999/")
        assert "not found" in exc.value.detail.lower()

    @respx.mock
    def test_422_shows_validation_details(self):
        from dualentry_cli.client import APIError, DualEntryClient

        respx.post("https://api.dualentry.com/public/v2/invoices/").mock(return_value=httpx.Response(422, json={"errors": {"customer_id": ["required"]}}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        with pytest.raises(APIError) as exc:
            client.post("/invoices/", json={})
        assert "validation" in exc.value.detail.lower()
        assert "customer_id" in exc.value.detail

    @respx.mock
    def test_429_says_rate_limited(self):
        from dualentry_cli.client import APIError, DualEntryClient

        respx.get("https://api.dualentry.com/public/v2/invoices/").mock(return_value=httpx.Response(429, json={"error": "too many requests"}))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        with pytest.raises(APIError) as exc:
            client.get("/invoices/")
        assert "rate limited" in exc.value.detail.lower()

    @respx.mock
    def test_500_says_server_error(self):
        from dualentry_cli.client import APIError, DualEntryClient

        respx.get("https://api.dualentry.com/public/v2/invoices/").mock(return_value=httpx.Response(500, text="Internal Server Error"))
        client = DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key")
        with pytest.raises(APIError) as exc:
            client.get("/invoices/")
        assert "server error" in exc.value.detail.lower()


class TestContextManager:
    """Test client as context manager."""

    def test_context_manager_closes_client(self):
        from dualentry_cli.client import DualEntryClient

        with DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key") as client:
            assert client._client is not None
        assert client._client.is_closed
