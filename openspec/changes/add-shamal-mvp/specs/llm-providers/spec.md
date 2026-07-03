# llm-providers

## ADDED Requirements

### Requirement: Provider-agnostic access
All LLM calls SHALL pass through a single internal module exposing `complete(messages, tools)` backed by litellm, so that no other module imports a provider SDK directly.

#### Scenario: Switching providers by configuration
- **WHEN** the user changes only `SHAMAL_MODEL` (e.g., from a Claude model to `ollama/qwen3`)
- **THEN** all commands work without code changes, and capability differences (e.g., context size) surface as clear warnings, not crashes

### Requirement: Local model support
Ollama-served local models SHALL be first-class: documented, tested in CI against a stub, and requiring no API key.

#### Scenario: Air-gapped configuration
- **WHEN** `SHAMAL_MODEL=ollama/<model>` and `SHAMAL_OLLAMA_BASE_URL` point to a local endpoint
- **THEN** no external API is contacted and no API-key configuration is demanded

### Requirement: Prompt/response boundaries
LLM interactions SHALL log token usage at debug level and never log request or response bodies at default verbosity.

#### Scenario: Default logging redacts content
- **WHEN** a command runs at default verbosity
- **THEN** logs contain model name, latency, and token counts but no prompt or completion text
