# Configuration reference

Shamal resolves configuration in precedence order:

1. Command-line flags (e.g. `--model`)
2. Environment variables prefixed `SHAMAL_`
3. `shamal.toml` in the working directory

Empty values are treated as unset.

| Key (`shamal.toml`) | Env var | Default | Purpose |
|---|---|---|---|
| `model` | `SHAMAL_MODEL` | none (required for `plan`/`investigate`) | LLM model id, e.g. `claude-sonnet-5`, `gpt-4o`, `gemini/gemini-2.5-pro`, `ollama/qwen3` |
| `ollama_base_url` | `SHAMAL_OLLAMA_BASE_URL` | litellm default (`http://localhost:11434`) | Ollama endpoint for `ollama/*` models |
| `k6_path` | `SHAMAL_K6_PATH` | `k6` on PATH | Explicit k6 binary location |
| `prometheus_url` | `SHAMAL_PROMETHEUS_URL` | none | Read-only Prometheus API for system-side correlation during `investigate` |
| `max_agent_steps` | `SHAMAL_MAX_AGENT_STEPS` | `15` | Hard cap on LLM calls per investigation |

Provider API keys use each provider's standard variable (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY`); Ollama needs none.

Example `shamal.toml`:

```toml
model = "claude-sonnet-5"
prometheus_url = "http://prometheus.internal:9090"
max_agent_steps = 20
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Run completed, thresholds passed |
| 1 | Run completed, thresholds failed |
| 2 | Execution error (engine crash, target unreachable) |
| 3 | Configuration error (missing config, unsupported input) |

`investigate` and `report` are annotative: they never turn a passing run
into a failing one.

## Network policy

Shamal connects only to endpoints you configure: the LLM endpoint, the test
target (via k6), and optionally Prometheus. There is no telemetry and no
update check.
