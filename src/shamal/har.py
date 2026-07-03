"""HAR parsing: extract the API journey, drop the static noise."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel

from shamal.config import ConfigError

STATIC_EXTENSIONS = {
    ".js", ".mjs", ".css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm",
}  # fmt: skip
STATIC_MIME_PREFIXES = (
    "image/", "font/", "video/", "text/css", "application/javascript",
    "text/javascript", "application/font",
)  # fmt: skip


class HarStep(BaseModel):
    method: str
    url: str
    body: str | None = None
    mime_type: str | None = None


class HarJourney(BaseModel):
    base_url: str
    steps: list[HarStep]


def parse_har(path: Path) -> HarJourney:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Could not parse HAR file {path}: {exc}") from exc

    entries = (document.get("log") or {}).get("entries") or []
    steps: list[HarStep] = []
    for entry in entries:
        request = entry.get("request") or {}
        url = request.get("url")
        method = request.get("method")
        if not url or not method:
            continue
        if _is_static(url, entry):
            continue
        post_data = request.get("postData") or {}
        steps.append(
            HarStep(
                method=str(method).upper(),
                url=str(url),
                body=post_data.get("text"),
                mime_type=post_data.get("mimeType"),
            )
        )

    if not steps:
        raise ConfigError(
            f"HAR file {path.name} contains no API requests after static-asset filtering."
        )

    origins = Counter(_origin(step.url) for step in steps)
    return HarJourney(base_url=origins.most_common(1)[0][0], steps=steps)


def _is_static(url: str, entry: dict[str, object]) -> bool:
    path = urlsplit(url).path.lower()
    if any(path.endswith(ext) for ext in STATIC_EXTENSIONS):
        return True
    response = entry.get("response")
    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, dict):
            mime = str(content.get("mimeType", ""))
            if mime.startswith(STATIC_MIME_PREFIXES):
                return True
    return False


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
