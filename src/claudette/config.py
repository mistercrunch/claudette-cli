"""Configuration management for claudette."""

from pathlib import Path
from typing import List, Optional, Set, Tuple

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Project files that are managed by claudette and symlinked to worktrees
PROJECT_MANAGED_FILES = [
    "PROJECT.md",  # Branch-specific documentation
    ".env.local",  # Local environment variables (future)
]

# Files that stay in the project folder only (not symlinked)
PROJECT_METADATA_FILES = [
    ".claudette",  # Project metadata
]


class ProjectMetadata(BaseModel):
    """Metadata for a claudette project."""

    name: str
    port: int = Field(ge=9000, le=9999)
    path: Path
    description: Optional[str] = None  # From PROJECT.md summary
    frozen: bool = False  # Whether project dependencies are removed to save space
    pr_number: Optional[int] = None  # Associated GitHub PR number

    def project_folder(self, claudette_home: Path) -> Path:
        """Path to the project's folder in ~/.claudette/projects/."""
        return claudette_home / "projects" / self.name

    def metadata_file(self, claudette_home: Path) -> Path:
        """Path to the .claudette metadata file."""
        # Now stored inside the project folder
        return self.project_folder(claudette_home) / ".claudette"

    def save(self, claudette_home: Path) -> None:
        """Save metadata to .claudette file."""
        metadata_file = self.metadata_file(claudette_home)
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Claudette project metadata
PROJECT_NAME="{self.name}"
NODE_PORT="{self.port}"
PROJECT_PATH="{self.path}"
PROJECT_FROZEN="{str(self.frozen).lower()}"
"""
        if self.description:
            # Escape quotes and newlines for shell format
            escaped_desc = self.description.replace('"', '\\"').replace("\n", "\\n")
            content += f'PROJECT_DESCRIPTION="{escaped_desc}"\n'

        if self.pr_number is not None:
            content += f'PROJECT_PR="{self.pr_number}"\n'
        metadata_file.write_text(content)

    @classmethod
    def load(cls, project_name: str, claudette_home: Path) -> "ProjectMetadata":
        """Load metadata from .claudette file."""
        # Try new location first (in project folder)
        project_folder = claudette_home / "projects" / project_name
        metadata_file = project_folder / ".claudette"

        # Fall back to old location for backward compatibility
        if not metadata_file.exists():
            old_metadata_file = claudette_home / "projects" / f"{project_name}.claudette"
            if old_metadata_file.exists():
                metadata_file = old_metadata_file
            else:
                raise FileNotFoundError(f"No .claudette file found for project {project_name}")

        # Parse the shell-style file
        metadata = {}
        for line in metadata_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip().strip('"').strip("'")
                metadata[key.strip()] = value

        # Parse frozen state - handle as boolean
        frozen_str = metadata.get("PROJECT_FROZEN", "false").lower()
        frozen = frozen_str in ("true", "1", "yes", "on")

        # Parse PR number if present
        pr_number = None
        if "PROJECT_PR" in metadata:
            try:
                pr_number = int(metadata["PROJECT_PR"])
            except (ValueError, TypeError):
                pr_number = None

        return cls(
            name=metadata["PROJECT_NAME"],
            port=int(metadata["NODE_PORT"]),
            path=Path(metadata["PROJECT_PATH"]),
            description=metadata.get("PROJECT_DESCRIPTION"),
            frozen=frozen,
            pr_number=pr_number,
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
        projects_dir = claudette_home / "projects"
        if not projects_dir.exists():
            return used_ports

        # Check both old-style (*.claudette) and new-style (folders with .claudette)
        # Old style
        for metadata_file in projects_dir.glob("*.claudette"):
            project_name = metadata_file.stem
            try:
                metadata = cls.load(project_name, claudette_home)
                used_ports.add(metadata.port)
            except Exception:
                pass  # Skip invalid metadata files

        # New style
        for project_folder in projects_dir.iterdir():
            if project_folder.is_dir():
                metadata_file = project_folder / ".claudette"
                if metadata_file.exists():
                    try:
                        metadata = cls.load(project_folder.name, claudette_home)
                        used_ports.add(metadata.port)
                    except Exception:
                        pass

        return used_ports

    @classmethod
    def get_managed_files(cls) -> List[Tuple[str, bool]]:
        """Get list of managed files and whether they should be symlinked.

        Returns:
            List of (filename, should_symlink) tuples
        """
        files = []
        # Add symlinked files
        for filename in PROJECT_MANAGED_FILES:
            files.append((filename, True))
        # Add metadata files (not symlinked)
        for filename in PROJECT_METADATA_FILES:
            files.append((filename, False))
        return files

    def update_from_project_md(self) -> bool:
        """Update metadata description from PROJECT.md title if it exists.

        Returns True if PROJECT.md was found and parsed.
        Uses the first non-empty line as the description, stripping any leading # symbols.
        """
        project_md = self.path / "PROJECT.md"
        # Check if file exists (works for both regular files and symlinks)
        if not project_md.exists():
            return False

        content = project_md.read_text()
        lines = content.split("\n")

        # Find the first non-empty line and use it as description
        for line in lines:
            stripped = line.strip()
            if stripped:
                # Remove any leading # symbols and spaces
                while stripped and stripped[0] == "#":
                    stripped = stripped[1:]
                stripped = stripped.strip()

                if stripped:  # Make sure we still have content after removing #
                    self.description = stripped
                    return True

        return False

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
    archive_path: Optional[Path] = None
    default_branch: str = "master"
    python_version: str = "python3.11"
    superset_repo_url: str = "git@github.com:apache/superset.git"

    # Optional paths
    claude_local_md: Optional[Path] = None
    claude_rc_template: Optional[Path] = None

    model_config = {
        "env_prefix": "CLAUDETTE_",
        "env_file": ".env",
        "extra": "ignore",  # Ignore extra environment variables
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set defaults based on claudette_home if not explicitly set
        if not self.worktree_base:
            self.worktree_base = self.claudette_home / "worktrees"
        if not self.superset_base:
            self.superset_base = self.claudette_home / ".superset"
        if not self.archive_path:
            self.archive_path = self.claudette_home / "archive"

        # Auto-discover files from claudette home if not set
        if not self.claude_local_md and (self.claudette_home / "CLAUDE.local.md").exists():
            self.claude_local_md = self.claudette_home / "CLAUDE.local.md"
        if not self.claude_rc_template and (self.claudette_home / ".claude_rc_template").exists():
            self.claude_rc_template = self.claudette_home / ".claude_rc_template"
