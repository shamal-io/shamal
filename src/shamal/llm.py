"""Provider-agnostic LLM access (spec: llm-providers).

All LLM traffic in Shamal flows through :class:`LLMClient`. No other module
may import a provider SDK. litellm is imported lazily because it is heavy
and must not slow down `--help`.

Logging policy: token usage and latency at DEBUG; prompt and completion
content are never logged at any level by this module.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel

from shamal.config import Settings

logger = logging.getLogger("shamal.llm")

Message = dict[str, Any]
ToolSchema = dict[str, Any]


def _call_litellm(**kwargs: Any) -> Any:
    """Seam around litellm.completion; tests monkeypatch this."""
    import litellm

    litellm.suppress_debug_info = True
    return litellm.completion(**kwargs)


def _supports_tools(model: str) -> bool:
    """Seam around litellm's capability lookup; tests monkeypatch this."""
    try:
        import litellm

        return bool(litellm.supports_function_calling(model=model))
    except Exception:  # unknown model ids should not crash the pipeline
        return True


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMResponse(BaseModel):
    content: str | None
    tool_calls: list[ToolCall] = []
    usage: TokenUsage = TokenUsage()


class LLMClient:
    """Thin, provider-agnostic completion client bound to resolved settings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.require_model()

    def complete(
        self, messages: list[Message], tools: list[ToolSchema] | None = None
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        if tools:
            if not _supports_tools(self._model):
                logger.warning(
                    "Model %s does not advertise tool-calling support; "
                    "investigation quality may degrade.",
                    self._model,
                )
            kwargs["tools"] = tools
        if self._model.startswith("ollama/") and self._settings.ollama_base_url:
            kwargs["api_base"] = self._settings.ollama_base_url

        started = time.monotonic()
        raw = _call_litellm(**kwargs)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        response = _parse_response(raw)
        logger.debug(
            "llm call model=%s latency_ms=%d prompt_tokens=%d completion_tokens=%d "
            "tool_calls=%d",
            self._model,
            elapsed_ms,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            len(response.tool_calls),
        )
        return response


def _parse_response(raw: Any) -> LLMResponse:
    message = raw.choices[0].message
    tool_calls: list[ToolCall] = []
    for call in message.tool_calls or []:
        try:
            arguments = json.loads(call.function.arguments)
            if not isinstance(arguments, dict):
                arguments = {}
        except (json.JSONDecodeError, TypeError):
            arguments = {}
        tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
    usage = getattr(raw, "usage", None)
    return LLMResponse(
        content=message.content,
        tool_calls=tool_calls,
        usage=TokenUsage(
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        ),
    )
