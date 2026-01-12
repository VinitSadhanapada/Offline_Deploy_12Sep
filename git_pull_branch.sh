#!/bin/bash

# Git Pull Branch Script
# Pulls from specific branch: project-reorganization-2025-12-31
# Repository: https://github.com/VinitSadhanapada/Offline_Deploy_12Sep

set -e  # Exit on any error

# Configuration
REPO_URL="https://github.com/VinitSadhanapada/Offline_Deploy_12Sep.git"
BRANCH_NAME="project-reorganization-2025-12-31"
REMOTE_NAME="origin-reorganization"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Git Pull Branch Script ===${NC}"
echo -e "${BLUE}Repository: ${REPO_URL}${NC}"
echo -e "${BLUE}Branch: ${BRANCH_NAME}${NC}"
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    echo -e "${YELLOW}Initialize git repository first with: git init${NC}"
    exit 1
fi

# Function to check if remote exists
check_remote_exists() {
    git remote | grep -q "^${REMOTE_NAME}$"
}

# Add remote if it doesn't exist
if check_remote_exists; then
    echo -e "${GREEN}Remote '${REMOTE_NAME}' already exists${NC}"
else
    echo -e "${YELLOW}Adding remote '${REMOTE_NAME}'...${NC}"
    git remote add ${REMOTE_NAME} ${REPO_URL}
    echo -e "${GREEN}Remote '${REMOTE_NAME}' added successfully${NC}"
fi

# Fetch the specific branch
echo -e "${YELLOW}Fetching branch '${BRANCH_NAME}' from remote...${NC}"
git fetch ${REMOTE_NAME} ${BRANCH_NAME}

# Check current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "detached")
echo -e "${BLUE}Current branch: ${CURRENT_BRANCH}${NC}"

# Show options to user
echo ""
echo -e "${YELLOW}Choose how to integrate the changes:${NC}"
echo "1. Checkout the branch (switch to it directly)"
echo "2. Create new local branch and checkout"
echo "3. Merge into current branch"
echo "4. View diff only (no changes)"
echo "5. Cancel"
echo ""

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo -e "${YELLOW}Checking out branch '${BRANCH_NAME}'...${NC}"
        git checkout ${REMOTE_NAME}/${BRANCH_NAME}
        echo -e "${GREEN}Successfully checked out '${BRANCH_NAME}'${NC}"
        ;;
    2)
        read -p "Enter local branch name (default: ${BRANCH_NAME}): " local_branch
        local_branch=${local_branch:-$BRANCH_NAME}
        echo -e "${YELLOW}Creating and checking out local branch '${local_branch}'...${NC}"
        git checkout -b ${local_branch} ${REMOTE_NAME}/${BRANCH_NAME}
        echo -e "${GREEN}Successfully created and checked out '${local_branch}'${NC}"
        ;;
    3)
        if [ "$CURRENT_BRANCH" = "detached" ]; then
            echo -e "${RED}Error: Cannot merge into detached HEAD${NC}"
            echo -e "${YELLOW}Please checkout a branch first${NC}"
            exit 1
        fi
        echo -e "${YELLOW}Merging '${BRANCH_NAME}' into '${CURRENT_BRANCH}'...${NC}"
        git merge ${REMOTE_NAME}/${BRANCH_NAME}
        echo -e "${GREEN}Successfully merged '${BRANCH_NAME}' into '${CURRENT_BRANCH}'${NC}"
        ;;
    4)
        echo -e "${YELLOW}Showing diff between current state and '${BRANCH_NAME}'...${NC}"
        git diff HEAD ${REMOTE_NAME}/${BRANCH_NAME} --stat
        echo ""
        echo -e "${BLUE}To see detailed diff, run:${NC}"
        echo "git diff HEAD ${REMOTE_NAME}/${BRANCH_NAME}"
        ;;
    5)
        echo -e "${YELLOW}Operation cancelled${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Show current status
echo ""
echo -e "${BLUE}=== Current Git Status ===${NC}"
git status --short
git log --oneline -5

echo ""
echo -e "${GREEN}Operation completed successfully!${NC}"