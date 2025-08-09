#!/bin/bash

# Backup script for claudette worktrees
# This preserves all work before fixing the git repository

BACKUP_DIR="$HOME/claudette-backup-$(date +%Y%m%d-%H%M%S)"
WORKTREE_DIR="$HOME/.claudette/worktrees"

echo "🔒 Claudette Worktree Backup Script"
echo "===================================="
echo "Backup location: $BACKUP_DIR"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# List of worktrees to backup
WORKTREES=(
    "custom-drillthrough"
    "default_chart_settings"
    "docker-pytest"
    "flask-config"
    "matrixify"
    "refactor_query"
    "rison"
    "sql-expression-validator"
    "superclaude"
    "theme_managed_by_admin"
    "theme-system-ui"
)

echo "Found ${#WORKTREES[@]} worktrees to backup:"
echo ""

for worktree in "${WORKTREES[@]}"; do
    if [ -d "$WORKTREE_DIR/$worktree" ]; then
        echo "📦 Backing up: $worktree"

        # Create tar archive excluding large directories
        tar -czf "$BACKUP_DIR/${worktree}.tar.gz" \
            -C "$WORKTREE_DIR" \
            --exclude="*/node_modules" \
            --exclude="*/.venv" \
            --exclude="*.pyc" \
            --exclude="*/__pycache__" \
            --exclude="*/dist" \
            --exclude="*/build" \
            --exclude="*/.pytest_cache" \
            --exclude="*/.mypy_cache" \
            --exclude="*/superset-frontend/node_modules" \
            --exclude="*/superset/static/assets" \
            --exclude="*.log" \
            "$worktree" 2>/dev/null

        if [ $? -eq 0 ]; then
            # Show the size of the backup
            SIZE=$(ls -lh "$BACKUP_DIR/${worktree}.tar.gz" | awk '{print $5}')
            echo "   ✅ Success: ${worktree}.tar.gz ($SIZE)"
        else
            echo "   ⚠️  Warning: Had issues with $worktree"
        fi
    else
        echo "❌ Not found: $worktree"
    fi
done

echo ""
echo "✨ Backup complete!"
echo "📁 Files saved to: $BACKUP_DIR"
echo ""
echo "To restore a worktree later:"
echo "  tar -xzf $BACKUP_DIR/<worktree-name>.tar.gz -C ~/.claudette/worktrees/"
