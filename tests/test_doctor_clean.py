"""Tests for doctor and clean commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess

import pytest
from claudette.cli import app
from claudette.config import ProjectMetadata
from typer.testing import CliRunner


class TestDoctorCommand:
    """Test the doctor command."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_doctor_healthy_environment(self):
        """Test doctor command with healthy environment."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"), \
             patch("subprocess.run") as mock_run:
            
            # Mock healthy environment
            mock_settings.claudette_home.exists.return_value = True
            mock_settings.superset_base.exists.return_value = True
            mock_settings.superset_base.__truediv__.return_value.exists.return_value = True
            mock_settings.worktree_base.exists.return_value = True
            
            # Mock successful command outputs
            mock_run.return_value = MagicMock(returncode=0, stdout="v20.0.0")
            
            # Mock no projects
            mock_projects_dir = MagicMock()
            mock_projects_dir.exists.return_value = False
            mock_settings.claudette_home.__truediv__.return_value = mock_projects_dir
            
            result = self.runner.invoke(app, ["doctor"])
            
            assert result.exit_code == 0
            assert "All checks passed" in result.stdout

    def test_doctor_detects_missing_initialization(self):
        """Test doctor command detects missing initialization."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"):
            
            # Mock missing initialization
            mock_settings.claudette_home.exists.return_value = False
            
            result = self.runner.invoke(app, ["doctor"])
            
            assert result.exit_code == 0
            assert "Claudette not initialized" in result.stdout or "Found" in result.stdout

    def test_doctor_detects_orphaned_projects(self):
        """Test doctor command detects orphaned projects."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"), \
             patch("subprocess.run") as mock_run:
            
            # Mock healthy base environment
            mock_settings.claudette_home.exists.return_value = True
            mock_settings.superset_base.exists.return_value = True
            mock_settings.superset_base.__truediv__.return_value.exists.return_value = True
            mock_settings.worktree_base.exists.return_value = True
            mock_run.return_value = MagicMock(returncode=0, stdout="v20.0.0")
            
            # Mock orphaned project
            mock_metadata_file = MagicMock()
            mock_metadata_file.stem = "orphaned-project"
            
            mock_projects_dir = MagicMock()
            mock_projects_dir.exists.return_value = True
            mock_projects_dir.glob.return_value = [mock_metadata_file]
            
            mock_settings.claudette_home.__truediv__.return_value = mock_projects_dir
            
            # Mock project path that doesn't exist
            mock_project_path = MagicMock()
            mock_project_path.exists.return_value = False
            mock_settings.worktree_base.__truediv__.return_value = mock_project_path
            
            # Mock metadata read
            with patch("claudette.cli.ProjectMetadata.from_file") as mock_from_file:
                mock_from_file.return_value = MagicMock(frozen=False, port=9001)
                
                result = self.runner.invoke(app, ["doctor"])
                
                assert result.exit_code == 0
                assert "Orphaned project" in result.stdout
                assert "claudette clean" in result.stdout


class TestCleanCommand:
    """Test the clean command."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_clean_no_projects(self):
        """Test clean command with no projects."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"):
            
            # Mock no projects
            mock_projects_dir = MagicMock()
            mock_projects_dir.exists.return_value = True
            mock_projects_dir.glob.return_value = []
            mock_settings.claudette_home.__truediv__.return_value = mock_projects_dir
            
            result = self.runner.invoke(app, ["clean", "--force"])
            
            assert result.exit_code == 0
            assert "No projects found" in result.stdout

    def test_clean_dry_run(self):
        """Test clean command with --dry-run flag."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"):
            
            # Mock orphaned project
            mock_metadata_file = MagicMock()
            mock_metadata_file.stem = "orphaned-project"
            mock_metadata_file.__str__.return_value = "/path/to/orphaned.claudette"
            
            mock_projects_dir = MagicMock()
            mock_projects_dir.exists.return_value = True
            mock_projects_dir.glob.return_value = [mock_metadata_file]
            mock_settings.claudette_home.__truediv__.return_value = mock_projects_dir
            
            # Mock project path that doesn't exist
            mock_project_path = MagicMock()
            mock_project_path.exists.return_value = False
            mock_settings.worktree_base.__truediv__.return_value = mock_project_path
            
            # Mock metadata read
            with patch("claudette.cli.ProjectMetadata.from_file") as mock_from_file:
                mock_from_file.return_value = MagicMock()
                
                result = self.runner.invoke(app, ["clean", "--dry-run"])
                
                assert result.exit_code == 0
                assert "Dry run mode" in result.stdout
                assert "Would remove" in result.stdout

    def test_clean_removes_orphaned_projects(self):
        """Test clean command removes orphaned projects."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"), \
             patch("subprocess.run") as mock_run:
            
            # Mock orphaned project
            mock_metadata_file = MagicMock()
            mock_metadata_file.stem = "orphaned-project"
            mock_metadata_file.unlink = MagicMock()
            
            mock_projects_dir = MagicMock()
            mock_projects_dir.exists.return_value = True
            mock_projects_dir.glob.return_value = [mock_metadata_file]
            mock_settings.claudette_home.__truediv__.return_value = mock_projects_dir
            
            # Mock project path that doesn't exist
            mock_project_path = MagicMock()
            mock_project_path.exists.return_value = False
            mock_settings.worktree_base.__truediv__.return_value = mock_project_path
            
            # Mock worktree list
            mock_settings.superset_base = Path("/mock/superset")
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            # Mock metadata read
            with patch("claudette.cli.ProjectMetadata.from_file") as mock_from_file:
                mock_from_file.return_value = MagicMock()
                
                result = self.runner.invoke(app, ["clean", "--force"])
                
                assert result.exit_code == 0
                assert "Successfully cleaned" in result.stdout
                mock_metadata_file.unlink.assert_called_once()

    def test_clean_with_confirmation_prompt(self):
        """Test clean command with confirmation prompt."""
        with patch("claudette.cli.settings") as mock_settings, \
             patch("claudette.cli._ensure_claudette_initialized"), \
             patch("subprocess.run") as mock_run, \
             patch("typer.confirm", return_value=True) as mock_confirm:
            
            # Mock orphaned project
            mock_metadata_file = MagicMock()
            mock_metadata_file.stem = "orphaned-project"
            mock_metadata_file.unlink = MagicMock()
            
            mock_projects_dir = MagicMock()
            mock_projects_dir.exists.return_value = True
            mock_projects_dir.glob.return_value = [mock_metadata_file]
            mock_settings.claudette_home.__truediv__.return_value = mock_projects_dir
            
            # Mock project path that doesn't exist
            mock_project_path = MagicMock()
            mock_project_path.exists.return_value = False
            mock_settings.worktree_base.__truediv__.return_value = mock_project_path
            
            # Mock worktree list
            mock_settings.superset_base = Path("/mock/superset")
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            # Mock metadata read
            with patch("claudette.cli.ProjectMetadata.from_file") as mock_from_file:
                mock_from_file.return_value = MagicMock()
                
                result = self.runner.invoke(app, ["clean"])
                
                assert result.exit_code == 0
                mock_confirm.assert_called_once()
                mock_metadata_file.unlink.assert_called_once()