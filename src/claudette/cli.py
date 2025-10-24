"""Main CLI module for claudette."""

import contextlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import PROJECT_MANAGED_FILES, ClaudetteSettings, ProjectMetadata


def get_user_shell() -> tuple[str, str]:
    """Get user's preferred shell and its config file.
    
    Returns:
        tuple: (shell_command, rc_file_path)
    """
    # Get shell from SHELL environment variable
    shell_path = os.environ.get("SHELL", "/bin/bash")
    shell_name = Path(shell_path).name
    
    if shell_name == "zsh":
        return ("zsh", "~/.zshrc")
    elif shell_name == "fish":
        return ("fish", "~/.config/fish/config.fish") 
    else:
        # Default to bash for bash and unknown shells
        return ("bash", "~/.bashrc")


def get_shell_rcfile_arg(shell: str) -> str:
    """Get the RC file argument for different shells."""
    if shell == "zsh":
        # zsh doesn't have --rcfile equivalent, we'll handle it differently
        return ""
    elif shell == "fish":
        return ""  # fish doesn't use rc files the same way
    else:
        return "--rcfile"  # bash uses --rcfile


def get_template_path(template_name: str) -> Path:
    """Get path to a template file."""
    return Path(__file__).parent / "templates" / template_name


class CommandRunner:
    """Enhanced command runner with streaming output and better control."""

    def __init__(self, console: Console):
        self.console = console

    def run(
        self,
        cmd: List[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        check: bool = True,
        quiet: bool = False,
        capture: bool = False,
        description: Optional[str] = None,
        input_data: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        """
        Run a command with enhanced logging and output control.

        Args:
            cmd: Command and arguments as list
            cwd: Working directory
            env: Environment variables
            check: Raise exception on non-zero exit
            quiet: Don't show command or stream output
            capture: Capture stdout/stderr instead of streaming
            description: Optional description to show
            input_data: Data to pass to stdin
        """
        if not quiet:
            # Show what we're running
            cmd_str = " ".join(cmd)
            if description:
                self.console.print(f"[dim]{description}[/dim]")
            self.console.print(f"[cyan]$ {cmd_str}[/cyan]")
            if cwd:
                self.console.print(f"[dim]  (in {cwd})[/dim]")

        # Prepare subprocess arguments
        kwargs = {
            "cwd": cwd,
            "env": env,
            "check": check,
            "text": True,
        }

        if input_data:
            kwargs["input"] = input_data

        if capture:
            kwargs["capture_output"] = True
        elif quiet:
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL

        return subprocess.run(cmd, **kwargs)


app = typer.Typer(
    name="claudette",
    help="Git worktree management for Apache Superset development, made simple. Fully loaded, concurrent dev environments, ready for Claude Code.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
settings = ClaudetteSettings()

# Global command runner instance
run_cmd = CommandRunner(console)


def get_package_version() -> str:
    """Get the current package version."""
    from . import __version__

    return __version__


# Current claudette schema version (for migrations)
CLAUDETTE_SCHEMA_VERSION = "0.2.0"


def _resolve_project_path(project_name: str) -> Path:
    """Resolve project path from metadata (works for both native & adopted projects).

    This is the single source of truth for project paths. Always use this instead
    of calculating worktree_base / project_name directly.

    Returns:
        Path to the project (may be in worktree_base for native, or external for adopted)

    Raises:
        typer.Exit: If project metadata cannot be found
    """
    try:
        metadata = ProjectMetadata.load(project_name, settings.claudette_home)
        return metadata.path
    except FileNotFoundError:
        # Fallback for backward compatibility or fuzzy matching
        fallback_path = settings.worktree_base / project_name
        if fallback_path.exists():
            return fallback_path

        # Try fuzzy matching
        possible_paths = [p for p in settings.worktree_base.glob(f"{project_name}*")]
        if len(possible_paths) == 1:
            console.print(
                f"[yellow]⚠️  Found '{possible_paths[0].name}' - treating as '{project_name}'[/yellow]"
            )
            return possible_paths[0]

        console.print(f"[red]❌ Project '{project_name}' not found[/red]")
        raise typer.Exit(1) from None


def _write_version_file(version_file: Path, version: str) -> None:
    """Write version file with current version and timestamp."""
    version_data = {
        "version": version,
        "last_updated": datetime.now().isoformat(),
    }
    version_file.write_text(json.dumps(version_data, indent=2))


def _migrate_v01_to_v02() -> None:
    """Migrate from old *.claudette files to new folder structure.

    Moves ~/.claudette/projects/*.claudette to ~/.claudette/projects/{project}/.claudette
    and creates PROJECT.md files with symlinks.
    """
    projects_dir = settings.claudette_home / "projects"
    if not projects_dir.exists():
        return

    # Use list() builtin explicitly to avoid conflict with list command
    old_files = [f for f in projects_dir.glob("*.claudette")]
    if not old_files:
        return  # Already migrated or no projects

    # Perform silent migration
    for old_file in old_files:
        project_name = old_file.stem
        new_folder = projects_dir / project_name
        new_folder.mkdir(exist_ok=True)

        # Move metadata file
        new_file = new_folder / ".claudette"
        if not new_file.exists():
            old_file.rename(new_file)

        # Create PROJECT.md if it doesn't exist
        project_md_path = new_folder / "PROJECT.md"
        if not project_md_path.exists():
            project_md_content = f"""# {project_name}

Project documentation for {project_name}.

## Overview
<!-- Add description of this feature/branch -->

## Goals
<!-- What are you trying to accomplish? -->

## Implementation Notes
<!-- Technical details, approach, key files -->

## Testing Strategy
<!-- How will you test this feature? -->

## Current Status
<!-- What's done, what's in progress, what's blocked -->

## Notes
<!-- Any other context or documentation -->
"""
            project_md_path.write_text(project_md_content)

        # Create symlink in worktree if the worktree exists
        worktree_path = settings.worktree_base / project_name
        if worktree_path.exists():
            worktree_project_md = worktree_path / "PROJECT.md"
            if not worktree_project_md.exists():
                with contextlib.suppress(OSError, FileExistsError):
                    worktree_project_md.symlink_to(project_md_path)

            # Also create .env.local while we're at it
            env_local_path = new_folder / ".env.local"
            if not env_local_path.exists():
                env_local_path.write_text(f"# Local environment variables for {project_name}\n")

            worktree_env_local = worktree_path / ".env.local"
            if not worktree_env_local.exists():
                with contextlib.suppress(OSError, FileExistsError):
                    worktree_env_local.symlink_to(env_local_path)


def _ensure_claudette_initialized() -> None:
    """Ensure claudette is properly initialized and migrated to latest version.

    This runs on every command to ensure users are always on the latest structure.
    """
    # Skip if claudette home doesn't exist yet
    if not settings.claudette_home.exists():
        return

    version_file = settings.claudette_home / ".claudette.json"

    if not version_file.exists():
        # Pre-0.2.0 installation detected - migrate silently
        _migrate_v01_to_v02()
        _write_version_file(version_file, CLAUDETTE_SCHEMA_VERSION)
    else:
        # Check if we need to run any migrations
        try:
            version_data = json.loads(version_file.read_text())
            stored_version = version_data.get("version", "0.1.0")

            # Simple version comparison (works for x.y.z format)
            if stored_version < CLAUDETTE_SCHEMA_VERSION:
                # Run migrations based on version
                if stored_version < "0.2.0":
                    _migrate_v01_to_v02()

                # Update version file after successful migration
                _write_version_file(version_file, CLAUDETTE_SCHEMA_VERSION)
        except (json.JSONDecodeError, KeyError):
            # Invalid version file, recreate it
            _write_version_file(version_file, CLAUDETTE_SCHEMA_VERSION)


@app.command()
def version() -> None:
    """📋 Show claudette version."""
    package_version = get_package_version()
    console.print(package_version)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Force re-initialization"),
) -> None:
    """🚀 Initialize claudette environment and clone Superset base repository."""
    console.print("\n[bold blue]🚀 Initializing Claudette[/bold blue]\n")

    # Check if already initialized
    if settings.superset_base.exists() and not force:
        console.print("[yellow]⚠️  Claudette is already initialized![/yellow]")
        console.print(f"[dim]Base repository: {settings.superset_base}[/dim]")
        console.print("[dim]Use --force to re-initialize[/dim]")
        raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        refresh_per_second=4,  # Reduce refresh rate to help with terminal lag
    ) as progress:
        # Create directory structure
        task = progress.add_task("Creating directory structure...", total=None)
        settings.claudette_home.mkdir(parents=True, exist_ok=True)
        settings.worktree_base.mkdir(parents=True, exist_ok=True)

        # Clone Superset repository
        progress.update(
            task, description="Cloning Apache Superset repository (this may take a while)..."
        )
        if settings.superset_base.exists():
            # Remove existing if force flag is set
            import shutil

            shutil.rmtree(settings.superset_base)

        try:
            run_cmd.run(
                ["git", "clone", settings.superset_repo_url, str(settings.superset_base)],
                description="Cloning Apache Superset repository",
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error cloning repository: {e.stderr}[/red]")
            raise typer.Exit(1) from e

        # Create template files
        progress.update(task, description="Creating template files...")

        # Copy CLAUDE.local.md
        import shutil

        shutil.copy(
            get_template_path("CLAUDE.local.md"), settings.claudette_home / "CLAUDE.local.md"
        )

        # Copy .claude_rc_template
        shutil.copy(
            get_template_path("claude_rc_template"), settings.claudette_home / ".claude_rc_template"
        )

        # Copy central .claude_rc
        shutil.copy(get_template_path("claude_rc_central"), settings.claudette_home / ".claude_rc")

        # Add claudette entries to Superset's .gitignore
        progress.update(task, description="Updating Superset .gitignore...")
        gitignore_path = settings.superset_base / ".gitignore"
        gitignore_additions = get_template_path("gitignore_additions").read_text()

        if gitignore_path.exists():
            existing_content = gitignore_path.read_text()
            if "PROJECT.md" not in existing_content:
                with gitignore_path.open("a") as f:
                    f.write("\n" + gitignore_additions + "\n")

    # Success message
    console.print("\n[bold green]✅ Claudette initialized successfully![/bold green]\n")

    panel = Panel.fit(
        f"""[yellow]Quick Start:[/yellow]

1. Create your first project:
   [cyan]claudette add my-feature 9001[/cyan]

2. Enter the project environment:
   [cyan]claudette shell my-feature[/cyan]

3. Start development!

[dim]Base repository: {settings.superset_base}
Configuration: {settings.claudette_home}[/dim]""",
        title="[bold]Ready to Go![/bold]",
        border_style="green",
    )
    console.print(panel)


@app.command()
def add(
    project: str = typer.Argument(
        ..., help="Project name (will be both the git branch name and worktree directory name)"
    ),
    port: Optional[int] = typer.Argument(
        None, min=9000, max=9999, help="Port for frontend (auto-assigned if not provided)"
    ),
    reuse: bool = typer.Option(
        False, "--reuse", help="Reuse existing git branch without prompting"
    ),
    force_new: bool = typer.Option(
        False, "--force-new", help="Delete existing branch and create new one"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Use different branch name if conflict occurs"
    ),
) -> None:
    """➕ Create a new Superset worktree project with isolated environment.

    NOTE: The project name will be used as both the git branch name and the
    worktree directory name (e.g., 'my-feature' creates branch 'my-feature'
    in directory ~/.claudette/worktrees/my-feature).
    """
    # Validate conflicting flags
    if reuse and force_new:
        console.print("[red]❌ Cannot use both --reuse and --force-new flags together[/red]")
        raise typer.Exit(1)

    # Check if claudette is initialized
    if not settings.superset_base.exists():
        console.print("[red]❌ Claudette is not initialized![/red]")
        console.print("[dim]Run 'claudette init' first to set up your environment[/dim]")
        raise typer.Exit(1)

    # Auto-assign port if not provided
    if port is None:
        try:
            port = ProjectMetadata.suggest_port(settings.claudette_home)
            console.print(
                f"\n[bold green]Creating project: {project} (auto-assigned port: {port})[/bold green]\n"
            )
        except ValueError as e:
            console.print(f"[red]❌ {e}[/red]")
            raise typer.Exit(1) from e
    else:
        console.print(f"\n[bold green]Creating project: {project} (port: {port})[/bold green]\n")

        # Check for port collisions only if user specified a port
        used_ports = ProjectMetadata.get_used_ports(settings.claudette_home)
        if port in used_ports:
            console.print(f"[red]❌ Port {port} is already in use by another project![/red]")
            console.print("[dim]Used ports:[/dim]")
            for used_port in sorted(used_ports):
                console.print(f"  • {used_port}")

            suggested_port = ProjectMetadata.suggest_port(settings.claudette_home)
            console.print(f"\n[yellow]💡 Try: claudette add {project} {suggested_port}[/yellow]")
            console.print(f"[dim]Or omit the port to auto-assign: claudette add {project}[/dim]")
            raise typer.Exit(1)

    project_path = settings.worktree_base / project

    metadata = ProjectMetadata(name=project, port=port, path=project_path)

    # Ensure worktree base exists
    settings.worktree_base.mkdir(parents=True, exist_ok=True)

    # Handle potential branch conflicts
    final_branch_name = project
    create_new_branch = True

    if _branch_exists(project):
        final_branch_name, create_new_branch = _handle_branch_conflict(
            project, reuse, force_new, name
        )
        # Update project name if branch name changed
        if final_branch_name != project:
            project = final_branch_name
            project_path = settings.worktree_base / project
            metadata = ProjectMetadata(name=project, port=port, path=project_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Ensure main repo is up-to-date
        task = progress.add_task("Updating main repository...", total=None)

        # First, verify the main repo is in a healthy state
        try:
            # Check if repo has commits
            head_check = run_cmd.run(
                ["git", "rev-parse", "HEAD"],
                cwd=settings.superset_base,
                capture=True,
                quiet=True,
                check=False,
            )

            if head_check.returncode != 0:
                console.print("[red]❌ Main repository is not in a valid state![/red]")
                console.print(
                    "[yellow]The repository may be corrupted or have no commits.[/yellow]"
                )
                console.print("\nTo fix this, run:")
                console.print("[cyan]claudette init --force[/cyan]")
                raise typer.Exit(1)

            # Fetch latest changes from remote
            run_cmd.run(
                ["git", "fetch", "origin"],
                cwd=settings.superset_base,
                description="Fetching latest changes from remote",
            )

            # Check current branch
            current_branch_result = run_cmd.run(
                ["git", "branch", "--show-current"],
                cwd=settings.superset_base,
                capture=True,
                quiet=True,
            )
            current_branch = current_branch_result.stdout.strip()

            # If on master, pull latest changes
            if current_branch == "master":
                run_cmd.run(
                    ["git", "pull", "origin", "master", "--ff-only"],
                    cwd=settings.superset_base,
                    description="Pulling latest master branch",
                )
            elif not current_branch:
                # Empty branch name might indicate a problem
                console.print(
                    "[yellow]⚠️  Main repo has no current branch, checking out master...[/yellow]"
                )
                run_cmd.run(
                    ["git", "checkout", "-b", "master", "origin/master"],
                    cwd=settings.superset_base,
                    description="Creating master branch from origin",
                )
            else:
                console.print(f"[dim]Main repo is on branch '{current_branch}', not pulling[/dim]")
        except subprocess.CalledProcessError as e:
            console.print("[red]❌ Could not update main repository![/red]")
            console.print(f"[yellow]Error: {e.stderr if hasattr(e, 'stderr') else str(e)}[/yellow]")
            console.print("\n[yellow]The main repository may be corrupted. To fix:[/yellow]")
            console.print("1. Back up any uncommitted work in worktrees")
            console.print("2. Run: [cyan]claudette init --force[/cyan]")
            raise typer.Exit(1) from None

        # Step 2: Create git worktree
        progress.update(task, description="Creating git worktree...")
        try:
            if create_new_branch:
                # Create new branch
                run_cmd.run(
                    ["git", "worktree", "add", str(project_path), "-b", final_branch_name],
                    cwd=settings.superset_base,
                    description=f"Creating git worktree with new branch '{final_branch_name}'",
                )
            else:
                # Use existing branch (might be remote)
                # First check if it's a remote branch that needs to be tracked
                local_exists = run_cmd.run(
                    ["git", "branch", "--list", final_branch_name],
                    cwd=settings.superset_base,
                    check=False,
                    capture=True,
                    quiet=True,
                ).stdout.strip()

                if not local_exists:
                    # Remote branch - create local tracking branch
                    run_cmd.run(
                        [
                            "git",
                            "worktree",
                            "add",
                            str(project_path),
                            "-b",
                            final_branch_name,
                            f"origin/{final_branch_name}",
                        ],
                        cwd=settings.superset_base,
                        description=f"Creating git worktree tracking remote branch 'origin/{final_branch_name}'",
                    )
                else:
                    # Local branch exists
                    run_cmd.run(
                        ["git", "worktree", "add", str(project_path), final_branch_name],
                        cwd=settings.superset_base,
                        description=f"Creating git worktree with existing branch '{final_branch_name}'",
                    )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error creating worktree: {e.stderr}[/red]")
            raise typer.Exit(1) from e

        # Step 3: Save metadata
        progress.update(task, description="Saving project metadata...")
        # Try to extract description from PROJECT.md if it exists (for reused branches)
        metadata.update_from_project_md()
        metadata.save(settings.claudette_home)

        # Step 4: Create Python venv
        progress.update(task, description="Creating Python virtual environment...")
        run_cmd.run(
            ["uv", "venv", "-p", settings.python_version],
            cwd=project_path,
            description="Creating Python virtual environment",
        )

        # Step 5: Install Python dependencies
        progress.update(
            task, description="Installing Python dependencies (this may take a while)..."
        )

    # Temporarily exit Progress context for uv operations to avoid spinner conflicts
    console.print("[dim]Installing Python development dependencies...[/dim]")
    run_cmd.run(
        [
            "uv",
            "pip",
            "install",
            "-r",
            "requirements/development.txt",
            "--python",
            str(project_path / ".venv" / "bin" / "python"),
        ],
        cwd=project_path,
        description="Installing Python development dependencies",
    )

    console.print("[dim]Installing Superset in editable mode...[/dim]")
    run_cmd.run(
        [
            "uv",
            "pip",
            "install",
            "-e",
            ".",
            "--python",
            str(project_path / ".venv" / "bin" / "python"),
        ],
        cwd=project_path,
        description="Installing Superset in editable mode",
    )

    # Resume Progress context
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Continuing setup...", total=None)

        # Step 6: Symlink CLAUDE.local.md if exists
        progress.update(task, description="Setting up Claude configuration...")
        if settings.claude_local_md:
            (project_path / "CLAUDE.local.md").symlink_to(settings.claude_local_md)

        # Step 7: Create project folder and managed files
        progress.update(task, description="Creating project folder and files...")
        project_folder = metadata.project_folder(settings.claudette_home)
        project_folder.mkdir(parents=True, exist_ok=True)

        # Create and symlink managed files
        for filename in PROJECT_MANAGED_FILES:
            source_path = project_folder / filename
            worktree_path = project_path / filename

            # Create file in project folder if it doesn't exist
            if filename == "PROJECT.md" and not source_path.exists():
                project_md_content = f"""# {project}

Branch-specific documentation for the {final_branch_name} feature branch.

## Overview
<!-- One-paragraph description of what this branch/feature is about -->

## Goals
<!-- What are you trying to accomplish? -->

## Implementation Notes
<!-- Technical details, approach, key files -->

## Testing Strategy
<!-- How will you test this feature? -->

## Current Status
<!-- What's done, what's in progress, what's blocked -->

## Related PRs/Issues
<!-- Links to GitHub issues, PRs, discussions -->

## Notes
<!-- Any other context, reminders, or documentation -->
"""
                source_path.write_text(project_md_content)
            elif filename == ".env.local" and not source_path.exists():
                # Create empty .env.local for future use
                source_path.write_text(f"# Local environment variables for {project}\n")

            # Create symlink in worktree if it doesn't exist
            if not worktree_path.exists() and source_path.exists():
                worktree_path.symlink_to(source_path)

        # Step 8: Create .claude_rc from template
        if settings.claude_rc_template and settings.claude_rc_template.exists():
            # Use template and replace placeholders
            template_content = settings.claude_rc_template.read_text()
            claude_rc_content = template_content.replace("{{PROJECT}}", project)
            claude_rc_content = claude_rc_content.replace("{{PROJECT_PATH}}", str(project_path))
            claude_rc_content = claude_rc_content.replace("{{NODE_PORT}}", str(port))
        else:
            # Fallback to inline content
            claude_rc_content = f"""# Claude Code RC for {project}

This is a claudette-managed Apache Superset development environment.

## Project: {project}
- Worktree Path: {project_path}
- Frontend Port: {port}
- Frontend URL: http://localhost:{port}

## Quick Commands

Start services:
```bash
claudette docker up
```

Access frontend:
```bash
open http://localhost:{port}
```

Run tests:
```bash
# Backend
pytest tests/unit_tests/

# Frontend
cd superset-frontend && npm test
```

## Environment Details
- Python venv: `.venv/` (auto-activated in claudette shell)
- Node modules: `superset-frontend/node_modules/`
- Docker prefix: `{project}_`

## Development Tips
- Always use `claudette shell` to work in this project
- Run `pre-commit run --all-files` before committing
- Use `claudette docker` instead of docker-compose directly
- The frontend dev server runs on port {port} to avoid conflicts
"""
        (project_path / ".claude_rc").write_text(claude_rc_content)

        # Step 9: Install frontend dependencies
        progress.update(task, description="Installing frontend dependencies...")

    # Temporarily exit Progress context for npm install to avoid spinner conflicts
    console.print("[dim]Installing frontend dependencies...[/dim]")
    run_cmd.run(
        ["npm", "install"],
        cwd=project_path / "superset-frontend",
        description="Installing frontend dependencies",
    )

    # Resume Progress context for final steps
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Finishing setup...", total=None)

        # Step 10: Setup pre-commit
        progress.update(task, description="Setting up pre-commit hooks...")
        venv_python = project_path / ".venv" / "bin" / "python"
        run_cmd.run(
            [str(venv_python), "-m", "pre_commit", "install"],
            cwd=project_path,
            description="Setting up pre-commit hooks",
        )

    # Success!
    console.print("\n[bold green]✨ Project created successfully![/bold green]\n")

    # Ask if user wants to activate the project immediately
    activate_now = typer.confirm("Would you like to activate this project now?", default=True)

    if activate_now:
        console.print(f"\n[green]🚀 Activating project: {project}[/green]")
        console.print("[dim]Setting up project environment...[/dim]")

        # Get user's preferred shell for activation
        user_shell, user_rc = get_user_shell()
        
        # Create activation script (same as in activate command)
        activate_script = f"""
# Source user's rc file first
source {user_rc} 2>/dev/null || true

# Set environment variables
export NODE_PORT={metadata.port}
export PROJECT={metadata.name}

# Navigate to project directory
cd {project_path}

# Activate Python virtual environment
source .venv/bin/activate

# Only modify prompt if PS1 exists and we're in a compatible shell
if [ -n "$PS1" ] && ([ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]); then
    PS1="({metadata.name}) $PS1"
fi

# Show activation status (using ANSI green for 'activated')
echo
echo -e "\\033[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m"
echo -e "🚀 Project '{metadata.name}' \\033[32mactivated\\033[0m - You are now in a project shell"
echo -e "\\033[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m"
echo
echo "✓ Directory: $(pwd)"
echo -e "✓ Virtual environment: \\033[32mactivated\\033[0m"
echo "✓ PROJECT=$PROJECT"
echo "✓ NODE_PORT=$NODE_PORT"
echo
echo "💡 This is a nested shell session. Press Ctrl+D to exit and return to your original shell."
echo -e "\\033[90mPython: $(which python)\\033[0m"
echo
echo "🚀 Quick next steps:"
echo "  • claudette docker up    (start database)"
echo "  • claudette open         (open browser)"
echo

"""

        # Write activation script to a temporary file
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(activate_script)
            temp_script = f.name

        try:
            # Start user's shell in the project directory with our activation script
            if user_shell == "zsh":
                # For zsh, create a wrapper script that sources both user config and our setup
                wrapper_script = f"""#!/bin/zsh
# Source user's zsh config first
source ~/.zshrc 2>/dev/null || true

# Then source our project activation
source {temp_script}

# Start interactive zsh
exec zsh -i
"""
                temp_wrapper = temp_script + "_wrapper.zsh"
                with Path(temp_wrapper).open('w') as f:
                    f.write(wrapper_script)
                
                subprocess.run(
                    [user_shell, temp_wrapper],
                    cwd=project_path,
                    check=False,
                )
                
                # Clean up wrapper script
                Path(temp_wrapper).unlink(missing_ok=True)
                
            elif user_shell == "bash":
                # For bash, use --rcfile
                subprocess.run(
                    ["bash", "--rcfile", temp_script],
                    cwd=project_path,
                    check=False,
                )
            else:
                # For other shells, just run them normally
                subprocess.run(
                    [user_shell],
                    cwd=project_path,
                    check=False,
                )
        finally:
            # Clean up temp file
            Path(temp_script).unlink(missing_ok=True)
    else:
        # Show next steps if not activating
        console.print("\n[dim]Quick start commands:[/dim]")

        # Create a table for next steps
        next_steps_table = Table(show_header=False, box=None, padding=(0, 2))
        next_steps_table.add_column("Command", style="cyan", no_wrap=True)
        next_steps_table.add_column("Description", style="dim")

        next_steps_table.add_row(
            f"claudette activate {project}", "Start a shell with Python venv activated"
        )
        next_steps_table.add_row("claudette docker up", "Start PostgreSQL database and Redis")
        next_steps_table.add_row("claudette open", f"Open browser at http://localhost:{port}")

        panel = Panel(
            next_steps_table,
            title="[bold]🚀 Get Started[/bold]",
            subtitle=f"[dim]Project: {project} | Port: {port}[/dim]",
            border_style="green",
            expand=False,
        )
        console.print(panel)


@app.command()
def adopt(
    path: Path = typer.Argument(
        Path("."), help="Path to existing Superset worktree (defaults to current directory)"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Port for frontend (auto-assigned if not provided)"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Project name (uses directory name if not provided)"
    ),
) -> None:
    """🔗 Adopt an existing Superset worktree into claudette management.

    This allows you to manage a Superset worktree created by other tools or manually.
    Claudette will set up dependencies and metadata but won't modify the git worktree itself.

    Example:
        cd ~/my-superset-worktree
        clo adopt .                    # Adopt current directory
        clo adopt /path/to/worktree    # Adopt specific path
        clo adopt . --port 9005 --name my-feature
    """
    console.print("\n[bold green]🔗 Adopting existing Superset worktree[/bold green]\n")

    # Resolve and validate path
    abs_path = path.resolve()
    if not abs_path.exists():
        console.print(f"[red]❌ Path does not exist: {abs_path}[/red]")
        raise typer.Exit(1)

    if not abs_path.is_dir():
        console.print(f"[red]❌ Path is not a directory: {abs_path}[/red]")
        raise typer.Exit(1)

    # Validate it's a Superset repository
    console.print(f"[dim]Validating Superset repository at {abs_path}...[/dim]")
    superset_markers = [
        abs_path / "superset-frontend",
        abs_path / "superset",
        abs_path / "setup.py",
    ]

    if not all(marker.exists() for marker in superset_markers):
        console.print("[red]❌ This doesn't appear to be a Superset repository![/red]")
        console.print("[dim]Expected to find: superset-frontend/, superset/, setup.py[/dim]")
        raise typer.Exit(1)

    console.print("[green]✓[/green] Valid Superset repository detected")

    # Determine project name
    project_name = name or abs_path.name
    console.print(f"[dim]Project name: {project_name}[/dim]")

    # Check if project name is already in use
    try:
        existing_metadata = ProjectMetadata.load(project_name, settings.claudette_home)

        # Idempotent behavior: if adopting the same path with the same settings, succeed
        if existing_metadata.path.resolve() == abs_path:
            # Same path - check if port matches (if specified)
            if port is not None and existing_metadata.port != port:
                console.print(
                    f"[red]❌ Project '{project_name}' already exists at this path with a different port![/red]"
                )
                console.print(
                    f"[dim]Existing port: {existing_metadata.port}, Requested port: {port}[/dim]"
                )
                console.print(
                    "[yellow]💡 Remove the --port flag to keep the existing port, or use a different project name[/yellow]"
                )
                raise typer.Exit(1)

            # Same path, same port (or no port specified) - idempotent success
            console.print(
                f"[green]✓ Project '{project_name}' is already adopted at this path[/green]"
            )
            console.print(f"[dim]Path: {abs_path}[/dim]")
            console.print(f"[dim]Port: {existing_metadata.port}[/dim]")
            console.print("[dim]No changes needed - project already managed by claudette[/dim]")
            raise typer.Exit(0)
        else:
            # Different path - conflict
            console.print(
                f"[red]❌ Project '{project_name}' already exists at a different path![/red]"
            )
            console.print(f"[dim]Existing path: {existing_metadata.path}[/dim]")
            console.print(f"[dim]Requested path: {abs_path}[/dim]")
            console.print("[yellow]💡 Use --name to specify a different project name[/yellow]")
            raise typer.Exit(1)
    except FileNotFoundError:
        pass  # Good, name is available

    # Auto-assign or validate port
    if port is None:
        port = ProjectMetadata.suggest_port(settings.claudette_home)
        console.print(f"[green]✓[/green] Auto-assigned port: {port}")
    else:
        # Check for port collisions
        used_ports = ProjectMetadata.get_used_ports(settings.claudette_home)
        if port in used_ports:
            console.print(f"[red]❌ Port {port} is already in use by another project![/red]")
            suggested_port = ProjectMetadata.suggest_port(settings.claudette_home)
            console.print(f"[yellow]💡 Suggested port: {suggested_port}[/yellow]")
            raise typer.Exit(1)
        console.print(f"[green]✓[/green] Using port: {port}")

    # Create metadata with adopted=True
    metadata = ProjectMetadata(
        name=project_name,
        port=port,
        path=abs_path,
        adopted=True,
    )

    # Try to extract description from existing PROJECT.md
    metadata.update_from_project_md()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Save metadata
        task = progress.add_task("Saving project metadata...", total=None)
        metadata.save(settings.claudette_home)

        # Step 2: Create Python venv
        progress.update(task, description="Creating Python virtual environment...")
        run_cmd.run(
            ["uv", "venv", "-p", settings.python_version],
            cwd=abs_path,
            description="Creating Python virtual environment",
        )

        # Step 3: Install Python dependencies
        progress.update(
            task, description="Installing Python dependencies (this may take a while)..."
        )

    # Temporarily exit Progress context for uv operations
    console.print("[dim]Installing Python development dependencies...[/dim]")
    run_cmd.run(
        [
            "uv",
            "pip",
            "install",
            "-r",
            "requirements/development.txt",
            "--python",
            str(abs_path / ".venv" / "bin" / "python"),
        ],
        cwd=abs_path,
        description="Installing Python development dependencies",
    )

    console.print("[dim]Installing Superset in editable mode...[/dim]")
    run_cmd.run(
        [
            "uv",
            "pip",
            "install",
            "-e",
            ".",
            "--python",
            str(abs_path / ".venv" / "bin" / "python"),
        ],
        cwd=abs_path,
        description="Installing Superset in editable mode",
    )

    # Continue with remaining setup
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Setting up environment...", total=None)

        # Step 4: Symlink CLAUDE.local.md if it exists
        if settings.claude_local_md and settings.claude_local_md.exists():
            progress.update(task, description="Symlinking CLAUDE.local.md...")
            claude_local_link = abs_path / "CLAUDE.local.md"
            if not claude_local_link.exists():
                claude_local_link.symlink_to(settings.claude_local_md)

        # Step 5: npm install
        progress.update(task, description="Installing npm dependencies...")
        run_cmd.run(
            ["npm", "ci"],
            cwd=abs_path / "superset-frontend",
            description="Installing npm dependencies",
        )

        # Step 6: Setup pre-commit hooks
        progress.update(task, description="Setting up pre-commit hooks...")
        venv_python = abs_path / ".venv" / "bin" / "python"
        run_cmd.run(
            [str(venv_python), "-m", "pre_commit", "install"],
            cwd=abs_path,
            description="Installing pre-commit hooks",
        )

    # Success!
    console.print(f"\n[bold green]✅ Successfully adopted worktree: {project_name}[/bold green]")
    console.print(f"[dim]Path: {abs_path}[/dim]")
    console.print(f"[dim]Port: {port}[/dim]")
    console.print(
        "\n[yellow]💡 This is an adopted project. Use 'clo disown' to remove management while keeping the worktree.[/yellow]"
    )

    # Show next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  clo activate {project_name}")
    console.print("  clo docker up -d")
    console.print("  clo open")


@app.command()
def remove(
    project: str = typer.Argument(..., help="Project name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    keep_docs: bool = typer.Option(False, "--keep-docs", help="Keep PROJECT.md and project folder"),
    delete_worktree: bool = typer.Option(
        False, "--delete-worktree", help="For adopted projects: also delete the worktree"
    ),
) -> None:
    """🗑️  Remove a worktree project and clean up resources.

    For native claudette projects: Removes everything including the worktree.
    For adopted projects: By default only removes claudette management (use --delete-worktree to also delete).

    By default, removes everything including PROJECT.md documentation.
    Use --keep-docs to preserve PROJECT.md for future use.
    """
    # First check if we have metadata for this project
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
        project_path = metadata.path  # Use path from metadata
    except FileNotFoundError:
        # No metadata, check if directory exists with project name
        project_path = settings.worktree_base / project
        metadata = None

        # If neither metadata nor directory exists, nothing to remove
        if not project_path.exists():
            # Check for variations (like rison-old, rison-backup, etc)
            possible_paths = [p for p in settings.worktree_base.glob(f"{project}*")]
            if not possible_paths:
                console.print(f"[red]Project '{project}' not found[/red]")
                raise typer.Exit(1) from None

            console.print("[yellow]Found related directories:[/yellow]")
            for p in possible_paths:
                console.print(f"  • {p.name}")

            if len(possible_paths) == 1:
                # If there's exactly one match, offer to remove it
                project_path = possible_paths[0]
                console.print(
                    f"\n[yellow]Found '{project_path.name}' - treating as '{project}'[/yellow]"
                )
            else:
                console.print(f"\n[yellow]Multiple matches found for '{project}'[/yellow]")
                console.print("[dim]You may need to manually clean up these directories.[/dim]")
                raise typer.Exit(1) from None

    # Handle adopted projects differently
    if metadata and metadata.adopted and not delete_worktree:
        console.print(f"\n[cyan]ℹ️  '{project}' is an adopted project[/cyan]")
        console.print(
            "[yellow]By default, 'remove' only removes claudette management for adopted projects.[/yellow]"
        )
        console.print("[dim]The worktree will remain intact.[/dim]\n")
        console.print("[bold]Options:[/bold]")
        console.print("  1. Remove management only (recommended)")
        console.print("  2. Remove management AND delete worktree (use --delete-worktree)")
        console.print(
            "\n[dim]Hint: Use 'clo disown' for more control over what gets removed.[/dim]"
        )

        if not force and not typer.confirm("\nRemove claudette management only (keep worktree)?"):
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

        # Call disown logic for adopted projects
        console.print(f"\n[yellow]Removing claudette management for '{project}'...[/yellow]")

        errors_occurred = []

        # Remove symlinks
        symlinks_to_remove = [
            project_path / "CLAUDE.local.md",
        ]

        for symlink in symlinks_to_remove:
            if symlink.is_symlink() or symlink.exists():
                try:
                    symlink.unlink()
                except Exception as e:
                    errors_occurred.append(f"Could not remove {symlink.name}: {e}")

        # Remove metadata
        try:
            metadata_file = metadata.metadata_file(settings.claudette_home)
            metadata_file.unlink()

            # Also remove the project folder if it's empty
            project_folder = metadata.project_folder(settings.claudette_home)
            if project_folder.exists() and not any(project_folder.iterdir()):
                project_folder.rmdir()
        except Exception as e:
            errors_occurred.append(f"Could not remove metadata: {e}")

        if errors_occurred:
            console.print(
                f"\n[yellow]⚠️  Removed management with {len(errors_occurred)} issues:[/yellow]"
            )
            for error in errors_occurred:
                console.print(f"  • {error}")
        else:
            console.print(f"\n[green]✅ Removed claudette management for '{project}'[/green]")
            console.print(f"[dim]Worktree remains at: {project_path}[/dim]")

        return

    # Standard remove logic for native projects or adopted with --delete-worktree
    if metadata and metadata.adopted and delete_worktree:
        console.print("\n[red]⚠️  WARNING: About to DELETE adopted worktree![/red]")
        console.print(f"[yellow]Path: {project_path}[/yellow]")

    if not force:
        console.print(
            f"[red]⚠️  This will permanently remove project '{project}' and all its data![/red]"
        )
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    errors_occurred = []

    with console.status("[yellow]Removing project...[/yellow]") as status:
        # Stop docker containers if metadata available
        if metadata and project_path.exists():
            status.update("Stopping Docker containers...")
            try:
                run_cmd.run(
                    [
                        "docker-compose",
                        "-p",
                        project,
                        "-f",
                        "docker-compose-light.yml",
                        "down",
                        "--timeout",
                        "10",  # Add timeout to prevent hanging
                    ],
                    cwd=project_path,
                    env={**os.environ, "NODE_PORT": str(metadata.port)},
                    description="Stopping Docker containers",
                    check=False,  # Don't fail if docker isn't running
                )
            except Exception as e:
                errors_occurred.append(f"Docker cleanup failed: {e}")
                console.print(
                    "[yellow]⚠️  Could not stop Docker containers (may not be running)[/yellow]"
                )

        # Remove git worktree
        status.update("Removing git worktree...")

        try:
            # Check if worktree is registered with git
            worktree_check = run_cmd.run(
                ["git", "worktree", "list"],
                cwd=settings.superset_base,
                capture=True,
                quiet=True,
                check=False,
            )

            if str(project_path) in worktree_check.stdout:
                # Worktree is registered, remove it properly
                run_cmd.run(
                    ["git", "worktree", "remove", str(project_path), "--force"],
                    cwd=settings.superset_base,
                    description="Removing git worktree",
                    check=False,
                )
            else:
                console.print("[dim]Worktree not registered with git[/dim]")
        except Exception as e:
            errors_occurred.append(f"Git worktree removal failed: {e}")
            console.print("[yellow]⚠️  Could not remove git worktree registration[/yellow]")

        # Remove the actual directory (bulldoze through even if it has permission issues)
        if project_path.exists():
            status.update("Removing project directory...")
            console.print(f"[dim]Removing directory: {project_path}[/dim]")

            import shutil
            import subprocess

            try:
                # First try normal removal
                shutil.rmtree(project_path)
                console.print("[green]✓ Directory removed[/green]")
            except PermissionError:
                # If permission denied, try with sudo (will prompt for password)
                console.print("[yellow]Permission denied, attempting forceful removal...[/yellow]")
                try:
                    # Use rm -rf which is more aggressive
                    subprocess.run(["rm", "-rf", str(project_path)], check=True)
                    console.print("[green]✓ Directory forcefully removed[/green]")
                except Exception:
                    errors_occurred.append(f"Could not remove directory {project_path}")
                    console.print(
                        "[red]❌ Could not remove directory (may need manual cleanup)[/red]"
                    )
                    console.print(f"[dim]Try: sudo rm -rf {project_path}[/dim]")
            except Exception as e:
                errors_occurred.append(f"Directory removal failed: {e}")
                console.print(f"[red]❌ Failed to remove directory: {e}[/red]")

    # Archive PROJECT.md before cleanup (if it exists and we're not keeping docs)
    if metadata and not keep_docs:
        _archive_project_docs(metadata, settings)

    # Handle project folder and metadata (always try to clean up)
    console.print("[dim]Cleaning up project metadata...[/dim]")

    # Clean up project folder
    if metadata:
        project_folder = metadata.project_folder(settings.claudette_home)
        if not keep_docs and project_folder.exists():
            try:
                import shutil

                shutil.rmtree(project_folder)
                console.print("[green]✓ Removed project folder and documentation[/green]")
            except Exception as e:
                errors_occurred.append(f"Could not remove project folder: {e}")
                console.print(
                    f"[yellow]⚠️  Could not remove project folder: {project_folder}[/yellow]"
                )
        elif keep_docs and project_folder.exists():
            console.print("[yellow]Kept project folder with PROJECT.md and settings[/yellow]")
            console.print(f"[dim]Location: {project_folder}[/dim]")
    else:
        # No metadata, but try to clean up anyway
        project_folder = settings.claudette_home / "projects" / project
        if project_folder.exists() and not keep_docs:
            try:
                import shutil

                shutil.rmtree(project_folder)
                console.print("[green]✓ Removed orphaned project folder[/green]")
            except Exception as e:
                errors_occurred.append(f"Could not remove project folder: {e}")

    # Also clean up old-style metadata file if it exists
    old_metadata_file = settings.claudette_home / "projects" / f"{project}.claudette"
    if old_metadata_file.exists():
        try:
            old_metadata_file.unlink()
            console.print("[green]✓ Cleaned up old metadata file[/green]")
        except Exception as e:
            errors_occurred.append(f"Could not remove old metadata file: {e}")

    # Clean up git references if needed
    with contextlib.suppress(Exception):
        # Prune any broken worktree references
        run_cmd.run(
            ["git", "worktree", "prune"],
            cwd=settings.superset_base,
            check=False,
            quiet=True,
        )

    # Report results
    if errors_occurred:
        console.print(
            f"\n[yellow]⚠️  Project '{project}' removed with {len(errors_occurred)} issues:[/yellow]"
        )
        for error in errors_occurred:
            console.print(f"  • {error}")
        console.print("\n[dim]Manual cleanup may be needed for remaining files.[/dim]")
    else:
        console.print(f"[green]✅ Project '{project}' removed successfully[/green]")


@app.command()
def disown(
    project: Optional[str] = typer.Argument(
        None, help="Project name (auto-detects if in project dir)"
    ),
    clean_deps: bool = typer.Option(
        False, "--clean-deps", help="Also remove .venv and node_modules"
    ),
) -> None:
    """🔓 Remove claudette management from project (keeps worktree by default).

    This removes claudette's metadata and optionally dependencies, but leaves
    the git worktree intact. Useful for adopted projects or when you want to
    stop using claudette for a project.

    For adopted projects, this is the recommended way to stop claudette management.
    For native projects, consider using 'remove' instead to fully clean up.

    Examples:
        clo disown                      # Remove management, keep worktree
        clo disown --clean-deps         # Also remove .venv and node_modules
        clo disown my-project           # Disown specific project
    """
    # Determine project name
    if not project:
        # Check if PROJECT env var is set
        project = os.environ.get("PROJECT")
        if not project:
            # Try to detect from current directory
            cwd = Path.cwd()
            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                project = cwd.name
            else:
                console.print(
                    "[red]❌ No project specified and not in a claudette project directory[/red]"
                )
                console.print("[dim]Use: claudette disown <project-name>[/dim]")
                console.print("[dim]Or: run from within a project directory[/dim]")
                raise typer.Exit(1)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]❌ Project '{project}' not found in claudette[/red]")
        raise typer.Exit(1) from None

    project_path = metadata.path

    # Show what will be done
    console.print(f"\n[bold yellow]🔓 Disowning project: {project}[/bold yellow]")
    console.print(f"[dim]Path: {project_path}[/dim]")

    if metadata.adopted:
        console.print("[cyan]ℹ️  This is an adopted project[/cyan]")
    else:
        console.print("[yellow]⚠️  This is a native claudette project[/yellow]")
        console.print(
            "[dim]Consider using 'clo remove' instead to fully clean up the worktree[/dim]"
        )

    console.print("\n[bold]What will be removed:[/bold]")
    console.print("  • Claudette metadata (.claudette file)")
    console.print("  • Symlinks (CLAUDE.local.md)")
    if clean_deps:
        console.print("  • Python venv (.venv)")
        console.print("  • Node modules (node_modules/)")

    console.print("\n[bold green]What will be kept:[/bold green]")
    console.print("  • Git worktree and all code")
    console.print("  • PROJECT.md (if it exists)")
    if not clean_deps:
        console.print("  • Python venv (.venv)")
        console.print("  • Node modules (node_modules/)")

    # Confirm
    if not typer.confirm(f"\nDisown project '{project}'?"):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    errors_occurred = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Removing claudette management...", total=None)

        # Step 1: Remove symlinks
        progress.update(task, description="Removing symlinks...")
        symlinks_to_remove = [
            project_path / "CLAUDE.local.md",
        ]

        for symlink in symlinks_to_remove:
            if symlink.is_symlink() or symlink.exists():
                try:
                    symlink.unlink()
                    console.print(f"[dim]Removed: {symlink.name}[/dim]")
                except Exception as e:
                    errors_occurred.append(f"Could not remove {symlink.name}: {e}")

        # Step 2: Clean deps if requested
        if clean_deps:
            import shutil

            progress.update(task, description="Removing Python venv...")
            venv_path = project_path / ".venv"
            if venv_path.exists():
                try:
                    shutil.rmtree(venv_path)
                    console.print("[dim]Removed: .venv[/dim]")
                except Exception as e:
                    errors_occurred.append(f"Could not remove .venv: {e}")

            progress.update(task, description="Removing node_modules...")
            node_modules = project_path / "superset-frontend" / "node_modules"
            if node_modules.exists():
                try:
                    shutil.rmtree(node_modules)
                    console.print("[dim]Removed: node_modules[/dim]")
                except Exception as e:
                    errors_occurred.append(f"Could not remove node_modules: {e}")

        # Step 3: Remove metadata
        progress.update(task, description="Removing metadata...")
        try:
            metadata_file = metadata.metadata_file(settings.claudette_home)
            metadata_file.unlink()

            # Also remove the project folder if it's empty
            project_folder = metadata.project_folder(settings.claudette_home)
            if project_folder.exists() and not any(project_folder.iterdir()):
                project_folder.rmdir()

            console.print("[dim]Removed: .claudette metadata[/dim]")
        except Exception as e:
            errors_occurred.append(f"Could not remove metadata: {e}")

    # Report results
    if errors_occurred:
        console.print(
            f"\n[yellow]⚠️  Project '{project}' disowned with {len(errors_occurred)} issues:[/yellow]"
        )
        for error in errors_occurred:
            console.print(f"  • {error}")
    else:
        console.print(f"\n[bold green]✅ Successfully disowned project '{project}'[/bold green]")
        console.print(f"[dim]Worktree remains at: {project_path}[/dim]")
        console.print(
            "\n[dim]The project is no longer managed by claudette but the worktree is intact.[/dim]"
        )


@app.command()
def list() -> None:
    """📋 List all claudette projects."""
    # Create a fresh console to ensure we get the current terminal width
    list_console = Console()

    table = Table(
        title="Claudette Projects",
        show_header=True,
        header_style="bold",
        title_style="bold",
        expand=True,  # This makes the table use the full terminal width
    )
    table.add_column("Project", style="cyan", no_wrap=True)
    table.add_column("Port", justify="right", style="green", width=6)
    table.add_column("PR", justify="center", style="magenta", width=8)
    table.add_column("Description", style="yellow", overflow="ellipsis", no_wrap=True, ratio=3)
    table.add_column("Status", justify="center", width=8)

    # Find all projects with metadata files
    projects_found = False
    project_rows = []  # Collect all project data for sorting
    projects_dir = settings.claudette_home / "projects"

    if projects_dir.exists():
        # Check old-style metadata files
        for metadata_file in projects_dir.glob("*.claudette"):
            projects_found = True
            project_name = metadata_file.stem
            try:
                metadata = ProjectMetadata.load(project_name, settings.claudette_home)

                # Check status - frozen takes precedence over docker
                if metadata.frozen:
                    status = "🧊"
                else:
                    status = "🟢" if _is_docker_running(metadata.name) else "⚫"

                # Try to update description from PROJECT.md
                metadata.update_from_project_md()

                # Get description for display
                description = metadata.description or "[dim]No description[/dim]"

                # Format PR display
                pr_display = f"#{metadata.pr_number}" if metadata.pr_number else "?"

                project_rows.append(
                    (
                        metadata.name,
                        str(metadata.port),
                        pr_display,
                        description,
                        status,
                    )
                )
            except Exception:
                project_rows.append(
                    (
                        project_name,
                        "?",
                        "?",
                        "[dim]Error loading[/dim]",
                        "⚠️",
                    )
                )

        # Check new-style project folders
        for project_folder in projects_dir.iterdir():
            if project_folder.is_dir() and (project_folder / ".claudette").exists():
                projects_found = True
                project_name = project_folder.name
                try:
                    metadata = ProjectMetadata.load(project_name, settings.claudette_home)

                    # Check status - frozen takes precedence over docker
                    if metadata.frozen:
                        status = "🧊"
                    else:
                        status = "🟢" if _is_docker_running(metadata.name) else "⚫"

                    # Try to update description from PROJECT.md
                    metadata.update_from_project_md()

                    # Get description for display
                    description = metadata.description or "[dim]No description[/dim]"

                    # Format PR display
                    pr_display = f"#{metadata.pr_number}" if metadata.pr_number else "?"

                    project_rows.append(
                        (
                            metadata.name,
                            str(metadata.port),
                            pr_display,
                            description,
                            status,
                        )
                    )
                except Exception:
                    project_rows.append(
                        (
                            project_name,
                            "?",
                            "?",
                            "[dim]Error loading[/dim]",
                            "⚠️",
                        )
                    )

    # Sort projects by name (first column) and add to table
    if project_rows:
        project_rows.sort(key=lambda row: row[0].lower())  # Sort by project name, case-insensitive
        for row in project_rows:
            table.add_row(*row)

    if projects_found:
        list_console.print(table)
        list_console.print("\n[dim]Status: 🟢 Running | ⚫ Stopped | 🧊 Frozen | ⚠️ Error[/dim]")
    else:
        list_console.print("[yellow]No claudette projects found[/yellow]")
        list_console.print(f"[dim]Projects are stored in: {settings.worktree_base}[/dim]")
        list_console.print("[dim]Run 'claudette init' to set up your environment[/dim]")


@app.command()
def activate(
    project: str = typer.Argument(..., help="Project name to activate"),
) -> None:
    """🚀 Activate a project: start a new shell session in the project directory with venv activated.

    This command starts a new shell subprocess with:
    - Working directory set to the project path
    - Python virtual environment activated
    - PROJECT and NODE_PORT environment variables set
    - Modified prompt showing the project name

    Note: This creates a nested shell. Use Ctrl+D or 'exit' to return to your original shell.
    """
    project_path = _resolve_project_path(project)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Check if project is frozen - activation requires dependencies
    if not _ensure_project_thawed(project, require_thaw=True):
        raise typer.Exit(1)

    console.print(f"[green]🚀 Activating project: {project}[/green]")
    console.print("[dim]Setting up project environment...[/dim]")

    # Get user's preferred shell
    user_shell, user_rc = get_user_shell()
    
    # Create activation script (only modify PS1 if it exists and we're in bash/zsh)
    activate_script = f"""
# Source user's rc file first
source {user_rc} 2>/dev/null || true

# Set environment variables
export NODE_PORT={metadata.port}
export PROJECT={metadata.name}

# Navigate to project directory
cd {project_path}

# Activate Python virtual environment
source .venv/bin/activate

# Only modify prompt if PS1 exists and we're in a compatible shell
if [ -n "$PS1" ] && ([ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]); then
    PS1="({metadata.name}) $PS1"
fi

# Show activation status (using ANSI green for 'activated')
echo
echo -e "\\033[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m"
echo -e "🚀 Project '{metadata.name}' \\033[32mactivated\\033[0m - You are now in a project shell"
echo -e "\\033[32m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\\033[0m"
echo
echo "✓ Directory: $(pwd)"
echo -e "✓ Virtual environment: \\033[32mactivated\\033[0m"
echo "✓ PROJECT=$PROJECT"
echo "✓ NODE_PORT=$NODE_PORT"
echo
echo "💡 This is a nested shell session. Press Ctrl+D to exit and return to your original shell."
echo -e "\\033[90mPython: $(which python)\\033[0m"
echo

"""

    # Write activation script to a temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write(activate_script)
        temp_script = f.name

    try:
        # Start user's shell in the project directory with our activation script
        if user_shell == "zsh":
            # For zsh, create a wrapper script that sources both user config and our setup
            wrapper_script = f"""#!/bin/zsh
# Source user's zsh config first
source ~/.zshrc 2>/dev/null || true

# Then source our project activation
source {temp_script}

# Start interactive zsh
exec zsh -i
"""
            temp_wrapper = temp_script + "_wrapper.zsh"
            with Path(temp_wrapper).open('w') as f:
                f.write(wrapper_script)
            
            subprocess.run(
                [user_shell, temp_wrapper],
                cwd=project_path,
                check=False,
            )
            
            # Clean up wrapper script
            Path(temp_wrapper).unlink(missing_ok=True)
            
        elif user_shell == "bash":
            # For bash, use --rcfile
            subprocess.run(
                ["bash", "--rcfile", temp_script],
                cwd=project_path,
                check=False,
            )
        else:
            # For other shells, just run them normally
            subprocess.run(
                [user_shell],
                cwd=project_path,
                check=False,
            )
    finally:
        # Clean up temp file
        Path(temp_script).unlink(missing_ok=True)


@app.command()
def deactivate() -> None:
    """🔴 Deactivate current claudette project (exit shell)."""
    console.print("[yellow]💡 To deactivate the current project:[/yellow]")
    console.print("[cyan]Press Ctrl+D[/cyan] [dim](recommended - won't close terminal)[/dim]")
    console.print("[dim]Or type 'exit' (may close your terminal/tmux)[/dim]")


@app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def shell(
    ctx: typer.Context,
) -> None:
    """🐚 Drop into Docker container shell or run a command.

    Interactive shell mode:
        clo shell                  # Enter interactive shell

    Command execution mode:
        clo shell -- ls -la          # Run a command and exit
        clo shell -- superset db upgrade
        clo shell -- bash -c "echo 'Hello' && ls"
        clo shell -- python --version

    Use '--' to separate shell command from arguments to run in container.
    Note: Project must be activated or you must be in a project directory.
    """
    # Get command arguments from context
    command_args = ctx.args if ctx.args else []

    # Try to detect current project
    project = os.environ.get("PROJECT")
    if not project:
        cwd = Path.cwd()
        if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
            project = cwd.name
        else:
            console.print("[red]❌ Not in a claudette project directory[/red]")
            console.print("[dim]Use: claudette activate <project-name> first[/dim]")
            console.print("[dim]Or run from within a project directory[/dim]")
            raise typer.Exit(1)

    # Resolve project path
    project_path = _resolve_project_path(project)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Check if project is frozen - shell needs Docker running
    if not _ensure_project_thawed(project):
        console.print("[yellow]⚠️  Shell access may be limited without dependencies[/yellow]")

    # Show appropriate message based on mode
    if command_args:
        console.print(
            f"[green]🚀 Running command in Superset container for project: {project}[/green]"
        )
        console.print(f"[dim]Command: {' '.join(command_args)}[/dim]")
    else:
        console.print(f"[green]🚀 Connecting to Superset container for project: {project}[/green]")
        console.print("[dim]Dropping you into the main Superset container...[/dim]")

    # Check if containers are running
    if not _is_docker_running(metadata.name):
        console.print("[yellow]⚠️  Docker containers not running[/yellow]")
        console.print("[dim]Starting containers first...[/dim]")

        # Start containers
        start_cmd = [
            "docker-compose",
            "-p",
            metadata.name,
            "-f",
            "docker-compose-light.yml",
            "up",
            "-d",
        ]
        env = {**os.environ, "NODE_PORT": str(metadata.port)}

        try:
            run_cmd.run(
                start_cmd, cwd=project_path, env=env, description="Starting Docker containers"
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Failed to start containers: {e.returncode}[/red]")
            raise typer.Exit(e.returncode) from e

    # Build docker exec command based on mode
    if command_args:
        # Command execution mode - use -T flag for non-interactive
        exec_cmd = [
            "docker-compose",
            "-p",
            metadata.name,
            "-f",
            "docker-compose-light.yml",
            "exec",
            "-T",  # Disable pseudo-TTY allocation for command execution
            "superset-light",
        ] + command_args
    else:
        # Interactive shell mode - use user's preferred shell if available in container
        user_shell, _ = get_user_shell()
        # Try to use user's shell, but fall back to bash if not available in container
        container_shell = f"/bin/{user_shell}" if user_shell in ["bash", "zsh", "sh"] else "/bin/bash"
        
        exec_cmd = [
            "docker-compose",
            "-p",
            metadata.name,
            "-f",
            "docker-compose-light.yml",
            "exec",
            "superset-light",
            container_shell,
        ]

    env = {**os.environ, "NODE_PORT": str(metadata.port)}

    if not command_args:
        console.print("[dim]Use 'exit' or Ctrl+D to leave the container[/dim]")

    try:
        result = subprocess.run(
            exec_cmd,
            cwd=project_path,
            env=env,
            check=False,  # Don't raise on non-zero exit (normal when user exits)
        )
        # For command mode, exit with the same code as the command
        if command_args:
            raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        if not command_args:
            console.print("\n[dim]Exited container shell[/dim]")
        else:
            console.print("\n[yellow]Command interrupted[/yellow]")
            raise typer.Exit(130) from None  # Standard exit code for SIGINT


@app.command(context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def psql(
    ctx: typer.Context,
) -> None:
    """🐘 Connect to PostgreSQL database or run SQL commands.

    Interactive psql mode:
        clo psql                           # Enter psql shell

    Command execution mode:
        clo psql -- -c "SELECT * FROM ab_user LIMIT 5;"
        clo psql -- -c "\\dt"              # List all tables
        clo psql -- -c "\\l"               # List databases
        clo psql -- -f script.sql         # Run SQL file

    Use '--' to separate psql command from arguments to pass to psql.
    Note: Project must be activated or you must be in a project directory.
    """
    # Get command arguments from context
    command_args = ctx.args if ctx.args else []

    # Try to detect current project
    project = os.environ.get("PROJECT")
    if not project:
        cwd = Path.cwd()
        if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
            project = cwd.name
        else:
            console.print("[red]❌ Not in a claudette project directory[/red]")
            console.print("[dim]Use: claudette activate <project-name> first[/dim]")
            console.print("[dim]Or run from within a project directory[/dim]")
            raise typer.Exit(1)

    # Resolve project path
    project_path = _resolve_project_path(project)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Check if project is frozen - psql needs Docker running
    if not _ensure_project_thawed(project):
        console.print("[yellow]⚠️  Database access may be limited without dependencies[/yellow]")

    # Show appropriate message based on mode
    if command_args:
        console.print(f"[green]🐘 Running SQL command for project: {project}[/green]")
        console.print(f"[dim]Arguments: {' '.join(command_args)}[/dim]")
    else:
        console.print(f"[green]🐘 Connecting to PostgreSQL for project: {project}[/green]")
        console.print("[dim]Database: superset_light | User: superset[/dim]")

    # Check if containers are running
    if not _is_docker_running(metadata.name):
        console.print("[yellow]⚠️  Docker containers not running[/yellow]")
        console.print("[dim]Starting containers first...[/dim]")

        # Start containers
        start_cmd = [
            "docker-compose",
            "-p",
            metadata.name,
            "-f",
            "docker-compose-light.yml",
            "up",
            "-d",
        ]
        env = {**os.environ, "NODE_PORT": str(metadata.port)}
        try:
            run_cmd.run(
                start_cmd, cwd=project_path, env=env, description="Starting Docker containers"
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Failed to start containers: {e.returncode}[/red]")
            raise typer.Exit(e.returncode) from e

    # Build docker exec command for psql
    base_cmd = [
        "docker-compose",
        "-p",
        metadata.name,
        "-f",
        "docker-compose-light.yml",
        "exec",
    ]

    # Add -T flag for non-interactive if running a command
    if command_args:
        base_cmd.append("-T")

    # Target the db-light container and run psql
    exec_cmd = (
        base_cmd
        + [
            "db-light",
            "psql",
            "-U",
            "superset",
            "-d",
            "superset_light",
        ]
        + command_args
    )

    env = {**os.environ, "NODE_PORT": str(metadata.port)}

    if not command_args:
        console.print("[dim]Type \\q to exit, \\? for help[/dim]")

    try:
        result = subprocess.run(
            exec_cmd,
            cwd=project_path,
            env=env,
            check=False,  # Don't raise on non-zero exit
        )
        # For command mode, exit with the same code as psql
        if command_args:
            raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        if not command_args:
            console.print("\n[dim]Exited psql[/dim]")
        else:
            console.print("\n[yellow]SQL command interrupted[/yellow]")
            raise typer.Exit(130) from None  # Standard exit code for SIGINT


@app.command()
def docker(
    ctx: typer.Context,  # noqa: ARG001
    args: List[str] = typer.Argument(None, help="Arguments to pass to docker-compose"),
) -> None:
    """🐳 Run docker-compose with project settings."""
    # Get current project
    cwd = Path.cwd()
    if len(cwd.parts) < 2 or cwd.parts[-2] != settings.worktree_base.name:
        console.print("[red]Not in a claudette project directory[/red]")
        raise typer.Exit(1)

    # Load metadata
    project_name = cwd.name
    try:
        metadata = ProjectMetadata.load(project_name, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project_name}[/red]")
        raise typer.Exit(1) from None

    # Check if project is frozen - Docker needs dependencies
    if not _ensure_project_thawed(project_name):
        console.print("[yellow]⚠️  Docker may not work properly without dependencies[/yellow]")

    # Run docker-compose
    env = {**os.environ, "NODE_PORT": str(metadata.port)}

    # Show port info if running 'up' or 'ps' commands
    if args and (args[0] in ["up", "ps", "logs"]):
        console.print(f"[dim]Using NODE_PORT={metadata.port} for container mapping[/dim]")

    cmd = [
        "docker-compose",
        "-p",
        metadata.name,
        "-f",
        "docker-compose-light.yml",
    ] + (args or [])

    try:
        run_cmd.run(cmd, env=env, description="Running docker-compose")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Docker command failed with exit code {e.returncode}[/red]")
        console.print("[dim]Run with more verbosity to see details, or check Docker logs[/dim]")
        raise typer.Exit(e.returncode) from e


@app.command()
def claude(
    ctx: typer.Context,  # noqa: ARG001
    args: List[str] = typer.Argument(None, help="Arguments to pass to claude"),
) -> None:
    """🤖 Run claude with project context (sets CWD based on $PROJECT if available).

    Passes all arguments through to claude. If $PROJECT is set, changes to that
    project's directory before running claude.

    Examples:
        claudette claude              # Launch claude
        claudette claude code         # Launch claude code editor
        claudette claude chat         # Launch claude chat
    """
    # Check if PROJECT env var is set
    project_name = os.environ.get("PROJECT")
    cwd = Path.cwd()

    if project_name:
        # Change to project directory
        project_path = _resolve_project_path(project_name)
        os.chdir(project_path)
        cwd = project_path
    else:
        # No PROJECT set, ask user to activate a project
        console.print("[red]❌ No project activated[/red]")
        console.print("[dim]Please activate a project first:[/dim]")
        console.print("[cyan]claudette activate <project-name>[/cyan]")
        raise typer.Exit(1)

    # Pass through to claude with all arguments
    subprocess.run(["claude"] + (args or []), cwd=cwd)


@app.command()
def nuke_db(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """💣 Nuke the PostgreSQL database volume for a project.

    This will completely remove all data in the PostgreSQL database for the project.
    Useful when you need a fresh database state.

    The volume name is: {project}_db_home_light
    """
    # Determine project
    if not project:
        # Check if PROJECT env var is set
        project = os.environ.get("PROJECT")
        if not project:
            # Try to detect from current directory
            cwd = Path.cwd()
            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                project = cwd.name
            else:
                console.print(
                    "[red]❌ No project specified and not in a claudette project directory[/red]"
                )
                console.print("[dim]Use: claudette nuke-db <project-name>[/dim]")
                console.print(
                    "[dim]Or: activate a project first with 'claudette activate <project-name>'[/dim]"
                )
                raise typer.Exit(1)

    # Resolve and verify project exists
    project_path = _resolve_project_path(project)

    # Load metadata to ensure it's a valid project
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Docker volume name
    volume_name = f"{project}_db_home_light"

    if not force:
        console.print(
            "\n[red]⚠️  WARNING: This will PERMANENTLY DELETE all data in the PostgreSQL database![/red]"
        )
        console.print(f"[yellow]Project: {project}[/yellow]")
        console.print(f"[yellow]Volume: {volume_name}[/yellow]")
        console.print("\n[dim]This action cannot be undone.[/dim]")
        confirm = typer.confirm("\nAre you sure you want to nuke the database?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    with console.status(f"[yellow]Nuking database for {project}...[/yellow]") as status:
        # First, stop any running containers using this volume
        status.update("Stopping Docker containers...")
        run_cmd.run(
            [
                "docker-compose",
                "-p",
                project,
                "-f",
                "docker-compose-light.yml",
                "down",
            ],
            cwd=project_path,
            env={**os.environ, "NODE_PORT": str(metadata.port)},
            check=False,  # Don't fail if containers aren't running
            quiet=True,
        )

        # Remove the volume
        status.update(f"Removing volume {volume_name}...")
        try:
            run_cmd.run(
                ["docker", "volume", "rm", volume_name],
                check=True,
                description=f"Removing volume {volume_name}",
            )
            console.print("\n[green]✅ Database nuked successfully![/green]")
            console.print(f"[dim]Volume {volume_name} has been removed.[/dim]")
            console.print(
                "\n[yellow]Next step:[/yellow] Run 'claudette docker up' to create a fresh database."
            )
        except subprocess.CalledProcessError:
            console.print(f"\n[red]❌ Failed to remove volume {volume_name}[/red]")
            console.print("[dim]The volume might not exist or might be in use.[/dim]")
            console.print("\n[yellow]Try:[/yellow]")
            console.print("  1. Make sure Docker is running")
            console.print("  2. Run 'claudette docker down' first")
            console.print(f"  3. Check if volume exists: docker volume ls | grep {volume_name}")
            raise typer.Exit(1) from None


@app.command()
def freeze(
    project: str = typer.Argument(..., help="Project name to freeze"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """🧊 Freeze a project to save disk space by removing node_modules and .venv.

    This removes the project's dependencies but preserves all code and git history.
    The project can be quickly restored with 'claudette thaw'.

    Saves approximately 3GB per project.
    """
    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    project_path = metadata.path

    if not project_path.exists():
        console.print(f"[red]Project directory not found: {project_path}[/red]")
        raise typer.Exit(1)

    # Check if already frozen
    if metadata.frozen:
        console.print(f"[yellow]Project '{project}' is already frozen[/yellow]")
        raise typer.Exit(0)

    # Check if Docker is running
    if _is_docker_running(project):
        console.print(f"[red]Cannot freeze project '{project}' while Docker is running[/red]")
        console.print("[dim]Run 'claudette docker down' first[/dim]")
        raise typer.Exit(1)

    # Calculate space to be saved
    node_modules_path = project_path / "node_modules"
    superset_node_modules = project_path / "superset-frontend" / "node_modules"
    venv_path = project_path / ".venv"

    total_size = 0
    paths_to_remove = []

    if node_modules_path.exists():
        size_mb = sum(f.stat().st_size for f in node_modules_path.rglob("*") if f.is_file()) / (
            1024 * 1024
        )
        total_size += size_mb
        paths_to_remove.append((node_modules_path, size_mb))

    if superset_node_modules.exists():
        size_mb = sum(f.stat().st_size for f in superset_node_modules.rglob("*") if f.is_file()) / (
            1024 * 1024
        )
        total_size += size_mb
        paths_to_remove.append((superset_node_modules, size_mb))

    if venv_path.exists():
        size_mb = sum(f.stat().st_size for f in venv_path.rglob("*") if f.is_file()) / (1024 * 1024)
        total_size += size_mb
        paths_to_remove.append((venv_path, size_mb))

    if not paths_to_remove:
        console.print(f"[yellow]No dependencies to freeze in project '{project}'[/yellow]")
        # Still mark as frozen for consistency
        metadata.frozen = True
        metadata.save(settings.claudette_home)
        raise typer.Exit(0)

    # Show what will be removed
    console.print(f"\n[cyan]Project: {project}[/cyan]")
    console.print(f"[cyan]Space to be freed: {total_size:.1f} MB[/cyan]\n")
    console.print("Will remove:")
    for path, size_mb in paths_to_remove:
        console.print(f"  • {path.name} ({size_mb:.1f} MB)")

    if not force:
        confirm = typer.confirm("\nProceed with freezing?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Remove the directories
    with console.status("[yellow]Freezing project...[/yellow]") as status:
        import shutil

        for path, _ in paths_to_remove:
            status.update(f"Removing {path.name}...")
            try:
                shutil.rmtree(path)
            except Exception as e:
                console.print(f"[red]Error removing {path}: {e}[/red]")

        # Update metadata
        status.update("Updating metadata...")
        metadata.frozen = True
        metadata.save(settings.claudette_home)

    console.print(f"[green]✅ Project '{project}' frozen successfully![/green]")
    console.print(f"[green]Freed {total_size:.1f} MB of disk space[/green]")
    console.print(f"\n[dim]To restore dependencies, run: claudette thaw {project}[/dim]")


@app.command()
def thaw(
    project: str = typer.Argument(..., help="Project name to thaw"),
) -> None:
    """🔥 Thaw a frozen project by restoring its dependencies.

    This restores node_modules and .venv for a frozen project.
    Uses npm ci for fast, reproducible installs.
    """
    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    project_path = metadata.path

    if not project_path.exists():
        console.print(f"[red]Project directory not found: {project_path}[/red]")
        raise typer.Exit(1)

    # Check if already thawed
    if not metadata.frozen:
        console.print(f"[yellow]Project '{project}' is not frozen[/yellow]")
        raise typer.Exit(0)

    console.print(f"[cyan]Thawing project: {project}[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Restoring dependencies...", total=None)

        # Restore Python virtual environment
        progress.update(task, description="Creating Python virtual environment...")
        venv_path = project_path / ".venv"
        if not venv_path.exists():
            try:
                run_cmd.run(
                    ["uv", "venv", ".venv"],
                    cwd=project_path,
                    description="Creating virtual environment",
                )

                # Install Python dependencies
                progress.update(task, description="Installing Python dependencies...")
                requirements_files = [
                    project_path / "requirements.txt",
                    project_path / "requirements" / "base.txt",
                    project_path / "requirements" / "development.txt",
                ]

                for req_file in requirements_files:
                    if req_file.exists():
                        run_cmd.run(
                            ["uv", "pip", "install", "-r", str(req_file)],
                            cwd=project_path,
                            env={**os.environ, "VIRTUAL_ENV": str(venv_path)},
                            description=f"Installing from {req_file.name}",
                        )

                # Install editable package
                if (project_path / "setup.py").exists():
                    run_cmd.run(
                        ["uv", "pip", "install", "-e", "."],
                        cwd=project_path,
                        env={**os.environ, "VIRTUAL_ENV": str(venv_path)},
                        description="Installing package in editable mode",
                    )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to restore Python environment: {e}[/red]")
                raise typer.Exit(1) from None

        # Restore node_modules
        node_modules_path = project_path / "node_modules"
        superset_frontend = project_path / "superset-frontend"

        if not node_modules_path.exists() and (project_path / "package.json").exists():
            progress.update(task, description="Installing npm dependencies (root)...")
            try:
                # Use npm ci for faster, reproducible installs
                run_cmd.run(
                    ["npm", "ci"],
                    cwd=project_path,
                    description="Installing npm dependencies",
                )
            except subprocess.CalledProcessError:
                # Fall back to npm install if ci fails (no package-lock.json)
                run_cmd.run(
                    ["npm", "install"],
                    cwd=project_path,
                    description="Installing npm dependencies (fallback)",
                )

        if (
            superset_frontend.exists()
            and not (superset_frontend / "node_modules").exists()
            and (superset_frontend / "package.json").exists()
        ):
            progress.update(task, description="Installing frontend dependencies...")
            try:
                run_cmd.run(
                    ["npm", "ci"],
                    cwd=superset_frontend,
                    description="Installing frontend dependencies",
                )
            except subprocess.CalledProcessError:
                run_cmd.run(
                    ["npm", "install"],
                    cwd=superset_frontend,
                    description="Installing frontend dependencies (fallback)",
                )

        # Update metadata
        progress.update(task, description="Updating metadata...")
        metadata.frozen = False
        metadata.save(settings.claudette_home)

    console.print(f"[green]✅ Project '{project}' thawed successfully![/green]")
    console.print("[dim]Dependencies have been restored. You can now activate the project.[/dim]")


@app.command()
def deps(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
    backend_only: bool = typer.Option(
        False, "--backend-only", help="Only resync Python dependencies"
    ),
    frontend_only: bool = typer.Option(
        False, "--frontend-only", help="Only resync npm dependencies"
    ),
    nuke: bool = typer.Option(
        False, "--nuke", help="Nuclear option: remove and reinstall everything"
    ),
) -> None:
    """🔄 Resync dependencies after rebase or branch changes.

    By default, performs a quick resync by updating existing dependencies.
    Use --nuke for complete removal and reinstallation when facing conflicts.

    Examples:
        clo deps                      # Quick resync of all dependencies
        clo deps --backend-only       # Only resync Python packages
        clo deps --frontend-only      # Only resync npm packages
        clo deps --nuke              # Nuclear: remove and reinstall everything
    """
    # Determine project
    if not project:
        # Check if PROJECT env var is set
        project = os.environ.get("PROJECT")
        if not project:
            # Try to detect from current directory
            cwd = Path.cwd()
            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                project = cwd.name
            else:
                console.print(
                    "[red]❌ No project specified and not in a claudette project directory[/red]"
                )
                console.print("[dim]Use: clo deps <project-name>[/dim]")
                console.print("[dim]Or run from within a project directory[/dim]")
                raise typer.Exit(1)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    project_path = metadata.path

    if not project_path.exists():
        console.print(f"[red]Project directory not found: {project_path}[/red]")
        raise typer.Exit(1)

    # Check if project is frozen
    if not _ensure_project_thawed(project, require_thaw=False):
        console.print("[red]❌ Project is frozen. Dependencies cannot be resynced.[/red]")
        console.print(f"[dim]Thaw first with: clo thaw {project}[/dim]")
        raise typer.Exit(1)

    # Validate exclusive options
    if backend_only and frontend_only:
        console.print("[red]❌ Cannot use --backend-only and --frontend-only together[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]🔄 Resyncing dependencies for {project}[/bold cyan]")
    if nuke:
        console.print(
            "[yellow]⚠️  Using nuclear option: complete removal and reinstallation[/yellow]"
        )
    else:
        console.print("[green]Using quick resync: updating existing dependencies[/green]")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Resyncing dependencies...", total=None)

        # Backend (Python) dependencies
        if not frontend_only:
            venv_path = project_path / ".venv"

            if nuke and venv_path.exists():
                progress.update(task, description="Removing Python virtual environment...")
                console.print(
                    "[dim]Removing Python virtual environment (this may take a moment)...[/dim]"
                )
                import shutil

                shutil.rmtree(venv_path)
                console.print("[yellow]🗑️  Removed .venv directory[/yellow]")

            # Create venv if it doesn't exist (for nuke mode or missing venv)
            if not venv_path.exists():
                progress.update(task, description="Creating Python virtual environment...")
                run_cmd.run(
                    ["uv", "venv", "-p", settings.python_version],
                    cwd=project_path,
                    description="Creating Python virtual environment",
                )

            # Install Python dependencies
            progress.update(task, description="Installing Python dependencies...")

    # Temporarily exit Progress context for uv operations to avoid spinner conflicts
    if not frontend_only:
        # Install requirements/development.txt (standard for Superset)
        dev_requirements = project_path / "requirements" / "development.txt"
        if dev_requirements.exists():
            try:
                console.print(f"[dim]Installing from {dev_requirements.name}...[/dim]")
                run_cmd.run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "-r",
                        str(dev_requirements),
                        "--python",
                        str(venv_path / "bin" / "python"),
                    ],
                    cwd=project_path,
                    description=f"Installing from {dev_requirements.name}",
                )
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]⚠️  Failed to install from {dev_requirements.name}: {e}[/yellow]"
                )
        else:
            console.print("[yellow]⚠️  No requirements/development.txt found[/yellow]")

        # Install editable package
        if (project_path / "setup.py").exists():
            try:
                console.print("[dim]Installing package in editable mode...[/dim]")
                run_cmd.run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "-e",
                        ".",
                        "--python",
                        str(venv_path / "bin" / "python"),
                    ],
                    cwd=project_path,
                    description="Installing package in editable mode",
                )
            except subprocess.CalledProcessError as e:
                console.print(
                    f"[yellow]⚠️  Failed to install package in editable mode: {e}[/yellow]"
                )

        console.print("[green]✅ Python dependencies resynced[/green]")

    # Resume Progress context for frontend dependencies
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Continuing resync...", total=None)

        # Frontend (npm) dependencies setup
        if not backend_only:
            # Root npm dependencies
            root_node_modules = project_path / "node_modules"
            root_package_json = project_path / "package.json"

            if root_package_json.exists() and nuke:
                # Remove node_modules and package-lock.json
                if root_node_modules.exists():
                    progress.update(task, description="Removing root node_modules...")
                    console.print(
                        "[dim]Removing root node_modules (this may take a moment)...[/dim]"
                    )
                    import shutil

                    shutil.rmtree(root_node_modules)
                    console.print("[yellow]🗑️  Removed root node_modules[/yellow]")

                root_lock = project_path / "package-lock.json"
                if root_lock.exists():
                    root_lock.unlink()
                    console.print("[yellow]🗑️  Removed root package-lock.json[/yellow]")

            # Frontend npm nuke preparation
            superset_frontend = project_path / "superset-frontend"
            frontend_node_modules = superset_frontend / "node_modules"
            frontend_package_json = superset_frontend / "package.json"

            if frontend_package_json.exists() and nuke:
                # Remove node_modules and package-lock.json
                if frontend_node_modules.exists():
                    progress.update(task, description="Removing frontend node_modules...")
                    console.print(
                        "[dim]Removing frontend node_modules (this may take a moment)...[/dim]"
                    )
                    import shutil

                    shutil.rmtree(frontend_node_modules)
                    console.print("[yellow]🗑️  Removed frontend node_modules[/yellow]")

                frontend_lock = superset_frontend / "package-lock.json"
                if frontend_lock.exists():
                    frontend_lock.unlink()
                    console.print("[yellow]🗑️  Removed frontend package-lock.json[/yellow]")

    # Temporarily exit Progress context for npm operations to avoid spinner conflicts
    if not backend_only:
        root_package_json = project_path / "package.json"
        if root_package_json.exists():
            # Install root dependencies
            console.print("[dim]Installing root npm dependencies...[/dim]")
            if nuke and (project_path / "package-lock.json").exists():
                # Use npm ci for clean installs after nuke (reproducible from lockfile)
                run_cmd.run(
                    ["npm", "ci"],
                    cwd=project_path,
                    description="Installing root npm dependencies (clean)",
                )
            else:
                # Use npm install for normal refresh (updates to compatible versions)
                run_cmd.run(
                    ["npm", "install"],
                    cwd=project_path,
                    description="Installing root npm dependencies (refresh)",
                )

        # Frontend npm dependencies
        superset_frontend = project_path / "superset-frontend"
        frontend_node_modules = superset_frontend / "node_modules"
        frontend_package_json = superset_frontend / "package.json"

        if frontend_package_json.exists():
            # Install frontend dependencies
            console.print("[dim]Installing frontend npm dependencies...[/dim]")
            if nuke and (superset_frontend / "package-lock.json").exists():
                # Use npm ci for clean installs after nuke (reproducible from lockfile)
                run_cmd.run(
                    ["npm", "ci"],
                    cwd=superset_frontend,
                    description="Installing frontend npm dependencies (clean)",
                )
            else:
                # Use npm install for normal refresh (updates to compatible versions)
                run_cmd.run(
                    ["npm", "install"],
                    cwd=superset_frontend,
                    description="Installing frontend npm dependencies (refresh)",
                )

            # Run npm prune in nuke mode to clean up package/plugin build artifacts
            if nuke:
                console.print(
                    "[dim]Running npm prune to clean up package/plugin build artifacts and dependencies...[/dim]"
                )
                try:
                    run_cmd.run(
                        ["npm", "run", "prune"],
                        cwd=superset_frontend,
                        description="Cleaning up package/plugin build artifacts",
                        check=False,  # Don't fail if prune command fails
                    )
                    console.print("[green]✅ Package/plugin cleanup completed[/green]")
                except subprocess.CalledProcessError as e:
                    console.print(f"[yellow]⚠️  npm run prune failed, but continuing: {e}[/yellow]")

        console.print("[green]✅ Frontend dependencies resynced[/green]")

    console.print(
        f"\n[bold green]🎉 Dependencies for '{project}' have been resynced successfully![/bold green]"
    )

    if nuke:
        console.print(
            "[dim]Nuclear resync complete. All dependencies were reinstalled from scratch.[/dim]"
        )
    else:
        console.print(
            "[dim]Quick resync complete. Use --nuke if you still have dependency conflicts.[/dim]"
        )


@app.command()
def pr(
    action: str = typer.Argument(..., help="Action: 'link', 'clear', or 'open'"),
    pr_number: Optional[int] = typer.Argument(None, help="PR number to link (for 'link' action)"),
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project name (optional if in project dir)"
    ),
) -> None:
    """🔗 Link or manage GitHub PR associations for projects.

    Examples:
        clo pr link 1234                 # Link current project to PR #1234
        clo pr link 1234 --project rison # Link rison project to PR #1234
        clo pr clear                     # Remove PR link from current project
        clo pr open                      # Open linked PR in browser
        clo pr open --project rison      # Open rison's linked PR in browser
    """
    # Determine project
    if not project:
        # Check if PROJECT env var is set
        project = os.environ.get("PROJECT")
        if not project:
            # Try to detect from current directory
            cwd = Path.cwd()
            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                project = cwd.name
            else:
                console.print(
                    "[red]❌ No project specified and not in a claudette project directory[/red]"
                )
                console.print("[dim]Use: clo pr link 1234 --project <project-name>[/dim]")
                raise typer.Exit(1)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    if action == "link":
        if pr_number is None:
            console.print("[red]PR number is required for 'link' action[/red]")
            console.print("[dim]Usage: clo pr link <pr_number>[/dim]")
            raise typer.Exit(1)

        # Update metadata with PR number
        metadata.pr_number = pr_number
        metadata.save(settings.claudette_home)

        console.print(f"[green]✅ Linked project '{project}' to PR #{pr_number}[/green]")

    elif action == "clear":
        if metadata.pr_number is None:
            console.print(f"[yellow]Project '{project}' has no PR association to clear[/yellow]")
            raise typer.Exit(0)

        old_pr = metadata.pr_number
        metadata.pr_number = None
        metadata.save(settings.claudette_home)

        console.print(
            f"[green]✅ Removed PR #{old_pr} association from project '{project}'[/green]"
        )

    elif action == "open":
        if metadata.pr_number is None:
            console.print(f"[yellow]Project '{project}' has no PR linked[/yellow]")
            console.print(f"[dim]Use: clo pr link <number> --project {project}[/dim]")
            raise typer.Exit(1)

        # Construct GitHub URL - assuming apache/superset repository
        pr_url = f"https://github.com/apache/superset/pull/{metadata.pr_number}"
        console.print(f"[cyan]Opening PR #{metadata.pr_number} in browser...[/cyan]")
        console.print(f"[dim]{pr_url}[/dim]")

        try:
            import platform
            import subprocess

            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["open", pr_url], check=True)
            elif system == "Linux":
                subprocess.run(["xdg-open", pr_url], check=True)
            elif system == "Windows":
                subprocess.run(["start", pr_url], shell=True, check=True)
            else:
                console.print("[yellow]Could not detect system to open browser[/yellow]")
                console.print(f"[dim]Please manually open: {pr_url}[/dim]")
        except subprocess.CalledProcessError:
            console.print("[red]❌ Failed to open browser[/red]")
            console.print(f"[dim]Please manually open: {pr_url}[/dim]")

    else:
        console.print(f"[red]Unknown action '{action}'. Use 'link', 'clear', or 'open'[/red]")
        raise typer.Exit(1)


@app.command()
def ports(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
) -> None:
    """🔌 Show port information and check if services are accessible."""
    # Determine project
    if not project:
        # Check if PROJECT env var is set
        project = os.environ.get("PROJECT")
        if not project:
            # Try to detect from current directory
            cwd = Path.cwd()
            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                project = cwd.name
            else:
                console.print(
                    "[red]❌ No project specified and not in a claudette project directory[/red]"
                )
                raise typer.Exit(1)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    console.print(f"\n[bold cyan]🔌 Port Configuration for {project}[/bold cyan]\n")

    # Show configured port
    console.print(f"[green]Configured port:[/green] {metadata.port}")
    console.print(f"[dim]External URL: http://localhost:{metadata.port}[/dim]")
    console.print("[dim]Container internal: http://localhost:9000 (webpack-dev-server)[/dim]\n")

    # Check if Docker containers are running
    docker_running = _is_docker_running(metadata.name)
    if docker_running:
        console.print("[green]✅ Docker containers are running[/green]")

        # Show actual port mappings for the node container specifically
        console.print("\n[yellow]Host-accessible ports:[/yellow]")
        cmd = ["docker", "port", f"{metadata.name}-superset-node-light-1"]
        result = run_cmd.run(cmd, capture=True, quiet=True, check=False)
        if result.returncode == 0 and result.stdout:
            # Parse docker port output (format: "9000/tcp -> 0.0.0.0:9012")
            for line in result.stdout.strip().split("\n"):
                if "->" in line:
                    container_port, host_mapping = line.split(" -> ")
                    host_port = host_mapping.split(":")[-1]
                    console.print(f"  • Container port {container_port} → localhost:{host_port}")
        else:
            console.print(f"  • Expected: localhost:{metadata.port} → container:9000")
            console.print("  [dim](Could not verify actual mapping)[/dim]")

        # Test connectivity to the port
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(("localhost", metadata.port))
            if result == 0:
                console.print(f"\n[green]✅ Port {metadata.port} is accessible[/green]")
                console.print(f"[dim]Try: claudette open {project}[/dim]")
            else:
                console.print(f"\n[red]❌ Port {metadata.port} is not responding[/red]")
                console.print("[yellow]Possible issues:[/yellow]")
                console.print("  • Container port mapping may be incorrect")
                console.print("  • Service inside container may not be running")
                console.print("  • Firewall may be blocking the port")
                console.print("\n[dim]Check logs: claudette docker logs superset-node-light[/dim]")
        finally:
            sock.close()
    else:
        console.print("[red]❌ Docker containers are not running[/red]")
        console.print("[dim]Start them with: claudette docker up -d[/dim]")


@app.command()
def open(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
) -> None:
    """🌐 Open Superset in your browser at the project's port."""
    # Determine project
    if not project:
        # Check if PROJECT env var is set
        project = os.environ.get("PROJECT")
        if not project:
            # Try to detect from current directory
            cwd = Path.cwd()
            if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
                project = cwd.name
            else:
                console.print(
                    "[red]❌ No project specified and not in a claudette project directory[/red]"
                )
                console.print("[dim]Use: claudette open <project-name>[/dim]")
                console.print(
                    "[dim]Or: activate a project first with 'claudette activate <project-name>'[/dim]"
                )
                raise typer.Exit(1)

    # Load metadata to get port
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Build URL
    url = f"http://localhost:{metadata.port}"

    # Detect platform and open browser
    import platform

    system = platform.system()

    console.print(f"[green]🌐 Opening {url} in your browser...[/green]")

    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", url], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", url], check=True)
        elif system == "Windows":
            subprocess.run(["start", url], shell=True, check=True)
        else:
            console.print(f"[yellow]⚠️  Unable to open browser on {system}[/yellow]")
            console.print(f"[dim]Please manually open: {url}[/dim]")
    except subprocess.CalledProcessError:
        console.print("[red]❌ Failed to open browser[/red]")
        console.print(f"[dim]Please manually open: {url}[/dim]")
        raise typer.Exit(1) from None


@app.command()
def status(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
) -> None:
    """📊 Show detailed status of a claudette project.

    Shows:
    - Project metadata (port, path)
    - Git status (branch, uncommitted changes)
    - Docker service status
    - Python venv status
    - Recent git commits
    """
    # Determine project
    if not project:
        cwd = Path.cwd()
        if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
            project = cwd.name
        else:
            console.print("[red]❌ Not in a claudette project directory[/red]")
            console.print("[dim]Use: claudette status <project-name>[/dim]")
            raise typer.Exit(1)

    # Resolve and verify project exists
    project_path = _resolve_project_path(project)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Create status panel
    console.print(f"\n[bold blue]📊 Project Status: {metadata.name}[/bold blue]\n")

    # Basic info
    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Path", str(project_path))
    table.add_row("Port", str(metadata.port))
    table.add_row("Frontend URL", f"http://localhost:{metadata.port}")

    # Add frozen status
    if metadata.frozen:
        table.add_row("Status", "[cyan]🧊 Frozen[/cyan] (dependencies removed)")
    else:
        table.add_row("Status", "[green]Active[/green]")

    # Add PR information if available
    if metadata.pr_number:
        table.add_row("GitHub PR", f"[magenta]#{metadata.pr_number}[/magenta]")

    console.print(table)
    console.print()

    # Git status
    console.print("[bold]Git Status:[/bold]")
    try:
        # Current branch
        branch_result = run_cmd.run(
            ["git", "branch", "--show-current"],
            cwd=project_path,
            capture=True,
            quiet=True,
        )
        current_branch = branch_result.stdout.strip()
        console.print(f"  Branch: [cyan]{current_branch}[/cyan]")

        # Uncommitted changes
        status_result = run_cmd.run(
            ["git", "status", "--porcelain"],
            cwd=project_path,
            capture=True,
            quiet=True,
        )
        if status_result.stdout.strip():
            changes = status_result.stdout.strip().split("\n")
            console.print(f"  Changes: [yellow]{len(changes)} uncommitted files[/yellow]")
            # Show first 5 changed files
            for change in changes[:5]:
                console.print(f"    [dim]{change}[/dim]")
            if len(changes) > 5:
                console.print(f"    [dim]... and {len(changes) - 5} more[/dim]")
        else:
            console.print("  Changes: [green]Working tree clean[/green]")

        # Recent commits
        commits_result = run_cmd.run(
            ["git", "log", "--oneline", "-5"],
            cwd=project_path,
            capture=True,
            quiet=True,
        )
        if commits_result.stdout.strip():
            console.print("  Recent commits:")
            for line in commits_result.stdout.strip().split("\n"):
                console.print(f"    [dim]{line}[/dim]")
    except Exception as e:
        console.print(f"  [red]Error getting git status: {e}[/red]")

    console.print()

    # Service status
    console.print("[bold]Service Status:[/bold]")

    # Docker
    docker_running = _is_docker_running(metadata.name)
    if docker_running:
        console.print("  Docker: [green]● Running[/green]")
        # Show running containers
        try:
            containers_result = run_cmd.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"label=com.docker.compose.project={metadata.name}",
                    "--format",
                    "table {{.Names}}\t{{.Status}}",
                ],
                capture=True,
                quiet=True,
            )
            if containers_result.stdout.strip():
                for line in containers_result.stdout.strip().split("\n")[1:]:  # Skip header
                    console.print(f"    [dim]{line}[/dim]")
        except Exception:
            pass
    else:
        console.print("  Docker: [red]○ Stopped[/red]")
        console.print("    [dim]Run 'claudette docker up' to start services[/dim]")

    # Python venv
    venv_path = project_path / ".venv"
    if metadata.frozen:
        console.print("  Python venv: [cyan]🧊 Frozen[/cyan]")
        console.print(f"    [dim]Run 'claudette thaw {project}' to restore[/dim]")
    elif venv_path.exists():
        console.print("  Python venv: [green]✓ Installed[/green]")
        # Check if activated
        if os.environ.get("VIRTUAL_ENV") == str(venv_path):
            console.print("    [dim]Status: [green]Activated[/green][/dim]")
        else:
            console.print(f"    [dim]Status: Not activated (run 'claudette activate {project}')")
    else:
        console.print("  Python venv: [red]✗ Missing[/red]")

    # Node modules
    node_modules = project_path / "superset-frontend" / "node_modules"
    if metadata.frozen:
        console.print("  Node modules: [cyan]🧊 Frozen[/cyan]")
        console.print(f"    [dim]Run 'claudette thaw {project}' to restore[/dim]")
    elif node_modules.exists():
        console.print("  Node modules: [green]✓ Installed[/green]")
    else:
        console.print("  Node modules: [red]✗ Missing[/red]")

    console.print()


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def jest(
    ctx: typer.Context,  # noqa: ARG001
) -> None:
    """🧪 Run Jest unit tests for frontend code.

    All arguments are passed directly to Jest. Paths starting with 'superset-frontend/'
    are automatically adjusted since Jest runs from that directory.

    Examples:
        clo jest                                         # Run all tests
        clo jest src/components/Button                   # Run tests in Button directory
        clo jest Button.test.tsx                         # Run specific test file
        clo jest --watch                                 # Run in watch mode
        clo jest --coverage                              # Generate coverage report
        clo jest --testPathPattern=Button                # Pattern matching
        clo jest superset-frontend/src/components/Button # Auto-strips superset-frontend/
    """
    # Get current project
    cwd = Path.cwd()
    if len(cwd.parts) < 2 or cwd.parts[-2] != settings.worktree_base.name:
        console.print("[red]❌ Not in a claudette project directory[/red]")
        console.print("[dim]Run this command from within a project directory[/dim]")
        raise typer.Exit(1)

    project_name = cwd.name
    try:
        metadata = ProjectMetadata.load(project_name, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]❌ No metadata found for project {project_name}[/red]")
        raise typer.Exit(1) from None

    # Check if project is frozen - jest needs node_modules
    if not _ensure_project_thawed(project_name):
        console.print("[red]Cannot run tests without dependencies[/red]")
        raise typer.Exit(1)

    # Get extra arguments from context (all arguments not parsed by Typer)
    extra_args = ctx.params.get("args", []) or []
    if hasattr(ctx, "args"):
        extra_args.extend(ctx.args)

    # Process arguments to handle superset-frontend/ prefix
    processed_args = []
    for arg in extra_args:
        if arg.startswith("superset-frontend/"):
            # Strip the prefix since we're already running from that directory
            cleaned_arg = arg[len("superset-frontend/") :]
            processed_args.append(cleaned_arg)
            console.print(f"[dim]Adjusted path: {arg} → {cleaned_arg}[/dim]")
        else:
            processed_args.append(arg)

    # Build Jest command - pass all processed args through
    jest_cmd = ["npm", "run", "test", "--"] + processed_args

    # Set environment variables
    env = {
        **os.environ,
        "NODE_PORT": str(metadata.port),
        "PROJECT": metadata.name,
    }

    # Run Jest from superset-frontend directory
    frontend_dir = metadata.path / "superset-frontend"
    if not frontend_dir.exists():
        console.print("[red]❌ superset-frontend directory not found[/red]")
        console.print(f"[dim]Expected: {frontend_dir}[/dim]")
        raise typer.Exit(1)

    console.print(f"[blue]🧪 Running Jest tests for project: {metadata.name}[/blue]")
    if processed_args:
        console.print(f"[dim]Arguments: {' '.join(processed_args)}[/dim]")

    try:
        run_cmd.run(
            jest_cmd,
            cwd=frontend_dir,
            env=env,
            description="Running Jest tests",
            quiet=False,  # Show output so we can see test results!
        )
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Tests failed with exit code {e.returncode}[/red]")
        raise typer.Exit(e.returncode) from e


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def pytest(
    ctx: typer.Context,  # noqa: ARG001
    nuke: bool = typer.Option(False, "--nuke", help="Nuke and recreate the test database"),
) -> None:
    """🐍 Run pytest using Docker with automatic test database setup.

    All arguments after the options are passed directly to pytest.

    Examples:
        clo pytest                                 # Run all tests
        clo pytest tests/unit_tests/               # Run unit tests only
        clo pytest -x tests/                       # Stop on first failure
        clo pytest -v tests/unit_tests/            # Verbose output
        clo pytest --nuke tests/                   # Nuke and recreate test database
        clo pytest -k test_charts                  # Run tests matching pattern
        clo pytest --maxfail=3 tests/              # Stop after 3 failures
        clo pytest -m "not slow" tests/            # Skip slow tests

    Note: Uses docker-compose pytest-runner service which automatically:
    - Creates test database on first run
    - Reuses test environment for fast startup (~2-3 seconds)
    - Supports all standard pytest arguments
    - Streams test output in real-time
    """
    # Get current project
    cwd = Path.cwd()
    if len(cwd.parts) < 2 or cwd.parts[-2] != settings.worktree_base.name:
        console.print("[red]❌ Not in a claudette project directory[/red]")
        console.print("[dim]Run this command from within a project directory[/dim]")
        raise typer.Exit(1)

    project_name = cwd.name
    try:
        metadata = ProjectMetadata.load(project_name, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]❌ No metadata found for project {project_name}[/red]")
        raise typer.Exit(1) from None

    # Check if project is frozen - pytest needs dependencies
    if not _ensure_project_thawed(project_name):
        console.print("[red]Cannot run tests without dependencies[/red]")
        raise typer.Exit(1)

    # Build docker-compose command
    docker_cmd = [
        "docker-compose",
        "-p",
        metadata.name,
        "-f",
        "docker-compose-light.yml",
        "run",
        "--rm",
    ]

    # Set environment variables
    env = {
        **os.environ,
        "NODE_PORT": str(metadata.port),
        "PROJECT": metadata.name,
    }

    # Add nuke flag if requested
    if nuke:
        docker_cmd.extend(["-e", "FORCE_RELOAD=true"])
        console.print("[yellow]💥 Nuking and recreating test database...[/yellow]")

    # Add pytest-runner service
    docker_cmd.append("pytest-runner")

    # Get extra arguments from context (all arguments not parsed by Typer)
    extra_args = ctx.params.get("args", []) or []
    if hasattr(ctx, "args"):
        extra_args.extend(ctx.args)

    # Build pytest command - now we just pass all args directly
    pytest_cmd = ["pytest"]
    if extra_args:
        pytest_cmd.extend(extra_args)

    # Combine docker and pytest commands
    full_cmd = docker_cmd + pytest_cmd

    console.print(f"[blue]🐍 Running pytest for project: {metadata.name}[/blue]")
    if extra_args and len(extra_args) > 0:
        console.print(f"[dim]Arguments: {' '.join(extra_args)}[/dim]")
    if nuke:
        console.print("[dim]Test database will be recreated[/dim]")

    try:
        run_cmd.run(
            full_cmd,
            cwd=metadata.path,
            env=env,
            description="Running pytest in Docker",
            quiet=False,  # Show output so we can see pytest results
        )
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]❌ Tests failed with exit code {e.returncode}[/red]")
        raise typer.Exit(e.returncode) from e


def _is_docker_running(project_name: str) -> bool:
    """Check if docker containers are running for a project."""
    try:
        result = run_cmd.run(
            ["docker", "ps", "--filter", f"label=com.docker.compose.project={project_name}", "-q"],
            check=False,
            capture=True,
            quiet=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _ensure_project_thawed(project_name: str, require_thaw: bool = False) -> bool:
    """Ensure a project is thawed (not frozen) before operations that need dependencies.

    Args:
        project_name: Name of the project to check
        require_thaw: If True, thawing is required (not optional)

    Returns:
        True if project is thawed or user chose to thaw it
        False if project is frozen and user declined to thaw
    """
    try:
        metadata = ProjectMetadata.load(project_name, settings.claudette_home)
    except FileNotFoundError:
        # No metadata means not frozen
        return True

    if not metadata.frozen:
        return True

    # Project is frozen
    console.print(f"\n[yellow]⚠️  Project '{project_name}' is frozen[/yellow]")
    console.print(
        "[dim]Dependencies (node_modules and .venv) have been removed to save space.[/dim]"
    )

    if require_thaw:
        console.print("[cyan]This operation requires the project to be thawed.[/cyan]")
        confirm = typer.confirm("Would you like to thaw the project now?", default=True)
    else:
        confirm = typer.confirm("Would you like to thaw the project now?", default=False)

    if not confirm:
        if require_thaw:
            console.print("[red]Operation cancelled - project must be thawed first[/red]")
            console.print(f"[dim]Run: claudette thaw {project_name}[/dim]")
        else:
            console.print(
                "[yellow]Proceeding without thawing - some features may not work[/yellow]"
            )
        return False

    # Thaw the project inline
    console.print(f"[cyan]Thawing project: {project_name}[/cyan]")

    project_path = metadata.path

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Restoring dependencies...", total=None)

        # Restore Python virtual environment
        progress.update(task, description="Creating Python virtual environment...")
        venv_path = project_path / ".venv"
        if not venv_path.exists():
            try:
                run_cmd.run(
                    ["uv", "venv", ".venv"],
                    cwd=project_path,
                    description="Creating virtual environment",
                    quiet=True,
                )

                # Install Python dependencies
                progress.update(task, description="Installing Python dependencies...")
                requirements_files = [
                    project_path / "requirements.txt",
                    project_path / "requirements" / "base.txt",
                    project_path / "requirements" / "development.txt",
                ]

                for req_file in requirements_files:
                    if req_file.exists():
                        run_cmd.run(
                            ["uv", "pip", "install", "-r", str(req_file)],
                            cwd=project_path,
                            env={**os.environ, "VIRTUAL_ENV": str(venv_path)},
                            description=f"Installing from {req_file.name}",
                            quiet=True,
                        )

                # Install editable package
                if (project_path / "setup.py").exists():
                    run_cmd.run(
                        ["uv", "pip", "install", "-e", "."],
                        cwd=project_path,
                        env={**os.environ, "VIRTUAL_ENV": str(venv_path)},
                        description="Installing package in editable mode",
                        quiet=True,
                    )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to restore Python environment: {e}[/red]")
                return False

        # Restore node_modules
        node_modules_path = project_path / "node_modules"
        superset_frontend = project_path / "superset-frontend"

        if not node_modules_path.exists() and (project_path / "package.json").exists():
            progress.update(task, description="Installing npm dependencies (root)...")
            try:
                # Use npm ci for faster, reproducible installs
                run_cmd.run(
                    ["npm", "ci"],
                    cwd=project_path,
                    description="Installing npm dependencies",
                    quiet=True,
                )
            except subprocess.CalledProcessError:
                # Fall back to npm install if ci fails (no package-lock.json)
                run_cmd.run(
                    ["npm", "install"],
                    cwd=project_path,
                    description="Installing npm dependencies (fallback)",
                    quiet=True,
                )

        if (
            superset_frontend.exists()
            and not (superset_frontend / "node_modules").exists()
            and (superset_frontend / "package.json").exists()
        ):
            progress.update(task, description="Installing frontend dependencies...")
            try:
                run_cmd.run(
                    ["npm", "ci"],
                    cwd=superset_frontend,
                    description="Installing frontend dependencies",
                    quiet=True,
                )
            except subprocess.CalledProcessError:
                run_cmd.run(
                    ["npm", "install"],
                    cwd=superset_frontend,
                    description="Installing frontend dependencies (fallback)",
                    quiet=True,
                )

        # Update metadata
        progress.update(task, description="Updating metadata...")
        metadata.frozen = False
        metadata.save(settings.claudette_home)

    console.print(f"[green]✅ Project '{project_name}' thawed successfully![/green]")
    return True


def _branch_exists(branch_name: str) -> bool:
    """Check if a git branch exists locally or remotely in the base repository."""
    try:
        # Check local branches
        local_result = run_cmd.run(
            ["git", "branch", "--list", branch_name],
            cwd=settings.superset_base,
            check=False,
            capture=True,
            quiet=True,
        )
        if local_result.stdout.strip():
            return True

        # Check remote branches
        remote_result = run_cmd.run(
            ["git", "branch", "-r", "--list", f"origin/{branch_name}"],
            cwd=settings.superset_base,
            check=False,
            capture=True,
            quiet=True,
        )
        return bool(remote_result.stdout.strip())
    except Exception:
        return False


def _get_branch_info(branch_name: str) -> Optional[dict]:
    """Get information about a git branch (local or remote)."""
    try:
        # Try local branch first
        result = run_cmd.run(
            ["git", "log", "-1", "--format=%H|%s|%ar", branch_name],
            cwd=settings.superset_base,
            check=False,
            capture=True,
            quiet=True,
        )
        if not result.stdout.strip():
            # Try remote branch
            result = run_cmd.run(
                ["git", "log", "-1", "--format=%H|%s|%ar", f"origin/{branch_name}"],
                cwd=settings.superset_base,
                check=False,
                capture=True,
                quiet=True,
            )

        if result.stdout.strip():
            commit_hash, subject, relative_time = result.stdout.strip().split("|", 2)
            return {
                "commit_hash": commit_hash[:8],
                "subject": subject,
                "relative_time": relative_time,
            }
    except Exception:
        pass
    return None


def _suggest_branch_names(base_name: str) -> List[str]:
    """Suggest alternative branch names if the base name is taken."""
    suggestions = []
    for i in range(2, 6):  # Suggest base-name-2 through base-name-5
        candidate = f"{base_name}-{i}"
        if not _branch_exists(candidate):
            suggestions.append(candidate)
    return suggestions


def _handle_branch_conflict(
    project: str, reuse: bool, force_new: bool, name: Optional[str]
) -> tuple[str, bool]:
    """
    Handle git branch conflicts when creating a new project.

    Returns:
        tuple[str, bool]: (final_branch_name, should_create_new_branch)
    """
    # If user provided --name flag, use that instead
    if name:
        if _branch_exists(name):
            console.print(f"[red]❌ Branch '{name}' also already exists![/red]")
            raise typer.Exit(1)
        return name, True

    # If user provided automation flags, handle them
    if reuse:
        console.print(f"[yellow]♻️  Reusing existing branch '{project}'[/yellow]")
        return project, False

    if force_new:
        console.print(
            f"[yellow]⚠️  Deleting existing branch '{project}' and creating new one[/yellow]"
        )

        # First check if there's an existing worktree using this branch
        existing_worktree = settings.worktree_base / project
        if existing_worktree.exists():
            console.print(f"[dim]Removing existing worktree at {existing_worktree}[/dim]")
            try:
                run_cmd.run(
                    ["git", "worktree", "remove", project, "--force"],
                    cwd=settings.superset_base,
                    description=f"Removing existing worktree '{project}'",
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]❌ Failed to remove worktree '{project}': {e.stderr}[/red]")
                raise typer.Exit(1) from e

        # Now delete the branch
        try:
            run_cmd.run(
                ["git", "branch", "-D", project],
                cwd=settings.superset_base,
                description=f"Deleting existing branch '{project}'",
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]❌ Failed to delete branch '{project}': {e.stderr}[/red]")
            raise typer.Exit(1) from e
        return project, True

    # Interactive mode - show branch info and options
    # Check if it's local or remote
    local_exists = run_cmd.run(
        ["git", "branch", "--list", project],
        cwd=settings.superset_base,
        check=False,
        capture=True,
        quiet=True,
    ).stdout.strip()

    if local_exists:
        console.print(f"\n[red]❌ Branch '{project}' already exists locally.[/red]\n")
    else:
        console.print(
            f"\n[yellow]⚠️  Branch '{project}' exists in the remote repository.[/yellow]\n"
        )

    # Show branch information if available
    branch_info = _get_branch_info(project)
    if branch_info:
        console.print("[dim]Branch info:[/dim]")
        console.print(f"  Last commit: {branch_info['commit_hash']} - {branch_info['subject']}")
        console.print(f"  Last updated: {branch_info['relative_time']}\n")

    # Show options
    console.print("[yellow]What would you like to do?[/yellow]")
    if local_exists:
        console.print(
            "  [cyan]1.[/cyan] Use existing local branch (checkout and continue with existing git history)"
        )
    else:
        console.print(
            "  [cyan]1.[/cyan] Pull and use remote branch (creates local tracking branch from origin)"
        )
    console.print("  [cyan]2.[/cyan] Create new branch with different name")
    if local_exists:
        console.print(
            "  [cyan]3.[/cyan] DELETE existing branch and start fresh [red](⚠️  loses git history)[/red]"
        )
    else:
        console.print("  [cyan]3.[/cyan] [dim](Not available - branch only exists remotely)[/dim]")
    console.print("  [cyan]4.[/cyan] Cancel")

    while True:
        choice = typer.prompt("\nChoice [1-4]", type=int)

        if choice == 1:  # Use existing branch
            console.print(f"[green]✓ Using existing branch '{project}'[/green]")
            return project, False

        elif choice == 2:  # Create new branch with different name
            suggestions = _suggest_branch_names(project)
            if suggestions:
                console.print(f"\n[dim]Suggested names: {', '.join(suggestions)}[/dim]")

            new_name = typer.prompt(
                "Enter new branch name", default=suggestions[0] if suggestions else f"{project}-2"
            )

            if _branch_exists(new_name):
                console.print(
                    f"[red]❌ Branch '{new_name}' also already exists! Try another name.[/red]"
                )
                continue

            console.print(f"[green]✓ Using new branch name '{new_name}'[/green]")
            return new_name, True

        elif choice == 3:  # Delete existing and recreate
            if not local_exists:
                console.print("[red]❌ Cannot delete a remote-only branch from here[/red]")
                console.print("[dim]Choose option 2 to use a different branch name instead[/dim]")
                continue

            console.print(
                f"\n[red]⚠️  This will permanently delete branch '{project}' and all its git history.[/red]"
            )
            confirm = typer.confirm("Are you sure?")
            if not confirm:
                console.print("[yellow]Cancelled deletion.[/yellow]")
                continue

            # First check if there's an existing worktree using this branch
            existing_worktree = settings.worktree_base / project
            if existing_worktree.exists():
                console.print(f"[dim]Removing existing worktree at {existing_worktree}[/dim]")
                try:
                    run_cmd.run(
                        ["git", "worktree", "remove", project, "--force"],
                        cwd=settings.superset_base,
                        description=f"Removing existing worktree '{project}'",
                    )
                except subprocess.CalledProcessError as e:
                    console.print(
                        f"[red]❌ Failed to remove worktree '{project}': {e.stderr}[/red]"
                    )
                    raise typer.Exit(1) from e

            # Now delete the branch
            try:
                run_cmd.run(
                    ["git", "branch", "-D", project],
                    cwd=settings.superset_base,
                    description=f"Deleting existing branch '{project}'",
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]❌ Failed to delete branch '{project}': {e.stderr}[/red]")
                raise typer.Exit(1) from e

            console.print(f"[green]✓ Deleted existing branch '{project}', creating new one[/green]")
            return project, True

        elif choice == 4:  # Cancel
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

        else:
            console.print("[red]Invalid choice. Please enter 1, 2, 3, or 4.[/red]")


def _archive_project_docs(metadata: ProjectMetadata, settings: ClaudetteSettings) -> None:
    """Archive PROJECT.md and other important files before project removal."""
    project_folder = metadata.project_folder(settings.claudette_home)
    if not project_folder.exists():
        return

    # Check if PROJECT.md exists
    project_md = project_folder / "PROJECT.md"
    if not project_md.exists():
        return

    # Create archive directory structure
    archive_dir = settings.archive_path / metadata.name
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for the archive
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        import shutil

        # Archive PROJECT.md with timestamp
        archived_project_md = archive_dir / f"PROJECT_{timestamp}.md"
        shutil.copy2(project_md, archived_project_md)

        # Also keep a copy as latest
        latest_project_md = archive_dir / "PROJECT_latest.md"
        shutil.copy2(project_md, latest_project_md)

        console.print(f"[green]📁 Archived PROJECT.md to {archived_project_md}[/green]")

        # Archive metadata as well
        metadata_file = project_folder / ".claudette"
        if metadata_file.exists():
            archived_metadata = archive_dir / f"claudette_{timestamp}.txt"
            shutil.copy2(metadata_file, archived_metadata)
            console.print(f"[dim]📄 Archived metadata to {archived_metadata}[/dim]")

    except Exception as e:
        console.print(f"[yellow]⚠️  Could not archive PROJECT.md: {e}[/yellow]")


@app.command()
def archive(
    list_archives: bool = typer.Option(False, "--list", "-l", help="List archived projects"),
) -> None:
    """📁 Manage archived PROJECT.md files.

    Archives are created automatically when removing projects.
    Use --list to see all archived projects and their files.
    """
    if list_archives:
        archive_path = settings.archive_path

        if not archive_path.exists():
            console.print("[dim]No archived projects found.[/dim]")
            return

        archived_projects = [d for d in archive_path.iterdir() if d.is_dir()]

        if not archived_projects:
            console.print("[dim]No archived projects found.[/dim]")
            return

        console.print(
            f"\n[bold green]📁 Archived Projects[/bold green] ([dim]{archive_path}[/dim])\n"
        )

        for project_dir in sorted(archived_projects):
            project_name = project_dir.name
            console.print(f"[cyan]{project_name}[/cyan]")

            # List PROJECT.md files
            project_files = list(project_dir.glob("PROJECT_*.md"))
            metadata_files = list(project_dir.glob("claudette_*.txt"))

            if project_files:
                console.print(f"  📄 {len(project_files)} archived versions:")
                for f in sorted(project_files, reverse=True):  # Most recent first
                    size = f.stat().st_size
                    console.print(f"    • {f.name} ({size} bytes)")

            if metadata_files:
                console.print(f"  ⚙️  {len(metadata_files)} metadata snapshots")

            console.print()
    else:
        console.print("[yellow]Use --list to see archived projects[/yellow]")
        console.print(f"[dim]Archive location: {settings.archive_path}[/dim]")


@app.command()
def sync(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
) -> None:
    """🔄 Sync PROJECT.md content with claudette metadata.

    Updates the project metadata with the description from PROJECT.md.
    Useful after editing PROJECT.md to update what shows in 'claudette list'.
    """
    # Determine project
    if not project:
        cwd = Path.cwd()
        if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
            project = cwd.name
        else:
            console.print("[red]❌ Not in a claudette project directory[/red]")
            console.print("[dim]Use: claudette sync <project-name>[/dim]")
            raise typer.Exit(1)

    project_path = settings.worktree_base / project
    if not project_path.exists():
        console.print(f"[red]Project '{project}' not found[/red]")
        raise typer.Exit(1)

    # Load metadata
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        console.print(f"[red]No metadata found for project {project}[/red]")
        raise typer.Exit(1) from None

    # Update from PROJECT.md
    if metadata.update_from_project_md():
        metadata.save(settings.claudette_home)
        console.print(f"[green]✅ Updated metadata for {project}[/green]")
        if metadata.description:
            console.print(
                f"[dim]Description: {metadata.description[:100]}...[/dim]"
                if len(metadata.description) > 100
                else f"[dim]Description: {metadata.description}[/dim]"
            )
    else:
        console.print(f"[yellow]No PROJECT.md found for {project}[/yellow]")
        console.print(f"[dim]Expected at: {project_path / 'PROJECT.md'}[/dim]")


@app.command()
def nuke() -> None:
    """🚨 COMPLETELY REMOVE claudette and all projects (DANGEROUS!)"""
    console.print("\n[bold red]🚨 NUCLEAR OPTION - COMPLETE CLAUDETTE REMOVAL 🚨[/bold red]\n")

    console.print("[yellow]This will:[/yellow]")
    console.print("• Stop and remove ALL Docker containers for ALL projects")
    console.print("• Delete ALL worktree projects and their work")
    console.print("• Remove the entire ~/.claudette directory")
    console.print("• Completely uninstall claudette from your system")
    console.print("\n[bold red]⚠️  THIS CANNOT BE UNDONE! ⚠️[/bold red]\n")

    # Check if claudette exists
    if not settings.claudette_home.exists():
        console.print("[yellow]Claudette directory doesn't exist. Nothing to remove.[/yellow]")
        raise typer.Exit(0)

    # Show what will be deleted
    console.print(f"[dim]Will delete: {settings.claudette_home}[/dim]")

    # Count projects
    project_count = 0
    metadata_dir = settings.claudette_home / "projects"
    if metadata_dir.exists():
        project_count = len(list(metadata_dir.glob("*.claudette")))

    if project_count > 0:
        console.print(f"[red]Found {project_count} active projects that will be DESTROYED[/red]")

    console.print("\n[bold]TO CONFIRM TOTAL DESTRUCTION, TYPE: [red]NUKE[/red][/bold]")
    confirmation = typer.prompt("Confirmation", hide_input=False)

    if confirmation != "NUKE":
        console.print("[green]Aborted. Your projects are safe.[/green]")
        raise typer.Exit(0)

    console.print("\n[red]💥 Beginning total annihilation...[/red]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Stopping all Docker containers...", total=None)

        # Stop all docker containers for all projects
        metadata_dir = settings.claudette_home / "projects"
        if metadata_dir.exists():
            for metadata_file in metadata_dir.glob("*.claudette"):
                project_name = metadata_file.stem
                try:
                    metadata = ProjectMetadata.load(project_name, settings.claudette_home)
                    progress.update(task, description=f"Stopping Docker for {metadata.name}...")
                    run_cmd.run(
                        [
                            "docker-compose",
                            "-p",
                            metadata.name,
                            "-f",
                            "docker-compose-light.yml",
                            "down",
                            "--volumes",
                            "--remove-orphans",
                        ],
                        cwd=metadata.path,
                        env={**os.environ, "NODE_PORT": str(metadata.port)},
                        check=False,  # Don't fail if containers don't exist
                        description=f"Nuking Docker containers for {metadata.name}",
                    )
                except Exception:
                    pass  # Continue even if this project fails

        # Remove all git worktrees
        if settings.superset_base.exists():
            progress.update(task, description="Removing all git worktrees...")
            with contextlib.suppress(Exception):
                run_cmd.run(
                    ["git", "worktree", "prune"],
                    cwd=settings.superset_base,
                    check=False,
                    description="Pruning all git worktrees",
                )

        # Nuclear option: remove the entire claudette directory
        progress.update(task, description="Deleting ~/.claudette directory...")
        import shutil

        if settings.claudette_home.exists():
            shutil.rmtree(settings.claudette_home)

        progress.update(task, description="Cleanup complete")

    console.print("\n[bold green]💀 CLAUDETTE HAS BEEN COMPLETELY REMOVED 💀[/bold green]")
    console.print("[dim]To use claudette again, run: pip install claudette && claudette init[/dim]")


# Handle no command specified
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Claudette - Git worktree management for Apache Superset development, made simple.

    Fully loaded, concurrent dev environments, ready for Claude Code.

    If no command is specified and you're in a project, launches Claude Code.
    Otherwise shows help.
    """
    # Run initialization/migration check for ALL commands (except 'init' itself)
    if ctx.invoked_subcommand != "init":
        _ensure_claudette_initialized()

    if ctx.invoked_subcommand is None:
        # Check if we're already in an activated claudette environment
        if os.environ.get("PROJECT") and os.environ.get("NODE_PORT"):
            project_name = os.environ.get("PROJECT")
            node_port = os.environ.get("NODE_PORT")
            console.print("[green]✓ Claudette environment activated[/green]")
            console.print(f"[dim]Project: {project_name}[/dim]")
            console.print(f"[dim]Port: {node_port}[/dim]")
            console.print("\n[dim]Run [cyan]claudette --help[/cyan] for available commands.[/dim]")
            raise typer.Exit(0)

        # Check if we're in a project directory
        cwd = Path.cwd()
        if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
            # We're in a project, show project info
            project_name = cwd.name
            console.print(f"[green]📁 In claudette project: {project_name}[/green]")
            console.print("\n[dim]Available commands:[/dim]")
            console.print(
                "• [cyan]claudette activate {project_name}[/cyan] - Activate this project"
            )
            console.print("• [cyan]claudette docker <cmd>[/cyan] - Run docker commands")
            console.print("• [cyan]claudette jest[/cyan] - Run frontend tests")
            console.print("• [cyan]claudette pytest[/cyan] - Run backend tests")
            console.print("\n[dim]Run [cyan]claudette --help[/cyan] for all commands.[/dim]")
            raise typer.Exit(0)
        else:
            # Not in a project, show help instead
            console.print("[yellow]No command specified.[/yellow]")
            console.print("\n[dim]Available commands:[/dim]")
            console.print("• [cyan]claudette init[/cyan] - Set up claudette environment")
            console.print(
                "• [cyan]claudette add <name>[/cyan] - Create a new project (auto-assigns port)"
            )
            console.print("• [cyan]claudette list[/cyan] - Show all projects")
            console.print("\n[dim]Run [cyan]claudette --help[/cyan] for full documentation.[/dim]")
            raise typer.Exit(0)


if __name__ == "__main__":
    app()
