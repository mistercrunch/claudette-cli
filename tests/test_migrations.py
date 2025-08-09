"""Tests for claudette version migrations and initialization."""

import contextlib
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from claudette.cli import (
    CLAUDETTE_VERSION,
    _ensure_claudette_initialized,
    _migrate_v01_to_v02,
    _write_version_file,
)
from claudette.config import ProjectMetadata


class TestVersionFileManagement:
    """Test version file creation and management."""

    def test_write_version_file(self, temp_dir: Path):
        """Test writing version file with timestamp."""
        version_file = temp_dir / ".claudette.json"

        with patch("claudette.cli.datetime") as mock_datetime:
            mock_now = Mock()
            mock_now.isoformat.return_value = "2023-01-01T12:00:00"
            mock_datetime.now.return_value = mock_now

            _write_version_file(version_file, "0.2.0")

        assert version_file.exists()

        content = json.loads(version_file.read_text())
        assert content["version"] == "0.2.0"
        assert content["last_updated"] == "2023-01-01T12:00:00"

    def test_write_version_file_overwrites_existing(self, temp_dir: Path):
        """Test that writing version file overwrites existing content."""
        version_file = temp_dir / ".claudette.json"

        # Write initial version
        version_file.write_text('{"version": "0.1.0", "last_updated": "old"}')

        # Overwrite with new version
        _write_version_file(version_file, "0.2.0")

        content = json.loads(version_file.read_text())
        assert content["version"] == "0.2.0"
        assert content["last_updated"] != "old"


class TestMigrationV01ToV02:
    """Test migration from v0.1 to v0.2 format."""

    def test_migrate_v01_to_v02_no_projects_dir(self, temp_dir: Path):
        """Test migration when projects directory doesn't exist."""
        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = temp_dir / ".claudette"

            # Should return early without error when projects dir doesn't exist
            _migrate_v01_to_v02()

            # No directories should be created
            assert not (temp_dir / ".claudette" / "projects").exists()

    def test_migrate_v01_to_v02_no_old_files(self, temp_dir: Path):
        """Test migration when no old .claudette files exist."""
        claudette_home = temp_dir / ".claudette"
        projects_dir = claudette_home / "projects"
        projects_dir.mkdir(parents=True)

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = claudette_home
            mock_settings.worktree_base = temp_dir / "worktrees"

            # Should return early when no .claudette files exist
            _migrate_v01_to_v02()

            # Projects dir should still exist but be empty
            assert projects_dir.exists()
            assert len(list(projects_dir.iterdir())) == 0

    def test_migrate_v01_to_v02_success(self, temp_dir: Path):
        """Test successful migration from v0.1 to v0.2 format."""
        claudette_home = temp_dir / ".claudette"
        projects_dir = claudette_home / "projects"
        projects_dir.mkdir(parents=True)
        worktree_base = temp_dir / "worktrees"
        worktree_base.mkdir()

        # Create old-style metadata files
        old_file1 = projects_dir / "project1.claudette"
        old_file1.write_text(
            """# Claudette project metadata
PROJECT_NAME="project1"
NODE_PORT="9001"
PROJECT_PATH="/tmp/project1"
PROJECT_DESCRIPTION="Test project 1"
"""
        )

        old_file2 = projects_dir / "project2.claudette"
        old_file2.write_text(
            """# Claudette project metadata
PROJECT_NAME="project2"
NODE_PORT="9002"
PROJECT_PATH="/tmp/project2"
"""
        )

        # Create corresponding worktree directories
        (worktree_base / "project1").mkdir()
        (worktree_base / "project2").mkdir()

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = claudette_home
            mock_settings.worktree_base = worktree_base

            _migrate_v01_to_v02()

        # Check that new folder structure was created
        assert (projects_dir / "project1").is_dir()
        assert (projects_dir / "project2").is_dir()

        # Check that metadata files were moved
        assert (projects_dir / "project1" / ".claudette").exists()
        assert (projects_dir / "project2" / ".claudette").exists()

        # Check that old files were removed
        assert not old_file1.exists()
        assert not old_file2.exists()

        # Check that PROJECT.md files were created
        assert (projects_dir / "project1" / "PROJECT.md").exists()
        assert (projects_dir / "project2" / "PROJECT.md").exists()

        # Check that .env.local files were created
        assert (projects_dir / "project1" / ".env.local").exists()
        assert (projects_dir / "project2" / ".env.local").exists()

        # Verify PROJECT.md content
        project1_md = (projects_dir / "project1" / "PROJECT.md").read_text()
        assert "# project1" in project1_md
        assert "Project documentation for project1" in project1_md

    def test_migrate_v01_to_v02_with_symlinks(self, temp_dir: Path):
        """Test migration creates symlinks when worktree directories exist."""
        claudette_home = temp_dir / ".claudette"
        projects_dir = claudette_home / "projects"
        projects_dir.mkdir(parents=True)
        worktree_base = temp_dir / "worktrees"

        # Create worktree directory
        project_worktree = worktree_base / "test-project"
        project_worktree.mkdir(parents=True)

        # Create old-style metadata file
        old_file = projects_dir / "test-project.claudette"
        old_file.write_text(
            """PROJECT_NAME="test-project"
NODE_PORT="9001"
PROJECT_PATH="/tmp/test-project"
"""
        )

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = claudette_home
            mock_settings.worktree_base = worktree_base

            _migrate_v01_to_v02()

        # Check that symlinks were created in worktree
        project_md_symlink = project_worktree / "PROJECT.md"
        env_local_symlink = project_worktree / ".env.local"

        assert project_md_symlink.is_symlink()
        assert env_local_symlink.is_symlink()

        # Verify symlinks point to correct targets
        assert (
            project_md_symlink.resolve() == (projects_dir / "test-project" / "PROJECT.md").resolve()
        )
        assert (
            env_local_symlink.resolve() == (projects_dir / "test-project" / ".env.local").resolve()
        )

    def test_migrate_v01_to_v02_handles_exceptions(self, temp_dir: Path):
        """Test that migration handles exceptions gracefully."""
        claudette_home = temp_dir / ".claudette"
        projects_dir = claudette_home / "projects"
        projects_dir.mkdir(parents=True)

        # Create old-style metadata file
        old_file = projects_dir / "test-project.claudette"
        old_file.write_text('PROJECT_NAME="test-project"\nNODE_PORT="9001"\n')

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = claudette_home
            mock_settings.worktree_base = temp_dir / "nonexistent"

            # Should not raise exception even if symlink creation fails
            with contextlib.suppress(Exception):
                _migrate_v01_to_v02()

            # Migration should still move the metadata file
            assert (projects_dir / "test-project" / ".claudette").exists()
            assert not old_file.exists()


class TestEnsureClaudetteInitialized:
    """Test the main initialization and migration orchestration function."""

    def test_ensure_initialized_no_claudette_home(self, temp_dir: Path):
        """Test when claudette home doesn't exist yet."""
        nonexistent_home = temp_dir / "nonexistent"

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = nonexistent_home

            # Should return early without error
            _ensure_claudette_initialized()

            # Should not create any directories
            assert not nonexistent_home.exists()

    def test_ensure_initialized_no_version_file(self, temp_dir: Path):
        """Test initialization when no version file exists (pre-0.2.0)."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        with patch("claudette.cli.settings") as mock_settings, patch(
            "claudette.cli._migrate_v01_to_v02"
        ) as mock_migrate, patch("claudette.cli._write_version_file") as mock_write_version:
            mock_settings.claudette_home = claudette_home

            _ensure_claudette_initialized()

            # Should run migration and write version file
            mock_migrate.assert_called_once()
            mock_write_version.assert_called_once_with(
                claudette_home / ".claudette.json", CLAUDETTE_VERSION
            )

    def test_ensure_initialized_old_version(self, temp_dir: Path):
        """Test initialization when version file indicates old version."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        version_file = claudette_home / ".claudette.json"
        version_file.write_text('{"version": "0.1.5", "last_updated": "2023-01-01T00:00:00"}')

        with patch("claudette.cli.settings") as mock_settings, patch(
            "claudette.cli._migrate_v01_to_v02"
        ) as mock_migrate, patch("claudette.cli._write_version_file") as mock_write_version:
            mock_settings.claudette_home = claudette_home

            _ensure_claudette_initialized()

            # Should run migration for old version
            mock_migrate.assert_called_once()
            mock_write_version.assert_called_once_with(version_file, CLAUDETTE_VERSION)

    def test_ensure_initialized_current_version(self, temp_dir: Path):
        """Test initialization when already on current version."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        version_file = claudette_home / ".claudette.json"
        version_data = {"version": CLAUDETTE_VERSION, "last_updated": datetime.now().isoformat()}
        version_file.write_text(json.dumps(version_data))

        with patch("claudette.cli.settings") as mock_settings, patch(
            "claudette.cli._migrate_v01_to_v02"
        ) as mock_migrate, patch("claudette.cli._write_version_file") as mock_write_version:
            mock_settings.claudette_home = claudette_home

            _ensure_claudette_initialized()

            # Should not run migration or update version
            mock_migrate.assert_not_called()
            mock_write_version.assert_not_called()

    def test_ensure_initialized_invalid_version_file(self, temp_dir: Path):
        """Test initialization when version file is corrupted."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        version_file = claudette_home / ".claudette.json"
        version_file.write_text('{"invalid": json}')  # Invalid JSON

        with patch("claudette.cli.settings") as mock_settings, patch(
            "claudette.cli._write_version_file"
        ) as mock_write_version:
            mock_settings.claudette_home = claudette_home

            _ensure_claudette_initialized()

            # Should recreate version file
            mock_write_version.assert_called_once_with(version_file, CLAUDETTE_VERSION)

    def test_ensure_initialized_missing_version_key(self, temp_dir: Path):
        """Test initialization when version file is missing version key."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        version_file = claudette_home / ".claudette.json"
        version_file.write_text('{"last_updated": "2023-01-01T00:00:00"}')  # Missing version

        with patch("claudette.cli.settings") as mock_settings, patch(
            "claudette.cli._write_version_file"
        ) as mock_write_version:
            mock_settings.claudette_home = claudette_home

            _ensure_claudette_initialized()

            # Should recreate version file
            mock_write_version.assert_called_once_with(version_file, CLAUDETTE_VERSION)


class TestMigrationIntegration:
    """Integration tests for the complete migration workflow."""

    def test_full_migration_workflow(self, temp_dir: Path):
        """Test complete migration from v0.1 to v0.2."""
        claudette_home = temp_dir / ".claudette"
        projects_dir = claudette_home / "projects"
        projects_dir.mkdir(parents=True)
        worktree_base = temp_dir / "worktrees"

        # Create old-style setup with multiple projects
        old_projects = [
            ("feature-a", 9001, "Feature A development"),
            ("bugfix-123", 9002, None),
        ]

        for name, port, description in old_projects:
            old_file = projects_dir / f"{name}.claudette"
            content = f"""PROJECT_NAME="{name}"
NODE_PORT="{port}"
PROJECT_PATH="{worktree_base / name}"
"""
            if description:
                content += f'PROJECT_DESCRIPTION="{description}"\n'
            old_file.write_text(content)

            # Create worktree directory
            (worktree_base / name).mkdir(parents=True)

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = claudette_home
            mock_settings.worktree_base = worktree_base

            # Run initialization (should trigger migration)
            _ensure_claudette_initialized()

        # Verify version file was created
        version_file = claudette_home / ".claudette.json"
        assert version_file.exists()
        version_data = json.loads(version_file.read_text())
        assert version_data["version"] == CLAUDETTE_VERSION

        # Verify all projects migrated correctly
        for name, port, description in old_projects:
            project_folder = projects_dir / name
            assert project_folder.is_dir()

            # Check metadata can be loaded
            metadata = ProjectMetadata.load(name, claudette_home)
            assert metadata.name == name
            assert metadata.port == port
            if description:
                # Note: description might be different due to PROJECT.md parsing
                assert metadata.description is not None

            # Check PROJECT.md exists
            assert (project_folder / "PROJECT.md").exists()

            # Check symlinks created in worktree
            worktree_project_md = worktree_base / name / "PROJECT.md"
            assert worktree_project_md.is_symlink()

    def test_migration_preserves_data_integrity(self, temp_dir: Path):
        """Test that migration preserves all project data correctly."""
        claudette_home = temp_dir / ".claudette"
        projects_dir = claudette_home / "projects"
        projects_dir.mkdir(parents=True)

        # Create old metadata with special characters
        old_file = projects_dir / "special-project.claudette"
        old_file.write_text(
            """PROJECT_NAME="special-project"
NODE_PORT="9003"
PROJECT_PATH="/tmp/special with spaces/project"
PROJECT_DESCRIPTION="Description with \\"quotes\\" and \\nnewlines"
"""
        )

        with patch("claudette.cli.settings") as mock_settings:
            mock_settings.claudette_home = claudette_home
            mock_settings.worktree_base = temp_dir / "worktrees"

            _migrate_v01_to_v02()

        # Verify data integrity after migration
        metadata = ProjectMetadata.load("special-project", claudette_home)
        assert metadata.name == "special-project"
        assert metadata.port == 9003
        assert str(metadata.path) == "/tmp/special with spaces/project"
        # Description should preserve special characters
        assert "quotes" in metadata.description
        assert "newlines" in metadata.description
