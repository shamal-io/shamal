"""The bounded investigation loop (spec: result-investigation).

A deliberately small, hand-rolled toolcalling loop: the model interrogates
the RunResult through deterministic tools and must conclude by calling
submit_finding. The loop never exceeds max_steps LLM calls, and it never
changes the run's pass/fail outcome - investigation is annotative only.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import ValidationError

from shamal.analysis import (
    detect_saturation_point,
    get_error_samples,
    get_summary_stats,
    get_timeseries_slice,
)
from shamal.finding import Finding
from shamal.llm import LLMResponse, Message, ToolSchema
from shamal.prometheus import PrometheusClient, PrometheusUnavailable
from shamal.results import RunResult

DEFAULT_MAX_STEPS = 15

SYSTEM_PROMPT = """You are a senior performance engineer investigating a load test run.

Work strictly from the tools' outputs - never invent numbers. Investigate
methodically: headline stats first, then narrow into suspicious windows,
error clusters, and the saturation detector. When system-side metrics are
available via query_prometheus, correlate them with the load timeline.

When done, call submit_finding with:
- symptom: what went wrong (or the headline observation if the run passed)
- evidence: specific metrics and time windows you actually observed
- hypotheses: ranked root causes with honest confidence (high/medium/low);
  if the evidence supports several explanations, list them all
- next_steps: concrete actions to confirm or fix
- conclusive: false if you could not reach a supported conclusion

Honesty about uncertainty beats a confident guess."""


class CompletionClient(Protocol):
    """Anything with an LLMClient-compatible complete()."""

    def complete(
        self, messages: list[Message], tools: list[ToolSchema] | None = None
    ) -> LLMResponse: ...


def investigate(
    result: RunResult,
    client: CompletionClient,
    *,
    prometheus: PrometheusClient | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> Finding:
    notes: list[str] = []
    if prometheus is None:
        notes.append(
            "System-side correlation unavailable: no Prometheus endpoint configured."
        )

    tools = _tool_schemas(include_prometheus=prometheus is not None)
    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Investigate this load test run. Headline stats:\n"
                + json.dumps(get_summary_stats(result), default=str)
            ),
        },
    ]

    for _ in range(max_steps):
        response = client.complete(messages, tools=tools)
        if not response.tool_calls:
            messages.append({"role": "assistant", "content": response.content or ""})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Use the provided tools to gather evidence, and finish by "
                        "calling submit_finding."
                    ),
                }
            )
            continue

        messages.append(_assistant_message(response))
        for call in response.tool_calls:
            if call.name == "submit_finding":
                try:
                    finding = Finding.model_validate(call.arguments)
                except ValidationError as exc:
                    messages.append(
                        _tool_message(call.id, {"error": f"Invalid finding: {exc}"})
                    )
                    continue
                finding.notes = [*finding.notes, *notes]
                return finding
            output = _dispatch(call.name, call.arguments, result, prometheus, notes)
            messages.append(_tool_message(call.id, output))

    return Finding(
        symptom="Investigation did not reach a conclusion.",
        conclusive=False,
        notes=[
            *notes,
            f"Investigation step budget ({max_steps} steps) exhausted before a "
            "conclusion; findings above are partial.",
        ],
    )


def _dispatch(
    name: str,
    arguments: dict[str, Any],
    result: RunResult,
    prometheus: PrometheusClient | None,
    notes: list[str],
) -> dict[str, Any]:
    try:
        if name == "get_summary_stats":
            return get_summary_stats(result)
        if name == "get_timeseries_slice":
            return get_timeseries_slice(
                result,
                start_s=_number(arguments.get("start_s")),
                end_s=_number(arguments.get("end_s")),
                max_points=int(arguments.get("max_points") or 60),
            )
        if name == "get_error_samples":
            return get_error_samples(result)
        if name == "detect_saturation_point":
            return detect_saturation_point(result)
        if name == "query_prometheus":
            return _query_prometheus(arguments, result, prometheus, notes)
    except Exception as exc:  # tool bugs must not kill the loop
        return {"error": f"Tool {name} failed: {exc}"}
    return {"error": f"Unknown tool: {name}"}


def _query_prometheus(
    arguments: dict[str, Any],
    result: RunResult,
    prometheus: PrometheusClient | None,
    notes: list[str],
) -> dict[str, Any]:
    if prometheus is None:
        return {"error": "Prometheus is not configured."}
    start = result.meta.started_at_epoch
    duration = result.meta.duration_s
    if start is None or duration is None:
        notes.append(
            "Prometheus correlation was attempted but this result lacks absolute "
            "timestamps; continued with load-side data only."
        )
        return {
            "error": (
                "Prometheus window unavailable: this result has no absolute "
                "timestamps to align with."
            )
        }
    promql = str(arguments.get("promql", ""))
    try:
        series = prometheus.query_range(
            promql, start=start, end=start + duration, step=max(1.0, duration / 60)
        )
    except PrometheusUnavailable as exc:
        notes.append(
            "Prometheus became unreachable during investigation; continued with "
            "load-side data only."
        )
        return {"error": f"Prometheus unavailable: {exc}"}
    return {"series": series[:20]}


def _assistant_message(response: LLMResponse) -> Message:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in response.tool_calls
        ],
    }


def _tool_message(call_id: str, output: dict[str, Any]) -> Message:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(output, default=str),
    }


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _tool_schemas(include_prometheus: bool) -> list[ToolSchema]:
    def tool(name: str, description: str, properties: dict[str, Any]) -> ToolSchema:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": properties},
            },
        }

    schemas = [
        tool("get_summary_stats", "Headline metrics, thresholds, and run metadata.", {}),
        tool(
            "get_timeseries_slice",
            "Downsampled series (vus, p50/p95/p99, rps, error_rate) for a window.",
            {
                "start_s": {"type": "number", "description": "Window start, seconds"},
                "end_s": {"type": "number", "description": "Window end, seconds"},
                "max_points": {"type": "integer", "description": "Max points returned"},
            },
        ),
        tool("get_error_samples", "Clustered error samples, largest first.", {}),
        tool(
            "detect_saturation_point",
            "Deterministic knee detection: latency degrading while throughput "
            "plateaus under growing load. Cite its window if detected.",
            {},
        ),
    ]
    if include_prometheus:
        schemas.append(
            tool(
                "query_prometheus",
                "Read-only PromQL query_range over the test window on the target's "
                "Prometheus.",
                {"promql": {"type": "string", "description": "PromQL expression"}},
            )
        )
    schemas.append(
        tool(
            "submit_finding",
            "Conclude the investigation with the structured finding.",
            Finding.model_json_schema().get("properties", {}),
        )
    )
    return schemas
