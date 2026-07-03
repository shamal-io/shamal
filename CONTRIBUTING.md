# Contributing to Shamal

Thanks for considering a contribution. Shamal is developed spec-first and test-first; this file tells you everything needed to get a change merged.

## Development setup

```bash
git clone https://github.com/shamal-io/shamal.git
cd shamal
uv sync                 # installs runtime + dev dependencies
uv run pytest           # unit tests (no network, no k6 needed)
uv run ruff check .     # lint
uv run mypy             # types (strict)
```

The integration tests need a real k6 binary and are opt-in:

```bash
uv run pytest -m integration
```

## How changes work here

1. **Spec first.** Behavior changes go through [OpenSpec](https://github.com/Fission-AI/OpenSpec): propose a change under `openspec/changes/<change-id>/` (proposal, spec deltas, tasks) before implementation. Small fixes that do not change specified behavior can go straight to a PR.
2. **Tests first.** Every implementation task starts with a failing test. PRs that add behavior without tests will be asked to add them.
3. **Conventional commits.** `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.

## Ground rules

- Generated scenarios must remain plain k6 code that runs without Shamal.
- No telemetry, ever. No network calls beyond user-configured endpoints.
- Local models (Ollama) are first-class: nothing may hard-require a cloud API key.
- Keep dependencies lean; adding one is a design decision, not a convenience.

## Reporting issues

Use [GitHub issues](https://github.com/shamal-io/shamal/issues). For performance-analysis quality problems (bad hypotheses, missed saturation points), attach the `RunResult` JSON if you can share it - it is the whole investigation input and makes reports reproducible.
