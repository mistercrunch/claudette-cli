#!/bin/bash

# Complete recovery script for ALL worktrees
# This will reconnect all worktrees and restore backed-up content

MAIN_REPO="$HOME/.claudette/.superset"
WORKTREE_DIR="$HOME/.claudette/worktrees"
TEMP_DIR="$HOME/.claudette/worktrees-temp"
BACKUP_DIR="$HOME/claudette-backup-*"  # From earlier backup

echo "🔧 Complete Worktree Recovery"
echo "============================="
echo ""

# List of ALL worktrees to recover
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

echo "📋 Current status:"
echo "------------------"
cd "$MAIN_REPO"
echo "Connected worktrees:"
git worktree list
echo ""

echo "📦 Backup locations:"
echo "-------------------"
echo "Temp backup: $TEMP_DIR"
ls -la "$TEMP_DIR" 2>/dev/null || echo "  (empty)"
echo ""
echo "Tar backups: $BACKUP_DIR"
ls -la $BACKUP_DIR/*.tar.gz 2>/dev/null | head -5 || echo "  (none found)"
echo ""

read -p "Ready to restore ALL worktrees? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 1
fi

echo ""
echo "🔄 Processing worktrees..."
echo "-------------------------"

for worktree in "${WORKTREES[@]}"; do
    echo ""
    echo "📂 $worktree"
    echo "  ----------------------------------------"

    WORKTREE_PATH="$WORKTREE_DIR/$worktree"
    TEMP_PATH="$TEMP_DIR/$worktree"

    # Check if already connected
    if git worktree list | grep -q "$worktree"; then
        echo "  ✅ Already connected"

        # Check if we need to restore from temp
        if [ -d "$TEMP_PATH" ]; then
            echo "  📥 Found backup in temp, restoring files..."
            # Use rsync to restore, preserving timestamps
            rsync -a --exclude=.git "$TEMP_PATH/" "$WORKTREE_PATH/" 2>/dev/null

            # Check git status after restore
            cd "$WORKTREE_PATH" 2>/dev/null
            CHANGES=$(git status --porcelain | wc -l)
            if [ "$CHANGES" -gt 0 ]; then
                echo "  ⚠️  Restored $CHANGES files with uncommitted changes"
                git status --short | head -5
            else
                echo "  ✨ No uncommitted changes"
            fi
        fi
        continue
    fi

    # Need to reconnect this worktree
    cd "$MAIN_REPO"

    # Move existing directory to temp if not already there
    if [ -d "$WORKTREE_PATH" ] && [ ! -d "$TEMP_PATH" ]; then
        echo "  💾 Moving existing directory to temp..."
        mv "$WORKTREE_PATH" "$TEMP_PATH"
    fi

    # Check if branch exists
    if git ls-remote --heads origin "$worktree" | grep -q "$worktree"; then
        echo "  🌐 Found remote branch origin/$worktree"

        # Add worktree with remote branch
        if git worktree add "$WORKTREE_PATH" -b "$worktree" "origin/$worktree" 2>/dev/null; then
            echo "  ✅ Reconnected to remote branch"
        else
            echo "  ❌ Failed to reconnect"
            continue
        fi
    else
        echo "  📝 Creating new local branch"

        # Add worktree with new branch
        if git worktree add "$WORKTREE_PATH" -b "$worktree" 2>/dev/null; then
            echo "  ✅ Created new worktree"
        else
            echo "  ❌ Failed to create worktree"
            continue
        fi
    fi

    # Restore content from temp if available
    if [ -d "$TEMP_PATH" ]; then
        echo "  📥 Restoring files from backup..."
        rsync -a --exclude=.git "$TEMP_PATH/" "$WORKTREE_PATH/" 2>/dev/null

        # Check what was restored
        cd "$WORKTREE_PATH" 2>/dev/null
        CHANGES=$(git status --porcelain | wc -l)
        if [ "$CHANGES" -gt 0 ]; then
            echo "  ⚠️  Restored $CHANGES files with changes:"
            git status --short | head -3
            if [ "$CHANGES" -gt 3 ]; then
                echo "      ... and $((CHANGES - 3)) more"
            fi
        else
            echo "  ✨ Clean working tree"
        fi
    fi
done

echo ""
echo "================================================================"
echo "✅ Recovery Complete!"
echo "================================================================"
echo ""
echo "📊 Final Status:"
cd "$MAIN_REPO"
git worktree list
echo ""

echo "🔍 To check each worktree for uncommitted changes:"
for worktree in "${WORKTREES[@]}"; do
    if [ -d "$WORKTREE_DIR/$worktree" ]; then
        cd "$WORKTREE_DIR/$worktree" 2>/dev/null
        CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
        if [ "$CHANGES" -gt 0 ]; then
            echo "  ⚠️  $worktree: $CHANGES uncommitted changes"
        else
            echo "  ✅ $worktree: clean"
        fi
    fi
done

echo ""
echo "💡 Next steps:"
echo "  1. Review any uncommitted changes with: cd ~/.claudette/worktrees/<name> && git status"
echo "  2. Commit important changes to preserve them"
echo "  3. Clean up temp directory when done: rm -rf $TEMP_DIR"
