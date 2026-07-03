# Shamal

**Open-source agentic performance testing.** Shamal generates load test scenarios from your API description, runs them through [k6](https://k6.io), and then does the part no load testing tool does: it investigates the results like a performance engineer would, and hands you a root-cause hypothesis.

> Named after the shamal, the northwesterly wind that stress-tests everything built along the Gulf.

## What it does

```
shamal plan ./openapi.yaml       # LLM drafts readable k6 scenarios from your API spec
shamal run ./scenarios/api.js    # executes via k6, captures structured results
shamal investigate               # AI agent digs through the results: where did it break, and why?
shamal report                    # markdown + self-contained HTML, CI-friendly exit codes
```

The output of `plan` is plain k6 JavaScript you can read, edit, commit, and run **without Shamal installed**. The `investigate` step works on any k6 results, including test suites Shamal did not generate.

## Principles

- **No lock-in.** Generated scenarios are standard k6 code. Delete Shamal and your tests still run.
- **Air-gap friendly.** Works with local models via Ollama; no API key required, nothing leaves your network.
- **No telemetry.** Shamal makes no network connections beyond the ones you configure: your LLM endpoint, your test target, and (optionally) your Prometheus.
- **Annotative AI.** Investigation never changes your pass/fail result. Thresholds decide; the agent explains.

## Status

Early development (pre-0.1). The full v1 scope is specified in [`openspec/changes/add-shamal-mvp/`](openspec/changes/add-shamal-mvp/) - proposal, design decisions, capability specs, and task breakdown are public.

## Quickstart

Coming with v0.1.0.

## Requirements

- Python 3.12+
- [k6](https://k6.io/docs/get-started/installation/) on your PATH (or `SHAMAL_K6_PATH`)
- An LLM: Claude (default), OpenAI, Gemini, or a local model via Ollama

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). This project is developed spec-first with [OpenSpec](https://github.com/Fission-AI/OpenSpec) and test-first (TDD); start with the open change proposals in `openspec/changes/`.

## License

[Apache-2.0](LICENSE)
