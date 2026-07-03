"""Source auto-detection (spec: scenario-generation, "Source ingestion")."""

from pathlib import Path

import pytest

from shamal.config import ConfigError
from shamal.ingest import SourceType, detect_source

FIXTURES = Path(__file__).parent / "fixtures"


class TestDetection:
    def test_openapi_yaml(self) -> None:
        assert detect_source(FIXTURES / "petstore.yaml") is SourceType.OPENAPI

    def test_openapi_json(self, tmp_path: Path) -> None:
        path = tmp_path / "spec.json"
        path.write_text('{"openapi": "3.1.0", "info": {}, "paths": {}}', encoding="utf-8")
        assert detect_source(path) is SourceType.OPENAPI

    def test_har(self) -> None:
        assert detect_source(FIXTURES / "session.har") is SourceType.HAR

    def test_k6_script(self) -> None:
        assert detect_source(FIXTURES / "existing.k6.js") is SourceType.K6_SCRIPT

    def test_detection_is_content_based_not_extension_based(self, tmp_path: Path) -> None:
        disguised = tmp_path / "totally-a-har.har"
        disguised.write_text('{"openapi": "3.0.0", "paths": {}}', encoding="utf-8")
        assert detect_source(disguised) is SourceType.OPENAPI


class TestRejection:
    def test_unsupported_content_names_supported_formats(self, tmp_path: Path) -> None:
        path = tmp_path / "notes.txt"
        path.write_text("just some prose", encoding="utf-8")
        with pytest.raises(ConfigError) as exc_info:
            detect_source(path)
        message = str(exc_info.value)
        for fmt in ("OpenAPI", "HAR", "k6"):
            assert fmt in message

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="does not exist"):
            detect_source(tmp_path / "ghost.yaml")
