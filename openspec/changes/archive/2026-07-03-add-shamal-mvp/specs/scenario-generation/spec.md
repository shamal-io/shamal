# scenario-generation

## ADDED Requirements

### Requirement: Source ingestion
`shamal plan` SHALL accept an OpenAPI 3.x document (YAML or JSON), a HAR file, or an existing k6 script as its scenario source, auto-detecting the type from content.

#### Scenario: OpenAPI ingestion
- **WHEN** the user runs `shamal plan ./openapi.yaml`
- **THEN** Shamal parses the spec, identifies endpoints and their parameters, and proceeds to scenario generation

#### Scenario: Unsupported source
- **WHEN** the input file is none of the supported types
- **THEN** the process exits with code 3 naming the supported formats

### Requirement: Constrained k6 output
Generated scenarios SHALL be produced by filling a fixed k6 template skeleton (imports, options block, function structure controlled by Shamal) so that every generated file is syntactically valid k6 JavaScript.

#### Scenario: Generated file runs under plain k6
- **WHEN** generation completes
- **THEN** the emitted `.js` file executes under the k6 binary directly, with no Shamal-specific runtime or imports

#### Scenario: Provenance header
- **WHEN** a scenario file is generated
- **THEN** it begins with a comment identifying the Shamal version, source input, and a statement that the file is intended to be reviewed and edited

### Requirement: Scenario content
Generated scenarios SHALL include realistic user journeys across the discovered endpoints, ramp profiles (at minimum: smoke, ramp-up, and sustained stages), thresholds for p95 latency and error rate, and generated test data for required parameters.

#### Scenario: Journey coverage summary
- **WHEN** the user runs `shamal plan` with `--review`
- **THEN** a human-readable summary lists each journey, its endpoints, stage profile, and thresholds before any file is written

### Requirement: Deterministic re-runs
`shamal plan` SHALL refuse to overwrite an existing scenario file unless `--force` is passed.

#### Scenario: Existing scenario protected
- **WHEN** the output path already exists and `--force` is absent
- **THEN** the process exits with code 3 without modifying the file
