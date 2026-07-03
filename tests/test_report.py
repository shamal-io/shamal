"""Report rendering: markdown for PRs, self-contained HTML, stable JSON (spec: reporting)."""

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from shamal.cli import app
from shamal.exitcodes import ExitCode
from shamal.finding import Evidence, Finding, Hypothesis
from shamal.report import render_html, render_markdown, report_data
from shamal.results import ThresholdResult
from tests.test_analysis import make_saturation_result

runner = CliRunner()

FINDING = Finding(
    symptom="p95 latency breached 500ms during the sustained phase",
    evidence=[
        Evidence(
            description="p95 rose from 130ms to 850ms",
            metric="http_req_duration",
            window_start_s=170.0,
            window_end_s=180.0,
        )
    ],
    hypotheses=[
        Hypothesis(cause="DB connection pool exhausted at ~95 VUs", confidence="high"),
        Hypothesis(cause="App-tier GC pressure", confidence="low"),
    ],
    next_steps=["Inspect pool utilization dashboards at the 170-180s window"],
    conclusive=True,
    notes=["System-side correlation unavailable: no Prometheus endpoint configured."],
)


class TestMarkdown:
    def test_verdict_is_the_first_line(self) -> None:
        md = render_markdown(make_saturation_result(), FINDING)
        assert "FAILED" in md.splitlines()[0]

    def test_failed_thresholds_come_before_metrics(self) -> None:
        result = make_saturation_result()
        result.thresholds.append(
            ThresholdResult(metric="http_req_failed", expression="rate<0.01", passed=True)
        )
        md = render_markdown(result, FINDING)
        assert md.index("p(95)<500") < md.index("Key metrics")

    def test_top_hypothesis_present(self) -> None:
        md = render_markdown(make_saturation_result(), FINDING)
        assert "DB connection pool exhausted" in md
        assert "high" in md

    def test_html_reference_included_when_given(self) -> None:
        md = render_markdown(
            make_saturation_result(), FINDING, html_path="reports/full.html"
        )
        assert "reports/full.html" in md

    def test_pr_comment_size_budget(self) -> None:
        bloated = FINDING.model_copy(
            update={
                "next_steps": [f"step {i}: " + "x" * 200 for i in range(50)],
                "notes": ["n" * 500] * 20,
            }
        )
        md = render_markdown(make_saturation_result(), bloated)
        assert len(md.encode()) <= 4000

    def test_passed_run_without_finding(self) -> None:
        result = make_saturation_result()
        result.passed = True
        md = render_markdown(result, None)
        assert "PASSED" in md.splitlines()[0]


class TestHtml:
    def test_self_contained_no_external_references(self) -> None:
        html = render_html(make_saturation_result(), FINDING)
        assert not re.search(r'(src|href)\s*=\s*["\']https?://', html)
        assert "<style>" in html

    def test_series_chart_rendered_inline_as_svg(self) -> None:
        html = render_html(make_saturation_result(), FINDING)
        assert "<svg" in html and "polyline" in html

    def test_finding_and_thresholds_rendered(self) -> None:
        html = render_html(make_saturation_result(), FINDING)
        assert "DB connection pool exhausted" in html
        assert "p(95)&lt;500" in html or "p(95)<500" in html

    def test_renders_without_finding_or_series(self) -> None:
        from shamal.results import RunResult

        html = render_html(RunResult(), None)
        assert "<style>" in html  # still a complete document


class TestReportData:
    def test_stable_schema(self) -> None:
        data = report_data(make_saturation_result(), FINDING)
        assert data["schema_version"] == 1
        assert data["verdict"] == "failed"
        assert data["finding"]["symptom"].startswith("p95")
        assert data["summary"]["latency_p95"] == 850.0


class TestReportCommand:
    def write_inputs(self, tmp_path: Path, with_finding: bool = True) -> Path:
        results = tmp_path / "results.json"
        results.write_text(make_saturation_result().model_dump_json(), encoding="utf-8")
        if with_finding:
            (tmp_path / "results-finding.json").write_text(
                FINDING.model_dump_json(), encoding="utf-8"
            )
        return results

    def test_writes_markdown_and_html(self, tmp_path: Path) -> None:
        results = self.write_inputs(tmp_path)
        result = runner.invoke(app, ["report", "--results", str(results)])
        assert result.exit_code == ExitCode.OK, result.output  # type: ignore[attr-defined]
        assert (tmp_path / "results-report.md").is_file()
        assert (tmp_path / "results-report.html").is_file()

    def test_sibling_finding_autodiscovered(self, tmp_path: Path) -> None:
        results = self.write_inputs(tmp_path)
        runner.invoke(app, ["report", "--results", str(results)])
        md = (tmp_path / "results-report.md").read_text(encoding="utf-8")
        assert "DB connection pool exhausted" in md

    def test_json_mode_stdout_is_pure(self, tmp_path: Path) -> None:
        results = self.write_inputs(tmp_path)
        result = runner.invoke(app, ["report", "--results", str(results), "--json"])
        data = json.loads(result.output)  # type: ignore[attr-defined]
        assert data["schema_version"] == 1
        assert not (tmp_path / "results-report.md").exists()  # json mode writes nothing

    def test_missing_results_is_config_error(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["report", "--results", str(tmp_path / "ghost.json")]
        )
        assert result.exit_code == ExitCode.CONFIG_ERROR  # type: ignore[attr-defined]
