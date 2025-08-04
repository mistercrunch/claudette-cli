# Development Setup

## Installing Development Dependencies

Using `uv` (recommended):
```bash
uv pip install -e ".[dev]"
```

Or with regular pip:
```bash
pip install -e ".[dev]"
```

This installs:
- pytest & pytest-cov for testing
- ruff for linting and formatting
- mypy for type checking
- pre-commit for git hooks

## Pre-commit Setup

After installing dev dependencies:
```bash
pre-commit install
pre-commit run --all-files  # Run on all files
```

## Running Tests

```bash
pytest
pytest --cov  # With coverage
```

## Linting & Formatting

```bash
ruff check src/  # Check for issues
ruff check src/ --fix  # Auto-fix issues
ruff format src/  # Format code
```

## Type Checking

```bash
mypy src/
```
