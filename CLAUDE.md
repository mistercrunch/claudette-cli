# Claudette Development Guide

This is a Python CLI tool for managing Apache Superset development environments using git worktrees.

## Project Structure

```
claudette-cli/
├── src/claudette/
│   ├── __init__.py      # Package initialization
│   ├── cli.py           # Main CLI commands (Typer app)
│   └── config.py        # Configuration and metadata management
├── pyproject.toml       # Modern Python packaging
├── README.md           # User documentation
└── CLAUDE.md           # This file - development guide
```

## Technology Stack

- **Typer**: Modern CLI framework with type hints
- **Rich**: Beautiful terminal output (tables, progress bars, colors)
- **Pydantic**: Configuration management with validation
- **GitPython**: Git operations (worktree management)
- **uv**: Fast Python package management (bundled dependency)

## Key Components

### CLI Commands (`cli.py`)

1. **add** - Creates new worktree project
   - Creates git worktree with new branch
   - Sets up Python venv using `uv`
   - Installs all dependencies
   - Creates `.claudette` metadata file
   - Symlinks `CLAUDE.local.md` and `PROJECT.md`
   - Sets up pre-commit hooks

2. **remove** - Removes project and cleans up
   - Stops Docker containers
   - Removes git worktree
   - Cleans up all files
   - `--keep-docs` flag preserves PROJECT.md

3. **list** - Shows all projects in a table
   - Reads all `.claudette` files
   - Shows Docker status (🟢 Running | ⚫ Stopped | 🧊 Frozen)
   - Shows PR associations (#1234 or ?)
   - Displays descriptions from PROJECT.md
   - Rich table with dynamic width

4. **activate** - Starts new shell with project environment
   - Python venv activated
   - Sets NODE_PORT and PROJECT env vars
   - Modified PS1 prompt
   - Requires thawing if project is frozen

5. **shell** - Drop into Docker container or run commands
   - Interactive: `clo shell` for bash shell
   - Command: `clo shell -- <cmd>` to run and exit
   - Auto-starts containers if needed
   - Examples: `clo shell -- python --version`

6. **psql** - Direct PostgreSQL database access
   - Interactive: `clo psql` for psql shell
   - Command: `clo psql -- -c "SELECT..."` to run query
   - Connects to db-light container automatically
   - Database: superset_light, User: superset
   - Examples: `clo psql -- -c "\\dt"` (list tables)

7. **docker** - Wrapper for docker-compose
   - Automatically sets NODE_PORT
   - Uses project name for container prefix
   - Passes through all arguments

8. **freeze/thaw** - Space-efficient project management
   - `freeze`: Removes node_modules and .venv (~3GB saved)
   - `thaw`: Restores dependencies with npm ci and uv
   - Frozen projects show 🧊 in list
   - Commands auto-prompt to thaw when needed

8. **pr** - GitHub PR association management
   - `pr link <number>`: Link project to PR
   - `pr clear`: Remove PR association
   - `pr open`: Open PR in browser
   - Shows in list and status commands

9. **status** - Detailed project information
   - Git branch and changes
   - Docker container status
   - Python venv and node_modules status
   - Shows frozen state and PR link
   - Recent commits

10. **jest/pytest** - Test runners
    - `jest`: Frontend tests with npm
    - `pytest`: Backend tests via Docker
    - Auto-thaws frozen projects

11. **open** - Open Superset in browser
    - Opens project's frontend URL
    - Auto-detects port from metadata

12. **nuke-db** - Reset PostgreSQL database
    - Removes Docker volume completely
    - Fresh database on next startup

13. **sync** - Sync PROJECT.md descriptions
    - Updates metadata from PROJECT.md
    - Refreshes list display

14. **init** - Initialize claudette environment
    - Clones Superset repository
    - Sets up configuration

15. **nuke** - Complete removal (DANGEROUS!)
    - Removes all projects and config
    - Requires confirmation

### Configuration (`config.py`)

- **ProjectMetadata**: Pydantic model for project data
  - Validates port range (9000-9999)
  - Handles `.claudette` file I/O
  - Shell-style format for compatibility

- **ClaudetteSettings**: Global configuration
  - Uses pydantic-settings for env vars
  - Auto-discovers CLAUDE.local.md
  - Configurable paths

## Development Tips

### Adding New Commands

```python
@app.command()
def status(
    project: Optional[str] = typer.Argument(None),
    detailed: bool = typer.Option(False, "--detailed", "-d"),
) -> None:
    """Show project status."""
    # Implementation
```

### Using Rich for Output

```python
# Progress bars
with Progress() as progress:
    task = progress.add_task("Installing...", total=None)

# Tables
table = Table(title="Projects")
table.add_column("Name", style="cyan")
console.print(table)

# Colored output
console.print("[green]Success![/green]")
```

### Error Handling

```python
if not path.exists():
    console.print("[red]Error: Not found[/red]")
    raise typer.Exit(1)  # Clean exit with error code
```

## Testing

Run the tool in development:
```bash
# Install in editable mode
pip install -e .

# Test commands
claudette --help
claudette add test-project 9007
claudette list
```

## Future Enhancements

1. **Auto port selection**: Find next available port
2. **Project templates**: Different setups for different work
3. **Health checks**: Verify project state
4. **Batch operations**: Act on multiple projects
5. **Config file**: ~/.claudette/config.toml
6. **Plugins**: Extensible command system

## Code Style

- Type hints everywhere (Typer uses them for CLI)
- Pydantic for data validation
- Rich for all output (no plain print)
- Subprocess for external commands
- Path objects instead of strings

## Publishing

```bash
# Build package
pip install build
python -m build

# Upload to PyPI
pip install twine
twine upload dist/*
```

## Common Issues

1. **Git worktree conflicts**: Check existing worktrees with `git worktree list`
2. **Port already in use**: Docker containers still running
3. **Permission errors**: Check file ownership in worktree base
4. **Slow npm install**: Normal, but could add npm cache

## Architecture Decisions

- **Why worktrees?**: True git isolation, shared object database
- **Why Python?**: Better than bash for complex logic, packaging, cross-platform
- **Why Typer?**: Modern, type-safe, great docs, built on Click
- **Why Rich?**: Beautiful output, maintained, good API
- **Why uv?**: 10-100x faster than pip, worth the dependency
