from pathlib import Path
import os


def find_project_root(script_path: Path | None = None) -> Path:
    """Find the project root directory by looking for key markers.

    Walks up from *script_path* (or this file's location) looking for
    a directory that contains both ``src/`` and ``config/``.
    """
    if script_path is None:
        script_path = Path(__file__).resolve()
    for parent in [script_path.parent, *script_path.parents]:
        if (parent / "src").is_dir() and (parent / "config").is_dir():
            return parent
        if (parent / "venv").is_dir() and (parent / "src").is_dir():
            return parent
        if (parent / "config" / "config.json").exists():
            return parent
        if parent == Path.home() or parent == Path("/"):
            break
    # Fallback: assume we are somewhere inside the project tree
    return script_path.parent.parent.parent


def get_config_dir() -> Path:
    """Return the canonical configuration directory for meter config.

    Resolution order:
    1. `METER_CONFIG_DIR` environment variable if set.
    2. `/home/pi/meter_config` legacy path if it exists (keeps backward compatibility).
    3. `$HOME/meter_config` (user's home directory).
    4. Project-local `./meter_config` as a last resort (caller can join project root).
    """
    env = os.environ.get("METER_CONFIG_DIR") or os.environ.get("APP_CONFIG_DIR")
    if env:
        return Path(env)

    legacy = Path("/home/pi/meter_config")
    if legacy.exists():
        return legacy

    home = Path.home() / "meter_config"
    if home.exists():
        return home

    # If none exist, return the home-based path (caller can create it)
    return home
