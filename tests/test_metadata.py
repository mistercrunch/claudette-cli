"""Tests for ProjectMetadata class and related functionality."""

from pathlib import Path

import pytest
from claudette.config import ProjectMetadata
from pydantic import ValidationError


class TestProjectMetadata:
    """Test the ProjectMetadata class."""

    def test_basic_creation(self, mock_worktree_base: Path):
        """Test basic ProjectMetadata creation."""
        metadata = ProjectMetadata(
            name="test-project", port=9001, path=mock_worktree_base / "test-project"
        )
        assert metadata.name == "test-project"
        assert metadata.port == 9001
        assert metadata.path == mock_worktree_base / "test-project"
        assert metadata.description is None

    def test_port_validation(self, mock_worktree_base: Path):
        """Test port number validation."""
        # Valid ports should work
        metadata = ProjectMetadata(
            name="test-project",
            port=9000,  # min
            path=mock_worktree_base / "test-project",
        )
        assert metadata.port == 9000

        metadata = ProjectMetadata(
            name="test-project",
            port=9999,  # max
            path=mock_worktree_base / "test-project",
        )
        assert metadata.port == 9999

        # Invalid ports should raise ValidationError
        with pytest.raises(ValidationError):
            ProjectMetadata(
                name="test-project",
                port=8999,  # too low
                path=mock_worktree_base / "test-project",
            )

        with pytest.raises(ValidationError):
            ProjectMetadata(
                name="test-project",
                port=10000,  # too high
                path=mock_worktree_base / "test-project",
            )

    def test_save_and_load(self, sample_metadata: ProjectMetadata, mock_claudette_home: Path):
        """Test saving and loading metadata."""
        # Save metadata
        sample_metadata.save(mock_claudette_home)

        # Check file was created
        metadata_file = sample_metadata.metadata_file(mock_claudette_home)
        assert metadata_file.exists()

        # Check file content
        content = metadata_file.read_text()
        assert 'PROJECT_NAME="test-project"' in content
        assert 'NODE_PORT="9001"' in content
        assert 'PROJECT_DESCRIPTION="Test project description"' in content

        # Load metadata and verify it matches
        loaded_metadata = ProjectMetadata.load("test-project", mock_claudette_home)
        assert loaded_metadata.name == sample_metadata.name
        assert loaded_metadata.port == sample_metadata.port
        assert loaded_metadata.path == sample_metadata.path
        assert loaded_metadata.description == sample_metadata.description

    def test_save_without_description(self, mock_claudette_home: Path, mock_worktree_base: Path):
        """Test saving metadata without description."""
        metadata = ProjectMetadata(
            name="no-desc-project", port=9002, path=mock_worktree_base / "no-desc-project"
        )

        metadata.save(mock_claudette_home)
        content = metadata.metadata_file(mock_claudette_home).read_text()

        assert 'PROJECT_NAME="no-desc-project"' in content
        assert 'NODE_PORT="9002"' in content
        assert "PROJECT_DESCRIPTION" not in content

    def test_load_nonexistent_project(self, mock_claudette_home: Path):
        """Test loading a project that doesn't exist."""
        with pytest.raises(FileNotFoundError, match="No .claudette file found"):
            ProjectMetadata.load("nonexistent-project", mock_claudette_home)

    def test_project_folder_path(self, sample_metadata: ProjectMetadata, mock_claudette_home: Path):
        """Test project folder path generation."""
        folder = sample_metadata.project_folder(mock_claudette_home)
        expected = mock_claudette_home / "projects" / "test-project"
        assert folder == expected

    def test_metadata_file_path(self, sample_metadata: ProjectMetadata, mock_claudette_home: Path):
        """Test metadata file path generation."""
        metadata_file = sample_metadata.metadata_file(mock_claudette_home)
        expected = mock_claudette_home / "projects" / "test-project" / ".claudette"
        assert metadata_file == expected


class TestProjectMetadataPortManagement:
    """Test port-related functionality."""

    def test_get_used_ports_empty(self, mock_claudette_home: Path):
        """Test getting used ports when no projects exist."""
        used_ports = ProjectMetadata.get_used_ports(mock_claudette_home)
        assert used_ports == set()

    def test_get_used_ports_with_projects(
        self, mock_claudette_home: Path, mock_worktree_base: Path
    ):
        """Test getting used ports with multiple projects."""
        # Create some test projects
        project1 = ProjectMetadata(name="project1", port=9001, path=mock_worktree_base / "project1")
        project1.save(mock_claudette_home)

        project2 = ProjectMetadata(name="project2", port=9005, path=mock_worktree_base / "project2")
        project2.save(mock_claudette_home)

        used_ports = ProjectMetadata.get_used_ports(mock_claudette_home)
        assert used_ports == {9001, 9005}

    def test_suggest_port_no_conflicts(self, mock_claudette_home: Path):
        """Test port suggestion when no ports are in use."""
        suggested = ProjectMetadata.suggest_port(mock_claudette_home)
        assert suggested == 9001  # Default start port

    def test_suggest_port_with_conflicts(self, mock_claudette_home: Path, mock_worktree_base: Path):
        """Test port suggestion when some ports are in use."""
        # Create projects using ports 9001 and 9002
        project1 = ProjectMetadata(name="project1", port=9001, path=mock_worktree_base / "project1")
        project1.save(mock_claudette_home)

        project2 = ProjectMetadata(name="project2", port=9002, path=mock_worktree_base / "project2")
        project2.save(mock_claudette_home)

        suggested = ProjectMetadata.suggest_port(mock_claudette_home)
        assert suggested == 9003  # Next available

    def test_suggest_port_custom_start(self, mock_claudette_home: Path):
        """Test port suggestion with custom start port."""
        suggested = ProjectMetadata.suggest_port(mock_claudette_home, start_port=9500)
        assert suggested == 9500


class TestProjectMetadataDescriptionExtraction:
    """Test PROJECT.md description extraction functionality."""

    def test_update_from_project_md_success(self, sample_metadata: ProjectMetadata):
        """Test successful description extraction from PROJECT.md."""
        # Create a PROJECT.md file
        project_md = sample_metadata.path / "PROJECT.md"
        project_md.parent.mkdir(parents=True, exist_ok=True)
        project_md.write_text(
            """# Test Project

This is a test project for testing description extraction.
It has multiple lines in the description.

## Overview
This should not be included in the description.
"""
        )

        result = sample_metadata.update_from_project_md()
        assert result is True
        assert (
            sample_metadata.description
            == "This is a test project for testing description extraction. It has multiple lines in the description."
        )

    def test_update_from_project_md_no_file(self, sample_metadata: ProjectMetadata):
        """Test description extraction when PROJECT.md doesn't exist."""
        result = sample_metadata.update_from_project_md()
        assert result is False
        # Description should remain unchanged
        assert sample_metadata.description == "Test project description"

    def test_update_from_project_md_empty_content(self, sample_metadata: ProjectMetadata):
        """Test description extraction with empty content after title."""
        project_md = sample_metadata.path / "PROJECT.md"
        project_md.parent.mkdir(parents=True, exist_ok=True)
        project_md.write_text(
            """# Test Project


## Overview
Only section headers, no description.
"""
        )

        result = sample_metadata.update_from_project_md()
        assert result is False
        # Description should remain unchanged
        assert sample_metadata.description == "Test project description"

    def test_update_from_project_md_only_title(self, sample_metadata: ProjectMetadata):
        """Test description extraction with only a title."""
        project_md = sample_metadata.path / "PROJECT.md"
        project_md.parent.mkdir(parents=True, exist_ok=True)
        project_md.write_text("# Test Project\n")

        result = sample_metadata.update_from_project_md()
        assert result is False

    def test_update_from_project_md_complex_content(self, sample_metadata: ProjectMetadata):
        """Test description extraction from complex PROJECT.md."""
        project_md = sample_metadata.path / "PROJECT.md"
        project_md.parent.mkdir(parents=True, exist_ok=True)
        project_md.write_text(
            """# My Awesome Feature

This feature adds amazing functionality to the system.
It includes multiple components and handles various edge cases.

Here's more detail that should be included.

## Implementation Notes
This should not be included.

## Goals
Neither should this.
"""
        )

        result = sample_metadata.update_from_project_md()
        assert result is True
        expected = "This feature adds amazing functionality to the system. It includes multiple components and handles various edge cases. Here's more detail that should be included."
        assert sample_metadata.description == expected


class TestProjectMetadataBackwardCompatibility:
    """Test backward compatibility with old file formats."""

    def test_load_from_old_format(self, mock_claudette_home: Path):
        """Test loading metadata from old .claudette format."""
        # Create old-style metadata file
        projects_dir = mock_claudette_home / "projects"
        old_file = projects_dir / "old-project.claudette"
        old_file.write_text(
            """# Claudette project metadata
PROJECT_NAME="old-project"
NODE_PORT="9003"
PROJECT_PATH="/tmp/test/old-project"
PROJECT_DESCRIPTION="Old format project"
"""
        )

        # Should be able to load it
        metadata = ProjectMetadata.load("old-project", mock_claudette_home)
        assert metadata.name == "old-project"
        assert metadata.port == 9003
        assert str(metadata.path) == "/tmp/test/old-project"
        assert metadata.description == "Old format project"

    def test_get_used_ports_includes_old_format(self, mock_claudette_home: Path):
        """Test that get_used_ports includes old format files."""
        # Create both old and new format files
        projects_dir = mock_claudette_home / "projects"

        # Old format
        old_file = projects_dir / "old-project.claudette"
        old_file.write_text(
            """PROJECT_NAME="old-project"
NODE_PORT="9003"
PROJECT_PATH="/tmp/old-project"
"""
        )

        # New format
        new_project_dir = projects_dir / "new-project"
        new_project_dir.mkdir()
        (new_project_dir / ".claudette").write_text(
            """PROJECT_NAME="new-project"
NODE_PORT="9004"
PROJECT_PATH="/tmp/new-project"
"""
        )

        used_ports = ProjectMetadata.get_used_ports(mock_claudette_home)
        assert used_ports == {9003, 9004}
