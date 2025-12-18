from pathlib import Path
import os


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
