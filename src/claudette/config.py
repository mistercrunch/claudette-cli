"""Configuration management for claudette."""

from pathlib import Path
from typing import Optional, Set

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProjectMetadata(BaseModel):
    """Metadata for a claudette project."""

    name: str
    port: int = Field(ge=9000, le=9999)
    path: Path

    def metadata_file(self, claudette_home: Path) -> Path:
        """Path to the .claudette metadata file."""
        # Store metadata outside the project directory to avoid committing to git
        return claudette_home / "projects" / f"{self.name}.claudette"

    def save(self, claudette_home: Path) -> None:
        """Save metadata to .claudette file."""
        metadata_file = self.metadata_file(claudette_home)
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Claudette project metadata
PROJECT_NAME="{self.name}"
NODE_PORT="{self.port}"
PROJECT_PATH="{self.path}"
"""
        metadata_file.write_text(content)

    @classmethod
    def load(cls, project_name: str, claudette_home: Path) -> "ProjectMetadata":
        """Load metadata from .claudette file."""
        metadata_file = claudette_home / "projects" / f"{project_name}.claudette"
        if not metadata_file.exists():
            raise FileNotFoundError(f"No .claudette file found for project {project_name}")

        # Parse the shell-style file
        metadata = {}
        for line in metadata_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                metadata[key.strip()] = value

        return cls(
            name=metadata["PROJECT_NAME"],
            port=int(metadata["NODE_PORT"]),
            path=Path(metadata["PROJECT_PATH"]),
        )

    @classmethod
    def load_from_project_dir(cls, project_path: Path, claudette_home: Path) -> "ProjectMetadata":
        """Load metadata from project directory name."""
        project_name = project_path.name
        return cls.load(project_name, claudette_home)

    @classmethod
    def get_used_ports(cls, claudette_home: Path) -> Set[int]:
        """Get all ports currently in use by existing projects."""
        used_ports = set()
        metadata_dir = claudette_home / "projects"
        if not metadata_dir.exists():
            return used_ports

        for metadata_file in metadata_dir.glob("*.claudette"):
            project_name = metadata_file.stem
            try:
                metadata = cls.load(project_name, claudette_home)
                used_ports.add(metadata.port)
            except Exception:
                pass  # Skip invalid metadata files
        return used_ports

    @classmethod
    def suggest_port(cls, claudette_home: Path, start_port: int = 9001) -> int:
        """Suggest next available port starting from start_port."""
        used_ports = cls.get_used_ports(claudette_home)

        port = start_port
        while port <= 9999:
            if port not in used_ports:
                return port
            port += 1

        # If all ports 9001-9999 are taken, start from 9000
        for port in range(9000, 9001):
            if port not in used_ports:
                return port

        raise ValueError("All ports in range 9000-9999 are in use!")


class ClaudetteSettings(BaseSettings):
    """Global settings for claudette."""

    claudette_home: Path = Path.home() / ".claudette"
    worktree_base: Optional[Path] = None
    superset_base: Optional[Path] = None
    default_branch: str = "master"
    python_version: str = "python3.11"
    superset_repo_url: str = "git@github.com:apache/superset.git"

    # Optional paths
    claude_local_md: Optional[Path] = None
    claude_rc_template: Optional[Path] = None

    model_config = {
        "env_prefix": "CLAUDETTE_",
        "env_file": ".env",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set defaults based on claudette_home if not explicitly set
        if not self.worktree_base:
            self.worktree_base = self.claudette_home / "worktrees"
        if not self.superset_base:
            self.superset_base = self.claudette_home / ".superset"

        # Auto-discover files from claudette home if not set
        if not self.claude_local_md and (self.claudette_home / "CLAUDE.local.md").exists():
            self.claude_local_md = self.claudette_home / "CLAUDE.local.md"
        if not self.claude_rc_template and (self.claudette_home / ".claude_rc_template").exists():
            self.claude_rc_template = self.claudette_home / ".claude_rc_template"
