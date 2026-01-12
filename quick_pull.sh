#!/bin/bash

# Quick Pull Script - Fast pull from project-reorganization-2025-12-31 branch
# Usage: ./quick_pull.sh [merge|checkout|branch_name]

set -e

REPO_URL="https://github.com/VinitSadhanapada/Offline_Deploy_12Sep.git"
BRANCH_NAME="project-reorganization-2025-12-31"
REMOTE_NAME="origin-reorganization"
ACTION=${1:-"merge"}  # Default action is merge

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Quick pulling from ${BRANCH_NAME}...${NC}"

# Add remote if doesn't exist
if ! git remote | grep -q "^${REMOTE_NAME}$"; then
    git remote add ${REMOTE_NAME} ${REPO_URL}
fi

# Fetch the branch
git fetch ${REMOTE_NAME} ${BRANCH_NAME}

# Perform the requested action
case $ACTION in
    "merge")
        echo -e "${YELLOW}Merging changes...${NC}"
        git merge ${REMOTE_NAME}/${BRANCH_NAME}
        ;;
    "checkout")
        echo -e "${YELLOW}Checking out branch...${NC}"
        git checkout ${REMOTE_NAME}/${BRANCH_NAME}
        ;;
    *)
        echo -e "${YELLOW}Creating local branch '${ACTION}'...${NC}"
        git checkout -b ${ACTION} ${REMOTE_NAME}/${BRANCH_NAME}
        ;;
esac

echo -e "${GREEN}Pull completed!${NC}"
git status --short