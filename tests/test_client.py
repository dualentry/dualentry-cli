import uuid
from types import SimpleNamespace

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


class TestIdempotencyKey:
    """
    Writes carry an Idempotency-Key so a retry cannot duplicate a record.

    The API replays the original response for a repeated key rather than running
    the operation again: https://docs.dualentry.com/developers/release-notes/2026-08-12
    """

    BASE = "https://api.dualentry.com/public/v2"

    @pytest.fixture
    def no_backoff(self, monkeypatch):
        """Collapse the retry backoff so retry tests stay fast."""
        monkeypatch.setattr("dualentry_cli.client._RETRY_DELAYS", [0, 0, 0])

    @staticmethod
    def _client(*, retry=False):
        from dualentry_cli.client import DualEntryClient

        return DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key", retry=retry)

    @pytest.mark.parametrize(
        ("method", "call"),
        [
            ("post", lambda c: c.post("/invoices/", json={"customer_id": 1})),
            ("put", lambda c: c.put("/invoices/1/", json={"memo": "x"})),
            ("patch", lambda c: c.patch("/customer-payments/1/", json={"memo": "x"})),
            ("delete", lambda c: c.delete("/invoices/1/")),
        ],
    )
    @respx.mock
    def test_write_methods_send_an_idempotency_key(self, method, call):
        route = getattr(respx, method)(url__startswith=self.BASE).mock(return_value=httpx.Response(200, json={"ok": True}))

        call(self._client())

        key = route.calls[0].request.headers.get("Idempotency-Key")
        assert key is not None, f"{method.upper()} must send an Idempotency-Key"
        # Documented as "a unique value (a UUID works well)", max length 255.
        assert uuid.UUID(key)
        assert len(key) <= 255

    @respx.mock
    def test_get_does_not_send_an_idempotency_key(self):
        route = respx.get(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(200, json={"items": [], "count": 0}))

        self._client().get("/invoices/")

        assert "Idempotency-Key" not in route.calls[0].request.headers

    @pytest.mark.usefixtures("no_backoff")
    @respx.mock
    def test_retry_reuses_the_same_key_across_attempts(self):
        """The whole point: a retried POST must not create a second record."""
        route = respx.post(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(502, text="bad gateway"),
                httpx.Response(201, json={"internal_id": 1}),
            ]
        )

        data = self._client(retry=True).post("/invoices/", json={"customer_id": 1})

        assert data == {"internal_id": 1}
        assert route.call_count == 2
        keys = {c.request.headers["Idempotency-Key"] for c in route.calls}
        assert len(keys) == 1, f"retry must reuse the original key, got {keys}"

    @pytest.mark.usefixtures("no_backoff")
    @respx.mock
    def test_every_retry_attempt_carries_the_key(self):
        from dualentry_cli.client import APIError

        route = respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(502, text="bad gateway"))

        with pytest.raises(APIError):
            self._client(retry=True).post("/invoices/", json={"customer_id": 1})

        # 4, not 3: the loop runs _MAX_RETRIES times and then issues one more
        # request after it. That off-by-one is tracked separately; it is harmless
        # here precisely because every attempt replays the same key.
        assert route.call_count == 4
        keys = {c.request.headers["Idempotency-Key"] for c in route.calls}
        assert len(keys) == 1, f"every attempt must reuse one key, got {keys}"

    @respx.mock
    def test_separate_requests_use_different_keys(self):
        route = respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(201, json={"internal_id": 1}))
        client = self._client()

        client.post("/invoices/", json={"customer_id": 1})
        client.post("/invoices/", json={"customer_id": 2})

        keys = [c.request.headers["Idempotency-Key"] for c in route.calls]
        assert keys[0] != keys[1], "each logical request needs its own key"

    @respx.mock
    def test_caller_supplied_key_is_not_overwritten(self):
        route = respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(201, json={"internal_id": 1}))

        self._client()._request("POST", "/invoices/", json={}, headers={"Idempotency-Key": "caller-supplied-key"})

        assert route.calls[0].request.headers["Idempotency-Key"] == "caller-supplied-key"

    @respx.mock
    def test_key_is_sent_even_when_retry_is_disabled(self):
        """Protects against retries outside our control (proxies, user re-runs are new keys)."""
        route = respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(201, json={"internal_id": 1}))

        self._client(retry=False).post("/invoices/", json={})

        assert "Idempotency-Key" in route.calls[0].request.headers


class TestRetryAfterAndConflicts:
    """
    Retry timing follows the server, and the two meanings of 409 are separated.

    https://docs.dualentry.com/developers/guides/rate-limiting
    https://docs.dualentry.com/developers/guides/idempotency-and-write-validation
    """

    BASE = "https://api.dualentry.com/public/v2"

    @pytest.fixture
    def sleeps(self, monkeypatch):
        """Record what the client would sleep, without actually sleeping."""
        recorded = []
        monkeypatch.setattr("dualentry_cli.client.time", SimpleNamespace(sleep=recorded.append))
        return recorded

    @staticmethod
    def _client():
        from dualentry_cli.client import DualEntryClient

        return DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key", retry=True)

    @respx.mock
    def test_conflict_with_retry_after_is_retried(self, sleeps):
        """A 409 with Retry-After means the first request is still running, so retry with the same key."""
        route = respx.post(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(409, headers={"Retry-After": "2"}, json={"errors": {"__all__": ["still processing"]}}),
                httpx.Response(201, json={"internal_id": 7}),
            ]
        )

        data = self._client().post("/invoices/", json={"customer_id": 1})

        assert data == {"internal_id": 7}
        assert route.call_count == 2
        assert sleeps == [2], "must wait exactly as long as Retry-After says"
        keys = {c.request.headers["Idempotency-Key"] for c in route.calls}
        assert len(keys) == 1, "the retry must reuse the original key"

    @respx.mock
    def test_conflict_without_retry_after_is_not_retried(self, sleeps):
        """A 409 without Retry-After means the response was too large to replay; the write did not run again."""
        from dualentry_cli.client import APIError

        route = respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(409, json={"errors": {"__all__": ["original response cannot be replayed"]}}))

        with pytest.raises(APIError) as exc:
            self._client().post("/invoices/", json={"customer_id": 1})

        assert route.call_count == 1
        assert sleeps == []
        assert exc.value.status_code == 409
        assert "256 KB" in exc.value.detail

    @respx.mock
    def test_rate_limit_waits_for_retry_after_not_the_hardcoded_backoff(self, sleeps):
        """On 429 the server says how long to wait, and that wins over _RETRY_DELAYS."""
        respx.get(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "7"}, json={"errors": {"__all__": ["slow down"]}}),
                httpx.Response(200, json={"items": [], "count": 0}),
            ]
        )

        self._client().get("/invoices/")

        assert sleeps == [7], "Retry-After must win over _RETRY_DELAYS[0] (1s)"

    @respx.mock
    def test_rate_limit_without_retry_after_falls_back_to_backoff(self, sleeps):
        """Without the header there is nothing to follow, so the exponential backoff is used."""
        from dualentry_cli.client import APIError

        respx.get(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(429, json={"errors": {"__all__": ["slow down"]}}))

        with pytest.raises(APIError):
            self._client().get("/invoices/")

        assert sleeps == [1, 2, 4], "no header, so use the exponential backoff"

    @respx.mock
    def test_the_last_attempt_also_waits_for_retry_after(self, sleeps):
        """Every request after a failure waits, including the final one sent after the loop."""
        from dualentry_cli.client import APIError

        route = respx.get(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(429, headers={"Retry-After": "3"}, json={}))

        with pytest.raises(APIError):
            self._client().get("/invoices/")

        assert sleeps == [3, 3, 3], "the request after the loop must wait too"
        assert route.call_count == len(sleeps) + 1

    @pytest.mark.parametrize("bad_value", ["next tuesday", "inf", "Infinity", "1e9", "2.5", "-5", ""])
    @respx.mock
    def test_unparsable_retry_after_falls_back_to_backoff(self, sleeps, bad_value):
        """Values int() cannot use fall back to the backoff; "inf" must never reach time.sleep()."""
        respx.get(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": bad_value}, json={}),
                httpx.Response(200, json={"items": [], "count": 0}),
            ]
        )

        self._client().get("/invoices/")

        assert sleeps == [1], f"{bad_value!r} should fall back to the backoff"

    @pytest.mark.parametrize(
        "error",
        [
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.CloseError,
            httpx.RemoteProtocolError,
        ],
    )
    @respx.mock
    def test_transient_transport_error_is_retried(self, sleeps, error):
        """These can succeed on a second attempt, so they are retried and then propagate."""
        route = respx.get(f"{self.BASE}/invoices/").mock(side_effect=error("boom"))

        with pytest.raises(error):
            self._client().get("/invoices/")

        assert route.call_count == 4
        assert sleeps == [1, 2, 4]

    @pytest.mark.parametrize(
        "error",
        [
            httpx.LocalProtocolError,
            httpx.UnsupportedProtocol,
            httpx.ProxyError,
            httpx.DecodingError,
            httpx.TooManyRedirects,
        ],
    )
    @respx.mock
    def test_non_transient_transport_error_is_not_retried(self, sleeps, error):
        """These fail the same way every time, so they are reported at once."""
        route = respx.get(f"{self.BASE}/invoices/").mock(side_effect=error("broken"))

        with pytest.raises(error):
            self._client().get("/invoices/")

        assert route.call_count == 1
        assert sleeps == []

    @pytest.mark.usefixtures("sleeps")
    @respx.mock
    def test_storage_unavailable_is_retried_with_the_same_key(self):
        """A 503 from idempotency storage should be retried with the same key, as the guide asks."""
        route = respx.post(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(503, json={"errors": {"__all__": ["retry with the same key"]}}),
                httpx.Response(201, json={"internal_id": 9}),
            ]
        )

        data = self._client().post("/invoices/", json={"customer_id": 1})

        assert data == {"internal_id": 9}
        keys = {c.request.headers["Idempotency-Key"] for c in route.calls}
        assert len(keys) == 1


class TestRetryAfterCeilingAndConflictDetail:
    BASE = "https://api.dualentry.com/public/v2"

    @pytest.fixture
    def sleeps(self, monkeypatch):
        recorded = []
        monkeypatch.setattr("dualentry_cli.client.time", SimpleNamespace(sleep=recorded.append))
        return recorded

    @staticmethod
    def _client():
        from dualentry_cli.client import DualEntryClient

        return DualEntryClient(api_url="https://api.dualentry.com", api_key="test_key", retry=True)

    @pytest.mark.parametrize("unreadable", ["soon", "2.5", "-5", ""])
    @respx.mock
    def test_conflict_with_unreadable_retry_after_still_retries(self, sleeps, unreadable):
        route = respx.post(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(409, headers={"Retry-After": unreadable}, json={}),
                httpx.Response(201, json={"internal_id": 5}),
            ]
        )

        data = self._client().post("/invoices/", json={})

        assert data == {"internal_id": 5}
        assert route.call_count == 2
        assert sleeps == [1], f"{unreadable!r} should fall back to the backoff, not cancel the retry"
        assert len({c.request.headers["Idempotency-Key"] for c in route.calls}) == 1

    @pytest.mark.parametrize("status", [409, 429, 503])
    @respx.mock
    def test_retry_after_beyond_the_ceiling_is_reported_not_slept_through(self, sleeps, status):
        from dualentry_cli.client import APIError

        route = respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(status, headers={"Retry-After": "3600"}, json={}))

        with pytest.raises(APIError) as exc:
            self._client().post("/invoices/", json={})

        assert route.call_count == 1, "no point retrying on a schedule we refuse to wait for"
        assert sleeps == [], "the whole point: we never sleep 3600s"
        assert exc.value.status_code == status
        assert "3600" in exc.value.detail, "the user still needs to know how long the server asked for"

    @respx.mock
    def test_retry_after_at_the_ceiling_is_still_honoured(self, sleeps):
        from dualentry_cli.client import _MAX_RETRY_AFTER

        respx.post(f"{self.BASE}/invoices/").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": str(_MAX_RETRY_AFTER)}, json={}),
                httpx.Response(201, json={"internal_id": 6}),
            ]
        )

        self._client().post("/invoices/", json={})

        assert sleeps == [_MAX_RETRY_AFTER], "the ceiling itself is allowed"

    @respx.mock
    def test_conflict_without_a_key_keeps_the_server_message(self, sleeps):
        from dualentry_cli.client import APIError

        respx.get(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(409, json={"errors": {"__all__": ["period is closed"]}}))

        with pytest.raises(APIError) as exc:
            self._client().get("/invoices/")

        assert exc.value.detail == "period is closed"
        assert "256 KB" not in exc.value.detail
        assert sleeps == []

    @respx.mock
    def test_conflict_on_a_write_keeps_both_the_guidance_and_the_server_message(self):
        from dualentry_cli.client import APIError

        respx.post(f"{self.BASE}/invoices/").mock(return_value=httpx.Response(409, json={"errors": {"__all__": ["response cannot be replayed"]}}))

        with pytest.raises(APIError) as exc:
            self._client().post("/invoices/", json={})

        assert "256 KB" in exc.value.detail, "the write did carry a key, so the guidance applies"
        assert "response cannot be replayed" in exc.value.detail, "and the server's own words survive"

    def test_backoff_table_and_retry_count_cannot_drift(self):
        from dualentry_cli.client import _MAX_RETRIES, _RETRY_DELAYS

        assert len(_RETRY_DELAYS) == _MAX_RETRIES
