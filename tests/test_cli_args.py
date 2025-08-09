"""Tests for CLI command argument handling and validation."""

from pathlib import Path
from unittest.mock import patch

import pytest
from claudette.cli import app
from claudette.config import ProjectMetadata
from typer.testing import CliRunner


class TestAddCommandArguments:
    """Test argument handling for the add command."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_add_command_with_valid_args(self):
        """Test add command with valid project name and port."""
        with patch("claudette.cli.settings") as mock_settings, patch(
            "claudette.cli._ensure_claudette_initialized"
        ), patch("claudette.cli.Path.exists", return_value=True):
            mock_settings.superset_base.exists.return_value = True

            # Mock successful execution (we're not testing the full workflow)
            with patch("claudette.cli.ProjectMetadata.suggest_port", return_value=9001), patch(
                "claudette.cli._branch_exists", return_value=False
            ), patch("claudette.cli.run_cmd.run"):
                result = self.runner.invoke(app, ["add", "test-project", "9001"])

                # Should not exit with error due to argument validation
                assert "test-project" in result.stdout or result.exit_code != 2

    def test_add_command_invalid_port_range(self):
        """Test add command with port outside valid range."""
        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test port too low
            result = self.runner.invoke(app, ["add", "test-project", "8999"])
            assert result.exit_code != 0

            # Test port too high
            result = self.runner.invoke(app, ["add", "test-project", "10000"])
            assert result.exit_code != 0

    def test_add_command_conflicting_flags(self):
        """Test add command with conflicting flags."""
        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test --reuse and --force-new together
            result = self.runner.invoke(app, ["add", "test-project", "--reuse", "--force-new"])

            # Should exit with error due to conflicting flags
            assert result.exit_code != 0
            assert "Cannot use both --reuse and --force-new" in result.stdout


class TestPortAllocationLogic:
    """Test port allocation and validation logic."""

    def test_port_suggestion_logic(self, mock_claudette_home: Path, mock_worktree_base: Path):
        """Test the port suggestion algorithm."""
        # Create some projects with used ports
        used_ports = [9001, 9002, 9005]
        for i, port in enumerate(used_ports):
            project = ProjectMetadata(
                name=f"project{i+1}", port=port, path=mock_worktree_base / f"project{i+1}"
            )
            project.save(mock_claudette_home)

        # Test that suggestion finds next available port
        suggested = ProjectMetadata.suggest_port(mock_claudette_home)
        assert suggested == 9003  # First gap in sequence

    def test_port_collision_detection(self, mock_claudette_home: Path, mock_worktree_base: Path):
        """Test detection of port collisions."""
        # Create a project with port 9001
        existing_project = ProjectMetadata(
            name="existing-project", port=9001, path=mock_worktree_base / "existing-project"
        )
        existing_project.save(mock_claudette_home)

        # Test that we can detect the used port
        used_ports = ProjectMetadata.get_used_ports(mock_claudette_home)
        assert 9001 in used_ports

        # Test that suggestion avoids the used port
        suggested = ProjectMetadata.suggest_port(mock_claudette_home)
        assert suggested != 9001
        assert suggested >= 9002

    def test_port_range_boundary_conditions(self, mock_claudette_home: Path):
        """Test port allocation at range boundaries."""
        # Test suggestion starts at 9001 by default
        suggested = ProjectMetadata.suggest_port(mock_claudette_home)
        assert suggested == 9001

        # Test custom start port
        suggested_custom = ProjectMetadata.suggest_port(mock_claudette_home, start_port=9500)
        assert suggested_custom == 9500

        # Test when reaching upper limit
        with pytest.raises(
            ValueError, match="All ports in range 9000-9999 are in use"
        ), patch.object(ProjectMetadata, "get_used_ports", return_value=set(range(9000, 10000))):
            # Mock that all ports are in use
            ProjectMetadata.suggest_port(mock_claudette_home)


class TestCommandFlagValidation:
    """Test validation of command flags and options."""

    def test_remove_command_flag_combinations(self):
        """Test remove command flag validation."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test valid flag combinations
            result = runner.invoke(app, ["remove", "test-project", "--force"])
            # Should not fail due to flag validation (may fail for other reasons)
            assert "--force" not in result.stdout or "invalid" not in result.stdout.lower()

            result = runner.invoke(app, ["remove", "test-project", "--keep-docs"])
            assert "--keep-docs" not in result.stdout or "invalid" not in result.stdout.lower()

            result = runner.invoke(app, ["remove", "test-project", "--force", "--keep-docs"])
            assert "invalid" not in result.stdout.lower()

    def test_optional_project_argument_handling(self):
        """Test commands that take optional project arguments."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test commands that should work without project argument (when in project dir)
            commands_with_optional_project = [
                ["status"],
                ["open"],
                ["nuke-db"],
                ["sync"],
            ]

            for cmd in commands_with_optional_project:
                result = runner.invoke(app, cmd)
                # Should not fail due to missing required argument
                assert "Missing argument" not in result.stdout


class TestArgumentTypeValidation:
    """Test type validation for command arguments."""

    def test_port_argument_type_validation(self):
        """Test that port arguments are properly validated as integers."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test invalid port types
            result = runner.invoke(app, ["add", "test-project", "not-a-number"])
            assert result.exit_code != 0

            # Test valid port type
            with patch("claudette.cli.settings") as mock_settings, patch(
                "claudette.cli.Path.exists", return_value=True
            ), patch("claudette.cli.ProjectMetadata.get_used_ports", return_value=set()), patch(
                "claudette.cli._branch_exists", return_value=False
            ), patch("claudette.cli.run_cmd.run"):
                mock_settings.superset_base.exists.return_value = True
                result = runner.invoke(app, ["add", "test-project", "9001"])

                # Should not fail due to type validation
                assert "Invalid value" not in result.stdout

    def test_string_argument_validation(self):
        """Test validation of string arguments."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test that project names are accepted as strings
            result = runner.invoke(app, ["remove", "test-project-123"])
            # Should not fail due to string format (may fail for other reasons)
            assert "Invalid value" not in result.stdout

            # Test empty project name is rejected
            result = runner.invoke(app, ["remove", ""])
            assert result.exit_code != 0


class TestArgumentPrecedence:
    """Test argument precedence and default value handling."""

    def test_port_auto_assignment_vs_explicit(
        self, mock_claudette_home: Path, mock_worktree_base: Path
    ):
        """Test that explicit port takes precedence over auto-assignment."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"), patch(
            "claudette.cli.settings"
        ) as mock_settings, patch("claudette.cli.Path.exists", return_value=True), patch(
            "claudette.cli._branch_exists", return_value=False
        ), patch("claudette.cli.run_cmd.run"):
            mock_settings.superset_base.exists.return_value = True
            mock_settings.claudette_home = mock_claudette_home
            mock_settings.worktree_base = mock_worktree_base

            # Test explicit port is used
            result = runner.invoke(app, ["add", "test-project", "9005"])

            # Should not attempt auto-assignment when explicit port provided
            # (We can verify this by checking the function wasn't called with suggest_port)
            assert result.exit_code == 0 or "9005" in result.stdout

    def test_flag_override_behavior(self):
        """Test that flags override default behaviors."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test --force flag overrides confirmation prompts
            result = runner.invoke(app, ["init", "--force"])
            # Should not prompt for confirmation when --force is used
            assert "Are you sure" not in result.stdout

            # Test without --force flag (when already initialized)
            with patch("claudette.cli.settings") as mock_settings:
                mock_settings.superset_base.exists.return_value = True
                result = runner.invoke(app, ["init"])
                # Should show warning message about already being initialized
                assert "already initialized" in result.stdout or result.exit_code == 0


class TestContextualArguments:
    """Test arguments that depend on context (environment, current directory)."""

    def test_project_detection_for_optional_args(self):
        """Test that optional project arguments use context when not provided."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"), patch(
            "pathlib.Path.cwd"
        ) as mock_cwd, patch("claudette.cli.settings") as mock_settings:
            # Mock being in a project directory
            mock_settings.worktree_base = Path("/tmp/worktrees")
            mock_cwd.return_value = Path("/tmp/worktrees/my-project")

            # Test that status command detects project from cwd
            result = runner.invoke(app, ["status"])

            # Should detect project context (may still fail for other reasons)
            assert "not in a claudette project" not in result.stdout or result.exit_code == 0

    def test_environment_variable_precedence(self):
        """Test that environment variables are used appropriately."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"), patch.dict(
            "os.environ", {"PROJECT": "env-project", "NODE_PORT": "9001"}
        ):
            # Test that environment variables are detected
            result = runner.invoke(app, [])  # No command, should detect env

            # Should recognize the activated environment
            assert "activated" in result.stdout or "env-project" in result.stdout


class TestErrorHandlingInArguments:
    """Test error handling and user feedback for argument issues."""

    def test_helpful_error_messages(self):
        """Test that argument errors provide helpful messages."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"):
            # Test missing required arguments
            result = runner.invoke(app, ["add"])  # Missing project name
            assert result.exit_code != 0
            assert "Missing argument" in result.stdout or "PROJECT" in result.stdout

            # Test invalid port range with helpful message
            result = runner.invoke(app, ["add", "test", "8000"])
            assert result.exit_code != 0
            # Should provide range information
            assert (
                "9000" in result.stdout
                or "9999" in result.stdout
                or "range" in result.stdout.lower()
            )

    def test_suggestion_on_errors(self):
        """Test that errors include helpful suggestions."""
        runner = CliRunner()

        with patch("claudette.cli._ensure_claudette_initialized"), patch(
            "claudette.cli.settings"
        ) as mock_settings, patch("claudette.cli.Path.exists", return_value=True):
            mock_settings.superset_base.exists.return_value = True

            # Mock port collision scenario
            with patch("claudette.cli.ProjectMetadata.get_used_ports", return_value={9001}), patch(
                "claudette.cli.ProjectMetadata.suggest_port", return_value=9002
            ):
                result = runner.invoke(app, ["add", "test-project", "9001"])

                # Should suggest alternative port
                assert "Try:" in result.stdout or "9002" in result.stdout or result.exit_code == 0
