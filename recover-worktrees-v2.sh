#!/bin/bash

# Recovery script v2 - Preserves existing worktree content
# This moves directories temporarily to reconnect them

MAIN_REPO="$HOME/.claudette/.superset"
WORKTREE_DIR="$HOME/.claudette/worktrees"
TEMP_DIR="$HOME/.claudette/worktrees-temp"

echo "🔧 Claudette Worktree Recovery Script v2"
echo "========================================"
echo ""
echo "This will preserve your existing work while reconnecting worktrees."
echo ""

# Create temp directory
mkdir -p "$TEMP_DIR"

# Test with one worktree first
WORKTREE="matrixify"

echo "🧪 Testing recovery with: $WORKTREE"
echo "------------------------------------"

if [ -d "$WORKTREE_DIR/$WORKTREE" ]; then
    echo "1️⃣  Moving $WORKTREE to temp location..."
    mv "$WORKTREE_DIR/$WORKTREE" "$TEMP_DIR/$WORKTREE"

    echo "2️⃣  Re-adding worktree from git..."
    cd "$MAIN_REPO"

    # Check if branch exists remotely
    if git ls-remote --heads origin "$WORKTREE" | grep -q "$WORKTREE"; then
        echo "   Found remote branch origin/$WORKTREE"
        git worktree add "$WORKTREE_DIR/$WORKTREE" -b "$WORKTREE" "origin/$WORKTREE" 2>&1
    else
        echo "   Creating new branch $WORKTREE"
        git worktree add "$WORKTREE_DIR/$WORKTREE" -b "$WORKTREE" 2>&1
    fi

    if [ $? -eq 0 ]; then
        echo "3️⃣  Worktree reconnected successfully!"

        echo "4️⃣  Checking for local changes to preserve..."
        # Now we can use git to check for changes
        cd "$TEMP_DIR/$WORKTREE"

        # List modified files (comparing temp with fresh worktree)
        echo "   Comparing directories for changes..."
        CHANGED_FILES=$(diff -rq "$TEMP_DIR/$WORKTREE" "$WORKTREE_DIR/$WORKTREE" 2>/dev/null | grep "differ" | wc -l)

        if [ "$CHANGED_FILES" -gt 0 ]; then
            echo "   ⚠️  Found $CHANGED_FILES files with local changes"
            echo ""
            echo "   To preserve your changes, you can:"
            echo "   1. Copy modified files from: $TEMP_DIR/$WORKTREE"
            echo "   2. To the reconnected worktree: $WORKTREE_DIR/$WORKTREE"
            echo ""
            echo "   Or use rsync to sync changes:"
            echo "   rsync -av --exclude=.git $TEMP_DIR/$WORKTREE/ $WORKTREE_DIR/$WORKTREE/"
        else
            echo "   ✅ No local changes detected"
        fi

        # Test git status in the reconnected worktree
        echo ""
        echo "5️⃣  Testing git commands in reconnected worktree..."
        cd "$WORKTREE_DIR/$WORKTREE"
        git status --short

        echo ""
        echo "✅ Success! The worktree is now functional."
        echo ""
        echo "Would you like to:"
        echo "1. Keep the fresh worktree from git (lose local changes)"
        echo "2. Restore your backed-up version (keep local changes)"
        echo ""
        echo "Your backed-up version is at: $TEMP_DIR/$WORKTREE"

    else
        echo "❌ Failed to create worktree"
        echo "   Restoring original directory..."
        mv "$TEMP_DIR/$WORKTREE" "$WORKTREE_DIR/$WORKTREE"
    fi
else
    echo "❌ Directory not found: $WORKTREE_DIR/$WORKTREE"
fi

echo ""
echo "This was a test with one worktree. If successful, we can process all worktrees."
