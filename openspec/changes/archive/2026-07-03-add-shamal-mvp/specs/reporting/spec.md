# reporting

## ADDED Requirements

### Requirement: Report formats
`shamal report` SHALL render a run (and its investigation, when present) as GitHub-flavored markdown and as a single self-contained HTML file with no external asset references.

#### Scenario: Self-contained HTML
- **WHEN** an HTML report is generated
- **THEN** the file renders fully offline: all CSS, JS, and chart assets are inlined

#### Scenario: Markdown for PR comments
- **WHEN** a markdown report is generated
- **THEN** it stays concise enough for a PR comment (summary table, threshold outcomes, top finding) with a link-style reference to the full HTML report path

### Requirement: CI gate summary
Reports SHALL lead with a pass/fail verdict matching the run's exit code, followed by threshold results, key percentiles, and the investigation's top hypothesis when available.

#### Scenario: Failed thresholds surfaced first
- **WHEN** any threshold failed
- **THEN** the failed thresholds appear at the top of the report with their configured limits and observed values

### Requirement: Machine-readable output
`shamal report --json` SHALL emit the full report data as a stable JSON document for downstream tooling.

#### Scenario: JSON output is quiet
- **WHEN** `--json` is passed
- **THEN** stdout contains only the JSON document; all human-facing messaging goes to stderr
