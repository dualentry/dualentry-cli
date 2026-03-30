import hashlib
import json
from unittest.mock import patch
import httpx
import pytest
import respx

class TestPKCE:
    def test_generate_pkce_pair(self):
        from dualentry_cli.auth import generate_pkce_pair
        verifier, challenge = generate_pkce_pair()
        assert len(verifier) >= 43
        assert challenge == hashlib.sha256(verifier.encode()).hexdigest()

class TestCredentialStorage:
    def test_store_and_load_api_key(self):
        from dualentry_cli.auth import load_api_key, store_api_key
        with patch("dualentry_cli.auth.keyring") as mock_keyring:
            mock_keyring.get_password.return_value = "org_live_xxxx_secret"
            store_api_key("org_live_xxxx_secret")
            mock_keyring.set_password.assert_called_once_with("dualentry-cli", "api_key", "org_live_xxxx_secret")
            key = load_api_key()
            assert key == "org_live_xxxx_secret"

    def test_clear_api_key(self):
        from dualentry_cli.auth import clear_api_key
        with patch("dualentry_cli.auth.keyring") as mock_keyring:
            clear_api_key()
            mock_keyring.delete_password.assert_called_once_with("dualentry-cli", "api_key")

class TestStartAuthorize:
    @respx.mock
    def test_calls_authorize_endpoint(self):
        from dualentry_cli.auth import start_authorize
        route = respx.post("https://api.dualentry.com/public/v2/oauth/authorize/").mock(
            return_value=httpx.Response(200, json={"authorization_url": "https://authkit.workos.com/authorize?state=abc"})
        )
        url = start_authorize(api_url="https://api.dualentry.com", redirect_uri="http://localhost:9876/callback", code_challenge="test_challenge", state="test_state")
        assert url == "https://authkit.workos.com/authorize?state=abc"
        assert route.called

class TestExchangeToken:
    @respx.mock
    def test_exchanges_code_for_api_key(self):
        from dualentry_cli.auth import exchange_token
        route = respx.post("https://api.dualentry.com/public/v2/oauth/token/").mock(
            return_value=httpx.Response(200, json={"api_key": "org_live_xxxx_secret", "organization_id": 123, "user_email": "user@example.com"})
        )
        result = exchange_token(api_url="https://api.dualentry.com", code="auth_code_123", code_verifier="test_verifier", redirect_uri="http://localhost:9876/callback")
        assert result["api_key"] == "org_live_xxxx_secret"
        assert result["organization_id"] == 123
        assert route.called
