#!/bin/bash

# Backup and Pull Script
# Creates a backup of current changes before pulling from the reorganization branch

set -e

REPO_URL="https://github.com/VinitSadhanapada/Offline_Deploy_12Sep.git"
BRANCH_NAME="project-reorganization-2025-12-31"
REMOTE_NAME="origin-reorganization"
BACKUP_BRANCH="backup-$(date +%Y%m%d-%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Backup and Pull Script ===${NC}"

# Check if there are uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Uncommitted changes detected${NC}"
    echo -e "${YELLOW}Creating backup branch: ${BACKUP_BRANCH}${NC}"
    
    # Create backup branch
    CURRENT_BRANCH=$(git branch --show-current)
    git checkout -b ${BACKUP_BRANCH}
    git add .
    git commit -m "Backup before pulling ${BRANCH_NAME} - $(date)"
    
    # Switch back to original branch
    git checkout ${CURRENT_BRANCH}
    
    echo -e "${GREEN}Backup created successfully on branch: ${BACKUP_BRANCH}${NC}"
else
    echo -e "${GREEN}No uncommitted changes found${NC}"
fi

# Add remote if doesn't exist
if ! git remote | grep -q "^${REMOTE_NAME}$"; then
    echo -e "${YELLOW}Adding remote...${NC}"
    git remote add ${REMOTE_NAME} ${REPO_URL}
fi

# Fetch and merge
echo -e "${YELLOW}Fetching latest changes...${NC}"
git fetch ${REMOTE_NAME} ${BRANCH_NAME}

echo -e "${YELLOW}Merging changes...${NC}"
git merge ${REMOTE_NAME}/${BRANCH_NAME}

echo ""
echo -e "${GREEN}=== Pull completed successfully! ===${NC}"
if [ ! -z "${BACKUP_BRANCH}" ]; then
    echo -e "${BLUE}Backup available on branch: ${BACKUP_BRANCH}${NC}"
    echo -e "${BLUE}To restore backup: git checkout ${BACKUP_BRANCH}${NC}"
fi

echo ""
echo -e "${BLUE}Current status:${NC}"
git status --short
git log --oneline -3