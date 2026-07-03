# Design: add-shamal-mvp

## Context

Greenfield repository. Shamal v1 is a solo-maintained OSS CLI whose credibility depends on two things: the generated scenarios being honest, readable k6 code, and the investigation step producing analysis a performance engineer would respect. Everything else (packaging, config, reports) is standard plumbing and should stay boring.

Constraints: solo + AI-agent development capacity, TDD throughout, air-gap-friendly operation is a product principle (a user with Ollama and a k6 binary must get the full experience offline), and no telemetry of any kind.

## Goals / Non-Goals

**Goals:**
- One coherent pipeline: `plan` (ingest + generate) -> `run` -> `investigate` -> `report`, each usable independently
- Generated artifacts are plain k6 JavaScript that runs without Shamal installed
- Investigation works on any k6 JSON results, including tests Shamal did not generate (standalone adoption wedge)
- Provider-agnostic LLM layer with local-model support
- CI-first ergonomics: deterministic exit codes, quiet mode, machine-readable output

**Non-Goals:**
- Browser-level load, distributed workers, web UI, trend storage, auto-remediation, SaaS, telemetry (per proposal)
- Perfect scenario realism in v1: the human reviews and edits generated scenarios; Shamal optimizes for a strong first draft, not autonomy

## Decisions

1. **Python 3.12+ over Go/TypeScript.** The LLM/agent ecosystem is Python-native and solo velocity matters most; load generation stays in k6 (Go) so Python is never in the hot path. Alternative considered: Go for single-binary distribution - rejected because iteration speed on the agent loop dominates v1 risk.
2. **k6 as the only engine, behind a `LoadEngine` protocol.** One engine done well; the adapter interface (`discover()`, `run(scenario, opts) -> RawResults`, `parse(RawResults) -> RunResult`) keeps Locust/Gatling additions honest later. k6 chosen for JSON summary output, thresholds, and market mindshare.
3. **Hand-rolled agent loop, no agent framework.** The investigation agent is a bounded toolcalling loop (max N steps) over a small tool set: `get_summary_stats`, `get_timeseries_slice`, `get_error_samples`, `query_prometheus` (optional). Frameworks (LangChain/CrewAI) add dependency weight and churn for no benefit at this size. HolmesGPT validates the pattern.
4. **litellm for provider abstraction.** Claude default (`SHAMAL_MODEL=claude-sonnet-5` or current), OpenAI/Gemini/Ollama via config. Alternative: native Anthropic SDK only - rejected; Ollama support is load-bearing for the air-gap story.
5. **Scenario generation emits constrained k6 JS from a template skeleton**, not freeform code: the LLM fills journeys, data, ramp stages, and thresholds into a fixed scaffold (imports, options block, default function structure are template-controlled). This bounds hallucination and guarantees the output parses. Generated files carry a header comment declaring provenance and that they are editable.
6. **Results flow through k6's `--summary-export` JSON plus the streaming JSON output (`--out json=`) downsampled by Shamal** into a compact `RunResult` model (phases, percentile series, error clusters). Raw NDJSON can be huge; downsampling at ingest keeps investigation context LLM-sized.
7. **Prometheus correlation is optional and read-only** via the HTTP API with a user-supplied URL and PromQL allowlist patterns; absent config, investigation runs on k6 data alone.
8. **Packaging: uv + hatchling, `pyproject.toml`; CLI via Typer; reports via Jinja2** with inline CSS/JS for a self-contained HTML file. Ruff + mypy strict on `src/`.
9. **Exit-code contract:** 0 = thresholds passed, 1 = thresholds failed, 2 = execution error, 3 = configuration error. `investigate` never changes pass/fail; it annotates.

## Risks / Trade-offs

- [LLM generates subtly wrong load profiles] -> constrained template + `shamal plan --review` prints a human-readable scenario summary; docs position output as a reviewed draft
- [k6 NDJSON output too large for analysis] -> streaming downsampler with fixed memory budget; summary-export always works as fallback
- [Grafana ships an official AI layer for k6] -> engine-neutral adapter + investigation-of-any-results wedge; community license
- [litellm dependency churn] -> isolate behind `shamal.llm` module; only `complete(messages, tools)` crosses the boundary
- [Solo-maintainer bus factor perception] -> OpenSpec artifacts, tests, and CONTRIBUTING.md public from first commit

## Open Questions

- Prometheus correlation may slip to a fast-follow change if the v1 timeline tightens; the tool interface reserves the slot either way.
