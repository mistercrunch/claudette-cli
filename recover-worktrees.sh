#!/bin/bash

# Recovery script for claudette worktrees
# This reconnects existing worktrees to the fixed main repository

MAIN_REPO="$HOME/.claudette/.superset"
WORKTREE_DIR="$HOME/.claudette/worktrees"
PATCH_DIR="$HOME/claudette-patches-$(date +%Y%m%d-%H%M%S)"

echo "🔧 Claudette Worktree Recovery Script"
echo "====================================="
echo ""

# Create patch directory for saving changes
mkdir -p "$PATCH_DIR"
echo "📁 Patches will be saved to: $PATCH_DIR"
echo ""

# List of worktrees to recover
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

echo "Found ${#WORKTREES[@]} worktrees to recover"
echo ""

# First, let's try to save any changes as patches
echo "Step 1: Attempting to save changes as patches..."
echo "-------------------------------------------------"
for worktree in "${WORKTREES[@]}"; do
    if [ -d "$WORKTREE_DIR/$worktree" ]; then
        echo "📝 Checking $worktree for changes..."
        cd "$WORKTREE_DIR/$worktree" 2>/dev/null

        # Try to create a patch even if git is broken
        # This uses git's low-level commands which might still work
        if git diff --no-index --no-prefix /dev/null . > "$PATCH_DIR/${worktree}.patch" 2>/dev/null; then
            if [ -s "$PATCH_DIR/${worktree}.patch" ]; then
                echo "   ✅ Saved changes to ${worktree}.patch"
            else
                echo "   ⚪ No changes detected"
                rm "$PATCH_DIR/${worktree}.patch"
            fi
        else
            echo "   ⚠️  Could not create patch (git might be too broken)"
        fi
    fi
done

echo ""
echo "Step 2: Re-adding worktrees to main repository..."
echo "--------------------------------------------------"
cd "$MAIN_REPO"

for worktree in "${WORKTREES[@]}"; do
    WORKTREE_PATH="$WORKTREE_DIR/$worktree"

    if [ -d "$WORKTREE_PATH" ]; then
        echo "🔄 Processing: $worktree"

        # Check if branch exists locally or remotely
        if git show-ref --verify --quiet "refs/heads/$worktree" 2>/dev/null; then
            echo "   📌 Branch $worktree exists locally"
            BRANCH_REF="$worktree"
        elif git show-ref --verify --quiet "refs/remotes/origin/$worktree" 2>/dev/null; then
            echo "   🌐 Branch $worktree exists on remote"
            BRANCH_REF="origin/$worktree"
        else
            echo "   ⚠️  Branch $worktree not found, will create new one"
            BRANCH_REF=""
        fi

        # Remove the old .git file in the worktree
        if [ -f "$WORKTREE_PATH/.git" ]; then
            mv "$WORKTREE_PATH/.git" "$WORKTREE_PATH/.git.old"
        fi

        # Try to add the worktree
        if [ -n "$BRANCH_REF" ]; then
            # Branch exists, use it
            if git worktree add "$WORKTREE_PATH" "$BRANCH_REF" --force 2>/dev/null; then
                echo "   ✅ Reconnected to existing branch"
            else
                echo "   ❌ Failed to reconnect"
            fi
        else
            # Create new branch
            if git worktree add "$WORKTREE_PATH" -b "$worktree" --force 2>/dev/null; then
                echo "   ✅ Created new branch and reconnected"
            else
                echo "   ❌ Failed to create worktree"
            fi
        fi

        # Clean up
        rm -f "$WORKTREE_PATH/.git.old"
    else
        echo "⚪ Skipping $worktree (directory not found)"
    fi
done

echo ""
echo "Step 3: Verification"
echo "--------------------"
cd "$MAIN_REPO"
echo "Current worktrees:"
git worktree list

echo ""
echo "✨ Recovery attempt complete!"
echo ""
echo "📋 Next steps:"
echo "1. Check each worktree with: cd ~/.claudette/worktrees/<name> && git status"
echo "2. If you have patches, apply them with: git apply $PATCH_DIR/<name>.patch"
echo "3. If a worktree is still broken, you may need to recreate it with: claudette add <name>"
