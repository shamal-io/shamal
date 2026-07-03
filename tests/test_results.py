"""NDJSON downsampler: bounded output, faithful extraction (spec: test-execution)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from shamal.results import RESULT_SIZE_BUDGET_BYTES, RunResult, downsample_stream
from tests.conftest import SUMMARY_EXPORT, ndjson_lines


def write_stream(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "out.ndjson"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


class TestExtraction:
    def test_series_vus_and_latency(self, tmp_path: Path) -> None:
        stream = write_stream(tmp_path, ndjson_lines())
        result = downsample_stream(stream, summary_export=SUMMARY_EXPORT)
        assert result.series, "expected non-empty series"
        first, last = result.series[0], result.series[-1]
        assert first.vus == 5
        assert last.vus == 50
        assert last.p95 is not None and last.p95 > first.p95  # latency grew with load

    def test_error_samples_clustered(self, tmp_path: Path) -> None:
        stream = write_stream(tmp_path, ndjson_lines())
        result = downsample_stream(stream, summary_export=SUMMARY_EXPORT)
        assert len(result.errors) == 1  # two identical 503s cluster into one sample
        cluster = result.errors[0]
        assert cluster.status == "503"
        assert cluster.count == 2
        assert "checkout" in (cluster.url or "")

    def test_thresholds_parsed_from_summary(self, tmp_path: Path) -> None:
        stream = write_stream(tmp_path, ndjson_lines())
        result = downsample_stream(stream, summary_export=SUMMARY_EXPORT)
        expressions = {t.expression for t in result.thresholds}
        assert expressions == {"p(95)<500", "rate<0.01"}
        assert all(t.passed for t in result.thresholds)

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        lines = [*ndjson_lines(), "not json at all", '{"type": "Metric"}']
        stream = write_stream(tmp_path, lines)
        result = downsample_stream(stream, summary_export=SUMMARY_EXPORT)
        assert result.series  # still parsed the good lines


class TestBoundedness:
    def test_large_stream_stays_within_budget(self, tmp_path: Path) -> None:
        """A multi-hour, high-volume stream must not blow up the result size."""
        start = datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC)
        lines = []
        for i in range(200_000):
            moment = (start + timedelta(milliseconds=i * 50)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            lines.append(
                json.dumps(
                    {
                        "type": "Point",
                        "metric": "http_req_duration",
                        "data": {
                            "time": moment,
                            "value": 100 + (i % 400),
                            "tags": {"status": "200", "url": "https://t.example/api"},
                        },
                    }
                )
            )
        stream = write_stream(tmp_path, lines)
        result = downsample_stream(stream, summary_export=SUMMARY_EXPORT)
        serialized = result.model_dump_json()
        assert len(serialized.encode()) < RESULT_SIZE_BUDGET_BYTES
        assert len(result.series) <= 300

    def test_roundtrip_serialization(self, tmp_path: Path) -> None:
        stream = write_stream(tmp_path, ndjson_lines())
        result = downsample_stream(stream, summary_export=SUMMARY_EXPORT)
        restored = RunResult.model_validate_json(result.model_dump_json())
        assert restored == result
