"""k6 engine adapter (spec: test-execution).

LoadEngine is the seam future engines (Locust, Gatling) implement; v1 ships
k6 only. k6's exit code 99 has defined meaning - thresholds crossed - and is
mapped onto Shamal's exit-code contract by the CLI.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from shamal.config import ConfigError, Settings
from shamal.results import RunResult, downsample_stream

logger = logging.getLogger("shamal.engine")

MIN_K6_VERSION = (0, 50, 0)
K6_EXIT_THRESHOLDS_FAILED = 99

INSTALL_HINT = (
    "k6 binary not found. Install it from https://k6.io/docs/get-started/installation/ "
    "(macOS: brew install k6; Linux: see docs), or point SHAMAL_K6_PATH at the binary."
)


class EngineInfo(BaseModel):
    path: str
    version: str


class RunOutcome(BaseModel):
    kind: Literal["passed", "thresholds_failed", "error"]
    result: RunResult | None = None
    error: str | None = None


class LoadEngine(Protocol):
    def discover(self) -> EngineInfo: ...

    def run(
        self, scenario: Path, results_out: Path, echo: Callable[[str], None]
    ) -> RunOutcome: ...


class K6Engine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def discover(self) -> EngineInfo:
        path = self._settings.k6_path or shutil.which("k6")
        if not path or not Path(path).is_file():
            raise ConfigError(INSTALL_HINT)
        try:
            output = subprocess.run(
                [path, "version"], capture_output=True, text=True, timeout=30, check=False
            ).stdout
        except OSError as exc:
            raise ConfigError(f"Could not execute k6 at {path}: {exc}") from exc
        match = re.search(r"k6\s+v(\d+)\.(\d+)\.(\d+)", output)
        version = ".".join(match.groups()) if match else "unknown"
        if match and tuple(int(part) for part in match.groups()) < MIN_K6_VERSION:
            minimum = ".".join(str(part) for part in MIN_K6_VERSION)
            logger.warning(
                "k6 %s found; Shamal is tested against k6 >= %s. "
                "Proceeding, but consider upgrading.",
                version,
                minimum,
            )
        return EngineInfo(path=path, version=version)

    def run(
        self, scenario: Path, results_out: Path, echo: Callable[[str], None]
    ) -> RunOutcome:
        info = self.discover()
        with tempfile.TemporaryDirectory(prefix="shamal-k6-") as raw_dir:
            summary_path = Path(raw_dir) / "summary.json"
            stream_path = Path(raw_dir) / "stream.ndjson"
            command = [
                info.path,
                "run",
                f"--summary-export={summary_path}",
                "--out",
                f"json={stream_path}",
                str(scenario),
            ]
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            assert process.stdout is not None
            for line in process.stdout:
                echo(line.rstrip("\n"))
            process.stdout.close()
            stderr = process.stderr.read() if process.stderr else ""
            returncode = process.wait()

            summary_export = _load_json(summary_path)
            result = downsample_stream(
                stream_path if stream_path.is_file() else None, summary_export
            )
            result.meta.scenario = scenario.name
            result.meta.k6_version = info.version

            if returncode == 0:
                kind: Literal["passed", "thresholds_failed", "error"] = "passed"
                result.passed = True
                error = None
            elif returncode == K6_EXIT_THRESHOLDS_FAILED:
                kind = "thresholds_failed"
                result.passed = False
                error = None
            else:
                kind = "error"
                result.passed = False
                error = stderr.strip() or f"k6 exited with code {returncode}"
                result.meta.error = error

        results_out.parent.mkdir(parents=True, exist_ok=True)
        results_out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return RunOutcome(kind=kind, result=result, error=error)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        return None
