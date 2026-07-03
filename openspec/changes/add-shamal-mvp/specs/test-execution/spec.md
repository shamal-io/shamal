# test-execution

## ADDED Requirements

### Requirement: Engine adapter interface
Load engines SHALL be integrated behind a `LoadEngine` protocol providing discovery, execution, and result parsing, with k6 as the sole v1 implementation.

#### Scenario: k6 binary discovery
- **WHEN** `shamal run` starts and the k6 binary is not found on PATH or at `SHAMAL_K6_PATH`
- **THEN** the process exits with code 3 with installation instructions for the user's platform

#### Scenario: Version check
- **WHEN** the discovered k6 binary is older than the minimum supported version
- **THEN** a warning names the found and required versions before execution proceeds

### Requirement: Structured result capture
`shamal run` SHALL execute the scenario via k6 and capture both the summary export and streaming JSON output, downsampling the stream into a bounded-size `RunResult` containing stage phases, latency percentile series, throughput series, and error samples.

#### Scenario: Successful run produces results file
- **WHEN** a run completes (pass or fail)
- **THEN** a `RunResult` JSON file is written whose size stays within the configured budget regardless of test duration

#### Scenario: Passthrough of k6 output
- **WHEN** `shamal run` executes
- **THEN** k6's live console output streams to the user unmodified

### Requirement: Run failure semantics
`shamal run` SHALL distinguish threshold failures (exit 1) from engine crashes or target-unreachable errors (exit 2).

#### Scenario: Target unreachable
- **WHEN** the target host refuses all connections
- **THEN** the process exits with code 2 and the error is recorded in the `RunResult` for later investigation
