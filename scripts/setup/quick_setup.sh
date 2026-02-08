#!/bin/bash
# ── Forwarder ──────────────────────────────────────────────────────────────
# The canonical quick_setup.sh lives at the project root.
# ───────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
exec bash "$PROJECT_ROOT/quick_setup.sh" "$@"
