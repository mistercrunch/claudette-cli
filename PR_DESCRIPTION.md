# Add doctor and clean commands for environment health

## Summary
This PR adds two new commands to help maintain a healthy claudette environment:
- `claudette doctor` - Comprehensive health check and diagnostics
- `claudette clean` - Cleanup tool for orphaned project metadata

## Problem
Users were experiencing issues where `claudette remove` would sometimes leave behind metadata files, causing:
- Phantom projects appearing in `claudette list`
- Failures when running `claudette activate` on these orphaned projects
- No easy way to diagnose environment issues

## Solution

### 🩺 `claudette doctor` command
Comprehensive health check that detects:
- Missing initialization or configuration issues
- Required tool availability (Docker, Git, Node.js, Python, uv)
- Orphaned projects (metadata without corresponding worktrees)
- Port conflicts between projects
- Provides actionable fix suggestions

Example output:
```
🩺 Claudette Doctor - Environment Health Check

Checking claudette initialization... ✓
Checking Superset base repository... ✓
Checking worktree directory... ✓
Checking Docker installation... ✓
Checking Docker daemon... ✓
Checking Git installation... ✓
Checking Node.js installation... ✓ (v20.18.1)
Checking Python version... ✓ (3.10.14)
Checking uv installation... ✓

Scanning for projects... 1 project(s) found
  • orphaned-project: directory missing

──────────────────────────────────────────────────

❌ Found 1 issue(s):
  • Orphaned project 'orphaned-project': worktree directory missing

⚠️  Orphaned projects detected!
Run claudette clean to remove orphaned project metadata
```

### 🧹 `claudette clean` command
Cleanup tool for orphaned project metadata:
- Finds projects with missing worktrees or corrupted metadata
- Removes stale metadata files that `claudette remove` may have missed
- Supports `--dry-run` to preview what would be cleaned
- Supports `--force` to skip confirmation prompt
- Only removes metadata files, never actual project files

Example usage:
```bash
# Preview what would be cleaned
claudette clean --dry-run

# Clean with confirmation prompt
claudette clean

# Clean without confirmation
claudette clean --force
```

## Changes
- Added `doctor` command in `src/claudette/cli.py`
- Added `clean` command in `src/claudette/cli.py`
- Added `from_file` classmethod to `ProjectMetadata` in `src/claudette/config.py`
- Updated README.md with documentation for both commands
- Added comprehensive tests in `tests/test_doctor_clean.py`

## Testing
- Added unit tests for both commands covering various scenarios
- Manually tested with orphaned projects
- Verified dry-run mode works correctly
- Tested force flag skips confirmation

## Documentation
Updated README.md with detailed descriptions of both commands including:
- Purpose and use cases
- Available options
- When to use each command

## Backward Compatibility
- No breaking changes
- Commands are additive only
- Existing functionality remains unchanged

## Future Enhancements
- Could add auto-fix capability to `doctor` command
- Could integrate `clean` functionality into `doctor --fix`
- Could add more health checks (disk space, network connectivity, etc.)