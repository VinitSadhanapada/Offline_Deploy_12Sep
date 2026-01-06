# Project Reorganization Plan
## Raspberry Pi Meter Monitoring System - Professional Documentation & Structure

**Date:** 31 December 2025  
**Purpose:** Transform the current workspace into a professionally documented, handover-ready codebase  
**Current State:** Functional but documentation scattered across 19 markdown files  
**Target State:** Clean, organized, production-ready structure with consolidated documentation

---

## Executive Summary

### Current Issues Identified
1. **Documentation Fragmentation**: 19 markdown files scattered across root, docs/, and subdirectories
2. **Duplicate Content**: Multiple overlapping guides (4+ quickstart variants, 3+ README files)
3. **Unclear Entry Points**: User confusion about where to start (START_HERE.md vs QUICKSTART.md vs README.md)
4. **Mixed Concerns**: Testing docs mixed with user guides, setup scripts scattered
5. **Legacy Files**: Old symlinks (quick_start, complete_setup), outdated READMEs in docs/
6. **No Developer Documentation**: No clear architecture guide for maintainers

### Reorganization Goals
✅ **Single source of truth** for each topic  
✅ **Clear separation** between user guides, developer docs, and deployment guides  
✅ **Professional structure** following industry best practices  
✅ **Easy handover** with comprehensive maintainer documentation  
✅ **Keep testing framework** but organize it properly  

---

## Proposed Directory Structure

```
offline-setup-12Sep/
│
├── README.md                          ← Project overview & quick navigation
├── CHANGELOG.md                       ← Version history (NEW)
├── LICENSE                            ← License file (if applicable)
│
├── docs/                              ← ALL documentation (restructured)
│   ├── user/                          ← End-user guides
│   │   ├── QUICKSTART.md             ← First-time setup (consolidated)
│   │   ├── SSH_ACCESS.md             ← SSH and remote access guide
│   │   ├── TERMINAL_UI.md            ← Terminal UI usage guide
│   │   ├── DESKTOP_UI.md             ← Desktop GUI guide (NEW)
│   │   ├── DATA_EXPORT.md            ← CSV download & USB export
│   │   └── TROUBLESHOOTING.md        ← Common issues & solutions
│   │
│   ├── deployment/                    ← Deployment & installation
│   │   ├── FRESH_PI_SETUP.md         ← Fresh Raspberry Pi installation
│   │   ├── NETWORK_SETUP.md          ← Ethernet & WiFi AP configuration
│   │   ├── PYTHON_UPGRADE.md         ← Python 3.13 upgrade guide
│   │   └── PRODUCTION_DEPLOYMENT.md  ← Production deployment checklist
│   │
│   ├── developer/                     ← Developer & maintainer docs (NEW)
│   │   ├── ARCHITECTURE.md           ← System architecture overview
│   │   ├── CODE_STRUCTURE.md         ← Code organization & modules
│   │   ├── METER_DRIVERS.md          ← Elmeasure driver documentation
│   │   ├── CONFIGURATION.md          ← Config file format & options
│   │   ├── CONTRIBUTING.md           ← Development guidelines
│   │   └── API_REFERENCE.md          ← Python module API docs
│   │
│   └── testing/                       ← Testing documentation
│       ├── TESTING_GUIDE.md          ← Testing framework overview
│       ├── TEST_CHECKLIST.md         ← Manual test procedures
│       └── AUTOMATED_TESTS.md        ← test_complete_setup.sh guide
│
├── src/                               ← Core application code (NEW folder)
│   ├── __init__.py                   
│   ├── dashboard/                     ← Dashboard components
│   │   ├── __init__.py
│   │   ├── simple_rpi_dashboard.py   ← Main dashboard engine
│   │   ├── simple_meter_ui.py        ← Desktop GUI
│   │   └── terminal_meter_ui.py      ← Terminal/SSH UI
│   │
│   ├── devices/                       ← Meter device drivers
│   │   ├── __init__.py
│   │   ├── meter_device.py           ← MeterDevice class
│   │   ├── meter_manager.py          ← MeterManager class
│   │   ├── elmeasure_LG6400.py       ← Device-specific drivers
│   │   ├── elmeasure_LG5310.py
│   │   ├── elmeasure_LG5220.py
│   │   ├── elmeasure_EN8410.py
│   │   └── elmeasure_iELR300.py
│   │
│   ├── network/                       ← Network & sync components
│   │   ├── __init__.py
│   │   ├── cloud_sync.py             ← Cloud synchronization
│   │   ├── mqtt_client.py            ← MQTT client
│   │   └── netwatch_trigger.py       ← Network monitoring
│   │
│   ├── utils/                         ← Utility modules
│   │   ├── __init__.py
│   │   ├── macros.py                 ← Constants & device types
│   │   ├── paths.py                  ← Path management
│   │   ├── venv_utils.py             ← Virtual environment utilities
│   │   └── rpi_status_led.py         ← RPi LED control
│   │
│   └── compat/                        ← Compatibility layers
│       ├── __init__.py
│       └── pymodbus_compat.py        ← Pymodbus version compatibility
│
├── scripts/                           ← Executable scripts (reorganized)
│   ├── setup/                         ← Setup & installation scripts
│   │   ├── master_setup.sh           ← Complete automated setup
│   │   ├── quick_setup.sh            ← Interactive setup menu
│   │   ├── enable_auto_start.sh      ← Service installation
│   │   ├── setup_static_ethernet.sh  ← Network configuration
│   │   └── one_click_system_py313.sh ← Python environment setup
│   │
│   ├── launchers/                     ← UI launcher scripts
│   │   ├── terminal_ui.sh            ← Terminal UI launcher
│   │   ├── MasterSetup_Admin.desktop ← Desktop shortcuts
│   │   └── SimpleMeterUI_Admin.desktop
│   │
│   ├── system/                        ← System maintenance scripts
│   │   ├── update_pull.sh            ← Git update script
│   │   ├── download_meter_data.sh    ← Data download helper
│   │   ├── set_rtc_from_system.py    ← RTC synchronization
│   │   └── usb_csv_auto_copy.py      ← USB auto-copy script
│   │
│   └── config/                        ← Configuration helpers
│       ├── configure_device.py       ← Device configuration tool
│       └── sitecustomize.py          ← Python site customization
│
├── tests/                             ← All testing code (NEW folder)
│   ├── test_complete_setup.sh        ← Comprehensive test suite
│   ├── quick_test.sh                 ← Quick validation
│   ├── preflight_check.sh            ← Pre-installation checks
│   └── test_results/                 ← Test output directory
│
├── config/                            ← Configuration files
│   ├── config.json                   ← Main configuration
│   ├── device_config.json            ← Device configuration
│   └── examples/                     ← Example configs
│       ├── config.example.jsonc
│       └── device_config.example.jsonc
│
├── data/                              ← Runtime data (unchanged)
│   └── csv/                          ← CSV readings storage
│
├── logs/                              ← Log files (unchanged)
│
├── exports/                           ← CSV export directory
│
├── packages/                          ← Offline Python packages
│   ├── README.md                     ← Package manifest
│   └── *.whl                         ← Wheel files
│
├── usb_download_mvp/                  ← USB download server (unchanged)
│   ├── README.md                     ← Server-specific docs
│   ├── server.py
│   ├── scripts/
│   ├── systemd/
│   └── ...
│
├── tools/                             ← Development tools
│   └── jsonc_get.py                  ← JSONC parser utility
│
└── archive/                           ← Legacy/deprecated files (NEW)
    ├── old_scripts/
    ├── deprecated_docs/
    └── ARCHIVE_README.md             ← Archive inventory
```

---

## Documentation Consolidation Plan

### Phase 1: User Documentation (docs/user/)

#### 1. QUICKSTART.md (Consolidate 4 files → 1)
**Merge:**
- ROOT/QUICKSTART.md
- docs/README_QUICKSTART.md
- docs/QUICKSTART_SSH_UI.md
- ROOT/START_HERE.md

**Content Structure:**
```markdown
# Quick Start Guide
## Prerequisites
## Installation Methods
  - Fresh Pi Clone & Setup
  - Existing System Installation
## First Run
  - Desktop UI Launch
  - Terminal/SSH Access
## Verification
## Next Steps
```

#### 2. SSH_ACCESS.md (Consolidate 2 files → 1)
**Merge:**
- docs/README_SSH_TERMINAL_UI.md
- docs/QUICKSTART_SSH_UI.md (SSH sections)

**Content Structure:**
```markdown
# SSH Access & Remote Management
## Network Configuration
  - Ethernet Static IP (192.168.137.100)
  - WiFi AP Mode (192.168.4.1)
## SSH Connection
## Terminal UI Usage
## File Download (SCP/RSYNC)
## WiFi AP Control
```

#### 3. TERMINAL_UI.md (New consolidated doc)
**Merge:**
- docs/TERMINAL_UI_SUMMARY.md
- terminal_meter_ui.py inline docs
- docs/SSH_UI_VISUAL_GUIDE.txt

**Content Structure:**
```markdown
# Terminal UI Guide
## Features Overview
## Menu Navigation
## Live Readings View
## CSV Export
## System Status
## WiFi AP Control
## Keyboard Shortcuts
## Screenshots (ASCII art)
```

#### 4. DESKTOP_UI.md (New doc)
**Source:**
- simple_meter_ui.py inline documentation
- Extract features & usage

**Content Structure:**
```markdown
# Desktop GUI Application
## Features
## Installation
## Usage
## Configuration
## Troubleshooting
```

#### 5. DATA_EXPORT.md (New doc)
**Source:**
- Scattered across multiple READMEs
- SCP/download instructions

**Content Structure:**
```markdown
# Data Export & Download
## CSV File Structure
## Export Methods
  - SSH/SCP Download
  - USB Auto-Copy
  - Terminal UI Export
## Data Organization
## Automated Backups
```

#### 6. TROUBLESHOOTING.md (New doc)
**Source:**
- Extract from all README files
- Common issues from testing

**Content Structure:**
```markdown
# Troubleshooting Guide
## Installation Issues
## Network Connection Problems
## Meter Communication Errors
## Service Status Checks
## Log Analysis
## Factory Reset
```

---

### Phase 2: Deployment Documentation (docs/deployment/)

#### 1. FRESH_PI_SETUP.md (Consolidate 2 files → 1)
**Merge:**
- ROOT/FRESH_PI_TEST_INSTRUCTIONS.md
- docs/FAST_DEPLOY_PI.md

**Content Structure:**
```markdown
# Fresh Raspberry Pi Setup
## Hardware Requirements
## OS Installation
## Clone Repository
## Run Automated Setup
## Verification
## Production Deployment
```

#### 2. NETWORK_SETUP.md (New doc)
**Source:**
- setup_static_ethernet.sh documentation
- usb_download_mvp/README.md (AP sections)

**Content Structure:**
```markdown
# Network Configuration
## Ethernet Static IP Setup
## WiFi AP Mode
## Dual-Interface Operation
## NetworkManager vs dhcpcd
## Firewall Configuration
```

#### 3. PYTHON_UPGRADE.md (Rename & consolidate)
**Current:**
- docs/UPGRADE_PYTHON_3.13.md

**Keep as-is, just move to deployment/**

#### 4. PRODUCTION_DEPLOYMENT.md (Consolidate)
**Merge:**
- docs/PRODUCTION_README.md
- ROOT/GIT_PREPARATION.md (relevant sections)

**Content Structure:**
```markdown
# Production Deployment Checklist
## Pre-Deployment
## Installation Steps
## Service Configuration
## Security Hardening
## Monitoring Setup
## Backup Strategy
## Sign-Off Checklist
```

---

### Phase 3: Developer Documentation (docs/developer/) **[NEW]**

#### 1. ARCHITECTURE.md (New comprehensive doc)
**Content:**
```markdown
# System Architecture
## Overview Diagram
## Component Layers
  - Dashboard Engine (simple_rpi_dashboard.py)
  - UI Layer (GUI, Terminal UI)
  - Device Layer (MeterDevice, MeterManager)
  - Drivers (Elmeasure modules)
  - Network Layer (Cloud sync, MQTT)
## Data Flow
## Service Architecture
## Configuration System
```

#### 2. CODE_STRUCTURE.md (New doc)
**Content:**
```markdown
# Code Structure & Organization
## Module Hierarchy
## File Purpose Reference
## Import Dependencies
## Configuration Files
## Data Directories
## Key Classes
  - MeterDevice
  - MeterManager
  - Dashboard components
```

#### 3. METER_DRIVERS.md (New doc)
**Content:**
```markdown
# Meter Driver Development
## Supported Models
  - LG6400, LG5310, LG5220
  - EN8410, EN8100
  - iELR300
## Driver Interface
## Modbus Communication
## Adding New Meter Models
## Testing Drivers
## Simulation Mode
```

#### 4. CONFIGURATION.md (New doc)
**Content:**
```markdown
# Configuration Reference
## config.json Format
## device_config.json Format
## Runtime Settings
## Environment Variables
## Service Configuration
## Example Configurations
```

#### 5. CONTRIBUTING.md (New doc)
**Content:**
```markdown
# Development Guidelines
## Getting Started
## Code Style
## Git Workflow
## Testing Requirements
## Pull Request Process
## Release Process
```

#### 6. API_REFERENCE.md (New doc)
**Content:**
```markdown
# Python Module API Reference
## meter_device.py
  - MeterDevice class
## meter_manager.py
  - MeterManager class
## Utility Modules
## Network Modules
## Configuration Helpers
```

---

### Phase 4: Testing Documentation (docs/testing/)

#### 1. TESTING_GUIDE.md (Consolidate)
**Merge:**
- ROOT/TESTING_GUIDE.md
- ROOT/TESTING_FRAMEWORK_SUMMARY.md

#### 2. TEST_CHECKLIST.md (New doc)
**Source:**
- Extract manual test procedures from TESTING_GUIDE.md

#### 3. AUTOMATED_TESTS.md (New doc)
**Source:**
- test_complete_setup.sh inline documentation
- Quick test & preflight check docs

---

## Code Reorganization Plan

### Phase 5: Source Code Organization

#### 1. Create src/ directory structure
```bash
mkdir -p src/{dashboard,devices,network,utils,compat}
touch src/__init__.py src/*/__init__.py
```

#### 2. Move Python files to src/
```bash
# Dashboard components
mv simple_rpi_dashboard.py src/dashboard/
mv simple_meter_ui.py src/dashboard/
mv terminal_meter_ui.py src/dashboard/

# Device drivers
mv meter_device.py src/devices/
mv meter_manager.py src/devices/
mv elmeasure_*.py src/devices/

# Network components
mv cloud_sync.py src/network/
mv mqtt_client.py src/network/
mv netwatch_trigger.py src/network/

# Utilities
mv macros.py src/utils/
mv paths.py src/utils/
mv venv_utils.py src/utils/
mv rpi_status_led.py src/utils/

# Compatibility
mv compat/pymodbus_compat.py src/compat/
```

#### 3. Update import paths
- Update all Python files to use new src/ structure
- Add src/ to Python path in launcher scripts
- Update systemd service files

#### 4. Create __init__.py files
- Export key classes/functions for easier imports
- Add version information

---

### Phase 6: Scripts Organization

#### 1. Create scripts/ structure
```bash
mkdir -p scripts/{setup,launchers,system,config}
```

#### 2. Move scripts
```bash
# Setup scripts
mv setup_launchers/*.sh scripts/setup/
mv setup_launchers/*.desktop scripts/launchers/

# System scripts
mv update_pull.sh scripts/system/
mv download_meter_data.sh scripts/system/
mv set_rtc_from_system.py scripts/system/
mv usb_csv_auto_copy.py scripts/system/

# Config scripts
mv configure_device.py scripts/config/
mv sitecustomize.py scripts/config/
```

#### 3. Update script references
- Update all scripts to reference new paths
- Update systemd service files
- Update desktop shortcuts
- Update documentation

---

### Phase 7: Configuration & Data

#### 1. Create config/ directory
```bash
mkdir -p config/examples
mv config.json config/
mv device_config.json config/
cp config/config.json config/examples/config.example.jsonc
cp config/device_config.json config/examples/device_config.example.jsonc
```

#### 2. Update config references
- Update all Python scripts to look in config/
- Add fallback to root directory for compatibility

---

### Phase 8: Testing Organization

#### 1. Create tests/ directory
```bash
mkdir -p tests/test_results
mv test_complete_setup.sh tests/
mv quick_test.sh tests/
mv preflight_check.sh tests/
```

#### 2. Update test scripts
- Fix paths to reference new structure
- Update documentation

---

### Phase 9: Archive Legacy Files

#### 1. Create archive/ directory
```bash
mkdir -p archive/{old_scripts,deprecated_docs}
```

#### 2. Move legacy files
```bash
# Old symlinks
mv quick_start archive/old_scripts/
mv complete_setup archive/old_scripts/

# Deprecated docs
mv docs/LEGACY_README_ENABLE_PERMISSION.txt archive/deprecated_docs/
mv docs/README_RUNTIME_FALLBACK.md archive/deprecated_docs/  # If superseded
```

#### 3. Create archive inventory
```bash
echo "# Archive Inventory" > archive/ARCHIVE_README.md
echo "Files moved here are deprecated but kept for reference" >> archive/ARCHIVE_README.md
```

---

## Root-Level Files

### New/Updated Root Files

#### 1. README.md (Rewrite)
**Content:**
```markdown
# Raspberry Pi Meter Monitoring System

Professional energy meter data acquisition system for Raspberry Pi.
Supports multiple Elmeasure meter models via Modbus RTU.

## Quick Navigation
- **New Users**: Start with [docs/user/QUICKSTART.md](docs/user/QUICKSTART.md)
- **Deployment**: See [docs/deployment/FRESH_PI_SETUP.md](docs/deployment/FRESH_PI_SETUP.md)
- **Developers**: Read [docs/developer/ARCHITECTURE.md](docs/developer/ARCHITECTURE.md)
- **Testing**: Check [docs/testing/TESTING_GUIDE.md](docs/testing/TESTING_GUIDE.md)

## Features
- Multi-meter support (LG6400, LG5310, EN8410, etc.)
- Real-time CSV data logging
- Desktop & Terminal UIs
- SSH remote access
- WiFi Access Point mode
- Cloud synchronization (MQTT)
- USB data export

## Installation
```bash
git clone <repo-url> offline-setup-12Sep
cd offline-setup-12Sep
sudo bash scripts/setup/master_setup.sh
```

## Documentation
See [docs/](docs/) directory for complete documentation.

## License
[Add license info]
```

#### 2. CHANGELOG.md (New)
```markdown
# Changelog
All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- WiFi AP toggle control in Terminal UI
- IP address detection fix (shows actual LAN IP)
- Comprehensive testing framework
- NetworkManager support for static Ethernet

### Changed
- Reorganized project structure
- Consolidated documentation
- Moved scripts to scripts/ directory
- Moved source code to src/ directory

### Fixed
- Terminal UI path resolution issues
- Static IP configuration with NetworkManager
- Bash compatibility in test scripts

## [1.0.0] - 2025-12-31
- Initial production-ready release
```

---

## Implementation Phases

### Phase Timeline (Suggested)

#### Phase 1: Documentation Consolidation (Day 1-2)
- ✅ Create new docs/ structure
- ✅ Write/consolidate user documentation
- ✅ Create developer documentation
- ✅ Update root README.md
- ⏳ Remove duplicates

#### Phase 2: Code Organization (Day 3-4)
- Create src/ directory structure
- Move Python files
- Update import paths
- Test all functionality

#### Phase 3: Scripts Organization (Day 4-5)
- Create scripts/ structure
- Move shell scripts
- Update references
- Test setup process

#### Phase 4: Configuration & Testing (Day 5-6)
- Organize config/ directory
- Move testing files
- Update all paths
- Run full test suite

#### Phase 5: Cleanup & Archive (Day 6)
- Archive legacy files
- Remove duplicates
- Final testing
- Create CHANGELOG.md

#### Phase 6: Documentation Review (Day 7)
- Proofread all docs
- Verify all links
- Test installation flow
- Final handover preparation

---

## Breaking Changes & Migration

### Import Path Changes
**Before:**
```python
from meter_device import MeterDevice
from simple_rpi_dashboard import Dashboard
```

**After:**
```python
from src.devices.meter_device import MeterDevice
from src.dashboard.simple_rpi_dashboard import Dashboard
```

### Script Path Changes
**Before:**
```bash
./setup_launchers/master_setup.sh
./terminal_ui.sh
```

**After:**
```bash
./scripts/setup/master_setup.sh
./scripts/launchers/terminal_ui.sh
```

### Config Path Changes
**Before:**
```python
config_file = "config.json"
```

**After:**
```python
config_file = "config/config.json"
# With fallback: config.json (for compatibility)
```

---

## Compatibility Considerations

### 1. Maintain backwards compatibility where possible
- Keep symlinks for critical paths (temporary)
- Add fallback config paths
- Provide migration script

### 2. Create migration helper script
```bash
scripts/migrate_v1_to_v2.sh
```

### 3. Update systemd services
- Modify service files to use new paths
- Reload systemd daemon
- Restart services

---

## Documentation Standards

### Markdown File Structure
```markdown
# Title (H1 - One per file)

Brief description (1-2 sentences)

## Section (H2)
### Subsection (H3)

- Bullet points for lists
- `code` for inline code
```bash
# Code blocks for commands
```

**Bold** for emphasis
*Italic* for terms

> Blockquotes for notes/warnings
```

### Code Documentation
- All Python files: docstrings for modules, classes, functions
- All shell scripts: Header comment with purpose, usage, author
- Inline comments for complex logic

---

## Quality Checklist

### Before Handover
- [ ] All documentation consolidated
- [ ] No duplicate READMEs
- [ ] Clear entry point (README.md)
- [ ] Architecture documented
- [ ] All scripts tested
- [ ] Import paths verified
- [ ] Service files updated
- [ ] CHANGELOG.md created
- [ ] License added
- [ ] Git history clean
- [ ] No sensitive data committed
- [ ] All tests passing
- [ ] Fresh Pi installation tested
- [ ] SSH access verified
- [ ] WiFi AP tested
- [ ] Data export verified

---

## Next Steps After Reorganization

1. **Code Review**: Have another developer review the structure
2. **Testing**: Run full test suite on fresh Pi
3. **Documentation Review**: Proofread all docs
4. **User Testing**: Have non-developer test installation
5. **Git Tag**: Create v2.0.0 release tag
6. **Deployment**: Update production systems
7. **Handover**: Transfer to next maintainer

---

## Files to Remove After Reorganization

### Root Directory
- [ ] QUICKSTART.md (moved to docs/user/)
- [ ] START_HERE.md (merged into QUICKSTART)
- [ ] WORKSPACE_ORGANIZATION.md (outdated, replaced)
- [ ] FRESH_PI_TEST_INSTRUCTIONS.md (moved to docs/deployment/)
- [ ] GIT_PREPARATION.md (merged into PRODUCTION_DEPLOYMENT)
- [ ] TESTING_FRAMEWORK_SUMMARY.md (merged)
- [ ] TESTING_GUIDE.md (moved to docs/testing/)
- [ ] quick_start (symlink - archive)
- [ ] complete_setup (symlink - archive)

### docs/ Directory
- [ ] README_QUICKSTART.md (merged)
- [ ] QUICKSTART_SSH_UI.md (merged)
- [ ] README_SSH_TERMINAL_UI.md (merged)
- [ ] TERMINAL_UI_SUMMARY.md (merged)
- [ ] FAST_DEPLOY_PI.md (merged)
- [ ] LEGACY_README_ENABLE_PERMISSION.txt (archive)
- [ ] SSH_UI_VISUAL_GUIDE.txt (merged into TERMINAL_UI.md)
- [ ] README_RUNTIME_FALLBACK.md (check if still needed)

### setup_launchers/ Directory
- [ ] Entire directory (moved to scripts/setup/ and scripts/launchers/)

---

## Estimated Effort

- **Documentation Work**: 12-16 hours
- **Code Reorganization**: 8-10 hours
- **Testing & Verification**: 6-8 hours
- **Review & Polish**: 4-6 hours

**Total**: 30-40 hours (4-5 working days)

---

## Contact & Handover

After reorganization, next maintainer should have:
1. ✅ Access to GitHub repository
2. ✅ Copy of this reorganization plan
3. ✅ Architecture documentation (docs/developer/ARCHITECTURE.md)
4. ✅ Test access to Raspberry Pi hardware
5. ✅ Meter hardware documentation
6. ✅ Production deployment credentials (if applicable)

---

**End of Reorganization Plan**
