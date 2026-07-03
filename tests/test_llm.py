"""LLM layer: single litellm-backed seam, Ollama first-class, content redaction.

Specs: llm-providers. litellm itself is stubbed - no network, no real SDK calls.
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import shamal.llm
from shamal.config import resolve_settings
from shamal.llm import LLMClient, LLMResponse


def fake_litellm_response(
    content: str | None = "hello",
    tool_calls: list[dict[str, Any]] | None = None,
    prompt_tokens: int = 11,
    completion_tokens: int = 7,
) -> SimpleNamespace:
    """Mimic the shape of litellm's ModelResponse."""
    calls = None
    if tool_calls is not None:
        calls = [
            SimpleNamespace(
                id=c.get("id", f"call_{i}"),
                function=SimpleNamespace(name=c["name"], arguments=c["arguments"]),
            )
            for i, c in enumerate(tool_calls)
        ]
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture
def captured_kwargs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub the litellm seam, capturing the kwargs it was called with."""
    captured: dict[str, Any] = {}

    def stub(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return fake_litellm_response()

    monkeypatch.setattr(shamal.llm, "_call_litellm", stub)
    monkeypatch.setattr(shamal.llm, "_supports_tools", lambda model: True)
    return captured


def make_client(tmp_path: Path, **overrides: Any) -> LLMClient:
    settings = resolve_settings(cli_overrides=overrides, env={}, cwd=tmp_path)
    return LLMClient(settings)


MESSAGES = [{"role": "user", "content": "generate a load profile"}]


class TestComplete:
    def test_passes_model_and_messages(
        self, tmp_path: Path, captured_kwargs: dict[str, Any]
    ) -> None:
        client = make_client(tmp_path, model="claude-sonnet-5")
        response = client.complete(MESSAGES)
        assert captured_kwargs["model"] == "claude-sonnet-5"
        assert captured_kwargs["messages"] == MESSAGES
        assert isinstance(response, LLMResponse)
        assert response.content == "hello"

    def test_parses_tool_calls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def stub(**kwargs: Any) -> SimpleNamespace:
            return fake_litellm_response(
                content=None,
                tool_calls=[{"name": "get_summary_stats", "arguments": '{"metric": "latency"}'}],
            )

        monkeypatch.setattr(shamal.llm, "_call_litellm", stub)
        monkeypatch.setattr(shamal.llm, "_supports_tools", lambda model: True)
        client = make_client(tmp_path, model="claude-sonnet-5")
        response = client.complete(MESSAGES, tools=[{"type": "function"}])
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "get_summary_stats"
        assert response.tool_calls[0].arguments == {"metric": "latency"}

    def test_malformed_tool_arguments_become_empty_dict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def stub(**kwargs: Any) -> SimpleNamespace:
            return fake_litellm_response(
                content=None, tool_calls=[{"name": "t", "arguments": "not json"}]
            )

        monkeypatch.setattr(shamal.llm, "_call_litellm", stub)
        monkeypatch.setattr(shamal.llm, "_supports_tools", lambda model: True)
        client = make_client(tmp_path, model="claude-sonnet-5")
        response = client.complete(MESSAGES)
        assert response.tool_calls[0].arguments == {}


class TestRedaction:
    def test_debug_logs_usage_but_never_content(
        self,
        tmp_path: Path,
        captured_kwargs: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        client = make_client(tmp_path, model="claude-sonnet-5")
        secret = "SECRET-PROMPT-CONTENT-XYZZY"
        with caplog.at_level(logging.DEBUG, logger="shamal.llm"):
            client.complete([{"role": "user", "content": secret}])
        joined = " ".join(record.getMessage() for record in caplog.records)
        assert "prompt_tokens=11" in joined
        assert "completion_tokens=7" in joined
        assert "claude-sonnet-5" in joined
        assert secret not in joined
        assert "hello" not in joined  # completion content redacted too


class TestOllama:
    def test_base_url_honored_and_no_api_key_sent(
        self, tmp_path: Path, captured_kwargs: dict[str, Any]
    ) -> None:
        client = make_client(
            tmp_path, model="ollama/qwen3", ollama_base_url="http://airgap:11434"
        )
        client.complete(MESSAGES)
        assert captured_kwargs["model"] == "ollama/qwen3"
        assert captured_kwargs["api_base"] == "http://airgap:11434"
        assert "api_key" not in captured_kwargs

    def test_no_base_url_config_still_works(
        self, tmp_path: Path, captured_kwargs: dict[str, Any]
    ) -> None:
        client = make_client(tmp_path, model="ollama/qwen3")
        client.complete(MESSAGES)
        assert "api_base" not in captured_kwargs  # litellm default (localhost) applies


class TestCapabilityWarnings:
    def test_warns_when_tools_requested_but_unsupported(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(
            shamal.llm, "_call_litellm", lambda **kw: fake_litellm_response()
        )
        monkeypatch.setattr(shamal.llm, "_supports_tools", lambda model: False)
        client = make_client(tmp_path, model="ollama/tinymodel")
        with caplog.at_level(logging.WARNING, logger="shamal.llm"):
            client.complete(MESSAGES, tools=[{"type": "function"}])
        assert any("tool" in r.getMessage().lower() for r in caplog.records)
