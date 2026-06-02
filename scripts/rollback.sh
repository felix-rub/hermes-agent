#!/usr/bin/env bash
# scripts/rollback.sh — Roll back to a known-good deploy state.
#
# Usage:
#   ./scripts/rollback.sh [commit-sha]
#
# If no commit SHA is given, reverts to the commit before the latest
# railway-deploy.trigger change. This restores both code and the trigger
# file so Railway deploys the previous version.
#
# This script:
#   1. Identifies the target rollback commit
#   2. Creates a snapshot of current state (tag)
#   3. Reverts main to the target commit
#   4. Pushes to trigger Railway redeploy with the old version
#
# SAFETY: Creates a backup tag before any destructive action.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { printf "${GREEN}[rollback]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[rollback]${NC} %s\n" "$*"; }
error() { printf "${RED}[rollback]${NC} %s\n" "$*" >&2; }

# Ensure we're on main
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "main" ]; then
    error "Must be on main branch (currently on: $current_branch)"
    exit 1
fi

# Ensure clean working tree
if ! git diff --quiet || ! git diff --cached --quiet; then
    error "Working tree is not clean. Commit or stash changes first."
    exit 1
fi

TARGET_SHA="${1:-}"

if [ -z "$TARGET_SHA" ]; then
    # Find the commit before the last railway-deploy.trigger change
    info "No target SHA provided. Finding last known-good deploy..."
    TARGET_SHA=$(git log --format='%H' --follow -- railway-deploy.trigger | sed -n '2p')
    if [ -z "$TARGET_SHA" ]; then
        error "Could not find a previous deploy commit to roll back to."
        exit 1
    fi
fi

# Validate target exists
if ! git cat-file -e "$TARGET_SHA" 2>/dev/null; then
    error "Target commit $TARGET_SHA does not exist."
    exit 1
fi

TARGET_SHORT=$(git rev-parse --short "$TARGET_SHA")
CURRENT_SHORT=$(git rev-parse --short HEAD)

info "Rolling back from $CURRENT_SHORT to $TARGET_SHORT"
info "Target: $(git log --oneline -1 "$TARGET_SHA")"
echo ""

# Create backup tag
backup_tag="pre-rollback-$(date -u +%Y%m%dT%H%M%SZ)"
info "Creating backup tag: $backup_tag"
git tag "$backup_tag" HEAD

# Revert to target
info "Reverting main to $TARGET_SHORT..."
git revert --no-commit HEAD..."$TARGET_SHA"
git commit -m "rollback: revert to $TARGET_SHORT

Automated rollback from $CURRENT_SHORT to $TARGET_SHORT.
Previous state preserved in tag: $backup_tag

To undo this rollback:
  git revert HEAD
  git push origin main
"

info "Rollback commit created. Summary:"
git log --oneline -3
echo ""
warn "Next steps:"
warn "  1. Review: git log --oneline -5"
warn "  2. Push:   git push origin main"
warn "  3. Railway will redeploy automatically (watchPatterns matches railway-deploy.trigger)"
warn ""
warn "To undo this rollback:"
warn "  git revert HEAD && git push origin main"
warn ""
warn "Backup tag: $backup_tag (git checkout $backup_tag to inspect)"
