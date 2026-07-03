"""Config resolution: CLI flags > SHAMAL_* env vars > shamal.toml (spec: cli-core)."""

from pathlib import Path

import pytest

from shamal.config import ConfigError, Settings, resolve_settings


def write_toml(tmp_path: Path, body: str) -> Path:
    (tmp_path / "shamal.toml").write_text(body, encoding="utf-8")
    return tmp_path


class TestPrecedence:
    def test_flag_overrides_env(self, tmp_path: Path) -> None:
        settings = resolve_settings(
            cli_overrides={"model": "claude-sonnet-5"},
            env={"SHAMAL_MODEL": "ollama/qwen3"},
            cwd=tmp_path,
        )
        assert settings.model == "claude-sonnet-5"

    def test_env_overrides_toml(self, tmp_path: Path) -> None:
        write_toml(tmp_path, 'model = "from-toml"\n')
        settings = resolve_settings(
            cli_overrides={}, env={"SHAMAL_MODEL": "from-env"}, cwd=tmp_path
        )
        assert settings.model == "from-env"

    def test_toml_used_when_nothing_else_set(self, tmp_path: Path) -> None:
        write_toml(tmp_path, 'model = "from-toml"\nk6_path = "/opt/k6"\n')
        settings = resolve_settings(cli_overrides={}, env={}, cwd=tmp_path)
        assert settings.model == "from-toml"
        assert settings.k6_path == "/opt/k6"

    def test_none_flag_does_not_mask_env(self, tmp_path: Path) -> None:
        settings = resolve_settings(
            cli_overrides={"model": None}, env={"SHAMAL_MODEL": "from-env"}, cwd=tmp_path
        )
        assert settings.model == "from-env"


class TestDefaults:
    def test_missing_toml_is_fine(self, tmp_path: Path) -> None:
        settings = resolve_settings(cli_overrides={}, env={}, cwd=tmp_path)
        assert isinstance(settings, Settings)
        assert settings.model is None
        assert settings.prometheus_url is None

    def test_unknown_toml_key_rejected(self, tmp_path: Path) -> None:
        write_toml(tmp_path, 'modle = "typo"\n')
        with pytest.raises(ConfigError, match="modle"):
            resolve_settings(cli_overrides={}, env={}, cwd=tmp_path)

    def test_malformed_toml_reports_path(self, tmp_path: Path) -> None:
        write_toml(tmp_path, "not [valid toml\n")
        with pytest.raises(ConfigError, match=r"shamal\.toml"):
            resolve_settings(cli_overrides={}, env={}, cwd=tmp_path)


class TestRequireModel:
    def test_missing_model_names_all_three_fixes(self, tmp_path: Path) -> None:
        settings = resolve_settings(cli_overrides={}, env={}, cwd=tmp_path)
        with pytest.raises(ConfigError) as exc_info:
            settings.require_model()
        message = str(exc_info.value)
        assert "--model" in message
        assert "SHAMAL_MODEL" in message
        assert "shamal.toml" in message

    def test_present_model_passes(self, tmp_path: Path) -> None:
        settings = resolve_settings(
            cli_overrides={"model": "claude-sonnet-5"}, env={}, cwd=tmp_path
        )
        assert settings.require_model() == "claude-sonnet-5"
