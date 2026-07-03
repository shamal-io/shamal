"""OpenAPI parsing into the source model handed to scenario generation."""

from pathlib import Path

from shamal.openapi import parse_openapi

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseOpenapi:
    def test_endpoints_extracted(self) -> None:
        api = parse_openapi(FIXTURES / "petstore.yaml")
        signatures = {(e.method, e.path) for e in api.endpoints}
        assert signatures == {
            ("GET", "/pets"),
            ("POST", "/pets"),
            ("GET", "/pets/{petId}"),
        }

    def test_base_url_from_servers(self) -> None:
        api = parse_openapi(FIXTURES / "petstore.yaml")
        assert api.base_url == "https://api.petstore.example"

    def test_required_params_captured(self) -> None:
        api = parse_openapi(FIXTURES / "petstore.yaml")
        list_pets = next(e for e in api.endpoints if e.method == "GET" and e.path == "/pets")
        assert ("status", "query") in [(p.name, p.location) for p in list_pets.required_params]
        assert "limit" not in [p.name for p in list_pets.required_params]

    def test_request_body_flag(self) -> None:
        api = parse_openapi(FIXTURES / "petstore.yaml")
        create = next(e for e in api.endpoints if e.method == "POST")
        assert create.has_request_body is True

    def test_auth_schemes_surfaced(self) -> None:
        api = parse_openapi(FIXTURES / "petstore.yaml")
        create = next(e for e in api.endpoints if e.method == "POST")
        assert create.auth == "bearerAuth"
        get_pet = next(e for e in api.endpoints if e.path == "/pets/{petId}")
        assert get_pet.auth is None

    def test_missing_servers_defaults_to_placeholder(self, tmp_path: Path) -> None:
        path = tmp_path / "no-servers.json"
        path.write_text(
            '{"openapi": "3.0.0", "paths": {"/x": {"get": {"responses": {}}}}}',
            encoding="utf-8",
        )
        api = parse_openapi(path)
        assert api.base_url == "http://localhost:8080"
