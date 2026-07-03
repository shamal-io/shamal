"""Deterministic analysis tools the investigation agent calls.

The agent does not eyeball charts: numeric judgments (like saturation-knee
detection) happen here in reviewable code, and the agent reasons over the
outputs. Tunables for the knee heuristic are module constants - they encode
performance-engineering judgment, not universal truth, and are meant to be
challenged.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from shamal.results import RunResult

# --- Saturation-knee heuristic tunables ------------------------------------
# Baseline = median p95 over the first BASELINE_FRACTION of points.
BASELINE_FRACTION = 0.2
# A knee requires p95 to exceed baseline by this factor...
LATENCY_DEGRADATION_FACTOR = 2.0
# ...while throughput growth over the trailing window stays under this rate
# although load (VUs) keeps growing by at least VUS_GROWTH_MIN.
RPS_PLATEAU_GROWTH_MAX = 0.10
VUS_GROWTH_MIN = 0.15
# Points compared against a trailing neighbor this many positions back.
TREND_LOOKBACK = 3
MIN_POINTS_FOR_DETECTION = 8


def get_summary_stats(result: RunResult) -> dict[str, Any]:
    """Headline numbers: summary metrics, threshold outcomes, run metadata."""
    return {
        "summary": result.summary.model_dump(),
        "thresholds": [t.model_dump() for t in result.thresholds],
        "meta": result.meta.model_dump(),
        "passed": result.passed,
        "series_available": bool(result.series),
        "error_cluster_count": len(result.errors),
    }


def get_timeseries_slice(
    result: RunResult,
    start_s: float | None = None,
    end_s: float | None = None,
    max_points: int = 60,
) -> dict[str, Any]:
    """A bounded window of the downsampled series."""
    if not result.series:
        return {
            "points": [],
            "note": (
                "Timeseries unavailable: this result carries only summary metrics "
                "(e.g. a k6 summary export produced outside shamal run)."
            ),
        }
    points = [
        p
        for p in result.series
        if (start_s is None or p.t >= start_s) and (end_s is None or p.t <= end_s)
    ]
    stride = max(1, len(points) // max_points + (1 if len(points) % max_points else 0))
    return {"points": [p.model_dump() for p in points[::stride]], "note": ""}


def get_error_samples(result: RunResult) -> dict[str, Any]:
    """Clustered error samples, largest clusters first."""
    if not result.errors:
        return {"errors": [], "note": "No error samples were recorded during the run."}
    return {"errors": [e.model_dump() for e in result.errors], "note": ""}


def detect_saturation_point(result: RunResult) -> dict[str, Any]:
    """Find the earliest knee: latency degrading while throughput plateaus under
    growing load. Returns the evidence window, never a verdict about the cause."""
    points = [p for p in result.series if p.p95 is not None]
    if len(points) < MIN_POINTS_FOR_DETECTION:
        return {
            "saturation_detected": False,
            "note": (
                f"Insufficient series data for knee detection "
                f"(need >= {MIN_POINTS_FOR_DETECTION} points with p95 latency)."
            ),
        }

    baseline_count = max(3, int(len(points) * BASELINE_FRACTION))
    baseline_p95 = median(p.p95 for p in points[:baseline_count] if p.p95 is not None)
    if baseline_p95 <= 0:
        return {"saturation_detected": False, "note": "Baseline p95 is zero; cannot compare."}

    for index in range(baseline_count, len(points)):
        point = points[index]
        prior = points[max(0, index - TREND_LOOKBACK)]
        if point.p95 is None or point.p95 < baseline_p95 * LATENCY_DEGRADATION_FACTOR:
            continue
        vus_growing = (
            point.vus is not None
            and prior.vus not in (None, 0)
            and (point.vus - prior.vus) / prior.vus >= VUS_GROWTH_MIN  # type: ignore[operator]
        )
        rps_plateaued = (
            point.rps is not None
            and prior.rps not in (None, 0)
            and (point.rps - prior.rps) / prior.rps <= RPS_PLATEAU_GROWTH_MAX  # type: ignore[operator]
        )
        if vus_growing and rps_plateaued:
            return {
                "saturation_detected": True,
                "window_start_s": prior.t,
                "window_end_s": point.t,
                "approx_vus_at_knee": point.vus,
                "baseline_p95_ms": round(baseline_p95, 1),
                "p95_at_knee_ms": round(point.p95, 1),
                "rps_at_knee": point.rps,
                "note": (
                    "Latency degraded beyond "
                    f"{LATENCY_DEGRADATION_FACTOR}x baseline while throughput "
                    "plateaued under growing load - classic saturation signature."
                ),
            }
    return {
        "saturation_detected": False,
        "note": "No saturation signature found: latency stayed proportional to load.",
    }
