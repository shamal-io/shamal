"""RunResult: the compact, bounded record of a load test run.

k6's streaming JSON output can reach gigabytes on long runs; everything
downstream (investigation, reporting) works from this downsampled form
instead. Aggregation is per-second buckets, merged after the fact so the
final series never exceeds MAX_SERIES_POINTS regardless of test duration.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

RESULT_SIZE_BUDGET_BYTES = 512_000
MAX_SERIES_POINTS = 300
MAX_ERROR_CLUSTERS = 50
RESERVOIR_PER_BUCKET = 500

_TIME_RE = re.compile(r"^(?P<base>[^.]+)(?:\.(?P<frac>\d+))?(?P<tz>Z|[+-]\d{2}:?\d{2})$")


class SeriesPoint(BaseModel):
    t: float  # seconds since stream start (bucket midpoint)
    vus: int | None = None
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None
    rps: float | None = None
    error_rate: float | None = None


class ErrorSample(BaseModel):
    status: str | None = None
    url: str | None = None
    error: str | None = None
    count: int
    first_t: float


class ThresholdResult(BaseModel):
    metric: str
    expression: str
    passed: bool


class RunMeta(BaseModel):
    scenario: str | None = None
    k6_version: str | None = None
    duration_s: float | None = None
    error: str | None = None


class RunSummary(BaseModel):
    http_reqs_count: int | None = None
    http_reqs_rate: float | None = None
    latency_avg: float | None = None
    latency_min: float | None = None
    latency_max: float | None = None
    latency_p90: float | None = None
    latency_p95: float | None = None
    failed_rate: float | None = None
    vus_max: int | None = None


class RunResult(BaseModel):
    meta: RunMeta = RunMeta()
    summary: RunSummary = RunSummary()
    thresholds: list[ThresholdResult] = []
    series: list[SeriesPoint] = []
    errors: list[ErrorSample] = []
    passed: bool | None = None


class _Bucket:
    __slots__ = ("failed", "latencies", "requests", "vus")

    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.requests = 0
        self.failed = 0
        self.vus: int | None = None


def downsample_stream(
    stream: Path | None, summary_export: dict[str, Any] | None
) -> RunResult:
    buckets: dict[int, _Bucket] = {}
    clusters: dict[tuple[str | None, str | None, str | None], ErrorSample] = {}
    t0: float | None = None

    if stream is not None and stream.is_file():
        with stream.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                point = _parse_point(line)
                if point is None:
                    continue
                metric, timestamp, value, tags = point
                if t0 is None:
                    t0 = timestamp
                t = timestamp - t0
                bucket = buckets.setdefault(int(t), _Bucket())
                if metric == "http_req_duration":
                    bucket.requests += 1
                    if len(bucket.latencies) < RESERVOIR_PER_BUCKET:
                        bucket.latencies.append(value)
                elif metric == "vus":
                    bucket.vus = int(value)
                elif metric == "http_req_failed" and value >= 1:
                    bucket.failed += 1
                    key = (tags.get("status"), tags.get("error"), tags.get("url"))
                    cluster = clusters.get(key)
                    if cluster is None and len(clusters) < MAX_ERROR_CLUSTERS:
                        clusters[key] = ErrorSample(
                            status=key[0], error=key[1], url=key[2], count=1, first_t=t
                        )
                    elif cluster is not None:
                        cluster.count += 1

    series = _merge_buckets(buckets)
    duration = max(buckets) + 1.0 if buckets else None
    return RunResult(
        meta=RunMeta(duration_s=duration),
        summary=_parse_summary(summary_export),
        thresholds=_parse_thresholds(summary_export),
        series=series,
        errors=sorted(clusters.values(), key=lambda e: e.count, reverse=True),
    )


def _parse_point(
    line: str,
) -> tuple[str, float, float, dict[str, str]] | None:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict) or record.get("type") != "Point":
        return None
    metric = record.get("metric")
    data = record.get("data")
    if not isinstance(metric, str) or not isinstance(data, dict):
        return None
    timestamp = _parse_time(str(data.get("time", "")))
    value = data.get("value")
    if timestamp is None or not isinstance(value, int | float):
        return None
    tags = data.get("tags")
    return metric, timestamp, float(value), tags if isinstance(tags, dict) else {}


def _parse_time(raw: str) -> float | None:
    match = _TIME_RE.match(raw.strip())
    if not match:
        return None
    frac = (match.group("frac") or "")[:6].ljust(6, "0")
    tz = match.group("tz").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(f"{match.group('base')}.{frac}{tz}").timestamp()
    except ValueError:
        return None


def _merge_buckets(buckets: dict[int, _Bucket]) -> list[SeriesPoint]:
    if not buckets:
        return []
    keys = sorted(buckets)
    factor = max(1, math.ceil(len(keys) / MAX_SERIES_POINTS))
    series: list[SeriesPoint] = []
    for group_start in range(0, len(keys), factor):
        group_keys = keys[group_start : group_start + factor]
        latencies: list[float] = []
        requests = failed = 0
        vus: int | None = None
        for key in group_keys:
            bucket = buckets[key]
            latencies.extend(bucket.latencies)
            requests += bucket.requests
            failed += bucket.failed
            if bucket.vus is not None:
                vus = bucket.vus
        width = float(len(group_keys))
        latencies.sort()
        series.append(
            SeriesPoint(
                t=group_keys[0] + width / 2,
                vus=vus,
                p50=_percentile(latencies, 50),
                p95=_percentile(latencies, 95),
                p99=_percentile(latencies, 99),
                rps=round(requests / width, 2) if requests else None,
                error_rate=round(failed / requests, 4) if requests else None,
            )
        )
    return series


def _percentile(sorted_values: list[float], percent: float) -> float | None:
    if not sorted_values:
        return None
    rank = max(1, math.ceil(percent / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def _parse_thresholds(summary_export: dict[str, Any] | None) -> list[ThresholdResult]:
    results: list[ThresholdResult] = []
    metrics = (summary_export or {}).get("metrics") or {}
    for metric_name, metric in metrics.items():
        if not isinstance(metric, dict):
            continue
        for expression, failed in (metric.get("thresholds") or {}).items():
            # k6 summary export: the boolean marks whether the threshold FAILED.
            results.append(
                ThresholdResult(
                    metric=str(metric_name), expression=str(expression), passed=not failed
                )
            )
    return results


def _parse_summary(summary_export: dict[str, Any] | None) -> RunSummary:
    metrics = (summary_export or {}).get("metrics") or {}

    def metric(name: str, key: str) -> Any:
        value = metrics.get(name)
        return value.get(key) if isinstance(value, dict) else None

    vus_max = metric("vus_max", "max") or metric("vus_max", "value")
    return RunSummary(
        http_reqs_count=metric("http_reqs", "count"),
        http_reqs_rate=metric("http_reqs", "rate"),
        latency_avg=metric("http_req_duration", "avg"),
        latency_min=metric("http_req_duration", "min"),
        latency_max=metric("http_req_duration", "max"),
        latency_p90=metric("http_req_duration", "p(90)"),
        latency_p95=metric("http_req_duration", "p(95)"),
        failed_rate=metric("http_req_failed", "value"),
        vus_max=int(vus_max) if vus_max is not None else None,
    )
