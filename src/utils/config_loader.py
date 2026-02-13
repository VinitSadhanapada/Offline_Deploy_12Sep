"""
Shared config loading utilities.

Provides a single canonical implementation of JSONC (JSON with comments)
parsing and config.json loading, used across the entire project.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict


def strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments from JSONC text, respecting strings.

    Handles:
    - ``// line comments`` (but not inside quoted strings or URLs like http://)
    - ``/* block comments */``
    """
    # Strip // line comments (not inside strings)
    result_lines = []
    for line in text.splitlines():
        in_str = False
        escaped = False
        out = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and not escaped:
                in_str = not in_str
            if not in_str and i + 1 < len(line) and line[i : i + 2] == "//":
                break
            escaped = (ch == "\\") and not escaped
            out.append(ch)
            i += 1
        result_lines.append("".join(out))
    cleaned = "\n".join(result_lines)
    # Strip /* block comments */
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    return cleaned


def load_jsonc(path: os.PathLike | str) -> Dict:
    """Load a JSON file that may contain // and /* */ comments.

    Returns an empty dict if the file doesn't exist or is unparseable.
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(strip_jsonc_comments(text) or "{}")
    except Exception:
        return {}


def load_config(project_root: Path | None = None) -> Dict:
    """Load the main config.json from the standard search path.

    Search order:
    1. ``METER_CONFIG_DIR`` env var ``/config.json``
    2. ``/home/pi/meter_config/config.json``
    3. ``$HOME/meter_config/config.json``
    4. ``<project_root>/config/config.json``
    """
    from src.utils.paths import get_config_dir

    candidates: list[Path] = []

    cfg_dir = get_config_dir()
    candidates.append(cfg_dir / "config.json")

    if project_root is not None:
        candidates.append(project_root / "config" / "config.json")

    for p in candidates:
        if p.exists():
            cfg = load_jsonc(p)
            if cfg:
                return cfg
    return {}
