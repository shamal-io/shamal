"""Source auto-detection and loading (spec: scenario-generation).

Detection is content-based, never extension-based: a mislabeled file should
still be recognized for what it actually contains.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from shamal.config import ConfigError
from shamal.har import HarJourney, parse_har
from shamal.openapi import OpenAPIModel, parse_openapi

SUPPORTED_FORMATS = "OpenAPI 3.x (YAML or JSON), HAR (browser export), or a k6 script (.js)"

K6_MARKERS = ("k6/http", "k6/execution", "export default function")


class SourceType(Enum):
    OPENAPI = "openapi"
    HAR = "har"
    K6_SCRIPT = "k6-script"


class K6Source(BaseModel):
    """An existing k6 script used as generation context."""

    content: str
    path: str


def detect_source(path: Path) -> SourceType:
    if not path.is_file():
        raise ConfigError(f"Source file {path} does not exist.")
    text = path.read_text(encoding="utf-8", errors="replace")

    document = _try_parse_structured(text)
    if isinstance(document, dict):
        if "openapi" in document or "swagger" in document:
            return SourceType.OPENAPI
        log = document.get("log")
        if isinstance(log, dict) and "entries" in log:
            return SourceType.HAR

    if any(marker in text for marker in K6_MARKERS):
        return SourceType.K6_SCRIPT

    raise ConfigError(
        f"Unsupported source file {path.name}: could not recognize it as any "
        f"supported format. Supported: {SUPPORTED_FORMATS}."
    )


def load_source(path: Path) -> OpenAPIModel | HarJourney | K6Source:
    """Detect and parse a scenario source into its model."""
    source_type = detect_source(path)
    if source_type is SourceType.OPENAPI:
        return parse_openapi(path)
    if source_type is SourceType.HAR:
        return parse_har(path)
    return K6Source(content=path.read_text(encoding="utf-8", errors="replace"), path=path.name)


def _try_parse_structured(text: str) -> Any:
    """Parse YAML (a superset of JSON here); return None when it is neither."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None
