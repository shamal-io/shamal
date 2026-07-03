"""`shamal investigate` CLI flow: foreign results, annotative exit codes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import shamal.cli
from shamal.cli import app
from shamal.config import ConfigError
from shamal.exitcodes import ExitCode
from shamal.finding import Finding, Hypothesis
from shamal.results import RunResult, load_run_result
from tests.conftest import SUMMARY_EXPORT
from tests.test_analysis import make_saturation_result

runner = CliRunner()

STUB_FINDING = Finding(
    symptom="latency knee at ~95 VUs",
    hypotheses=[Hypothesis(cause="connection pool saturation", confidence="high")],
    next_steps=["raise pool size"],
    conclusive=True,
)


class TestLoadRunResult:
    def test_native_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        path.write_text(make_saturation_result().model_dump_json(), encoding="utf-8")
        result = load_run_result(path)
        assert result.series

    def test_foreign_k6_summary_export(self, tmp_path: Path) -> None:
        path = tmp_path / "summary.json"
        path.write_text(json.dumps(SUMMARY_EXPORT), encoding="utf-8")
        result = load_run_result(path)
        assert result.summary.http_reqs_count == 5000
        assert result.series == []  # summary exports carry no timeseries
        assert result.thresholds

    def test_unrecognized_json_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "junk.json"
        path.write_text('{"hello": "world"}', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_run_result(path)


class TestInvestigateCommand:
    @pytest.fixture
    def stubbed_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            shamal.cli, "investigate_run", lambda *a, **kw: STUB_FINDING
        )
        monkeypatch.setenv("SHAMAL_MODEL", "claude-sonnet-5")

    def test_investigating_passed_run_exits_zero(
        self, tmp_path: Path, stubbed_agent: None
    ) -> None:
        results = tmp_path / "results.json"
        passed = RunResult(passed=True, series=make_saturation_result().series)
        results.write_text(passed.model_dump_json(), encoding="utf-8")
        result = runner.invoke(app, ["investigate", "--results", str(results)])
        assert result.exit_code == ExitCode.OK, result.output  # type: ignore[attr-defined]
        assert "connection pool saturation" in result.output  # type: ignore[attr-defined]

    def test_finding_written_next_to_results(
        self, tmp_path: Path, stubbed_agent: None
    ) -> None:
        results = tmp_path / "results.json"
        results.write_text(make_saturation_result().model_dump_json(), encoding="utf-8")
        runner.invoke(app, ["investigate", "--results", str(results)])
        finding_path = tmp_path / "results-finding.json"
        assert finding_path.is_file()
        assert Finding.model_validate_json(finding_path.read_text(encoding="utf-8"))

    def test_foreign_summary_export_accepted(
        self, tmp_path: Path, stubbed_agent: None
    ) -> None:
        path = tmp_path / "summary.json"
        path.write_text(json.dumps(SUMMARY_EXPORT), encoding="utf-8")
        result = runner.invoke(app, ["investigate", "--results", str(path)])
        assert result.exit_code == ExitCode.OK  # type: ignore[attr-defined]

    def test_missing_results_file_is_config_error(
        self, tmp_path: Path, stubbed_agent: None
    ) -> None:
        result = runner.invoke(
            app, ["investigate", "--results", str(tmp_path / "ghost.json")]
        )
        assert result.exit_code == ExitCode.CONFIG_ERROR  # type: ignore[attr-defined]
