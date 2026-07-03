"""Bounded agentic investigation loop (spec: result-investigation)."""

import json
from typing import Any

from shamal.agent import investigate
from shamal.finding import Finding
from shamal.llm import LLMResponse, TokenUsage, ToolCall
from shamal.prometheus import PrometheusClient
from tests.test_analysis import make_saturation_result

FINDING_PAYLOAD: dict[str, Any] = {
    "symptom": "p95 latency breached 500ms during the sustained phase",
    "evidence": [
        {
            "description": "p95 rose from 130ms to 850ms between 170s and 180s",
            "metric": "http_req_duration",
            "window_start_s": 170.0,
            "window_end_s": 180.0,
        }
    ],
    "hypotheses": [
        {"cause": "DB connection pool exhausted", "confidence": "medium", "evidence": []},
        {"cause": "GC pressure on the app tier", "confidence": "low", "evidence": []},
    ],
    "next_steps": ["Check pool utilization at ~95 VUs"],
    "conclusive": True,
}


def tool_response(name: str, arguments: dict[str, Any], call_id: str = "c1") -> LLMResponse:
    return LLMResponse(
        content=None,
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        usage=TokenUsage(),
    )


def submit_response(payload: dict[str, Any] | None = None) -> LLMResponse:
    return tool_response("submit_finding", payload or FINDING_PAYLOAD, call_id="c-final")


class ScriptedClient:
    """LLM double that replays a fixed sequence of responses."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self._responses:
            return LLMResponse(content="I give up", usage=TokenUsage())
        return self._responses.pop(0)


def tool_names(call: dict[str, Any]) -> set[str]:
    return {t["function"]["name"] for t in call["tools"]}


class TestAgentLoop:
    def test_happy_path_returns_finding(self) -> None:
        client = ScriptedClient(
            [tool_response("get_summary_stats", {}), submit_response()]
        )
        finding = investigate(make_saturation_result(), client, max_steps=10)
        assert isinstance(finding, Finding)
        assert finding.symptom.startswith("p95 latency")
        assert finding.conclusive is True
        # the tool result was fed back to the model before it concluded
        fed_back = json.dumps(client.calls[1]["messages"][-1]["content"])
        assert "latency_p95" in fed_back

    def test_step_budget_exhaustion_is_graceful(self) -> None:
        client = ScriptedClient([tool_response("get_summary_stats", {})] * 50)
        finding = investigate(make_saturation_result(), client, max_steps=3)
        assert finding.conclusive is False
        assert any("step budget" in note.lower() for note in finding.notes)
        assert len(client.calls) == 3

    def test_competing_hypotheses_preserved_in_order(self) -> None:
        client = ScriptedClient([submit_response()])
        finding = investigate(make_saturation_result(), client, max_steps=5)
        assert [h.confidence for h in finding.hypotheses] == ["medium", "low"]
        assert finding.hypotheses[0].cause.startswith("DB connection pool")

    def test_unknown_tool_call_does_not_crash_loop(self) -> None:
        client = ScriptedClient(
            [tool_response("read_the_stars", {}), submit_response()]
        )
        finding = investigate(make_saturation_result(), client, max_steps=5)
        assert finding.conclusive is True
        fed_back = json.dumps(client.calls[1]["messages"][-1]["content"])
        assert "unknown tool" in fed_back.lower()

    def test_invalid_finding_payload_costs_a_step_not_the_run(self) -> None:
        client = ScriptedClient(
            [submit_response({"not_a_finding": True}), submit_response()]
        )
        finding = investigate(make_saturation_result(), client, max_steps=5)
        assert finding.conclusive is True


class TestPrometheusIntegration:
    def test_without_prometheus_tool_absent_and_noted(self) -> None:
        client = ScriptedClient([submit_response()])
        finding = investigate(make_saturation_result(), client, max_steps=5)
        assert "query_prometheus" not in tool_names(client.calls[0])
        assert any("prometheus" in note.lower() for note in finding.notes)

    def test_unreachable_prometheus_mid_loop_degrades_gracefully(self) -> None:
        prometheus = PrometheusClient("http://127.0.0.1:1", timeout_s=0.2)
        client = ScriptedClient(
            [
                tool_response("query_prometheus", {"promql": "up"}),
                submit_response(),
            ]
        )
        finding = investigate(
            make_saturation_result(), client, prometheus=prometheus, max_steps=5
        )
        assert "query_prometheus" in tool_names(client.calls[0])
        fed_back = json.dumps(client.calls[1]["messages"][-1]["content"])
        assert "unavailable" in fed_back.lower() or "failed" in fed_back.lower()
        assert any("prometheus" in note.lower() for note in finding.notes)


class TestSaturationScenario:
    def test_agent_can_cite_the_detected_knee(self) -> None:
        """Task 5.6: the scripted agent consults the knee detector and the
        deterministic tool hands it the correct window to cite."""
        client = ScriptedClient(
            [tool_response("detect_saturation_point", {}), submit_response()]
        )
        investigate(make_saturation_result(), client, max_steps=5)
        fed_back = client.calls[1]["messages"][-1]["content"]
        payload = json.loads(fed_back) if isinstance(fed_back, str) else fed_back
        text = json.dumps(payload)
        assert '"saturation_detected": true' in text
        assert "approx_vus_at_knee" in text
