"""CLI skeleton: subcommands, help without side effects, exit codes (spec: cli-core)."""

import pytest
from typer.testing import CliRunner

import shamal.cli
from shamal.cli import app
from shamal.exitcodes import ExitCode

runner = CliRunner()

SUBCOMMANDS = ["plan", "run", "investigate", "report"]


class TestExitCodeContract:
    def test_values_match_spec(self) -> None:
        assert ExitCode.OK == 0
        assert ExitCode.THRESHOLDS_FAILED == 1
        assert ExitCode.EXECUTION_ERROR == 2
        assert ExitCode.CONFIG_ERROR == 3


class TestHelp:
    def test_root_help_exits_zero_and_lists_subcommands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for name in SUBCOMMANDS:
            assert name in result.output

    @pytest.mark.parametrize("name", SUBCOMMANDS)
    def test_subcommand_help_exits_zero(self, name: str) -> None:
        result = runner.invoke(app, [name, "--help"])
        assert result.exit_code == 0

    @pytest.mark.parametrize("args", [["--help"], *[[name, "--help"] for name in SUBCOMMANDS]])
    def test_help_never_resolves_config(
        self, args: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode(*a: object, **kw: object) -> None:
            raise AssertionError("--help must not resolve configuration")

        monkeypatch.setattr(shamal.cli, "resolve_settings", explode)
        result = runner.invoke(app, args)
        assert result.exit_code == 0


class TestConfigErrors:
    def test_config_error_exits_three(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A command that needs an LLM but has no provider config exits 3 with guidance."""
        monkeypatch.delenv("SHAMAL_MODEL", raising=False)
        result = runner.invoke(
            app, ["plan", "does-not-matter.yaml"], env={"SHAMAL_MODEL": ""}
        )
        assert result.exit_code == ExitCode.CONFIG_ERROR
        assert "--model" in result.output or "SHAMAL_MODEL" in result.output
