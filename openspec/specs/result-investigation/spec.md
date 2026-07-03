# result-investigation Specification

## Purpose
TBD - created by archiving change add-shamal-mvp. Update Purpose after archive.
## Requirements
### Requirement: Bounded agentic investigation
`shamal investigate` SHALL run a toolcalling agent loop over the `RunResult` with a configurable maximum step count, using analysis tools (`get_summary_stats`, `get_timeseries_slice`, `get_error_samples`, and `query_prometheus` when configured) to examine the run.

#### Scenario: Step budget exhausted
- **WHEN** the agent reaches the maximum step count without a confident conclusion
- **THEN** investigation terminates gracefully and reports partial findings labeled as inconclusive

#### Scenario: Works on foreign k6 results
- **WHEN** the input is a k6 summary export produced without Shamal
- **THEN** investigation runs with the tools that apply and notes which analyses were unavailable

### Requirement: Root-cause hypothesis output
Investigation SHALL produce a structured finding containing: observed symptom, correlated evidence (with the specific metrics and time windows cited), a ranked root-cause hypothesis list, and suggested next steps, each labeled with a confidence level.

#### Scenario: Saturation detection
- **WHEN** latency percentiles degrade sharply while throughput plateaus during a ramp stage
- **THEN** the finding identifies the saturation point (approximate VU level and time window) and cites the supporting series

#### Scenario: Honest uncertainty
- **WHEN** the evidence supports multiple explanations
- **THEN** the output presents competing hypotheses with confidence levels rather than asserting a single cause

### Requirement: Optional Prometheus correlation
When a Prometheus URL is configured, the agent MAY query it read-only for target-system metrics over the test window; absent configuration, investigation SHALL complete using k6 data alone.

#### Scenario: No Prometheus configured
- **WHEN** no Prometheus URL is set
- **THEN** investigation completes without error and the report notes that system-side correlation was not available

#### Scenario: Prometheus unreachable mid-investigation
- **WHEN** a configured Prometheus endpoint fails during the loop
- **THEN** the agent continues with k6 data only and the failure is noted in the finding

### Requirement: Investigation never alters pass/fail
`shamal investigate` SHALL be annotative only: it never changes the run's threshold outcome or exit-code semantics.

#### Scenario: Investigating a passed run
- **WHEN** the user investigates a run whose thresholds passed
- **THEN** the command exits 0 regardless of what the investigation finds

