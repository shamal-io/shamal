"""Shared fixtures: a fake k6 binary for engine tests."""

import json
import os
import stat
from pathlib import Path
from typing import Protocol

import pytest

SUMMARY_EXPORT = {
    "metrics": {
        "http_req_duration": {
            "avg": 182.5,
            "min": 12.1,
            "max": 2411.0,
            "p(90)": 310.0,
            "p(95)": 420.0,
            "thresholds": {"p(95)<500": False},
        },
        "http_req_failed": {"value": 0.004, "thresholds": {"rate<0.01": False}},
        "http_reqs": {"count": 5000, "rate": 83.3},
        "vus_max": {"value": 50, "max": 50},
    }
}


def ndjson_lines() -> list[str]:
    """A small deterministic k6 JSON output stream."""
    lines = []
    for second in range(10):
        timestamp = f"2026-07-01T10:00:{second:02d}.000000Z"
        lines.append(
            json.dumps(
                {
                    "type": "Point",
                    "metric": "vus",
                    "data": {"time": timestamp, "value": (second + 1) * 5},
                }
            )
        )
        for value in (100 + second * 20, 150 + second * 20, 900 + second * 100):
            lines.append(
                json.dumps(
                    {
                        "type": "Point",
                        "metric": "http_req_duration",
                        "data": {
                            "time": timestamp,
                            "value": value,
                            "tags": {"status": "200", "url": "https://t.example/api"},
                        },
                    }
                )
            )
        if second >= 8:  # errors appear late in the ramp
            lines.append(
                json.dumps(
                    {
                        "type": "Point",
                        "metric": "http_req_failed",
                        "data": {
                            "time": timestamp,
                            "value": 1,
                            "tags": {
                                "status": "503",
                                "url": "https://t.example/api/checkout",
                                "error": "unexpected status",
                            },
                        },
                    }
                )
            )
    return lines


class FakeK6Factory(Protocol):
    def __call__(
        self,
        exit_code: int = 0,
        version: str = "v1.0.0",
        banner: str = "FAKE-K6-RUNNING",
        stderr: str = "",
    ) -> Path: ...


@pytest.fixture
def fake_k6(tmp_path: Path) -> FakeK6Factory:
    """Create an executable that impersonates the k6 CLI."""

    def factory(
        exit_code: int = 0,
        version: str = "v1.0.0",
        banner: str = "FAKE-K6-RUNNING",
        stderr: str = "",
    ) -> Path:
        summary = json.dumps(SUMMARY_EXPORT)
        stream = "\n".join(ndjson_lines())
        script = tmp_path / "k6"
        script.write_text(
            f"""#!/bin/sh
if [ "$1" = "version" ]; then
  echo "k6 {version} (go1.24, linux/amd64)"
  exit 0
fi
# parse --summary-export=<path> and --out json=<path> from args
for arg in "$@"; do
  case "$arg" in
    --summary-export=*) summary_path="${{arg#--summary-export=}}" ;;
    json=*) out_path="${{arg#json=}}" ;;
  esac
done
echo "{banner}"
[ -n "$stderr_msg" ] || true
{f'echo "{stderr}" >&2' if stderr else ""}
[ -n "$summary_path" ] && cat > "$summary_path" <<'SUMMARY_EOF'
{summary}
SUMMARY_EOF
[ -n "$out_path" ] && cat > "$out_path" <<'NDJSON_EOF'
{stream}
NDJSON_EOF
exit {exit_code}
""",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return script

    return factory


@pytest.fixture
def scenario_file(tmp_path: Path) -> Path:
    path = tmp_path / "scenario.js"
    path.write_text("export default function () {}\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clean_shamal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's real SHAMAL_* environment out of tests."""
    for key in list(os.environ):
        if key.startswith("SHAMAL_"):
            monkeypatch.delenv(key, raising=False)
