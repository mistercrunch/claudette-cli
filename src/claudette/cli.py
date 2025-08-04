"""Main CLI module for claudette."""

import contextlib
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import ClaudetteSettings, ProjectMetadata


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
    help="Superset multi-environment workflow manager using git worktrees.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
settings = ClaudetteSettings()

# Global command runner instance
run_cmd = CommandRunner(console)


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
        # Step 1: Create git worktree
        task = progress.add_task("Creating git worktree...", total=None)
        try:
            if create_new_branch:
                # Create new branch
                run_cmd.run(
                    ["git", "worktree", "add", str(project_path), "-b", final_branch_name],
                    cwd=settings.superset_base,
                    description=f"Creating git worktree with new branch '{final_branch_name}'",
                )
            else:
                # Use existing branch
                run_cmd.run(
                    ["git", "worktree", "add", str(project_path), final_branch_name],
                    cwd=settings.superset_base,
                    description=f"Creating git worktree with existing branch '{final_branch_name}'",
                )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error creating worktree: {e.stderr}[/red]")
            raise typer.Exit(1) from e

        # Step 2: Save metadata
        progress.update(task, description="Saving project metadata...")
        metadata.save(settings.claudette_home)

        # Step 3: Create Python venv
        progress.update(task, description="Creating Python virtual environment...")
        run_cmd.run(
            ["uv", "venv", "-p", settings.python_version],
            cwd=project_path,
            description="Creating Python virtual environment",
        )

        # Step 4: Install Python dependencies
        progress.update(
            task, description="Installing Python dependencies (this may take a while)..."
        )
        # Use system uv with the venv's pip
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

        # Step 5: Symlink CLAUDE.local.md if exists
        progress.update(task, description="Setting up Claude configuration...")
        if settings.claude_local_md:
            (project_path / "CLAUDE.local.md").symlink_to(settings.claude_local_md)

        # Step 6: Create .claude_rc from template
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

        # Step 7: Install frontend dependencies
        progress.update(task, description="Installing frontend dependencies...")
        run_cmd.run(
            ["npm", "install"],
            cwd=project_path / "superset-frontend",
            description="Installing frontend dependencies",
        )

        # Step 8: Setup pre-commit
        progress.update(task, description="Setting up pre-commit hooks...")
        venv_python = project_path / ".venv" / "bin" / "python"
        run_cmd.run(
            [str(venv_python), "-m", "pre_commit", "install"],
            cwd=project_path,
            description="Setting up pre-commit hooks",
        )

    # Success!
    console.print("\n[bold green]✨ Project created successfully![/bold green]\n")

    panel = Panel.fit(
        f"""[yellow]Next steps:[/yellow]

1. claudette activate {project}
2. claudette docker up
3. claudette code""",
        title="[bold]Get Started[/bold]",
        border_style="green",
    )
    console.print(panel)


@app.command()
def remove(
    project: str = typer.Argument(..., help="Project name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """🗑️  Remove a worktree project and clean up resources."""
    project_path = settings.worktree_base / project

    if not project_path.exists():
        console.print(f"[red]Project '{project}' not found[/red]")
        raise typer.Exit(1)

    # Load metadata to get port for docker cleanup
    try:
        metadata = ProjectMetadata.load(project, settings.claudette_home)
    except FileNotFoundError:
        metadata = None

    if not force:
        console.print(
            f"[red]⚠️  This will permanently remove project '{project}' and all its data![/red]"
        )
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    with console.status("[yellow]Removing project...[/yellow]") as status:
        # Stop docker containers if metadata available
        if metadata:
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
                description="Stopping Docker containers",
            )

        # Remove git worktree
        status.update("Removing git worktree...")
        run_cmd.run(
            ["git", "worktree", "remove", project, "--force"],
            cwd=settings.superset_base,
            description="Removing git worktree",
        )

    console.print(f"[green]✓ Project '{project}' removed successfully[/green]")


@app.command()
def list() -> None:
    """📋 List all claudette projects."""
    table = Table(title="Claudette Projects", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan", no_wrap=True)
    table.add_column("Port", justify="right", style="green")
    table.add_column("Path", style="dim")
    table.add_column("Status", justify="center")

    # Find all projects with metadata files
    projects_found = False
    metadata_dir = settings.claudette_home / "projects"
    if metadata_dir.exists():
        for metadata_file in metadata_dir.glob("*.claudette"):
            projects_found = True
            project_name = metadata_file.stem
            try:
                metadata = ProjectMetadata.load(project_name, settings.claudette_home)

                # Check if docker is running
                docker_status = "🟢" if _is_docker_running(metadata.name) else "⚫"

                table.add_row(
                    metadata.name,
                    str(metadata.port),
                    str(metadata.path.relative_to(Path.home())),
                    docker_status,
                )
            except Exception:
                table.add_row(
                    project_name,
                    "?",
                    "?",
                    "⚠️",
                )

    if projects_found:
        console.print(table)
        console.print("\n[dim]Status: 🟢 Running | ⚫ Stopped | ⚠️ Error[/dim]")
    else:
        console.print("[yellow]No claudette projects found[/yellow]")
        console.print(f"[dim]Projects are stored in: {settings.worktree_base}[/dim]")
        console.print("[dim]Run 'claudette init' to set up your environment[/dim]")


@app.command()
def activate(
    project: str = typer.Argument(..., help="Project name to activate"),
) -> None:
    """🚀 Activate a project: navigate to directory, start shell with venv and set PROJECT/NODE_PORT env vars."""
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

    console.print(f"[green]🚀 Activating project: {project}[/green]")
    console.print("[dim]Setting up project environment...[/dim]")

    # Create activation script (only modify PS1 if it exists and we're in bash/zsh)
    activate_script = f"""
# Source user's bashrc first
source ~/.bashrc 2>/dev/null || true

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
echo -e "🚀 Project '{metadata.name}' \\033[32mactivated\\033[0m"
echo "✓ Directory: $(pwd)"
echo -e "✓ Virtual environment: \\033[32mactivated\\033[0m"
echo "✓ PROJECT=$PROJECT"
echo "✓ NODE_PORT=$NODE_PORT"
echo "💡 Press Ctrl+D to deactivate (or 'exit' - but this may close your terminal)"

# Debug: Show Python path to verify venv is activated
echo -e "\\033[90mPython: $(which python)\\033[0m"

# Ensure we're in the right directory (in case bashrc changed it)
cd {project_path}
"""

    # Write activation script to a temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write(activate_script)
        temp_script = f.name

    try:
        # Start interactive bash shell with our activation script
        # Using subprocess directly to ensure we get an interactive shell
        subprocess.run(["bash", "--rcfile", temp_script], check=False)
    finally:
        # Clean up temp file
        Path(temp_script).unlink(missing_ok=True)


@app.command()
def deactivate() -> None:
    """🔴 Deactivate current claudette project (exit shell)."""
    console.print("[yellow]💡 To deactivate the current project:[/yellow]")
    console.print("[cyan]Press Ctrl+D[/cyan] [dim](recommended - won't close terminal)[/dim]")
    console.print("[dim]Or type 'exit' (may close your terminal/tmux)[/dim]")


@app.command()
def shell(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
) -> None:
    """🐚 Start shell in project context (alias for activate, but can auto-detect current project)."""
    if not project:
        # Try to detect current project
        cwd = Path.cwd()
        if len(cwd.parts) >= 2 and cwd.parts[-2] == settings.worktree_base.name:
            project = cwd.name
        else:
            console.print("[red]❌ Not in a claudette project directory[/red]")
            console.print("[dim]Use: claudette activate <project-name>[/dim]")
            console.print("[dim]Or: claudette shell <project-name>[/dim]")
            raise typer.Exit(1)

    # Call activate logic directly
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

    console.print(f"[green]🚀 Activating project: {project}[/green]")
    console.print("[dim]Setting up project environment...[/dim]")

    # Create activation script (only modify PS1 if it exists and we're in bash/zsh)
    activate_script = f"""
# Source user's bashrc first
source ~/.bashrc 2>/dev/null || true

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
echo -e "🚀 Project '{metadata.name}' \\033[32mactivated\\033[0m"
echo "✓ Directory: $(pwd)"
echo -e "✓ Virtual environment: \\033[32mactivated\\033[0m"
echo "✓ PROJECT=$PROJECT"
echo "✓ NODE_PORT=$NODE_PORT"
echo "💡 Press Ctrl+D to deactivate (or 'exit' - but this may close your terminal)"

# Debug: Show Python path to verify venv is activated
echo -e "\\033[90mPython: $(which python)\\033[0m"

# Ensure we're in the right directory (in case bashrc changed it)
cd {project_path}
"""

    # Write activation script to a temporary file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write(activate_script)
        temp_script = f.name

    try:
        # Start interactive bash shell with our activation script
        # Using subprocess directly to ensure we get an interactive shell
        subprocess.run(["bash", "--rcfile", temp_script], check=False)
    finally:
        # Clean up temp file
        Path(temp_script).unlink(missing_ok=True)


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

    # Run docker-compose
    env = {**os.environ, "NODE_PORT": str(metadata.port)}
    cmd = [
        "docker-compose",
        "-p",
        metadata.name,
        "-f",
        "docker-compose-light.yml",
    ] + (args or [])

    run_cmd.run(cmd, env=env, description="Running docker-compose")


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
        project_path = settings.worktree_base / project_name
        if project_path.exists():
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

    # Verify project exists
    project_path = settings.worktree_base / project
    if not project_path.exists():
        console.print(f"[red]Project '{project}' not found[/red]")
        raise typer.Exit(1)

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

    # Create status panel
    console.print(f"\n[bold blue]📊 Project Status: {metadata.name}[/bold blue]\n")

    # Basic info
    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Path", str(project_path))
    table.add_row("Port", str(metadata.port))
    table.add_row("Frontend URL", f"http://localhost:{metadata.port}")

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
    if venv_path.exists():
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
    if node_modules.exists():
        console.print("  Node modules: [green]✓ Installed[/green]")
    else:
        console.print("  Node modules: [red]✗ Missing[/red]")

    console.print()


@app.command()
def jest(
    ctx: typer.Context,  # noqa: ARG001
    args: List[str] = typer.Argument(None, help="Arguments to pass to Jest"),
) -> None:
    """🧪 Run Jest unit tests for frontend code.

    All arguments are passed through to Jest via 'npm run test -- [args]'.

    Examples:
        claudette jest                          # Run all tests
        claudette jest components/Button        # Run tests for Button component
        claudette jest Button.test.tsx         # Run specific test file
        claudette jest --watch                  # Run in watch mode
        claudette jest --coverage               # Generate coverage report
        claudette jest --testPathPattern=Button # Pattern matching
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

    # Build Jest command - pass all args through
    jest_cmd = ["npm", "run", "test", "--"] + (args or [])

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

    run_cmd.run(
        jest_cmd,
        cwd=frontend_dir,
        env=env,
        description="Running Jest tests",
        quiet=True,  # Don't show the command to avoid flashing
    )


@app.command()
def pytest(
    target: Optional[str] = typer.Argument(
        None, help="Test file or folder to run (e.g., tests/unit_tests/, test_charts.py)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    coverage: bool = typer.Option(False, "--coverage", "-c", help="Generate coverage report"),
    markers: Optional[str] = typer.Option(
        None, "--markers", "-m", help="Run tests with specific markers (e.g., 'not slow')"
    ),
    maxfail: Optional[int] = typer.Option(None, "--maxfail", help="Stop after N failures"),
    pdb: bool = typer.Option(False, "--pdb", help="Drop into debugger on failures"),
) -> None:
    """🐍 Run pytest unit tests for backend code.

    Examples:
        claudette pytest                           # Run all tests
        claudette pytest tests/unit_tests/         # Run unit tests only
        claudette pytest test_charts.py           # Run specific test file
        claudette pytest -v --coverage            # Verbose with coverage
        claudette pytest -m "not slow"            # Skip slow tests
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

    # Build pytest command - use venv's pytest
    venv_python = metadata.path / ".venv" / "bin" / "python"
    pytest_cmd = [str(venv_python), "-m", "pytest"]

    # Add target if specified
    if target:
        pytest_cmd.append(target)

    # Add pytest options
    if verbose:
        pytest_cmd.append("-v")

    if coverage:
        pytest_cmd.extend(["--cov=superset", "--cov-report=term-missing"])

    if markers:
        pytest_cmd.extend(["-m", markers])

    if maxfail:
        pytest_cmd.extend(["--maxfail", str(maxfail)])

    if pdb:
        pytest_cmd.append("--pdb")

    # Set environment variables
    env = {
        **os.environ,
        "NODE_PORT": str(metadata.port),
        "PROJECT": metadata.name,
    }

    console.print(f"[blue]🐍 Running pytest for project: {metadata.name}[/blue]")
    if target:
        console.print(f"[dim]Target: {target}[/dim]")

    run_cmd.run(
        pytest_cmd,
        cwd=metadata.path,
        env=env,
        description="Running pytest",
        quiet=True,  # Don't show the command to avoid flashing
    )


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


def _branch_exists(branch_name: str) -> bool:
    """Check if a git branch exists in the base repository."""
    try:
        result = run_cmd.run(
            ["git", "branch", "--list", branch_name],
            cwd=settings.superset_base,
            check=False,
            capture=True,
            quiet=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _get_branch_info(branch_name: str) -> Optional[dict]:
    """Get information about a git branch."""
    try:
        # Get last commit info
        result = run_cmd.run(
            ["git", "log", "-1", "--format=%H|%s|%ar", branch_name],
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
    console.print(f"\n[red]❌ Branch '{project}' already exists in the git repository.[/red]\n")

    # Show branch information if available
    branch_info = _get_branch_info(project)
    if branch_info:
        console.print("[dim]Branch info:[/dim]")
        console.print(f"  Last commit: {branch_info['commit_hash']} - {branch_info['subject']}")
        console.print(f"  Last updated: {branch_info['relative_time']}\n")

    # Show options
    console.print("[yellow]What would you like to do?[/yellow]")
    console.print(
        "  [cyan]1.[/cyan] Use existing branch (checkout and continue with existing git history)"
    )
    console.print("  [cyan]2.[/cyan] Create new branch with different name")
    console.print(
        "  [cyan]3.[/cyan] DELETE existing branch and start fresh [red](⚠️  loses git history)[/red]"
    )
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
    Claudette - Superset multi-environment workflow manager.

    If no command is specified and you're in a project, launches Claude Code.
    Otherwise shows help.
    """
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
