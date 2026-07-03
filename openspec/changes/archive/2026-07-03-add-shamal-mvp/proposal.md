# Proposal: add-shamal-mvp

## Why

Performance testing has no AI-native open-source tool: k6, Locust, and Gatling generate load but leave scenario design and bottleneck analysis to experts, while the AI-testing wave (agentic E2E, AI code review, AI root-cause analysis for alerts) has skipped the performance domain entirely. Shamal fills that gap: an Apache-2.0 CLI that generates load scenarios from an API description, runs them through k6, and agentically investigates the results to produce a root-cause hypothesis - self-hosted, air-gap-friendly, no SaaS dependency.

## What Changes

- New Python 3.12+ package `shamal` with a Typer-based CLI (`shamal plan`, `shamal run`, `shamal investigate`, `shamal report`)
- Ingestion of OpenAPI 3.x specs, HAR files, and existing k6 scripts as scenario sources
- LLM-powered generation of plain, editable k6 JavaScript scenarios (user journeys, ramp profiles, thresholds, test data)
- Test execution via the k6 binary behind an engine adapter interface, capturing k6 JSON summary output
- Agentic investigation loop over results: latency percentiles vs ramp phases, error clustering, saturation signatures, optional Prometheus correlation, ending in a ranked root-cause hypothesis
- Markdown and self-contained HTML reports with CI-friendly exit codes (pass/fail against thresholds)
- Provider-agnostic LLM access via litellm: Claude default; OpenAI, Gemini, and Ollama (air-gapped/local) supported from day one

## Capabilities

### New Capabilities
- `cli-core`: command structure, configuration file/env handling, exit-code contract, no-telemetry guarantee
- `scenario-generation`: ingest OpenAPI/HAR/k6 sources and produce readable k6 scenarios via LLM
- `test-execution`: run scenarios through the k6 engine adapter and capture structured results
- `result-investigation`: agentic analysis of run results with optional Prometheus metrics correlation, producing a root-cause hypothesis
- `reporting`: markdown/HTML report rendering and CI gate semantics
- `llm-providers`: provider-agnostic LLM configuration incl. local models for air-gapped use

### Modified Capabilities
(none - greenfield project)

## Non-goals

- Browser-level load testing (HTTP/protocol level only in v1)
- Distributed load workers or multi-node orchestration
- Web UI, dashboards, or historical trend storage
- Auto-remediation of findings
- SaaS offering, telemetry, or any phone-home behavior
- Engines other than k6 (the adapter interface exists so Locust/Gatling/JMeter can be added later, but v1 ships k6 only)

## Impact

- New repository content: `src/shamal/`, `tests/`, `pyproject.toml` (uv), CI workflow, README, LICENSE (Apache-2.0)
- External runtime dependencies: k6 binary (user-installed, discovery + version check required), LLM API or local Ollama endpoint
- No existing code affected (first change in the repo)
