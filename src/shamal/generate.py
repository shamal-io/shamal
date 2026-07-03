"""LLM-backed scenario generation: source model in, validated ScenarioSpec out.

The LLM returns JSON matching ScenarioSpec, never code. Validation failures
get one bounded retry with the error fed back; after that we fail loudly
rather than emit a scenario nobody asked for.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from shamal.har import HarJourney
from shamal.ingest import K6Source
from shamal.llm import LLMClient, Message
from shamal.openapi import OpenAPIModel
from shamal.scenario import DEFAULT_THRESHOLDS, ScenarioSpec

MAX_ATTEMPTS = 2


class GenerationError(Exception):
    """Scenario generation failed; maps to exit code 2 at the CLI boundary."""


SYSTEM_PROMPT = f"""You are a senior performance engineer designing a k6 load test.

Given a description of an API, respond with ONLY a JSON object (no prose, no
code fences) with this exact shape:

{{
  "name": "<kebab-case scenario name>",
  "base_url": "<scheme://host>",
  "journeys": [
    {{
      "name": "<realistic user journey name>",
      "weight": <int, relative frequency>,
      "think_time_s": <float seconds between steps>,
      "steps": [
        {{
          "method": "GET|POST|PUT|PATCH|DELETE",
          "path": "</path?query=values>",
          "headers": {{}},
          "body": {{}} or null,
          "expect_status": <int>
        }}
      ]
    }}
  ],
  "stages": [
    {{"duration": "30s", "target": <smoke VUs>}},
    {{"duration": "<ramp duration>", "target": <peak VUs>}},
    {{"duration": "<sustain duration>", "target": <peak VUs>}},
    {{"duration": "30s", "target": 0}}
  ],
  "thresholds": {json.dumps(DEFAULT_THRESHOLDS)}
}}

Rules:
- Design journeys a real user would take, not one request per endpoint.
- Fill required parameters with realistic example values.
- Include smoke, ramp-up, sustained, and ramp-down stages.
- Adjust thresholds to the API's likely SLOs; keep both default metrics.
"""


def generate_scenario(
    source: OpenAPIModel | HarJourney | K6Source, client: LLMClient
) -> ScenarioSpec:
    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": describe_source(source)},
    ]
    last_error = "empty response"
    for _ in range(MAX_ATTEMPTS):
        response = client.complete(messages)
        text = response.content or ""
        try:
            return ScenarioSpec.model_validate(_extract_json(text))
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = str(exc)
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That response was not valid. Error:\n"
                        f"{last_error}\n"
                        "Respond again with ONLY the corrected JSON object."
                    ),
                }
            )
    raise GenerationError(
        f"The model did not produce a valid scenario after {MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )


def describe_source(source: OpenAPIModel | HarJourney | K6Source) -> str:
    if isinstance(source, OpenAPIModel):
        lines = [f"OpenAPI service: {source.title}", f"Base URL: {source.base_url}", "Endpoints:"]
        for endpoint in source.endpoints:
            required = ", ".join(
                f"{p.name} ({p.location})" for p in endpoint.required_params
            )
            details = [
                part
                for part in (
                    endpoint.summary,
                    f"required params: {required}" if required else None,
                    "has request body" if endpoint.has_request_body else None,
                    f"auth: {endpoint.auth}" if endpoint.auth else None,
                )
                if part
            ]
            suffix = f"  [{'; '.join(details)}]" if details else ""
            lines.append(f"- {endpoint.method} {endpoint.path}{suffix}")
        return "\n".join(lines)
    if isinstance(source, HarJourney):
        lines = [
            "Recorded browser session (HAR). Reproduce this user journey:",
            f"Base URL: {source.base_url}",
        ]
        for step in source.steps:
            body = f" body={step.body}" if step.body else ""
            lines.append(f"- {step.method} {step.url}{body}")
        return "\n".join(lines)
    return (
        "Existing k6 script (improve its realism, keep its intent; "
        f"source: {source.path}):\n\n{source.content}"
    )


def _extract_json(text: str) -> object:
    """Tolerate code fences and surrounding prose around the JSON object."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        cleaned = cleaned.removeprefix("json").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    return json.loads(cleaned[start : end + 1])
