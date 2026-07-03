# cli-core Specification

## Purpose
TBD - created by archiving change add-shamal-mvp. Update Purpose after archive.
## Requirements
### Requirement: Command structure
The CLI SHALL expose four subcommands: `shamal plan`, `shamal run`, `shamal investigate`, and `shamal report`, each executable independently given its required inputs.

#### Scenario: Help without side effects
- **WHEN** the user runs `shamal --help` or any subcommand with `--help`
- **THEN** usage information is printed and the process exits 0 without reading config, contacting an LLM, or touching the network

#### Scenario: Independent stage execution
- **WHEN** the user runs `shamal investigate --results ./results.json` on results produced by a plain k6 run outside Shamal
- **THEN** investigation executes normally without requiring `plan` or `run` to have been used

### Requirement: Configuration resolution
The CLI SHALL resolve configuration in precedence order: command-line flags, environment variables prefixed `SHAMAL_`, then a `shamal.toml` file in the working directory.

#### Scenario: Flag overrides environment
- **WHEN** `SHAMAL_MODEL` is set and `--model` is passed with a different value
- **THEN** the `--model` value is used

#### Scenario: Missing required configuration
- **WHEN** a command needs an LLM and no provider configuration can be resolved
- **THEN** the process exits with code 3 and an actionable message naming the flag, env var, and config key that would fix it

### Requirement: Exit-code contract
The CLI SHALL exit 0 when thresholds pass, 1 when thresholds fail, 2 on execution errors, and 3 on configuration errors.

#### Scenario: Threshold failure in CI
- **WHEN** `shamal run` completes and any k6 threshold failed
- **THEN** the process exits with code 1

### Requirement: No telemetry
The CLI SHALL make no network connections other than those explicitly required by the invoked operation (LLM endpoint, target under test, optional Prometheus URL).

#### Scenario: Offline operation with local model
- **WHEN** Shamal is configured with an Ollama endpoint and run on an air-gapped network
- **THEN** all commands complete without attempting any connection beyond the configured Ollama endpoint, the k6 target, and optional Prometheus

