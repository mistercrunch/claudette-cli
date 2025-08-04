"""Configuration management for claudette."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProjectMetadata(BaseModel):
    """Metadata for a claudette project."""
    
    name: str
    port: int = Field(ge=9000, le=9999)
    path: Path
    
    @property
    def metadata_file(self) -> Path:
        """Path to the .claudette metadata file."""
        return self.path / ".claudette"
    
    def save(self) -> None:
        """Save metadata to .claudette file."""
        content = f'''# Claudette project metadata
PROJECT_NAME="{self.name}"
NODE_PORT="{self.port}"
PROJECT_PATH="{self.path}"
'''
        self.metadata_file.write_text(content)
    
    @classmethod
    def load(cls, project_path: Path) -> "ProjectMetadata":
        """Load metadata from .claudette file."""
        metadata_file = project_path / ".claudette"
        if not metadata_file.exists():
            raise FileNotFoundError(f"No .claudette file found in {project_path}")
        
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
            path=Path(metadata["PROJECT_PATH"])
        )


class ClaudetteSettings(BaseSettings):
    """Global settings for claudette."""
    
    worktree_base: Path = Path.home() / "code" / "superset-worktree"
    claudette_home: Path = Path.home() / ".claudette"
    default_branch: str = "master"
    python_version: str = "python3.11"
    
    # Optional paths
    claude_local_md: Optional[Path] = None
    claude_rc_template: Optional[Path] = None
    
    model_config = {
        "env_prefix": "CLAUDETTE_",
        "env_file": ".env",
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-discover files if not set
        if not self.claude_local_md and (self.worktree_base / "CLAUDE.local.md").exists():
            self.claude_local_md = self.worktree_base / "CLAUDE.local.md"
        if not self.claude_rc_template and (self.worktree_base / ".claude_rc_template").exists():
            self.claude_rc_template = self.worktree_base / ".claude_rc_template"