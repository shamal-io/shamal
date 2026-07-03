# Air-gapped setup (Ollama)

Shamal's full pipeline works without any cloud API: a local model via
[Ollama](https://ollama.com) plus the k6 binary is a complete installation.
No API key is required or requested.

## Setup

```bash
# on a machine with internet access, mirror what you need:
#   - the shamal wheel and its dependencies (pip download / uv export)
#   - the k6 binary for your platform
#   - an Ollama model archive (ollama pull, then copy ~/.ollama/models)

# on the air-gapped host:
ollama serve &
ollama run qwen3          # or any tool-calling-capable model you mirrored

export SHAMAL_MODEL="ollama/qwen3"
export SHAMAL_OLLAMA_BASE_URL="http://127.0.0.1:11434"   # default; set if remote

shamal plan ./openapi.yaml --review
shamal run ./openapi.k6.js
shamal investigate --results shamal-results.json
shamal report --results shamal-results.json
```

## Model guidance

- `investigate` relies on tool calling. Pick a model that supports it
  (Shamal warns, but does not refuse, when the model does not advertise
  support).
- Larger context helps investigation quality; the RunResult is compact by
  design (bounded series, clustered errors), so 16k context is workable.

## What leaves the network

With `ollama/*` models: nothing. Shamal's only connections are the local
Ollama endpoint, the load-test target itself, and (only if you configure it)
your Prometheus. This is a design guarantee tested in the suite, not a
best-effort claim.
