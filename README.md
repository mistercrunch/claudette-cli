# Claudette

<img walt="Claudette" src="https://github.com/user-attachments/assets/ea21e509-2aa6-4ca6-b3e5-51248bef8395" />

Git worktree management for Apache Superset development, made simple. Fully loaded, concurrent dev environments, ready for Claude Code.

<img src="https://github.com/user-attachments/assets/eb809525-0783-4fa3-934b-cbbe740dd773" />
<img src="https://github.com/user-attachments/assets/8367ec7f-791f-49ad-89fd-e0dcd5169fa8" />

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
- 📝 **Shared CLAUDE.local.md** - Single source of truth for Claude instructions across all projects
- 🎯 **Auto Port Assignment** - Automatically finds available ports when not specified

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

1. **Initialize Claudette**:
   ```bash
   claudette init
   ```
   This will clone the Superset repository and set up your environment.

2. **Required Tools**:
   - Python 3.8+
   - Git with worktree support
   - Docker and docker-compose
   - Node.js and npm
   - `uv` (will be installed automatically)

## Quick Start

```bash
# Initialize claudette environment
claudette init

# Create a new project (port auto-assigned)
claudette add my-feature

# Or specify a port
claudette add my-feature 9007

# Activate the project environment
claudette activate my-feature

# Start Docker containers
claudette docker up

# Launch Claude with project context
claudette claude code

# Check project status
claudette status

# List all projects
claudette list

# Clean up when done
claudette remove my-feature
```

## Commands

### `claudette init`
Initializes claudette environment:
- Clones Apache Superset base repository
- Creates configuration directory
- Sets up templates for CLAUDE.local.md and .claude_rc

### `claudette add <project> [port]`
Creates a new worktree project with:
- Git worktree branch (with conflict resolution)
- Python virtual environment with all dependencies
- Frontend node_modules
- Pre-commit hooks
- Docker configuration
- Auto-assigns port if not specified

### `claudette activate <project>` / `claudette shell [project]`
Starts a new shell with:
- Python venv activated
- NODE_PORT and PROJECT environment variables set
- Project directory as working directory
- Modified prompt showing active project

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

### `claudette status [project]`
Shows detailed project status:
- Git branch and uncommitted changes
- Docker container status
- Python venv status
- Recent commits

### `claudette docker [args]`
Wrapper for docker-compose that automatically:
- Sets the correct NODE_PORT
- Uses the project name for container prefix
- Passes through all docker-compose commands

### `claudette claude [args]`
Launches claude CLI with project context:
- Sets working directory to project root
- Requires activated project (via $PROJECT)
- Passes through all arguments

### `claudette jest [args]` / `claudette pytest [args]`
Run tests with project context:
- `jest`: Frontend tests with all arguments passed to npm test
- `pytest`: Backend tests with venv Python and common options

### `claudette nuke-db [project]`
Nukes the PostgreSQL database volume:
- Stops containers first
- Removes the Docker volume completely
- Useful for fresh database state

### `claudette remove <project>`
Cleanly removes a project:
- Stops Docker containers
- Removes git worktree
- Cleans up all project files

### `claudette nuke` (DANGEROUS!)
Completely removes claudette and all projects:
- Stops ALL Docker containers
- Removes ALL worktrees
- Deletes entire ~/.claudette directory
- Requires typing "NUKE" to confirm

## Configuration

### Environment Variables
- `CLAUDETTE_WORKTREE_BASE` - Base directory for worktrees (default: `~/code/superset-worktree`)
- `CLAUDETTE_PYTHON_VERSION` - Python version to use (default: `python3.11`)

### Files
- `CLAUDE.local.md` - Symlinked to all projects for consistent Claude instructions
- `.claude_rc_template` - Template for project-specific Claude configuration

## Development Workflow

1. **Initialize claudette** (first time only):
   ```bash
   claudette init
   ```

2. **Create a feature branch**:
   ```bash
   claudette add new-feature  # Auto-assigns port
   ```

3. **Activate the project**:
   ```bash
   claudette activate new-feature
   ```

4. **Start services**:
   ```bash
   claudette docker up
   ```

5. **Develop with AI assistance**:
   ```bash
   claudette claude code  # Opens Claude Code with project context
   ```

6. **Run tests**:
   ```bash
   claudette pytest tests/unit_tests/
   claudette jest --watch
   pre-commit run --all-files
   ```

7. **Check status**:
   ```bash
   claudette status
   ```

8. **Clean up**:
   ```bash
   claudette docker down
   exit  # Leave the shell (or Ctrl+D)
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
Claudette handles this automatically! When adding a project:
- Choose to reuse the existing branch
- Create a new branch with a different name
- Delete the existing branch and start fresh

Or use flags:
```bash
claudette add my-feature --reuse        # Use existing branch
claudette add my-feature --force-new    # Delete and recreate
claudette add my-feature --name alt-name # Use different branch name
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
# Backend tests
claudette pytest tests/unit_tests/
claudette pytest -v --coverage

# Frontend tests
claudette jest
claudette jest --watch
claudette jest components/Button
```

### Refreshing Database
```bash
# Completely wipe the PostgreSQL database
claudette nuke-db
claudette docker up  # Starts fresh
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
