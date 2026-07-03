# CI recipe: performance gate on pull requests

Shamal's exit codes make it a natural PR gate: `shamal run` exits 1 when
thresholds fail, and the markdown report fits in a PR comment.

## GitHub Actions

```yaml
name: perf-gate

on: pull_request

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install k6
        run: |
          curl -fsSL https://github.com/grafana/k6/releases/latest/download/k6-linux-amd64.tar.gz \
            | tar xz --strip-components=1
          sudo mv k6 /usr/local/bin/

      - name: Install shamal
        run: pipx install shamal

      - name: Start the app under test
        run: docker compose up -d && ./scripts/wait-for-healthy.sh

      - name: Run the committed scenario
        run: shamal run ./perf/checkout.k6.js --results results.json
        env:
          BASE_URL: http://127.0.0.1:8080

      - name: Investigate and report (runs even when the gate fails)
        if: always()
        env:
          SHAMAL_MODEL: claude-sonnet-5
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          shamal investigate --results results.json
          shamal report --results results.json

      - name: Comment on the PR
        if: always()
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          path: results-report.md
```

Notes:

- Commit the scenario file (`shamal plan` output) to the repo; regenerate it
  deliberately with `--force`, not on every run. Reviewable diffs of load
  scenarios are the point.
- The gate is `shamal run`'s exit code. `investigate` and `report` run under
  `if: always()` so a failing gate still gets a root-cause comment.
- Keep the LLM out of the hot path: only `investigate` needs the API key;
  `run` works without any LLM configured.
