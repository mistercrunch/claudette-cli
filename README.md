# Claudette

<img walt="Claudette" src="https://github.com/user-attachments/assets/ea21e509-2aa6-4ca6-b3e5-51248bef8395" />

Git worktree management for Apache Superset development, made simple. Fully loaded, concurrent dev environments, ready for Claude Code.

<img src="https://github.com/user-attachments/assets/eb809525-0783-4fa3-934b-cbbe740dd773" />
<img src="https://github.com/user-attachments/assets/8367ec7f-791f-49ad-89fd-e0dcd5169fa8" />

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Get Started

```bash
# Install claudette
pip install git+https://github.com/mistercrunch/claudette-cli.git

# Initialize your environment (clones Superset and sets up base config)
claudette init

# See available commands
claudette --help

# Pro tip: Use 'clo' as a shorter alias for claudette!
clo --help
```

## Features

- 🌳 **Git Worktree Management** - Isolated branches in separate directories
- 🐍 **Automatic Python Environment** - Each project gets its own venv with dependencies
- 📦 **Node.js Isolation** - Separate node_modules per project
- 🐳 **Docker Integration** - Run containers on different ports per project
- 🎨 **Beautiful CLI** - Powered by Typer and Rich for a great experience
- 🔧 **Claude Code Integration** - Automatic environment setup for AI assistance
- ⚡ **Fast Setup** - Uses `uv` for blazing fast Python package installation
- 📝 **PROJECT.md Standard** - Persistent branch docs in `~/.claudette/projects/`, symlinked to worktrees
- 🔗 **Shared CLAUDE.local.md** - Single source of truth for Claude instructions across all projects
- 🎯 **Auto Port Assignment** - Automatically finds available ports when not specified
- 🧊 **Freeze/Thaw Projects** - Save ~3GB per project by removing dependencies when not in use
- 🔗 **GitHub PR Integration** - Track and quickly access pull requests associated with projects

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

**Note:** Both `claudette` and `clo` commands will be available after installation. Use whichever you prefer!

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
clo add my-feature

# Or specify a port
clo add my-feature 9007

# Drop into Docker container for development
clo shell

# Or run a quick command
clo shell -- python --version

# Access the database directly
clo psql -- -c "\\dt"

# Start Docker containers
clo docker up

# Launch Claude with project context
clo claude code

# Link a GitHub PR to the project
clo pr link 12345

# Check project status
clo status

# List all projects
clo list

# Freeze inactive project to save space
clo freeze old-feature

# Thaw when ready to work again
clo thaw old-feature

# Clean up when done
clo remove my-feature
```

## Commands

All commands below can be run with either `claudette` or its shorter alias `clo`.

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

### `claudette activate <project>` / `claudette shell`
- `activate`: Starts a new shell with Python venv activated and project environment
- `shell`: Drop into Docker container or run commands
  - Interactive mode: `clo shell` enters bash shell
  - Command mode: `clo shell -- <command>` runs command and exits
  - Auto-starts containers if not running
  - Examples:
    - `clo shell -- python --version` - Check Python version
    - `clo shell -- superset db upgrade` - Run database migrations
    - `clo shell -- bash -c "ls -la | head"` - Complex commands

### `claudette list`
Shows all projects with their ports, Docker status, freeze state, and PRs:
```
┏━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃ Project     ┃ Port ┃ Path                          ┃ Status ┃ State ┃ PR   ┃
┡━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━┩
│ my-feature  │ 9007 │ code/superset-worktree/my-... │   🟢   │   🟢  │ #123 │
│ bug-fix     │ 9008 │ code/superset-worktree/bug... │   ⚫   │   🧊  │  ?   │
└─────────────┴──────┴───────────────────────────────┴────────┴───────┴──────┘
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
- `pytest`: Backend tests using Docker with automatic test database setup

### `claudette psql`
Direct PostgreSQL database access:
- Interactive mode: `clo psql` enters psql shell
- Command mode: `clo psql -- -c "SELECT..."` runs query and exits
- Auto-starts containers if not running
- Examples:
  - `clo psql -- -c "\\dt"` - List all tables
  - `clo psql -- -c "SELECT COUNT(*) FROM ab_user;"` - Run query
  - `clo psql -- -f script.sql` - Execute SQL file

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

### `claudette sync [project]`
Syncs PROJECT.md content with claudette metadata:
- Updates project description from PROJECT.md
- Refreshes what shows in `claudette list`
- Run after editing PROJECT.md

### `claudette freeze <project>`
Freezes a project to save disk space (~3GB per project):
- Removes node_modules directory
- Removes Python .venv directory
- Project must be thawed before use
- Use `--force` to skip confirmation

### `claudette thaw <project>`
Thaws a frozen project to restore dependencies:
- Reinstalls npm packages with `npm ci`
- Recreates Python venv and installs packages
- Automatically triggered by commands that need dependencies

### `claudette pr <action> [pr_number] [project]`
Manage GitHub PR associations:
- `clo pr link <pr_number>` - Associate a PR with current/specified project
- `clo pr clear` - Remove PR association from current/specified project
- `clo pr open` - Open associated PR in browser

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

### Files & Directories

#### Project Folder Structure
Each project gets a dedicated folder in `~/.claudette/projects/{project}/` containing:
- `.claudette` - Project metadata (port, path, description)
- `PROJECT.md` - Branch-specific documentation (symlinked to worktree)
- `.env.local` - Local environment variables (symlinked to worktree, future)

#### File Hierarchy
- `CLAUDE.md` - Repo-wide Superset development guidelines (in Superset repo)
- `CLAUDE.local.md` - Shared claudette configuration (symlinked to all worktrees)
- `PROJECT.md` - Branch-specific docs (lives in project folder, symlinked to worktree)
- `.claude_rc` - Central configuration referencing the PROJECT.md standard

### PROJECT.md Standard

Claudette uses PROJECT.md for branch-specific documentation:
- Lives in `~/.claudette/projects/{project}/PROJECT.md`
- Symlinked into worktree for easy editing
- Edit in your worktree → changes persist in project folder
- Survives worktree removal/recreation
- Use `--keep-docs` with `claudette remove` to preserve for later
- Claude loads PROJECT.md when present for branch context

### Extensible Architecture

The project folder structure is designed to be extensible. Files are managed via constants in the code, making it easy to add more symlinked files in the future (scripts, configs, etc.).

### Automatic Migration

Claudette automatically migrates older installations to the latest structure. A version file (`~/.claudette/.claudette.json`) tracks the schema version and ensures smooth upgrades without user intervention.

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
   clo shell                     # Drop into Docker container (recommended)
   # OR
   clo activate new-feature     # Activate Python venv in local shell
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
   clo pytest tests/unit_tests/             # Backend tests via Docker
   clo jest --watch                         # Frontend tests
   pre-commit run --all-files               # Code quality checks
   ```

7. **Check status**:
   ```bash
   claudette status
   ```

8. **Clean up**:
   ```bash
   exit                    # Leave Docker container (or Ctrl+D)
   clo docker down         # Stop containers
   clo remove new-feature  # Remove project
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

### "Project is frozen"
Frozen projects have their dependencies removed to save space. When you try to use a frozen project:
```bash
# Either thaw it first
claudette thaw my-feature

# Or commands will prompt you to thaw automatically
claudette shell my-feature  # Will ask to thaw first
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
# Backend tests (using Docker with automatic test DB setup)
clo pytest tests/unit_tests/
clo pytest -x tests/                    # Stop on first failure
clo pytest -v tests/unit_tests/         # Verbose output
clo pytest --nuke tests/                # Nuke and recreate test database
clo pytest -k test_charts               # Run tests matching pattern
clo pytest --maxfail=3 tests/           # Stop after 3 failures

# Frontend tests
clo jest                                         # Run all tests
clo jest --watch                                 # Watch mode
clo jest --coverage                              # Coverage report
clo jest src/components/Button                   # Test specific directory
clo jest superset-frontend/src/components/Button # Auto-strips prefix
```

### Refreshing Database
```bash
# Completely wipe the PostgreSQL database
claudette nuke-db
claudette docker up  # Starts fresh
```

### Managing Disk Space
```bash
# Freeze inactive projects to save ~3GB each
clo freeze old-project
clo freeze another-project --force  # Skip confirmation

# List projects to see which are frozen
clo list  # Frozen projects show 🧊 icon

# Thaw when ready to work
clo thaw old-project
```

### Working with GitHub PRs
```bash
# Link a PR to your project
clo pr link 12345

# View PR association
clo status  # Shows PR number
clo list    # Shows PR column

# Open PR in browser
clo pr open

# Clear PR association
clo pr clear
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
