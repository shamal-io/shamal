"""Minimal OpenAPI 3.x parsing: just what scenario generation needs.

Deliberately not a full validator - unknown constructs are ignored, not
rejected. The LLM receives a compact endpoint summary, not the raw spec.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from shamal.config import ConfigError

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
DEFAULT_BASE_URL = "http://localhost:8080"


class Param(BaseModel):
    name: str
    location: str  # "query" | "path" | "header" | "cookie"


class Endpoint(BaseModel):
    method: str
    path: str
    summary: str | None = None
    required_params: list[Param] = []
    has_request_body: bool = False
    auth: str | None = None


class OpenAPIModel(BaseModel):
    title: str
    base_url: str
    endpoints: list[Endpoint]


def parse_openapi(path: Path) -> OpenAPIModel:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse OpenAPI document {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise ConfigError(f"OpenAPI document {path} is not a mapping.")

    servers = document.get("servers") or []
    base_url = DEFAULT_BASE_URL
    if servers and isinstance(servers[0], dict) and servers[0].get("url"):
        base_url = str(servers[0]["url"]).rstrip("/")

    global_security = _first_security_scheme(document.get("security"))

    endpoints: list[Endpoint] = []
    paths = document.get("paths") or {}
    for route, operations in paths.items():
        if not isinstance(operations, dict):
            continue
        shared_params = operations.get("parameters") or []
        for method, operation in operations.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            params = [*shared_params, *(operation.get("parameters") or [])]
            required = [
                Param(name=str(p["name"]), location=str(p.get("in", "query")))
                for p in params
                if isinstance(p, dict) and p.get("required") and p.get("name")
            ]
            operation_security = _first_security_scheme(operation.get("security"))
            body = operation.get("requestBody")
            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=str(route),
                    summary=operation.get("summary"),
                    required_params=required,
                    has_request_body=bool(body),
                    auth=operation_security if operation_security is not None else global_security,
                )
            )

    info = document.get("info") or {}
    return OpenAPIModel(
        title=str(info.get("title", path.stem)), base_url=base_url, endpoints=endpoints
    )


def _first_security_scheme(security: Any) -> str | None:
    if isinstance(security, list):
        for requirement in security:
            if isinstance(requirement, dict) and requirement:
                return str(next(iter(requirement)))
    return None
