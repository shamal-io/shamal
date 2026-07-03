"""Read-only Prometheus HTTP API client (spec: result-investigation).

Strictly query_range over the test window; Shamal never writes to, or
administers, the target's monitoring stack.
"""

from __future__ import annotations

from typing import Any

import httpx


class PrometheusUnavailable(Exception):
    """Prometheus could not be queried; investigation continues without it."""


class PrometheusClient:
    def __init__(self, base_url: str, timeout_s: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def query_range(
        self, promql: str, start: float, end: float, step: float
    ) -> list[dict[str, Any]]:
        try:
            response = httpx.get(
                f"{self._base_url}/api/v1/query_range",
                params={"query": promql, "start": start, "end": end, "step": step},
                timeout=self._timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PrometheusUnavailable(f"Prometheus query failed: {exc}") from exc
        if payload.get("status") != "success":
            raise PrometheusUnavailable(
                f"Prometheus returned an error: {payload.get('error', 'unknown')}"
            )
        result = (payload.get("data") or {}).get("result")
        return result if isinstance(result, list) else []
