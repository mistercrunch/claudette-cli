"""Main CLI module for claudette."""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import ClaudetteSettings, ProjectMetadata

app = typer.Typer(
    name="claudette",
    help="Superset multi-environment workflow manager using git worktrees.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
settings = ClaudetteSettings()


@app.command()
def add(
    project: str = typer.Argument(..., help="Project name (will be branch name)"),
    port: int = typer.Argument(..., min=9000, max=9999, help="Port for frontend (9000-9999)"),
) -> None:
    """Create a new Superset worktree project with isolated environment."""
    console.print(f"\n[bold green]Creating project: {project} (port: {port})[/bold green]\n")
    
    project_path = settings.worktree_base / project
    metadata = ProjectMetadata(name=project, port=port, path=project_path)
    
    # Ensure worktree base exists
    settings.worktree_base.mkdir(parents=True, exist_ok=True)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Create git worktree
        task = progress.add_task("Creating git worktree...", total=None)
        try:
            subprocess.run(
                ["git", "worktree", "add", str(project_path), "-b", project],
                cwd=settings.worktree_base,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error creating worktree: {e.stderr}[/red]")
            raise typer.Exit(1)
        
        # Step 2: Save metadata
        progress.update(task, description="Saving project metadata...")
        metadata.save()
        
        # Step 3: Create Python venv
        progress.update(task, description="Creating Python virtual environment...")
        subprocess.run(
            ["uv", "venv", "-p", settings.python_version],
            cwd=project_path,
            check=True,
            capture_output=True,
        )
        
        # Step 4: Install Python dependencies
        progress.update(task, description="Installing Python dependencies (this may take a while)...")
        venv_python = project_path / ".venv" / "bin" / "python"
        subprocess.run(
            [str(venv_python), "-m", "uv", "pip", "install", "-r", "requirements/development.txt"],
            cwd=project_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [str(venv_python), "-m", "uv", "pip", "install", "-e", "."],
            cwd=project_path,
            check=True,
            capture_output=True,
        )
        
        # Step 5: Symlink CLAUDE.local.md if exists
        progress.update(task, description="Setting up Claude configuration...")
        if settings.claude_local_md:
            (project_path / "CLAUDE.local.md").symlink_to(settings.claude_local_md)
        
        # Step 6: Create .claude_rc
        claude_rc_content = f"""# Claude Code RC for {project}

This is a configuration file for Claude Code specific to this project.

## Project Context
- Working on: {project}
- Base directory: {project_path}
- Frontend port: {port}

## Environment Setup
- Python virtual environment: .venv
- Always run: source .venv/bin/activate

## Development Commands
- Frontend: cd superset-frontend && npm run dev
- Backend: flask run -p 8088 --debugger --reload
- Tests: pytest tests/unit_tests/
- Linting: pre-commit run --all-files
- Docker: NODE_PORT={port} docker-compose -p {project} -f docker-compose-light.yml up

## Instructions
- Always activate the virtual environment before running Python commands
- Use `npm run dev` in superset-frontend for frontend development
- Run `pre-commit run` before committing changes
"""
        (project_path / ".claude_rc").write_text(claude_rc_content)
        
        # Step 7: Install frontend dependencies
        progress.update(task, description="Installing frontend dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=project_path / "superset-frontend",
            check=True,
            capture_output=True,
        )
        
        # Step 8: Setup pre-commit
        progress.update(task, description="Setting up pre-commit hooks...")
        subprocess.run(
            [str(venv_python), "-m", "pre_commit", "install"],
            cwd=project_path,
            check=True,
            capture_output=True,
        )
    
    # Success!
    console.print("\n[bold green]✨ Project created successfully![/bold green]\n")
    
    panel = Panel.fit(
        f"""[yellow]Next steps:[/yellow]

1. cd {project_path}
2. claudette shell
3. claudette docker up
4. claudette code""",
        title="[bold]Get Started[/bold]",
        border_style="green",
    )
    console.print(panel)


@app.command()
def remove(
    project: str = typer.Argument(..., help="Project name to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Remove a worktree project and clean up resources."""
    project_path = settings.worktree_base / project
    
    if not project_path.exists():
        console.print(f"[red]Project '{project}' not found[/red]")
        raise typer.Exit(1)
    
    # Load metadata to get port for docker cleanup
    try:
        metadata = ProjectMetadata.load(project_path)
    except FileNotFoundError:
        metadata = None
    
    if not force:
        confirm = typer.confirm(f"Remove project '{project}' and all its data?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)
    
    with console.status("[yellow]Removing project...[/yellow]") as status:
        # Stop docker containers if metadata available
        if metadata:
            status.update("Stopping Docker containers...")
            subprocess.run(
                [
                    "docker-compose",
                    "-p", project,
                    "-f", "docker-compose-light.yml",
                    "down",
                ],
                cwd=project_path,
                env={**os.environ, "NODE_PORT": str(metadata.port)},
                capture_output=True,
            )
        
        # Remove git worktree
        status.update("Removing git worktree...")
        subprocess.run(
            ["git", "worktree", "remove", project, "--force"],
            cwd=settings.worktree_base,
            check=True,
            capture_output=True,
        )
    
    console.print(f"[green]✓ Project '{project}' removed successfully[/green]")


@app.command()
def list() -> None:
    """List all claudette projects."""
    table = Table(title="Claudette Projects", show_header=True, header_style="bold magenta")
    table.add_column("Project", style="cyan", no_wrap=True)
    table.add_column("Port", justify="right", style="green")
    table.add_column("Path", style="dim")
    table.add_column("Status", justify="center")
    
    # Find all projects with .claudette files
    projects_found = False
    for project_dir in settings.worktree_base.iterdir():
        if project_dir.is_dir() and (project_dir / ".claudette").exists():
            projects_found = True
            try:
                metadata = ProjectMetadata.load(project_dir)
                
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
                    project_dir.name,
                    "?",
                    str(project_dir.relative_to(Path.home())),
                    "⚠️",
                )
    
    if projects_found:
        console.print(table)
        console.print("\n[dim]Status: 🟢 Running | ⚫ Stopped | ⚠️ Error[/dim]")
    else:
        console.print("[yellow]No claudette projects found[/yellow]")
        console.print(f"[dim]Projects are stored in: {settings.worktree_base}[/dim]")


@app.command()
def shell(
    project: Optional[str] = typer.Argument(None, help="Project name (optional if in project dir)"),
) -> None:
    """Start a new shell with Python venv activated."""
    if project:
        project_path = settings.worktree_base / project
        if not project_path.exists():
            console.print(f"[red]Project '{project}' not found[/red]")
            raise typer.Exit(1)
    else:
        # Try to detect current project
        cwd = Path.cwd()
        if cwd.parts[-2] == settings.worktree_base.name and (cwd / ".claudette").exists():
            project_path = cwd
            project = cwd.name
        else:
            console.print("[red]Not in a claudette project directory[/red]")
            console.print("[dim]Use: claudette shell <project-name>[/dim]")
            raise typer.Exit(1)
    
    # Load metadata
    try:
        metadata = ProjectMetadata.load(project_path)
    except FileNotFoundError:
        console.print(f"[red]No .claudette file found in {project_path}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[green]Starting shell for project: {project}[/green]")
    console.print(f"[dim]Activating Python virtual environment...[/dim]")
    
    # Create activation script
    activate_script = f"""
source ~/.bashrc 2>/dev/null || true
cd {project_path}
source .venv/bin/activate
export NODE_PORT={metadata.port}
export PROJECT={metadata.name}
PS1="({metadata.name}) $PS1"
echo -e "\\033[0;32m✓ Virtual environment activated\\033[0m"
echo -e "\\033[0;34m  PROJECT={metadata.name}\\033[0m"
echo -e "\\033[0;34m  NODE_PORT={metadata.port}\\033[0m"
"""
    
    # Start new shell
    subprocess.run(["bash", "--rcfile", "/dev/stdin"], input=activate_script, text=True)


@app.command()
def docker(
    ctx: typer.Context,
    args: List[str] = typer.Argument(None, help="Arguments to pass to docker-compose"),
) -> None:
    """Run docker-compose with project settings."""
    # Get current project
    cwd = Path.cwd()
    if not (cwd / ".claudette").exists():
        console.print("[red]Not in a claudette project directory[/red]")
        raise typer.Exit(1)
    
    # Load metadata
    metadata = ProjectMetadata.load(cwd)
    
    # Run docker-compose
    env = {**os.environ, "NODE_PORT": str(metadata.port)}
    cmd = [
        "docker-compose",
        "-p", metadata.name,
        "-f", "docker-compose-light.yml",
    ] + (args or [])
    
    subprocess.run(cmd, env=env)


@app.command()
def code(
    ctx: typer.Context,
    args: List[str] = typer.Argument(None, help="Arguments to pass to claude code"),
) -> None:
    """Launch Claude Code with project context."""
    # Try to get current project
    cwd = Path.cwd()
    if (cwd / ".claudette").exists():
        metadata = ProjectMetadata.load(cwd)
        console.print(f"[blue]Launching Claude Code for project: {metadata.name}[/blue]")
        env = {
            **os.environ,
            "NODE_PORT": str(metadata.port),
            "PROJECT": metadata.name,
        }
    else:
        env = os.environ
    
    # Launch claude code
    subprocess.run(["claude", "code"] + (args or []), env=env)


def _is_docker_running(project_name: str) -> bool:
    """Check if docker containers are running for a project."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"label=com.docker.compose.project={project_name}", "-q"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


# Make 'code' the default command if no command specified
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """
    Claudette - Superset multi-environment workflow manager.
    
    If no command is specified, launches Claude Code.
    """
    if ctx.invoked_subcommand is None:
        code(ctx, [])


if __name__ == "__main__":
    app()