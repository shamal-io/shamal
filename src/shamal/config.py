"""Configuration resolution: CLI flags > SHAMAL_* environment variables > shamal.toml.

Empty-string values (from flags or env) are treated as unset so that
`SHAMAL_MODEL=""` behaves like an absent variable.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

CONFIG_FILENAME = "shamal.toml"
ENV_PREFIX = "SHAMAL_"


class ConfigError(Exception):
    """Invalid or missing configuration; maps to exit code 3 at the CLI boundary."""


class Settings(BaseModel):
    """Resolved Shamal configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str | None = None
    ollama_base_url: str | None = None
    k6_path: str | None = None
    prometheus_url: str | None = None
    max_agent_steps: int = 15

    def require_model(self) -> str:
        if self.model:
            return self.model
        raise ConfigError(
            "No LLM model configured. Set one via the --model flag, the "
            "SHAMAL_MODEL environment variable, or the `model` key in shamal.toml "
            "(e.g. claude-sonnet-5, or ollama/<name> for a local model)."
        )


def _load_toml(cwd: Path) -> dict[str, Any]:
    path = cwd / CONFIG_FILENAME
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Malformed {CONFIG_FILENAME} at {path}: {exc}") from exc


def _from_env(env: Mapping[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in Settings.model_fields:
        raw = env.get(ENV_PREFIX + field.upper())
        if raw:
            values[field] = raw
    return values


def resolve_settings(
    cli_overrides: Mapping[str, Any],
    env: Mapping[str, str],
    cwd: Path,
) -> Settings:
    """Merge configuration layers by precedence: flags, then env, then shamal.toml."""
    merged: dict[str, Any] = _load_toml(cwd)
    merged.update(_from_env(env))
    merged.update({k: v for k, v in cli_overrides.items() if v not in (None, "")})
    try:
        return Settings(**merged)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigError(f"Invalid configuration: {details}") from exc
