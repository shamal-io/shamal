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

## Quickstart

```bash
pipx install shamal        # or: uv tool install shamal
brew install k6            # or: https://k6.io/docs/get-started/installation/

export SHAMAL_MODEL=claude-sonnet-5   # any litellm model id; ollama/<name> for local
export ANTHROPIC_API_KEY=...          # not needed for ollama/* models

# 1. Draft scenarios from your API spec (or a HAR file, or an existing k6 script)
shamal plan ./openapi.yaml --review

# 2. Review the generated k6 code, commit it, then run it
shamal run ./openapi.k6.js --results results.json

# 3. Let the agent find out where and why it degraded
shamal investigate --results results.json

# 4. Ship the evidence: markdown for the PR, self-contained HTML for humans
shamal report --results results.json
```

`shamal run` exits `1` when thresholds fail, which makes it a drop-in CI
gate - see [docs/ci.md](docs/ci.md). Air-gapped? See
[docs/airgap.md](docs/airgap.md). All knobs: [docs/configuration.md](docs/configuration.md).

## How investigation works

`shamal investigate` runs a bounded agent loop over the captured results:
deterministic tools compute summary stats, timeseries windows, error
clusters, and a saturation-knee detection; the model interrogates those
tools and must conclude with a structured finding - symptom, cited evidence
windows, ranked hypotheses with honest confidence levels, and next steps.
It works on any k6 results, including summary exports from test suites
Shamal did not generate.

## Status

v0.1.0 - early but real: the full pipeline works end-to-end. The v1 scope
was built spec-first in [`openspec/changes/add-shamal-mvp/`](openspec/changes/add-shamal-mvp/) -
proposal, design decisions, capability specs, and task breakdown are all public.

## Requirements

- Python 3.12+
- [k6](https://k6.io/docs/get-started/installation/) on your PATH (or `SHAMAL_K6_PATH`)
- An LLM: Claude (default), OpenAI, Gemini, or a local model via Ollama

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). This project is developed spec-first with [OpenSpec](https://github.com/Fission-AI/OpenSpec) and test-first (TDD); start with the open change proposals in `openspec/changes/`.

## License

[Apache-2.0](LICENSE)
