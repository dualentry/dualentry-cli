import base64
import hashlib
from unittest.mock import patch

import httpx
import respx


class TestPKCE:
    def test_generate_pkce_pair(self):
        from dualentry_cli.auth import _generate_pkce_pair

        verifier, challenge = _generate_pkce_pair()
        assert len(verifier) >= 43
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode("ascii")
        assert challenge == expected


class TestCredentialStorage:
    def test_store_and_load_tokens(self):
        from dualentry_cli.auth import load_tokens, store_tokens

        with patch("dualentry_cli.auth.keyring") as mock_keyring:
            mock_keyring.get_password.side_effect = lambda _svc, key: {"access_token": "acc_123", "refresh_token": "ref_456"}.get(key)
            store_tokens("acc_123", "ref_456")
            assert mock_keyring.set_password.call_count == 2
            access, refresh = load_tokens()
            assert access == "acc_123"
            assert refresh == "ref_456"

    def test_clear_credentials(self):
        from dualentry_cli.auth import clear_credentials

        with patch("dualentry_cli.auth.keyring") as mock_keyring:
            clear_credentials()
            assert mock_keyring.delete_password.call_count == 3


class TestRegisterClient:
    @respx.mock
    def test_registers_oauth_client(self):
        from dualentry_cli.auth import _register_client

        route = respx.post("https://api.dualentry.com/mcp/register").mock(return_value=httpx.Response(200, json={"client_id": "client_abc", "client_secret": ""}))
        result = _register_client("https://api.dualentry.com/mcp", "http://localhost:9876/callback")
        assert result["client_id"] == "client_abc"
        assert route.called


class TestExchangeToken:
    @respx.mock
    def test_exchanges_code_for_tokens(self):
        from dualentry_cli.auth import _exchange_token

        route = respx.post("https://api.dualentry.com/mcp/token").mock(
            return_value=httpx.Response(200, json={"access_token": "acc_xyz", "refresh_token": "ref_xyz", "expires_in": 43200, "token_type": "Bearer"})
        )
        result = _exchange_token(
            mcp_url="https://api.dualentry.com/mcp", client_id="client_abc", code="auth_code_123", code_verifier="test_verifier", redirect_uri="http://localhost:9876/callback"
        )
        assert result["access_token"] == "acc_xyz"
        assert result["refresh_token"] == "ref_xyz"
        assert route.called


class TestRefreshToken:
    @respx.mock
    def test_refreshes_access_token(self):
        from dualentry_cli.auth import refresh_access_token

        route = respx.post("https://api.dualentry.com/mcp/token").mock(
            return_value=httpx.Response(200, json={"access_token": "acc_new", "refresh_token": "ref_new", "expires_in": 43200, "token_type": "Bearer"})
        )
        result = refresh_access_token(mcp_url="https://api.dualentry.com/mcp", client_id="client_abc", refresh_token="ref_old")
        assert result["access_token"] == "acc_new"
        assert route.called
