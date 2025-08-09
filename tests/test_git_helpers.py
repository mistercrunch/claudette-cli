"""Tests for git-related helper functions in the CLI."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

# Import the private functions we want to test
from claudette.cli import (
    _branch_exists,
    _get_branch_info,
    _handle_branch_conflict,
    _is_docker_running,
    _suggest_branch_names,
    settings,
)


class TestBranchExists:
    """Test the _branch_exists helper function."""

    @patch("claudette.cli.run_cmd.run")
    def test_branch_exists_local(self, mock_run):
        """Test detecting a local branch."""
        # Mock local branch exists
        mock_run.side_effect = [
            Mock(stdout="  feature-branch\n"),  # Local check succeeds
        ]

        result = _branch_exists("feature-branch")
        assert result is True

        # Should only call local check, not remote
        assert mock_run.call_count == 1
        mock_run.assert_called_with(
            ["git", "branch", "--list", "feature-branch"],
            cwd=settings.superset_base,
            check=False,
            capture=True,
            quiet=True,
        )

    @patch("claudette.cli.run_cmd.run")
    def test_branch_exists_remote_only(self, mock_run):
        """Test detecting a remote-only branch."""
        # Mock local branch doesn't exist, but remote does
        mock_run.side_effect = [
            Mock(stdout=""),  # Local check fails
            Mock(stdout="  origin/feature-branch\n"),  # Remote check succeeds
        ]

        result = _branch_exists("feature-branch")
        assert result is True

        # Should call both local and remote checks
        assert mock_run.call_count == 2

    @patch("claudette.cli.run_cmd.run")
    def test_branch_does_not_exist(self, mock_run):
        """Test when branch doesn't exist anywhere."""
        # Mock neither local nor remote branch exists
        mock_run.side_effect = [
            Mock(stdout=""),  # Local check fails
            Mock(stdout=""),  # Remote check fails
        ]

        result = _branch_exists("nonexistent-branch")
        assert result is False

        assert mock_run.call_count == 2

    @patch("claudette.cli.run_cmd.run")
    def test_branch_exists_exception_handling(self, mock_run):
        """Test exception handling in branch existence check."""
        # Mock exception during git call
        mock_run.side_effect = Exception("Git command failed")

        result = _branch_exists("feature-branch")
        assert result is False


class TestGetBranchInfo:
    """Test the _get_branch_info helper function."""

    @patch("claudette.cli.run_cmd.run")
    def test_get_branch_info_local_success(self, mock_run):
        """Test getting branch info from local branch."""
        mock_run.side_effect = [Mock(stdout="abc12345|Add new feature|2 days ago\n")]

        result = _get_branch_info("feature-branch")

        assert result == {
            "commit_hash": "abc12345",
            "subject": "Add new feature",
            "relative_time": "2 days ago",
        }

        mock_run.assert_called_with(
            ["git", "log", "-1", "--format=%H|%s|%ar", "feature-branch"],
            cwd=settings.superset_base,
            check=False,
            capture=True,
            quiet=True,
        )

    @patch("claudette.cli.run_cmd.run")
    def test_get_branch_info_remote_fallback(self, mock_run):
        """Test falling back to remote branch info."""
        mock_run.side_effect = [
            Mock(stdout=""),  # Local fails
            Mock(stdout="def67890|Remote feature|1 week ago\n"),  # Remote succeeds
        ]

        result = _get_branch_info("feature-branch")

        assert result == {
            "commit_hash": "def67890",
            "subject": "Remote feature",
            "relative_time": "1 week ago",
        }

        assert mock_run.call_count == 2

    @patch("claudette.cli.run_cmd.run")
    def test_get_branch_info_not_found(self, mock_run):
        """Test when branch info cannot be found."""
        mock_run.side_effect = [
            Mock(stdout=""),  # Local fails
            Mock(stdout=""),  # Remote fails
        ]

        result = _get_branch_info("nonexistent-branch")
        assert result is None

    @patch("claudette.cli.run_cmd.run")
    def test_get_branch_info_exception_handling(self, mock_run):
        """Test exception handling in branch info retrieval."""
        mock_run.side_effect = Exception("Git command failed")

        result = _get_branch_info("feature-branch")
        assert result is None


class TestSuggestBranchNames:
    """Test the _suggest_branch_names helper function."""

    @patch("claudette.cli._branch_exists")
    def test_suggest_branch_names_all_available(self, mock_branch_exists):
        """Test suggesting branch names when all suggestions are available."""
        mock_branch_exists.return_value = False  # All suggestions available

        result = _suggest_branch_names("feature")

        expected = ["feature-2", "feature-3", "feature-4", "feature-5"]
        assert result == expected

    @patch("claudette.cli._branch_exists")
    def test_suggest_branch_names_some_taken(self, mock_branch_exists):
        """Test suggesting branch names when some are already taken."""

        # Mock feature-2 and feature-4 as taken, others available
        def mock_exists(name):
            return name in ["feature-2", "feature-4"]

        mock_branch_exists.side_effect = mock_exists

        result = _suggest_branch_names("feature")

        expected = ["feature-3", "feature-5"]
        assert result == expected

    @patch("claudette.cli._branch_exists")
    def test_suggest_branch_names_all_taken(self, mock_branch_exists):
        """Test when all suggested branch names are taken."""
        mock_branch_exists.return_value = True  # All suggestions taken

        result = _suggest_branch_names("feature")

        assert result == []


class TestDockerRunning:
    """Test the _is_docker_running helper function."""

    @patch("claudette.cli.run_cmd.run")
    def test_docker_running_true(self, mock_run):
        """Test when Docker containers are running."""
        mock_run.return_value = Mock(stdout="container_id_1\ncontainer_id_2\n")

        result = _is_docker_running("test-project")
        assert result is True

        mock_run.assert_called_with(
            ["docker", "ps", "--filter", "label=com.docker.compose.project=test-project", "-q"],
            check=False,
            capture=True,
            quiet=True,
        )

    @patch("claudette.cli.run_cmd.run")
    def test_docker_not_running(self, mock_run):
        """Test when no Docker containers are running."""
        mock_run.return_value = Mock(stdout="")

        result = _is_docker_running("test-project")
        assert result is False

    @patch("claudette.cli.run_cmd.run")
    def test_docker_exception_handling(self, mock_run):
        """Test exception handling in Docker status check."""
        mock_run.side_effect = Exception("Docker command failed")

        result = _is_docker_running("test-project")
        assert result is False


class TestHandleBranchConflict:
    """Test the _handle_branch_conflict function logic (mocked interactions)."""

    def test_handle_branch_conflict_with_name_flag_success(self):
        """Test using --name flag with available name."""
        with patch("claudette.cli._branch_exists") as mock_exists:
            mock_exists.return_value = False  # New name is available

            result = _handle_branch_conflict(
                project="feature", reuse=False, force_new=False, name="feature-alt"
            )

            assert result == ("feature-alt", True)

    def test_handle_branch_conflict_with_name_flag_conflict(self):
        """Test using --name flag with conflicting name."""
        with patch("claudette.cli._branch_exists") as mock_exists:
            mock_exists.return_value = True  # New name conflicts too

            with pytest.raises(typer.Exit):
                _handle_branch_conflict(
                    project="feature", reuse=False, force_new=False, name="feature-alt"
                )

    def test_handle_branch_conflict_reuse_flag(self):
        """Test using --reuse flag."""
        result = _handle_branch_conflict(project="feature", reuse=True, force_new=False, name=None)

        assert result == ("feature", False)  # Reuse existing, don't create new

    def test_handle_branch_conflict_force_new_flag(self):
        """Test using --force-new flag."""
        with patch("claudette.cli.run_cmd.run") as mock_run, patch(
            "claudette.cli.settings"
        ) as mock_settings:
            mock_settings.worktree_base = Path("/tmp/worktrees")
            mock_settings.superset_base = Path("/tmp/superset")

            # Mock successful worktree removal and branch deletion
            mock_run.return_value = Mock()

            # Mock that worktree exists
            with patch("pathlib.Path.exists", return_value=True):
                result = _handle_branch_conflict(
                    project="feature", reuse=False, force_new=True, name=None
                )

                assert result == ("feature", True)  # Create new branch
                assert mock_run.call_count == 2  # Remove worktree + delete branch


# Integration-style tests for more complex scenarios
class TestBranchConflictIntegration:
    """Integration tests for branch conflict handling."""

    @patch("claudette.cli._branch_exists")
    def test_suggest_branch_names_integration(self, mock_branch_exists):
        """Test the full suggestion workflow."""
        # Simulate feature, feature-2, feature-3 exist, but feature-4, feature-5 don't
        existing_branches = ["feature", "feature-2", "feature-3"]
        mock_branch_exists.side_effect = lambda name: name in existing_branches

        suggestions = _suggest_branch_names("feature")

        assert "feature-4" in suggestions
        assert "feature-5" in suggestions
        assert "feature-2" not in suggestions
        assert "feature-3" not in suggestions
