"""
End-to-end: run the real CLI binary over a real socket against a stub v2 API.

Covers the whole stack the unit tests mock out - argv parsing, config/auth from
the environment, httpx, and response formatting - so `patch` is proven to
preserve omitted fields as the shipped command, not as an in-process call.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RECORD_PATH = "/public/v2/invoices/1001/"

POPULATED = {
    "internal_id": 42,
    "number": 1001,
    "customer_id": 7,
    "company_id": 3,
    "due_date": "2026-03-01",
    "currency_iso_4217_code": "USD",
    "exchange_rate": "1.00000000",
    "memo": "Original memo",
    "reference_number": "REF-9",
    "term_id": 5,
    "ar_account_id": 11,
    "sales_order_id": 88,
    "contracted": True,
    "record_status": "draft",
    "items": [{"id": 1, "item_id": 2, "quantity": "3.0", "rate": "50.00", "position": 1, "memo": "line"}],
}

# What PublicInvoiceSchemaUpdateIn (= CreateIn) fills in for fields a PUT omits.
PUT_DEFAULTS = {
    "customer_id": None,
    "company_id": None,
    "due_date": None,
    "memo": None,
    "term_id": None,
    "ar_account_id": None,
    "sales_order_id": None,
    "items": None,
    "reference_number": "",
    "contracted": False,
    "record_status": "posted",
}
SERVER_MANAGED = ("internal_id", "number")


class _Handler(BaseHTTPRequestHandler):
    record: dict = {}

    def log_message(self, *args):
        pass

    def _send(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self):
        if self.path != RECORD_PATH:
            self._send({"errors": {"detail": ["not found"]}}, 404)
            return
        self._send(type(self).record)

    def do_PATCH(self):
        if self.path != RECORD_PATH:
            self._send({"errors": {"detail": ["not found"]}}, 404)
            return
        type(self).record = {**type(self).record, **self._body()}
        self._send(type(self).record)

    def do_PUT(self):
        if self.path != RECORD_PATH:
            self._send({"errors": {"detail": ["not found"]}}, 404)
            return
        sent = self._body()
        replaced = {k: type(self).record[k] for k in SERVER_MANAGED}
        replaced.update({field: sent.get(field, default) for field, default in PUT_DEFAULTS.items()})
        replaced.update({k: v for k, v in sent.items() if k not in replaced})
        type(self).record = replaced
        self._send(type(self).record)


@pytest.fixture
def api():
    _Handler.record = json.loads(json.dumps(POPULATED))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def _cli(api_url, *args, stdin=""):
    binary = Path(sys.executable).with_name("dualentry")
    cmd = [str(binary), *args] if binary.exists() else [sys.executable, "-c", "from dualentry_cli.main import main_entrypoint; main_entrypoint()", *args]
    env = {
        **os.environ,
        "DUALENTRY_API_URL": api_url,
        "X_API_KEY": "test_key",
        "NO_COLOR": "1",
    }
    return subprocess.run(cmd, check=False, capture_output=True, text=True, input=stdin, env=env, timeout=60)  # noqa: S603


def _fetch(api_url):
    done = _cli(api_url, "invoices", "get", "1001", "-o", "json")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_patch_changes_two_fields_and_leaves_the_rest_alone(api, tmp_path):
    change = {"memo": "Patched memo", "reference_number": "REF-10"}
    payload_file = tmp_path / "change.json"
    payload_file.write_text(json.dumps(change))

    done = _cli(api, "invoices", "patch", "1001", "--file", str(payload_file), "-o", "json")
    assert done.returncode == 0, done.stderr

    after = _fetch(api)
    assert after["memo"] == "Patched memo"
    assert after["reference_number"] == "REF-10"
    for field, original in POPULATED.items():
        if field not in change:
            assert after[field] == original, f"{field} changed"


def test_update_clears_the_fields_the_file_omits(api, tmp_path):
    payload_file = tmp_path / "change.json"
    payload_file.write_text(json.dumps({"memo": "Replaced memo"}))

    done = _cli(api, "invoices", "update", "1001", "--file", str(payload_file), "--yes", "-o", "json")
    assert done.returncode == 0, done.stderr

    after = _fetch(api)
    assert after["memo"] == "Replaced memo"
    assert after["customer_id"] is None
    assert after["items"] is None
    assert after["reference_number"] == ""
    assert after["contracted"] is False
    # The bug this ticket is about, reproduced against a real request.
    assert after["record_status"] == "posted"


def test_update_warns_on_stderr_before_replacing(api, tmp_path):
    payload_file = tmp_path / "change.json"
    payload_file.write_text(json.dumps({"memo": "Replaced memo"}))

    done = _cli(api, "invoices", "update", "1001", "--file", str(payload_file))

    assert done.returncode == 0, done.stderr
    assert "replaces the whole invoice" in done.stderr
    assert "customer_id" in done.stderr
    assert "this will post the record" in done.stderr
    assert "Use 'patch' instead" in done.stderr


def test_patch_warns_about_nothing(api, tmp_path):
    payload_file = tmp_path / "change.json"
    payload_file.write_text(json.dumps({"memo": "Patched memo"}))

    done = _cli(api, "invoices", "patch", "1001", "--file", str(payload_file))

    assert done.returncode == 0, done.stderr
    assert "replaces the whole" not in done.stderr
