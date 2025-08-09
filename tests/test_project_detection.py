"""Tests for project and path detection logic."""

import os
from pathlib import Path
from unittest.mock import patch

from claudette.config import ClaudetteSettings, ProjectMetadata


class TestProjectDetectionFromCwd:
    """Test project detection from current working directory."""

    def setup_method(self):
        """Set up test paths."""
        self.worktree_base = Path("/tmp/test-claudette/worktrees")
        self.settings = ClaudetteSettings(worktree_base=self.worktree_base)

    def test_detect_project_from_cwd_success(self):
        """Test successful project detection when in a project directory."""
        project_path = self.worktree_base / "my-feature"

        with patch("pathlib.Path.cwd", return_value=project_path):
            # Simulate the common project detection logic
            cwd = Path.cwd()
            is_in_project = (
                len(cwd.parts) >= 2 and cwd.parts[-2] == self.settings.worktree_base.name
            )
            project_name = cwd.name if is_in_project else None

        assert is_in_project is True
        assert project_name == "my-feature"

    def test_detect_project_from_cwd_not_in_project(self):
        """Test project detection when not in a project directory."""
        random_path = Path("/home/user/some-other-directory")

        with patch("pathlib.Path.cwd", return_value=random_path):
            cwd = Path.cwd()
            is_in_project = (
                len(cwd.parts) >= 2 and cwd.parts[-2] == self.settings.worktree_base.name
            )
            project_name = cwd.name if is_in_project else None

        assert is_in_project is False
        assert project_name is None

    def test_detect_project_from_cwd_in_worktree_base(self):
        """Test when in the worktree base directory itself."""
        with patch("pathlib.Path.cwd", return_value=self.worktree_base):
            cwd = Path.cwd()
            is_in_project = (
                len(cwd.parts) >= 2 and cwd.parts[-2] == self.settings.worktree_base.name
            )
            project_name = cwd.name if is_in_project else None

        assert is_in_project is False
        assert project_name is None

    def test_detect_project_from_cwd_nested_path(self):
        """Test project detection from nested paths within project."""
        nested_path = self.worktree_base / "my-feature" / "superset-frontend" / "src"

        with patch("pathlib.Path.cwd", return_value=nested_path):
            # This simulates the actual detection logic which only checks direct children
            cwd = Path.cwd()

            # Walk up to find the project directory
            current = cwd
            project_name = None
            while current.parent != current:  # Not at filesystem root
                if (
                    len(current.parts) >= 2
                    and current.parts[-2] == self.settings.worktree_base.name
                ):
                    project_name = current.name
                    break
                current = current.parent

        assert project_name == "my-feature"


class TestProjectDetectionFromEnvironment:
    """Test project detection from environment variables."""

    def test_detect_project_from_env_vars_success(self):
        """Test project detection when PROJECT and NODE_PORT are set."""
        with patch.dict(os.environ, {"PROJECT": "test-project", "NODE_PORT": "9001"}):
            project_name = os.environ.get("PROJECT")
            node_port = os.environ.get("NODE_PORT")

            has_project_env = project_name and node_port

        assert has_project_env is True
        assert project_name == "test-project"
        assert node_port == "9001"

    def test_detect_project_from_env_vars_partial(self):
        """Test when only some environment variables are set."""
        with patch.dict(os.environ, {"PROJECT": "test-project"}, clear=True):
            project_name = os.environ.get("PROJECT")
            node_port = os.environ.get("NODE_PORT")

            has_project_env = project_name and node_port

        assert has_project_env is False
        assert project_name == "test-project"
        assert node_port is None

    def test_detect_project_from_env_vars_none(self):
        """Test when no environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            project_name = os.environ.get("PROJECT")
            node_port = os.environ.get("NODE_PORT")

            has_project_env = project_name and node_port

        assert has_project_env is False
        assert project_name is None
        assert node_port is None


class TestProjectMetadataPathResolution:
    """Test path resolution in ProjectMetadata."""

    def test_project_folder_path_resolution(self, mock_claudette_home: Path):
        """Test project folder path generation."""
        metadata = ProjectMetadata(
            name="test-project", port=9001, path=Path("/tmp/worktrees/test-project")
        )

        folder = metadata.project_folder(mock_claudette_home)
        expected = mock_claudette_home / "projects" / "test-project"
        assert folder == expected

    def test_metadata_file_path_resolution(self, mock_claudette_home: Path):
        """Test metadata file path generation."""
        metadata = ProjectMetadata(
            name="test-project", port=9001, path=Path("/tmp/worktrees/test-project")
        )

        metadata_file = metadata.metadata_file(mock_claudette_home)
        expected = mock_claudette_home / "projects" / "test-project" / ".claudette"
        assert metadata_file == expected

    def test_load_from_project_dir(self, mock_claudette_home: Path, mock_worktree_base: Path):
        """Test loading metadata from project directory."""
        # Create a project with metadata
        project_name = "test-project"
        project_path = mock_worktree_base / project_name
        project_path.mkdir(parents=True)

        metadata = ProjectMetadata(
            name=project_name, port=9001, path=project_path, description="Test project"
        )
        metadata.save(mock_claudette_home)

        # Test loading from project directory
        loaded_metadata = ProjectMetadata.load_from_project_dir(project_path, mock_claudette_home)

        assert loaded_metadata.name == project_name
        assert loaded_metadata.port == 9001
        assert loaded_metadata.path == project_path
        assert loaded_metadata.description == "Test project"


class TestClaudetteSettingsPathResolution:
    """Test path resolution in ClaudetteSettings."""

    def test_default_paths_from_home(self, temp_dir: Path):
        """Test that default paths are set correctly from claudette_home."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        settings = ClaudetteSettings(claudette_home=claudette_home)

        assert settings.worktree_base == claudette_home / "worktrees"
        assert settings.superset_base == claudette_home / ".superset"

    def test_explicit_paths_override_defaults(self, temp_dir: Path):
        """Test that explicitly set paths override defaults."""
        claudette_home = temp_dir / ".claudette"
        custom_worktree = temp_dir / "custom-worktrees"
        custom_superset = temp_dir / "custom-superset"

        settings = ClaudetteSettings(
            claudette_home=claudette_home,
            worktree_base=custom_worktree,
            superset_base=custom_superset,
        )

        assert settings.worktree_base == custom_worktree
        assert settings.superset_base == custom_superset

    def test_auto_discovery_claude_files(self, temp_dir: Path):
        """Test auto-discovery of Claude configuration files."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        # Create the files that should be auto-discovered
        claude_local_md = claudette_home / "CLAUDE.local.md"
        claude_local_md.write_text("# Claude Config")

        claude_rc_template = claudette_home / ".claude_rc_template"
        claude_rc_template.write_text("# Template")

        settings = ClaudetteSettings(claudette_home=claudette_home)

        assert settings.claude_local_md == claude_local_md
        assert settings.claude_rc_template == claude_rc_template

    def test_no_auto_discovery_when_files_missing(self, temp_dir: Path):
        """Test that auto-discovery doesn't set paths when files don't exist."""
        claudette_home = temp_dir / ".claudette"
        claudette_home.mkdir()

        settings = ClaudetteSettings(claudette_home=claudette_home)

        assert settings.claude_local_md is None
        assert settings.claude_rc_template is None


class TestProjectDetectionHelpers:
    """Test utility functions for project detection."""

    def create_project_detection_helper(self, settings: ClaudetteSettings):
        """Helper function that mimics the project detection logic used in CLI."""

        def detect_current_project(cwd: Path = None) -> tuple[bool, str | None]:
            """Detect if we're in a project directory and return project name."""
            if cwd is None:
                cwd = Path.cwd()

            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                return True, cwd.name
            return False, None

        return detect_current_project

    def test_project_detection_helper_success(self):
        """Test the project detection helper when in a project."""
        settings = ClaudetteSettings(worktree_base=Path("/tmp/worktrees"))
        detector = self.create_project_detection_helper(settings)

        test_path = Path("/tmp/worktrees/my-feature")
        is_project, project_name = detector(test_path)

        assert is_project is True
        assert project_name == "my-feature"

    def test_project_detection_helper_failure(self):
        """Test the project detection helper when not in a project."""
        settings = ClaudetteSettings(worktree_base=Path("/tmp/worktrees"))
        detector = self.create_project_detection_helper(settings)

        test_path = Path("/home/user/other-directory")
        is_project, project_name = detector(test_path)

        assert is_project is False
        assert project_name is None

    def test_project_detection_edge_cases(self):
        """Test edge cases in project detection."""
        settings = ClaudetteSettings(worktree_base=Path("/tmp/worktrees"))
        detector = self.create_project_detection_helper(settings)

        # Test filesystem root
        is_project, project_name = detector(Path("/"))
        assert is_project is False
        assert project_name is None

        # Test single-level path
        is_project, project_name = detector(Path("/tmp"))
        assert is_project is False
        assert project_name is None

        # Test exact worktree base path
        is_project, project_name = detector(Path("/tmp/worktrees"))
        assert is_project is False
        assert project_name is None
