#!/bin/bash

# =====================================================
# Setup Git Hooks
# Install pre-commit hook to local .git/hooks
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_HOOKS_DIR="$SCRIPT_DIR/.git/hooks"
SOURCE_HOOKS_DIR="$SCRIPT_DIR/.git-hooks"

echo "🔗 Installing Git hooks..."

# Create hooks directory if it doesn't exist
mkdir -p "$GIT_HOOKS_DIR"

# Install pre-commit hook
if [ -f "$SOURCE_HOOKS_DIR/pre-commit" ]; then
    cp "$SOURCE_HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
    chmod +x "$GIT_HOOKS_DIR/pre-commit"
    echo "✅ Installed: pre-commit hook"
else
    echo "❌ Source hook not found: $SOURCE_HOOKS_DIR/pre-commit"
    exit 1
fi

echo ""
echo "🎉 Git hooks installed successfully!"
echo ""
echo "The pre-commit hook will run automatically before each commit."
echo "To bypass (NOT RECOMMENDED): git commit --no-verify"
echo ""

exit 0
