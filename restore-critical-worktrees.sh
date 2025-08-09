#!/bin/bash

# Restore the two worktrees with uncommitted changes: rison and custom-drillthrough

MAIN_REPO="$HOME/.claudette/.superset"
WORKTREE_DIR="$HOME/.claudette/worktrees"
BACKUP_BASE="$HOME/claudette-backup-20250808-115415"

echo "🔧 Restoring Critical Worktrees (rison & custom-drillthrough)"
echo "============================================================="
echo ""

# First, let's extract the tar backups to see your original work
echo "📦 Extracting backups to check for changes..."
echo ""

# Process rison (remote branch exists)
echo "1️⃣ Processing: rison"
echo "-------------------"

if [ -f "$BACKUP_BASE/rison.tar.gz" ]; then
    echo "  📂 Extracting backup..."
    cd "$HOME/.claudette"
    tar -xzf "$BACKUP_BASE/rison.tar.gz" 2>/dev/null

    if [ -d "$WORKTREE_DIR/rison" ]; then
        # Move existing to temp
        echo "  💾 Moving existing to temp..."
        mv "$WORKTREE_DIR/rison" "$WORKTREE_DIR/rison-old" 2>/dev/null
    fi

    # Add worktree for rison (remote branch exists)
    echo "  🔗 Connecting to remote branch origin/rison..."
    cd "$MAIN_REPO"
    git worktree add "$WORKTREE_DIR/rison-fresh" -b rison origin/rison 2>/dev/null

    # Now check for differences
    echo "  🔍 Checking for your local changes..."
    DIFF_COUNT=$(diff -rq "$WORKTREE_DIR/rison" "$WORKTREE_DIR/rison-fresh" 2>/dev/null | grep -v ".git" | wc -l)

    if [ "$DIFF_COUNT" -gt 0 ]; then
        echo "  ⚠️  Found $DIFF_COUNT files with changes"

        # Show what's different
        echo "  📝 Changed files:"
        diff -rq "$WORKTREE_DIR/rison" "$WORKTREE_DIR/rison-fresh" 2>/dev/null | grep -v ".git" | head -10

        # Restore the backed up version with your changes
        echo "  ♻️  Restoring your version with changes..."
        rm -rf "$WORKTREE_DIR/rison-fresh"
        # The extracted backup is already at $WORKTREE_DIR/rison

        # Fix the .git file to point to the right place
        echo "gitdir: $MAIN_REPO/.git/worktrees/rison" > "$WORKTREE_DIR/rison/.git"

        # Re-add to git worktree tracking
        cd "$MAIN_REPO"
        git worktree add "$WORKTREE_DIR/rison" rison --force 2>/dev/null

        # Check status
        cd "$WORKTREE_DIR/rison"
        echo "  📊 Git status:"
        git status --short | head -5
    else
        echo "  ✨ No changes detected, using fresh checkout"
        mv "$WORKTREE_DIR/rison-fresh" "$WORKTREE_DIR/rison"
    fi
else
    echo "  ❌ No backup found at $BACKUP_BASE/rison.tar.gz"
fi

echo ""
echo "2️⃣ Processing: custom-drillthrough"
echo "---------------------------------"

if [ -f "$BACKUP_BASE/custom-drillthrough.tar.gz" ]; then
    echo "  📂 Extracting backup..."
    cd "$HOME/.claudette"
    tar -xzf "$BACKUP_BASE/custom-drillthrough.tar.gz" 2>/dev/null

    if [ -d "$WORKTREE_DIR/custom-drillthrough" ]; then
        # This is a local branch, so we need to recreate it
        echo "  🔗 Creating local branch custom-drillthrough..."

        cd "$MAIN_REPO"
        # Create the worktree with a new local branch
        git worktree add "$WORKTREE_DIR/custom-drillthrough-temp" -b custom-drillthrough 2>/dev/null

        # Now restore the backed up files over the fresh checkout
        echo "  📥 Restoring your work..."
        rsync -a --exclude=.git "$WORKTREE_DIR/custom-drillthrough/" "$WORKTREE_DIR/custom-drillthrough-temp/" 2>/dev/null

        # Replace old with new
        rm -rf "$WORKTREE_DIR/custom-drillthrough"
        mv "$WORKTREE_DIR/custom-drillthrough-temp" "$WORKTREE_DIR/custom-drillthrough"

        # Check status
        cd "$WORKTREE_DIR/custom-drillthrough"
        echo "  📊 Git status:"
        git status --short | head -5
        CHANGES=$(git status --porcelain | wc -l)
        if [ "$CHANGES" -gt 5 ]; then
            echo "      ... and $((CHANGES - 5)) more files"
        fi
    fi
else
    echo "  ❌ No backup found at $BACKUP_BASE/custom-drillthrough.tar.gz"
fi

echo ""
echo "================================================================"
echo "✅ Critical Worktrees Restored!"
echo "================================================================"
echo ""

cd "$MAIN_REPO"
echo "📊 Current worktrees:"
git worktree list | grep -E "rison|custom-drillthrough|matrixify"

echo ""
echo "🔍 Status of restored worktrees:"
for worktree in rison custom-drillthrough; do
    if [ -d "$WORKTREE_DIR/$worktree" ]; then
        cd "$WORKTREE_DIR/$worktree" 2>/dev/null
        CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
        BRANCH=$(git branch --show-current 2>/dev/null)
        if [ "$CHANGES" -gt 0 ]; then
            echo "  ⚠️  $worktree [$BRANCH]: $CHANGES uncommitted changes"
        else
            echo "  ✅ $worktree [$BRANCH]: clean"
        fi
    fi
done

echo ""
echo "💡 Next steps:"
echo "  1. Check your changes: cd ~/.claudette/worktrees/rison && git status"
echo "  2. Check your changes: cd ~/.claudette/worktrees/custom-drillthrough && git status"
echo "  3. Commit any important work to preserve it"
