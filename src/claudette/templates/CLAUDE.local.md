# 🎯 Claudette - Your Superset Development Assistant

You're in a **claudette-managed** Apache Superset development environment! Claudette provides powerful commands to streamline your workflow.

## 🚀 Essential Commands You Should Use

### Testing Commands (Use These Often!)
```bash
# Run Jest tests for frontend
clo jest                                    # Run all frontend tests
clo jest src/components/Button             # Run tests in specific directory
clo jest Button.test.tsx                   # Run specific test file
clo jest --watch                           # Run in watch mode
clo jest --coverage                        # Generate coverage report

# Run pytest for backend
clo pytest                                  # Run all backend tests
clo pytest tests/unit_tests/               # Run unit tests only
clo pytest -x tests/                       # Stop on first failure
clo pytest -v tests/unit_tests/            # Verbose output
clo pytest --nuke tests/                   # Nuke and recreate test database
clo pytest -k test_charts                  # Run tests matching pattern
```

### Docker & Services
```bash
clo docker up                               # Start PostgreSQL and Redis
clo docker down                             # Stop services
clo docker logs -f                         # Follow logs
clo docker exec superset-light bash        # Enter container
clo shell                                   # Drop into Superset container (recommended!)
```

### Development Workflow
```bash
clo status                                  # Show project status, git info, services
clo open                                    # Open browser at project's port
clo sync                                    # Sync PROJECT.md with metadata
clo list                                    # Show all projects with descriptions
```

### Project Management
```bash
clo add my-feature                          # Create new project (auto-assigns port)
clo activate my-feature                     # Activate project environment
clo remove my-feature                       # Remove project
clo remove my-feature --keep-docs          # Remove but keep PROJECT.md
```

## 💡 Pro Tips

1. **Use `clo` as shorthand** - It's an alias for `claudette`!
2. **Tests are Docker-based** - `clo pytest` runs in Docker with automatic test DB setup
3. **Each project is isolated** - Different ports, databases, and environments
4. **PROJECT.md persists** - Your documentation survives even if you remove/recreate the worktree

## 🎯 Current Project Context

When activated, these environment variables are available:
- `PROJECT` - Current project/branch name
- `NODE_PORT` - Frontend dev server port (9000-9999)
- `PROJECT_PATH` - Path to worktree

## 📁 Project Structure

```
~/.claudette/
├── projects/{project}/          # Your project folder
│   ├── .claudette              # Metadata
│   ├── PROJECT.md              # Your documentation (symlinked to worktree)
│   └── .env.local              # Local environment variables
└── worktrees/{project}/         # Git worktree with code
    ├── .venv/                  # Python virtual environment
    ├── superset-frontend/      # Frontend code
    └── tests/                  # Test suites
```

## 🔥 Quick Start for Testing

When working on a feature, use these commands frequently:

```bash
# Backend: Run relevant tests after changes
clo pytest tests/unit_tests/charts/        # Test specific area
clo pytest -x                               # Stop on first failure for debugging

# Frontend: Test your components
clo jest --watch                           # Auto-run tests as you code
clo jest MyComponent --coverage            # Check test coverage

# Full test suite before committing
clo pytest tests/unit_tests/ && clo jest
```

## 📝 Remember

- **Edit PROJECT.md** in your worktree to document your work
- **Use `clo sync`** after editing PROJECT.md to update descriptions
- **Run tests frequently** - claudette makes it easy!
- **Each project is independent** - Switch between them freely

---
*This is your shared claudette configuration. Project-specific notes should go in PROJECT.md.*
