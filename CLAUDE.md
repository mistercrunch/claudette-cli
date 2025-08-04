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
   - Symlinks `CLAUDE.local.md`
   - Sets up pre-commit hooks

2. **remove** - Removes project and cleans up
   - Stops Docker containers
   - Removes git worktree
   - Cleans up all files

3. **list** - Shows all projects in a table
   - Reads all `.claudette` files
   - Checks Docker status
   - Displays with Rich table

4. **shell** - Starts new bash with venv activated
   - Can take project name or detect current
   - Sets NODE_PORT and PROJECT env vars
   - Changes PS1 prompt

5. **docker** - Wrapper for docker-compose
   - Automatically sets NODE_PORT
   - Uses project name for container prefix
   - Passes through all arguments

6. **code** - Launches Claude Code
   - Sets environment variables
   - Default command if none specified

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
