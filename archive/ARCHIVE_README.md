# Archive Directory

This directory contains deprecated, duplicate, or legacy files that have been superseded by the reorganized structure.

**Date Archived:** 31 December 2025  
**Reason:** Project reorganization to professional structure

---

## Contents

### deprecated_scripts/

Old script files that were duplicates of files now in `scripts/` directory:

- **download_meter_data.sh** → Now in `scripts/system/download_meter_data.sh`
- **one_click_system_py313.sh** → Now in `scripts/setup/one_click_system_py313.sh`
- **update_pull.sh** → Now in `scripts/system/update_pull.sh`

**Status:** Safe to delete - duplicates only  
**Kept for:** Reference and rollback safety

### deprecated_docs/

*(Currently empty - ready for future doc consolidation)*

---

## Why These Files Were Archived

As part of the project reorganization (Dec 31, 2025):

1. **Scripts reorganized** into `scripts/setup/`, `scripts/launchers/`, `scripts/system/`
2. **Backward compatibility** maintained via symlinks in project root
3. **Originals archived** to keep workspace clean while preserving history

---

## Can I Delete This Directory?

**After successful deployment:** Yes, these are duplicates.  
**Before testing:** No, keep for rollback safety.  
**Recommendation:** Keep until next stable release, then remove.

---

**Last Updated:** 31 December 2025
