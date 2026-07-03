"""`shamal run` exit-code semantics through the CLI (spec: test-execution, cli-core)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from shamal.cli import app
from shamal.exitcodes import ExitCode
from tests.conftest import FakeK6Factory

runner = CliRunner()


def invoke_run(
    scenario: Path, results: Path, k6: Path, monkeypatch: pytest.MonkeyPatch
) -> object:
    monkeypatch.setenv("SHAMAL_K6_PATH", str(k6))
    return runner.invoke(app, ["run", str(scenario), "--results", str(results)])


class TestRunCommand:
    def test_pass_exits_zero(
        self,
        tmp_path: Path,
        fake_k6: FakeK6Factory,
        scenario_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = invoke_run(scenario_file, tmp_path / "r.json", fake_k6(), monkeypatch)
        assert result.exit_code == ExitCode.OK, result.output  # type: ignore[attr-defined]
        assert (tmp_path / "r.json").exists()

    def test_threshold_failure_exits_one(
        self,
        tmp_path: Path,
        fake_k6: FakeK6Factory,
        scenario_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = invoke_run(
            scenario_file, tmp_path / "r.json", fake_k6(exit_code=99), monkeypatch
        )
        assert result.exit_code == ExitCode.THRESHOLDS_FAILED  # type: ignore[attr-defined]

    def test_target_unreachable_exits_two(
        self,
        tmp_path: Path,
        fake_k6: FakeK6Factory,
        scenario_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        binary = fake_k6(exit_code=107, stderr="connection refused")
        result = invoke_run(scenario_file, tmp_path / "r.json", binary, monkeypatch)
        assert result.exit_code == ExitCode.EXECUTION_ERROR  # type: ignore[attr-defined]

    def test_missing_k6_exits_three(
        self,
        tmp_path: Path,
        scenario_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PATH", str(tmp_path))
        result = runner.invoke(app, ["run", str(scenario_file)])
        assert result.exit_code == ExitCode.CONFIG_ERROR  # type: ignore[attr-defined]

    def test_k6_output_visible_to_user(
        self,
        tmp_path: Path,
        fake_k6: FakeK6Factory,
        scenario_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = invoke_run(scenario_file, tmp_path / "r.json", fake_k6(), monkeypatch)
        assert "FAKE-K6-RUNNING" in result.output  # type: ignore[attr-defined]
