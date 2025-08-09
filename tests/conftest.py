"""Test fixtures and configuration for claudette tests."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest
from claudette.config import ClaudetteSettings, ProjectMetadata


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test use."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_claudette_home(temp_dir: Path) -> Path:
    """Create a mock claudette home directory structure."""
    claudette_home = temp_dir / ".claudette"
    claudette_home.mkdir()

    # Create projects directory
    (claudette_home / "projects").mkdir()

    # Create CLAUDE.local.md
    (claudette_home / "CLAUDE.local.md").write_text("# Test Claude Config")

    # Create template files
    (claudette_home / ".claude_rc_template").write_text("# Template {{PROJECT}}")

    return claudette_home


@pytest.fixture
def mock_worktree_base(temp_dir: Path) -> Path:
    """Create a mock worktree base directory."""
    worktree_base = temp_dir / "worktrees"
    worktree_base.mkdir()
    return worktree_base


@pytest.fixture
def mock_superset_base(temp_dir: Path) -> Path:
    """Create a mock Superset base directory."""
    superset_base = temp_dir / "apache-superset"
    superset_base.mkdir()

    # Create .gitignore
    (superset_base / ".gitignore").write_text("node_modules/\n.env\n")

    # Create superset-frontend directory
    (superset_base / "superset-frontend").mkdir()

    return superset_base


@pytest.fixture
def mock_settings(
    mock_claudette_home: Path,
    mock_worktree_base: Path,
    mock_superset_base: Path,
) -> ClaudetteSettings:
    """Create mock settings for testing."""
    return ClaudetteSettings(
        claudette_home=mock_claudette_home,
        worktree_base=mock_worktree_base,
        superset_base=mock_superset_base,
        superset_repo_url="https://github.com/apache/superset.git",
        python_version="3.11",
    )


@pytest.fixture
def sample_metadata(mock_worktree_base: Path) -> ProjectMetadata:
    """Create sample project metadata for testing."""
    return ProjectMetadata(
        name="test-project",
        port=9001,
        path=mock_worktree_base / "test-project",
        description="Test project description",
    )


@pytest.fixture
def sample_metadata_dict() -> dict:
    """Sample metadata as a dictionary (like what's saved to .claudette files)."""
    return {
        "name": "test-project",
        "port": "9001",
        "path": "/tmp/worktrees/test-project",
        "description": "Test project description",
    }
