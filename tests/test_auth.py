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

    def test_rfc7636_appendix_b_vector(self):
        """Verify PKCE uses base64url(SHA256()) per RFC 7636 appendix B."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        actual = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        assert actual == expected


class TestCredentialStorage:
    def test_store_and_load_api_key(self):
        from dualentry_cli.auth import load_api_key, store_api_key

        with patch("dualentry_cli.auth.keyring") as mock_keyring:
            mock_keyring.get_password.return_value = "key_123"
            store_api_key("key_123")
            mock_keyring.set_password.assert_called_once_with("dualentry-cli", "api_key", "key_123")
            key = load_api_key()
            assert key == "key_123"

    def test_clear_credentials(self):
        from dualentry_cli.auth import clear_credentials

        with patch("dualentry_cli.auth.keyring") as mock_keyring:
            clear_credentials()
            mock_keyring.delete_password.assert_called_once_with("dualentry-cli", "api_key")


class TestAuthorize:
    @respx.mock
    def test_authorize_returns_url(self):
        from dualentry_cli.auth import _authorize

        route = respx.post("https://api.dualentry.com/public/v2/oauth/authorize/").mock(
            return_value=httpx.Response(200, json={"authorization_url": "https://authkit.workos.com/authorize?state=abc"})
        )
        url = _authorize("https://api.dualentry.com", "http://localhost:9876/callback", "challenge", "state")
        assert url == "https://authkit.workos.com/authorize?state=abc"
        assert route.called


class TestExchangeCode:
    @respx.mock
    def test_exchanges_code_for_api_key(self):
        from dualentry_cli.auth import _exchange_code

        route = respx.post("https://api.dualentry.com/public/v2/oauth/token/").mock(
            return_value=httpx.Response(200, json={"api_key": "org_live_xxxx", "organization_id": 42, "user_email": "test@example.com"})
        )
        result = _exchange_code("https://api.dualentry.com", "auth_code_123", "test_verifier", "http://localhost:9876/callback")
        assert result["api_key"] == "org_live_xxxx"
        assert result["organization_id"] == 42
        assert route.called
