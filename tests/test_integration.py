"""Opt-in integration smoke: real k6 against a local HTTP server.

Run with: uv run pytest -m integration
"""

import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from shamal.config import resolve_settings
from shamal.engine import K6Engine

pytestmark = pytest.mark.integration

k6_available = shutil.which("k6") is not None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # http.server API requires this exact name
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # keep test output clean
        pass


@pytest.fixture
def local_server() -> object:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.mark.skipif(not k6_available, reason="k6 binary not installed")
def test_real_k6_run_end_to_end(tmp_path: Path, local_server: str) -> None:
    scenario = tmp_path / "smoke.js"
    scenario.write_text(
        f"""
import http from 'k6/http';
import {{ check }} from 'k6';

export const options = {{
  vus: 2,
  duration: '2s',
  thresholds: {{ http_req_failed: ['rate<0.5'] }},
}};

export default function () {{
  const res = http.get('{local_server}/api/ping');
  check(res, {{ 'status 200': (r) => r.status === 200 }});
}}
""",
        encoding="utf-8",
    )
    settings = resolve_settings(cli_overrides={}, env={}, cwd=tmp_path)
    engine = K6Engine(settings)
    lines: list[str] = []
    outcome = engine.run(scenario, tmp_path / "results.json", echo=lines.append)

    assert outcome.kind == "passed", outcome.error
    assert outcome.result is not None
    assert outcome.result.summary.http_reqs_count
    assert outcome.result.series, "downsampled series should not be empty"
    assert any(t.passed for t in outcome.result.thresholds)
    assert (tmp_path / "results.json").is_file()
