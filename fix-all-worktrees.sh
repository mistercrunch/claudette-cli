#!/bin/bash

# Complete fix for ALL worktrees
# This script will properly restore all worktrees with correct branches

MAIN_REPO="$HOME/.claudette/.superset"
WORKTREE_DIR="$HOME/.claudette/worktrees"
BACKUP_DIR="$HOME/claudette-backup-20250808-115415"

echo "🔧 Complete Worktree Fix - All Projects"
echo "========================================"
echo ""

# Define which branches exist on remote vs local only
declare -A BRANCH_STATUS
BRANCH_STATUS["custom-drillthrough"]="local"
BRANCH_STATUS["default_chart_settings"]="remote"
BRANCH_STATUS["docker-pytest"]="local"
BRANCH_STATUS["flask-config"]="local"
BRANCH_STATUS["matrixify"]="remote"
BRANCH_STATUS["refactor_query"]="remote"
BRANCH_STATUS["rison"]="remote"
BRANCH_STATUS["sql-expression-validator"]="local"
BRANCH_STATUS["superclaude"]="local"
BRANCH_STATUS["theme_managed_by_admin"]="local"
BRANCH_STATUS["theme-system-ui"]="remote"

echo "📋 Worktrees to process:"
for worktree in "${!BRANCH_STATUS[@]}"; do
    echo "  • $worktree (${BRANCH_STATUS[$worktree]} branch)"
done | sort
echo ""

cd "$MAIN_REPO"

# First, clean up any broken worktree references
echo "🧹 Cleaning up broken references..."
git worktree prune
echo ""

# Process each worktree
for worktree in custom-drillthrough default_chart_settings docker-pytest flask-config matrixify refactor_query rison sql-expression-validator superclaude theme_managed_by_admin theme-system-ui; do
    echo "📂 Processing: $worktree"
    echo "  ----------------------------------------"

    WORKTREE_PATH="$WORKTREE_DIR/$worktree"
    BACKUP_TAR="$BACKUP_DIR/${worktree}.tar.gz"

    # Check if already properly connected
    if git worktree list | grep -q "$WORKTREE_PATH"; then
        echo "  ✅ Already connected"

        # Verify it's working
        cd "$WORKTREE_PATH" 2>/dev/null
        if git status >/dev/null 2>&1; then
            BRANCH=$(git branch --show-current)
            echo "  📌 On branch: $BRANCH"
        else
            echo "  ⚠️  Connected but git commands failing, will reconnect..."
            cd "$MAIN_REPO"
            git worktree remove "$WORKTREE_PATH" --force 2>/dev/null
        fi
        continue
    fi

    cd "$MAIN_REPO"

    # Extract backup if we have one
    if [ -f "$BACKUP_TAR" ]; then
        echo "  📦 Extracting backup..."
        # Extract to parent directory
        tar -xzf "$BACKUP_TAR" -C "$WORKTREE_DIR/.." 2>/dev/null

        # Save the extracted content
        if [ -d "$WORKTREE_PATH" ]; then
            mv "$WORKTREE_PATH" "${WORKTREE_PATH}-backup"
        fi
    fi

    # Create worktree with appropriate branch
    if [ "${BRANCH_STATUS[$worktree]}" == "remote" ]; then
        echo "  🌐 Connecting to remote branch origin/$worktree..."

        # For remote branches, track them
        if git worktree add "$WORKTREE_PATH" -b "$worktree" "origin/$worktree" 2>/dev/null; then
            echo "  ✅ Connected to remote branch"
        else
            # Try without -b flag if branch already exists locally
            git worktree add "$WORKTREE_PATH" "$worktree" --force 2>/dev/null && \
                echo "  ✅ Connected to existing local tracking branch" || \
                echo "  ❌ Failed to connect"
        fi
    else
        echo "  📝 Creating local branch..."

        # For local branches, create from master
        if git worktree add "$WORKTREE_PATH" -b "$worktree" 2>/dev/null; then
            echo "  ✅ Created local branch"
        else
            # Branch might already exist
            git worktree add "$WORKTREE_PATH" "$worktree" --force 2>/dev/null && \
                echo "  ✅ Connected to existing local branch" || \
                echo "  ❌ Failed to create branch"
        fi
    fi

    # Restore backed up content if we have it
    if [ -d "${WORKTREE_PATH}-backup" ]; then
        echo "  📥 Restoring your files..."
        rsync -a --exclude=.git "${WORKTREE_PATH}-backup/" "$WORKTREE_PATH/" 2>/dev/null
        rm -rf "${WORKTREE_PATH}-backup"

        # Check for changes
        cd "$WORKTREE_PATH" 2>/dev/null
        CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
        if [ "$CHANGES" -gt 0 ]; then
            echo "  ⚠️  Restored $CHANGES files with changes"
        fi
    fi

    echo ""
done

echo "================================================================"
echo "✅ All Worktrees Processed!"
echo "================================================================"
echo ""

echo "📊 Final Status:"
cd "$MAIN_REPO"
git worktree list
echo ""

echo "🔍 Checking each worktree:"
for worktree in custom-drillthrough default_chart_settings docker-pytest flask-config matrixify refactor_query rison sql-expression-validator superclaude theme_managed_by_admin theme-system-ui; do
    WORKTREE_PATH="$WORKTREE_DIR/$worktree"
    if [ -d "$WORKTREE_PATH" ]; then
        cd "$WORKTREE_PATH" 2>/dev/null
        if git status >/dev/null 2>&1; then
            BRANCH=$(git branch --show-current 2>/dev/null)
            CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
            if [ "$CHANGES" -gt 0 ]; then
                echo "  ⚠️  $worktree [$BRANCH]: $CHANGES uncommitted changes"
            else
                echo "  ✅ $worktree [$BRANCH]: clean"
            fi
        else
            echo "  ❌ $worktree: git not working"
        fi
    else
        echo "  ❌ $worktree: directory missing"
    fi
done

echo ""
echo "💡 To check a specific worktree:"
echo "  cd ~/.claudette/worktrees/<name> && git status"
echo ""
echo "🎯 Worktrees with changes (rison, custom-drillthrough):"
echo "  cd ~/.claudette/worktrees/rison && git diff"
echo "  cd ~/.claudette/worktrees/custom-drillthrough && git diff"
