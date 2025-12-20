#!/usr/bin/env bash
set -euo pipefail

# update_pull.sh
# Safely update an existing checkout to a remote branch.
# Usage:
#   ./update_pull.sh [--repo DIR] [--branch NAME] [--install] [--reload] [--force-clean]
#
# Defaults:
#   repo: current directory
#   branch: temp-usb-copy-fixes-2025-12-03
# Options:
#   --install      : run usb_download_mvp/scripts/install_service.sh after pulling
#   --reload       : run sudo systemctl daemon-reload after pulling
#   --force-clean  : run `git clean -fdx` (removes untracked files)
#

REPO_DIR="$(pwd)"
BRANCH="temp-usb-copy-fixes-2025-12-03"
DO_INSTALL=0
DO_RELOAD=0
DO_FORCE_CLEAN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_DIR="$2"; shift 2;;
        --branch)
            BRANCH="$2"; shift 2;;
        --install)
            DO_INSTALL=1; shift;;
        --reload)
            DO_RELOAD=1; shift;;
        --force-clean)
            DO_FORCE_CLEAN=1; shift;;
        -h|--help)
            sed -n '1,120p' "$0"; exit 0;;
        *)
            echo "Unknown arg: $1"; exit 2;;
    esac
done

cd "$REPO_DIR"
if [ ! -d .git ]; then
    echo "Error: $REPO_DIR is not a git repository (no .git directory)" >&2
    exit 2
fi

echo "Updating repo at: $REPO_DIR"
REMOTE_ORIGIN=$(git remote get-url origin 2>/dev/null || true)
if [ -z "$REMOTE_ORIGIN" ]; then
    echo "Warning: no 'origin' remote configured. Pull will attempt to fetch default remote." >&2
else
    echo "Remote origin: $REMOTE_ORIGIN"
fi

TS=$(date -u +%Y%m%dT%H%M%SZ)

# 1) Stash local changes (including untracked) so nothing is lost
echo "Stashing local changes (including untracked) as pre-pull-$TS"
# Stash may fail if nothing to stash; ignore non-zero
git stash push -u -m "pre-pull-$TS" || true

# 2) Fetch remote
echo "Fetching from origin..."
git fetch origin --prune

# 3) If remote branch exists, reset to it; otherwise create/checkout branch
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    echo "Remote branch origin/$BRANCH found; checking out and resetting to it"
    if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
        git checkout "$BRANCH"
    else
        git checkout -b "$BRANCH" "origin/$BRANCH"
    fi
    git reset --hard "origin/$BRANCH"
else
    echo "Remote branch origin/$BRANCH not found; attempting to checkout local branch $BRANCH (or creating it)"
    if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
        git checkout "$BRANCH"
    else
        git checkout -b "$BRANCH"
    fi
    echo "Note: branch $BRANCH created locally but no remote branch found."
fi

# 4) Optional: force-clean untracked files
if [ "$DO_FORCE_CLEAN" -eq 1 ]; then
    echo "Removing untracked files (git clean -fdx)"
    git clean -fdx
fi

# 5) Make sure scripts are executable (installer expects this)
echo "Fixing executable bits for scripts"
chmod +x "$REPO_DIR"/usb_download_mvp/scripts/*.sh || true

# 6) Optional: reload systemd
if [ "$DO_RELOAD" -eq 1 ]; then
    echo "Reloading systemd daemon (requires sudo)"
    sudo systemctl daemon-reload
fi

# 7) Optional: run installer script
if [ "$DO_INSTALL" -eq 1 ]; then
    INSTALL_SCRIPT="$REPO_DIR/usb_download_mvp/scripts/install_service.sh"
    if [ -x "$INSTALL_SCRIPT" ]; then
        echo "Running installer: $INSTALL_SCRIPT (requires sudo for some operations)"
        sudo bash "$INSTALL_SCRIPT"
    else
        echo "Installer not found or not executable: $INSTALL_SCRIPT" >&2
    fi
fi

# 8) Show status
echo "Done. Current HEAD:"
git --no-pager log -n 1 --oneline

echo -e "\nIf you previously had local changes, they were stashed as 'pre-pull-$TS'.\nInspect with: git stash list; to restore: git stash pop <stash@{N}>\n"

exit 0
