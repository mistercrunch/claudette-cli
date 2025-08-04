# Claudette

A modern workflow manager for Apache Superset development using git worktrees. Each project gets its own isolated Python environment, node_modules, and Docker containers on different ports.

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Features

- 🌳 **Git Worktree Management** - Isolated branches in separate directories
- 🐍 **Automatic Python Environment** - Each project gets its own venv with dependencies
- 📦 **Node.js Isolation** - Separate node_modules per project
- 🐳 **Docker Integration** - Run containers on different ports per project
- 🎨 **Beautiful CLI** - Powered by Typer and Rich for a great experience
- 🔧 **Claude Code Integration** - Automatic environment setup for AI assistance
- ⚡ **Fast Setup** - Uses `uv` for blazing fast Python package installation

## Installation

### From PyPI (coming soon)
```bash
pip install claudette
```

### From Source
```bash
git clone https://github.com/yourusername/claudette.git
cd claudette
pip install -e .
```

### Prerequisites

1. **Base Superset Repository**:
   ```bash
   mkdir ~/code/superset-worktree
   cd ~/code/superset-worktree
   git clone https://github.com/apache/superset.git .
   ```

2. **Required Tools**:
   - Python 3.8+
   - Git with worktree support
   - Docker and docker-compose
   - Node.js and npm
   - `uv` (will be installed automatically)

## Quick Start

```bash
# Create a new project
claudette add my-feature 9007

# Jump into the project with activated venv
claudette shell my-feature

# Start Docker containers
claudette docker up

# Launch Claude Code with project context
claudette

# List all projects
claudette list

# Clean up when done
claudette remove my-feature
```

## Commands

### `claudette add <project> <port>`
Creates a new worktree project with:
- Git worktree branch
- Python virtual environment with all dependencies
- Frontend node_modules
- Pre-commit hooks
- Docker configuration

### `claudette list`
Shows all projects with their ports and Docker status:
```
┏━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Project     ┃ Port ┃ Path                          ┃ Status ┃
┡━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ my-feature  │ 9007 │ code/superset-worktree/my-... │   🟢   │
│ bug-fix     │ 9008 │ code/superset-worktree/bug... │   ⚫   │
└─────────────┴──────┴───────────────────────────────┴────────┘
```

### `claudette shell [project]`
Opens a new shell with:
- Python venv activated
- NODE_PORT and PROJECT environment variables set
- Project directory as working directory

### `claudette docker [args]`
Wrapper for docker-compose that automatically:
- Sets the correct NODE_PORT
- Uses the project name for container prefix
- Passes through all docker-compose commands

### `claudette remove <project>`
Cleanly removes a project:
- Stops Docker containers
- Removes git worktree
- Cleans up all project files

## Configuration

### Environment Variables
- `CLAUDETTE_WORKTREE_BASE` - Base directory for worktrees (default: `~/code/superset-worktree`)
- `CLAUDETTE_PYTHON_VERSION` - Python version to use (default: `python3.11`)

### Files
- `CLAUDE.local.md` - Symlinked to all projects for consistent Claude instructions
- `.claude_rc_template` - Template for project-specific Claude configuration

## Development Workflow

1. **Create a feature branch**:
   ```bash
   claudette add new-feature 9007
   ```

2. **Enter the development environment**:
   ```bash
   claudette shell new-feature
   ```

3. **Start services**:
   ```bash
   claudette docker up
   ```

4. **Develop with AI assistance**:
   ```bash
   claudette  # Launches Claude Code with context
   ```

5. **Run tests**:
   ```bash
   pytest tests/unit_tests/
   pre-commit run --all-files
   ```

6. **Clean up**:
   ```bash
   claudette docker down
   exit  # Leave the shell
   claudette remove new-feature
   ```

## Why Claudette?

Managing multiple Superset development environments is painful:
- Switching branches breaks your node_modules
- Frontend port conflicts when running multiple versions
- Python dependencies get mixed up
- Docker containers collide

Claudette solves this by giving each feature branch its own **complete** environment.

## How It Works

1. **Git Worktrees**: Each project is a separate git worktree, allowing multiple branches to be checked out simultaneously
2. **Isolated Environments**: Each project gets its own:
   - Python virtual environment (`.venv`)
   - Node modules (`node_modules`)
   - Docker containers (prefixed by project name)
   - Frontend port (9000-9999 range)
3. **Shared Configuration**: Common files like `CLAUDE.local.md` are symlinked to keep consistency

## Troubleshooting

### "Port already in use"
```bash
# Check what's using the port
lsof -i :9007

# Or just pick a different port
claudette add my-feature 9008
```

### "Git worktree already exists"
```bash
# List existing worktrees
git worktree list

# Remove the old one
git worktree remove my-feature
```

### "Docker containers won't start"
```bash
# Check if containers are already running
docker ps

# Force remove old containers
claudette docker down
docker system prune
```

## Advanced Usage

### Custom Base Directory
```bash
export CLAUDETTE_WORKTREE_BASE=~/projects/superset
claudette add my-feature 9007
```

### Using with VS Code
```bash
# Open project in VS Code with correct Python interpreter
claudette shell my-feature
code .  # VS Code will detect the activated venv
```

### Running Tests in Isolation
```bash
claudette shell my-feature
pytest tests/unit_tests/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
```bash
git clone https://github.com/yourusername/claudette.git
cd claudette
pip install -e ".[dev]"
```

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Credits

Built with:
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer

Name inspired by Claude (Anthropic's AI assistant) + "-ette" (French diminutive suffix).
