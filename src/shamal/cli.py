"""Shamal CLI: plan, run, investigate, report.

Configuration is resolved inside command bodies, never at import time or
during --help (spec: cli-core, "Help without side effects").
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

import typer

from shamal.config import ConfigError, Settings, resolve_settings
from shamal.exitcodes import ExitCode

app = typer.Typer(
    name="shamal",
    help="Agentic performance testing: generate, run, and investigate load tests.",
    add_completion=False,
    no_args_is_help=True,
)

ModelOption = Annotated[
    str | None,
    typer.Option("--model", help="LLM model id (e.g. claude-sonnet-5, ollama/<name>)."),
]


def _settings(**cli_overrides: Any) -> Settings:
    """Resolve settings, translating ConfigError into the exit-code contract."""
    try:
        return resolve_settings(cli_overrides=cli_overrides, env=os.environ, cwd=Path.cwd())
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}")
        raise typer.Exit(ExitCode.CONFIG_ERROR) from exc


def _require_model(settings: Settings) -> str:
    try:
        return settings.require_model()
    except ConfigError as exc:
        typer.echo(f"Configuration error: {exc}")
        raise typer.Exit(ExitCode.CONFIG_ERROR) from exc


def _not_implemented(stage: str) -> None:
    typer.echo(f"shamal {stage} is not implemented yet.")
    raise typer.Exit(ExitCode.EXECUTION_ERROR)


@app.command()
def plan(
    source: Annotated[
        Path, typer.Argument(help="Scenario source: OpenAPI spec, HAR file, or k6 script.")
    ],
    model: ModelOption = None,
    out: Annotated[
        Path | None, typer.Option("--out", help="Output path for the generated scenario.")
    ] = None,
    review: Annotated[
        bool, typer.Option("--review", help="Print a journey summary before writing files.")
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite an existing scenario file.")
    ] = False,
) -> None:
    """Generate k6 scenarios from an API description."""
    settings = _settings(model=model)
    _require_model(settings)
    _not_implemented("plan")


@app.command()
def run(
    scenario: Annotated[Path, typer.Argument(help="k6 scenario file to execute.")],
    results: Annotated[
        Path | None, typer.Option("--results", help="Path for the RunResult JSON output.")
    ] = None,
) -> None:
    """Execute a scenario through the k6 engine and capture structured results."""
    _settings()
    _not_implemented("run")


@app.command()
def investigate(
    results: Annotated[
        Path, typer.Option("--results", help="RunResult or k6 summary JSON to analyze.")
    ],
    model: ModelOption = None,
) -> None:
    """Agentically analyze run results into a root-cause hypothesis."""
    settings = _settings(model=model)
    _require_model(settings)
    _not_implemented("investigate")


@app.command()
def report(
    results: Annotated[
        Path, typer.Option("--results", help="RunResult JSON to render.")
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON on stdout.")
    ] = False,
) -> None:
    """Render run results (and investigation findings) as markdown/HTML."""
    _settings()
    _not_implemented("report")
