"""k6 engine adapter: discovery, version check, structured result capture.

Specs: test-execution. Uses the fake-k6 fixture; no real k6 required.
"""

import json
import logging
from pathlib import Path

import pytest

from shamal.config import ConfigError, resolve_settings
from shamal.engine import K6Engine, RunOutcome
from tests.conftest import FakeK6Factory


def make_engine(tmp_path: Path, k6_path: Path | None) -> K6Engine:
    overrides = {"k6_path": str(k6_path)} if k6_path else {}
    settings = resolve_settings(cli_overrides=overrides, env={}, cwd=tmp_path)
    return K6Engine(settings)


class TestDiscovery:
    def test_missing_binary_raises_config_error_with_install_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", str(tmp_path))  # nothing on PATH
        engine = make_engine(tmp_path, None)
        with pytest.raises(ConfigError, match=r"k6\.io"):
            engine.discover()

    def test_explicit_path_honored(self, tmp_path: Path, fake_k6: FakeK6Factory) -> None:
        binary = fake_k6()
        engine = make_engine(tmp_path, binary)
        info = engine.discover()
        assert info.path == str(binary)
        assert info.version == "1.0.0"

    def test_old_version_warns_but_proceeds(
        self,
        tmp_path: Path,
        fake_k6: FakeK6Factory,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        binary = fake_k6(version="v0.42.0")
        engine = make_engine(tmp_path, binary)
        with caplog.at_level(logging.WARNING, logger="shamal.engine"):
            info = engine.discover()
        assert info.version == "0.42.0"
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "0.42.0" in joined and "0.50.0" in joined


class TestRun:
    def run_outcome(
        self,
        tmp_path: Path,
        fake_k6: FakeK6Factory,
        scenario_file: Path,
        exit_code: int = 0,
    ) -> tuple[RunOutcome, list[str]]:
        binary = fake_k6(exit_code=exit_code)
        engine = make_engine(tmp_path, binary)
        echoed: list[str] = []
        outcome = engine.run(scenario_file, tmp_path / "results.json", echo=echoed.append)
        return outcome, echoed

    def test_success_produces_result_file(
        self, tmp_path: Path, fake_k6: FakeK6Factory, scenario_file: Path
    ) -> None:
        outcome, _ = self.run_outcome(tmp_path, fake_k6, scenario_file)
        assert outcome.kind == "passed"
        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        assert data["summary"]["http_reqs_count"] == 5000
        assert data["thresholds"]  # parsed from summary export

    def test_threshold_failure_detected_via_exit_99(
        self, tmp_path: Path, fake_k6: FakeK6Factory, scenario_file: Path
    ) -> None:
        outcome, _ = self.run_outcome(tmp_path, fake_k6, scenario_file, exit_code=99)
        assert outcome.kind == "thresholds_failed"
        assert outcome.result is not None  # results still captured on failure

    def test_engine_crash_is_execution_error_and_recorded(
        self, tmp_path: Path, fake_k6: FakeK6Factory, scenario_file: Path
    ) -> None:
        binary = fake_k6(exit_code=107, stderr="connection refused")
        engine = make_engine(tmp_path, binary)
        outcome = engine.run(scenario_file, tmp_path / "results.json", echo=lambda _: None)
        assert outcome.kind == "error"
        assert "connection refused" in (outcome.error or "")
        data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
        assert "connection refused" in data["meta"]["error"]

    def test_k6_stdout_streams_through(
        self, tmp_path: Path, fake_k6: FakeK6Factory, scenario_file: Path
    ) -> None:
        _, echoed = self.run_outcome(tmp_path, fake_k6, scenario_file)
        assert any("FAKE-K6-RUNNING" in line for line in echoed)
