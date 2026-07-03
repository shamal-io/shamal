# Tasks: add-shamal-mvp

## 1. Repository foundation

- [x] 1.1 Scaffold `pyproject.toml` (uv + hatchling, Python 3.12+), `src/shamal/`, `tests/`, ruff + mypy strict config
- [x] 1.2 Add LICENSE (Apache-2.0), README skeleton (positioning, quickstart placeholder, no-telemetry statement), CONTRIBUTING.md, CODE_OF_CONDUCT.md
- [x] 1.3 CI workflow (GitHub Actions): lint, typecheck, pytest on 3.12/3.13, no network in tests
- [x] 1.4 Write failing tests for config resolution (flags > env > shamal.toml), then implement `shamal.config`
- [x] 1.5 Write failing tests for the exit-code contract and Typer app skeleton with the four subcommands, then implement `shamal.cli`

## 2. LLM layer

- [x] 2.1 Write failing tests for `shamal.llm.complete(messages, tools)` against a stubbed litellm, then implement the module (model/provider from config, token-usage debug logging, content redaction at default verbosity)
- [x] 2.2 Write failing tests for Ollama configuration (no API key demanded, base URL honored), then implement provider wiring + capability warnings

## 3. Ingestion and scenario generation

- [x] 3.1 Write failing tests for source auto-detection (OpenAPI YAML/JSON, HAR, k6 JS, unsupported), then implement `shamal.ingest`
- [x] 3.2 Write failing tests for the OpenAPI parser (endpoints, params, auth schemes) on fixture specs, then implement
- [x] 3.3 Write failing tests for the HAR parser (journey extraction, static-asset filtering), then implement
- [x] 3.4 Build the constrained k6 template skeleton; write failing tests asserting any filled template parses as valid JS (node --check or esprima fixture harness), then implement `shamal.generate` with LLM journey/stage/threshold filling
- [x] 3.5 Write failing tests for provenance header, `--review` summary rendering, and `--force` overwrite protection, then implement `shamal plan` end-to-end with a stubbed LLM

## 4. Execution engine

- [x] 4.1 Write failing tests for the `LoadEngine` protocol and k6 discovery/version-check (PATH, `SHAMAL_K6_PATH`, missing-binary exit 3), then implement
- [x] 4.2 Write failing tests for the NDJSON downsampler (bounded output size on large fixture streams, phase/percentile/error extraction), then implement `RunResult` capture
- [x] 4.3 Write failing tests for run semantics (threshold fail -> exit 1, target unreachable -> exit 2, k6 stdout passthrough), then implement `shamal run` with a fake-k6 test double
- [x] 4.4 Integration smoke test behind an opt-in marker: real k6 against a local httpbin container

## 5. Investigation agent

- [x] 5.1 Write failing tests for the analysis tools (`get_summary_stats`, `get_timeseries_slice`, `get_error_samples`) over `RunResult` fixtures, then implement
- [x] 5.2 Write failing tests for the bounded agent loop (step budget, graceful inconclusive exit, scripted-LLM double), then implement the loop
- [x] 5.3 Write failing tests for finding structure (symptom, cited evidence windows, ranked hypotheses with confidence, competing-hypotheses case), then implement finding assembly
- [x] 5.4 Write failing tests for foreign k6 summary input (tools degrade gracefully, unavailable analyses noted), then implement
- [x] 5.5 Write failing tests for `query_prometheus` (configured, absent, mid-loop failure) against a stub server, then implement read-only Prometheus correlation
- [x] 5.6 Curate a saturation-signature fixture (ramp + latency knee + throughput plateau) and assert the loop identifies the knee window with a scripted LLM

## 6. Reporting

- [x] 6.1 Write failing tests for markdown report (verdict first, failed thresholds on top, PR-comment size budget), then implement
- [x] 6.2 Write failing tests for self-contained HTML (zero external references, renders investigation finding), then implement Jinja2 templates with inlined assets
- [x] 6.3 Write failing tests for `--json` mode (stable schema, stdout purity), then implement

## 7. Release readiness

- [x] 7.1 End-to-end walkthrough test with stubbed LLM + fake k6: plan -> run -> investigate -> report
- [x] 7.2 Write README quickstart against the real flow; record demo cast/GIF (quickstart done; demo GIF deferred to post-v0.1.0)
- [x] 7.3 Docs: air-gapped setup guide (Ollama), CI recipe (GitHub Actions PR gate), configuration reference
- [x] 7.4 Package build + `uvx shamal` / `pipx run shamal` verification; tag v0.1.0
