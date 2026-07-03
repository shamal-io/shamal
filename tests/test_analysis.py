"""Deterministic analysis tools over RunResult (spec: result-investigation).

The saturation detector is plain code, not LLM judgment: the agent cites its
output, it does not eyeball charts.
"""

from shamal.analysis import (
    detect_saturation_point,
    get_error_samples,
    get_summary_stats,
    get_timeseries_slice,
)
from shamal.results import (
    ErrorSample,
    RunMeta,
    RunResult,
    RunSummary,
    SeriesPoint,
    ThresholdResult,
)


def make_saturation_result() -> RunResult:
    """A classic knee: latency flat, then climbing while throughput plateaus."""
    series = []
    for i in range(30):
        vus = 5 + i * 5  # ramp 5 -> 150 VUs
        if i < 18:
            p95 = 120.0 + i  # healthy and flat
            rps = vus * 9.5  # throughput scales with load
        else:
            p95 = 200.0 + (i - 17) * 150  # knee: latency climbs fast
            rps = 90 * 9.5 + (i - 17) * 2  # throughput has plateaued
        series.append(
            SeriesPoint(
                t=float(i * 10),
                vus=vus,
                p50=p95 * 0.5,
                p95=p95,
                p99=p95 * 1.4,
                rps=rps,
                error_rate=0.0 if i < 25 else 0.05,
            )
        )
    return RunResult(
        meta=RunMeta(scenario="checkout.k6.js", duration_s=300.0),
        summary=RunSummary(http_reqs_count=250_000, latency_p95=850.0, vus_max=150),
        thresholds=[
            ThresholdResult(
                metric="http_req_duration", expression="p(95)<500", passed=False
            )
        ],
        series=series,
        errors=[
            ErrorSample(
                status="503", url="https://t.example/api/checkout", count=340, first_t=250.0
            )
        ],
        passed=False,
    )


def make_healthy_result() -> RunResult:
    series = [
        SeriesPoint(t=float(i * 10), vus=5 + i * 5, p95=120.0 + (i % 3), rps=(5 + i * 5) * 9.5)
        for i in range(30)
    ]
    return RunResult(series=series, passed=True)


class TestSummaryStats:
    def test_includes_summary_thresholds_and_meta(self) -> None:
        stats = get_summary_stats(make_saturation_result())
        assert stats["summary"]["latency_p95"] == 850.0
        assert stats["thresholds"][0]["expression"] == "p(95)<500"
        assert stats["meta"]["scenario"] == "checkout.k6.js"
        assert stats["series_available"] is True


class TestTimeseriesSlice:
    def test_window_bounds_respected(self) -> None:
        points = get_timeseries_slice(make_saturation_result(), start_s=100, end_s=150)
        assert points["points"]
        assert all(100 <= p["t"] <= 150 for p in points["points"])

    def test_no_series_reports_unavailable(self) -> None:
        result = RunResult()  # e.g. built from a foreign summary export
        response = get_timeseries_slice(result)
        assert response["points"] == []
        assert "unavailable" in response["note"].lower()

    def test_large_slice_downsampled_to_limit(self) -> None:
        result = make_saturation_result()
        response = get_timeseries_slice(result, max_points=10)
        assert len(response["points"]) <= 10


class TestErrorSamples:
    def test_clusters_returned(self) -> None:
        samples = get_error_samples(make_saturation_result())
        assert samples["errors"][0]["status"] == "503"
        assert samples["errors"][0]["count"] == 340


class TestSaturationDetection:
    def test_knee_found_in_saturating_run(self) -> None:
        finding = detect_saturation_point(make_saturation_result())
        assert finding["saturation_detected"] is True
        # knee is at index 18: t=180s, vus=95
        assert 150 <= finding["window_start_s"] <= 200
        assert 85 <= finding["approx_vus_at_knee"] <= 110
        assert finding["baseline_p95_ms"] < 150
        assert finding["p95_at_knee_ms"] > finding["baseline_p95_ms"] * 2

    def test_healthy_run_reports_no_knee(self) -> None:
        finding = detect_saturation_point(make_healthy_result())
        assert finding["saturation_detected"] is False

    def test_insufficient_data_is_explicit(self) -> None:
        finding = detect_saturation_point(RunResult())
        assert finding["saturation_detected"] is False
        assert "insufficient" in finding["note"].lower()
