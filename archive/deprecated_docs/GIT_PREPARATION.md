# Git Repository Preparation Checklist

Before pushing to Git and testing on fresh Pi, ensure the repository is ready.

## 📋 Pre-Push Checklist

### 1. Files to Include (Essential)

**Core Application:**
- ✓ All `*.py` files (meter_manager, mqtt_client, terminal_meter_ui, etc.)
- ✓ `config.json`, `device_config.json` (or examples)
- ✓ `setup_launchers/` directory with all `.sh` scripts
- ✓ `setup_launchers/*.desktop` files
- ✓ `docs/` directory with all documentation
- ✓ `packages_folder/` with all `.whl` files
- ✓ `usb_download_mvp/` complete directory
- ✓ `compat/`, `tools/`, `examples/` directories
- ✓ All helper scripts (`terminal_ui.sh`, `one_click_system_py313.sh`, etc.)

**Testing Scripts:**
- ✓ `test_complete_setup.sh`
- ✓ `quick_test.sh`
- ✓ `preflight_check.sh`

**Documentation:**
- ✓ `README.md`
- ✓ `WORKSPACE_ORGANIZATION.md`
- ✓ `TESTING_GUIDE.md`
- ✓ `FRESH_PI_TEST_INSTRUCTIONS.md`
- ✓ `GIT_PREPARATION.md` (this file)

**Symlinks:**
- ✓ `quick_start` → `setup_launchers/quick_setup.sh`
- ✓ `complete_setup` → `setup_launchers/master_setup.sh`
- ✓ `QUICKSTART.md` → `docs/SETUP_GUIDE.md`

### 2. Files to Exclude (.gitignore)

Create/update `.gitignore`:

```gitignore
# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so

# Virtual environment
venv/
env/
ENV/

# Logs
logs/*.log
*.log
mqtt_log.txt
rtc_drift_log.csv

# Data files (exclude actual meter readings, keep directory structure)
data/csv/*.csv
!data/csv/.gitkeep

# Exports
exports/

# IDE/Editor
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Test results
test_results/
/tmp/

# Local config overrides (if you create them)
local_config.json
config.local.json

# Service PIDs
*.pid
```

### 3. Create .gitkeep Files

Keep empty directories in git:

```bash
# Create .gitkeep files for empty directories
touch data/csv/.gitkeep
touch logs/.gitkeep
touch exports/.gitkeep
touch test_results/.gitkeep
```

### 4. Verify File Permissions

Before committing:

```bash
# Make all scripts executable
chmod +x setup_launchers/*.sh
chmod +x *.sh
chmod +x terminal_ui.sh
chmod +x one_click_system_py313.sh
chmod +x update_pull.sh
chmod +x usb_download_mvp/scripts/*.sh

# Make test scripts executable
chmod +x test_complete_setup.sh
chmod +x quick_test.sh
chmod +x preflight_check.sh

# Verify
git ls-files --stage | grep -E '\\.sh$'
# Should show mode 100755 for executable files
```

### 5. Check for Sensitive Data

**Before committing, search for:**

```bash
# Check for passwords, API keys, tokens
grep -r -i "password" --exclude-dir=.git --exclude-dir=venv
grep -r -i "api_key" --exclude-dir=.git --exclude-dir=venv
grep -r -i "token" --exclude-dir=.git --exclude-dir=venv
grep -r -i "secret" --exclude-dir=.git --exclude-dir=venv

# Check config files
cat config.json | grep -i "password\|api_key\|token"
cat device_config.json | grep -i "password\|api_key\|token"
```

**If found:**
- Replace with placeholders: `"password": "YOUR_PASSWORD_HERE"`
- Or use example configs in `examples/` directory

### 6. Validate JSON Files

```bash
# Check all JSON files are valid
for file in *.json examples/*.jsonc; do
    echo "Checking $file..."
    python3 -c "import json; json.load(open('$file'))" 2>&1 || echo "FAILED: $file"
done
```

### 7. Test Symlinks

```bash
# Verify symlinks are relative, not absolute
ls -la quick_start complete_setup QUICKSTART.md

# Should show:
# quick_start -> setup_launchers/quick_setup.sh
# complete_setup -> setup_launchers/master_setup.sh
# QUICKSTART.md -> docs/SETUP_GUIDE.md

# NOT:
# quick_start -> /home/pi/Desktop/offline-setup-12Sep/setup_launchers/quick_setup.sh
```

**If absolute paths:**
```bash
rm quick_start complete_setup QUICKSTART.md
ln -s setup_launchers/quick_setup.sh quick_start
ln -s setup_launchers/master_setup.sh complete_setup
ln -s docs/SETUP_GUIDE.md QUICKSTART.md
```

### 8. Update README with Git Instructions

Ensure `README.md` has clone instructions:

```markdown
## Clone this repository

```bash
cd ~/Desktop
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git offline-setup-12Sep
cd offline-setup-12Sep
```

## Quick Start
```bash
sudo bash test_complete_setup.sh
```
````

---

## 🚀 Git Commands

### Initial Setup (if not already a repo)

```bash
cd ~/Desktop/offline-setup-12Sep

# Initialize git
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Create .gitignore (see section 2 above)
nano .gitignore

# Add all files
git add .

# First commit
git commit -m "Initial commit: Complete meter monitoring system with testing framework"

# Push to GitHub
git push -u origin main
```

### Update Existing Repo

```bash
cd ~/Desktop/offline-setup-12Sep

# Check status
git status

# Review changes
git diff

# Stage all changes
git add .

# Commit
git commit -m "Add comprehensive testing framework and reorganize workspace"

# Push
git push origin main
```

### Before Testing on Fresh Pi

```bash
# 1. Ensure all changes are committed
git status
# Should show: "nothing to commit, working tree clean"

# 2. Tag the test version
git tag -a v1.0-test1 -m "First complete test version"
git push origin v1.0-test1

# 3. Note the commit hash
git log -1
# Copy the commit hash for reference
```

---

## ✅ Pre-Push Validation

Run this complete check before pushing:

```bash
#!/bin/bash
echo "Git Pre-Push Validation"
echo "======================="

# 1. Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠ Warning: Uncommitted changes"
    git status --short
else
    echo "✓ No uncommitted changes"
fi

# 2. Check for large files (>10MB)
find . -type f -size +10M ! -path "./.git/*" ! -path "./venv/*"
# Should find only wheel files in packages_folder/

# 3. Verify .gitignore exists
if [ -f .gitignore ]; then
    echo "✓ .gitignore exists"
else
    echo "✗ .gitignore missing!"
fi

# 4. Check symlinks
if [ -L quick_start ] && [ -L complete_setup ]; then
    echo "✓ Symlinks present"
else
    echo "✗ Symlinks missing"
fi

# 5. Verify test scripts
if [ -x test_complete_setup.sh ] && [ -x quick_test.sh ]; then
    echo "✓ Test scripts executable"
else
    echo "✗ Test scripts not executable"
fi

# 6. Check README
if grep -q "git clone" README.md; then
    echo "✓ README has clone instructions"
else
    echo "⚠ README missing clone instructions"
fi

echo ""
echo "If all checks pass, ready to push!"
echo "Run: git push origin main"
```

---

## 📦 What Gets Pushed vs What Stays Local

### PUSH (Include in Git):
- ✓ All source code
- ✓ Documentation
- ✓ Setup scripts
- ✓ Test scripts
- ✓ Offline packages (`.whl` files)
- ✓ Example configs
- ✓ Empty directory structure

### DON'T PUSH (Exclude from Git):
- ✗ Virtual environments (`venv/`)
- ✗ Log files (`logs/*.log`)
- ✗ Actual meter data (`data/csv/*.csv`)
- ✗ Python cache (`__pycache__/`)
- ✗ Test results
- ✗ Generated exports
- ✗ IDE config (`.vscode/`, `.idea/`)

---

## 🧪 Post-Push Verification

After pushing, verify on GitHub:

```bash
# 1. Check GitHub web interface
# - All files present?
# - README displays correctly?
# - Symlinks work?

# 2. Test clone on different machine
cd /tmp
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git test-clone
cd test-clone
ls -la
bash quick_test.sh
cd .. && rm -rf test-clone
```

---

## 🔄 Continuous Integration (Future)

For production, consider:

1. **GitHub Actions** to run `quick_test.sh` on every push
2. **Pre-commit hooks** to validate files before commit
3. **Version tags** for releases (v1.0, v1.1, etc.)
4. **Branch protection** on main branch

---

## 📝 Commit Message Convention

Use clear, descriptive messages:

```bash
# Good:
git commit -m "Add comprehensive testing framework with 20 test suites"
git commit -m "Fix: Correct desktop file paths after reorganization"
git commit -m "Docs: Add fresh Pi testing instructions"

# Bad:
git commit -m "updates"
git commit -m "fix bug"
git commit -m "wip"
```

---

## 🆘 Common Git Issues

### Issue: Large files rejected

```bash
# GitHub has 100MB file size limit
# Check file sizes:
find . -type f -size +50M ! -path "./.git/*"

# If wheel files are too large, consider:
# 1. Use Git LFS for large files
# 2. Host wheels separately
# 3. Download wheels during setup instead
```

### Issue: Symlinks not working on Windows

```bash
# Symlinks may not work on Windows clone
# Solution: Add README note for Windows users
# Or create .bat scripts instead
```

### Issue: File permissions lost

```bash
# Git preserves execute bit, but may need manual fix
# After clone, run:
find . -name "*.sh" -exec chmod +x {} \;
```

---

## ✅ Final Checklist Before Fresh Pi Test

- [ ] All changes committed
- [ ] .gitignore configured
- [ ] No sensitive data in repo
- [ ] Symlinks are relative paths
- [ ] Test scripts executable
- [ ] Documentation complete
- [ ] Pushed to GitHub
- [ ] Test clone works
- [ ] README has clone instructions
- [ ] Version tagged

**If all checked:** Ready for fresh Pi test! 🚀

---

**Next Step:** Follow `FRESH_PI_TEST_INSTRUCTIONS.md`
