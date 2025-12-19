import os
import json

BASE_DIR = os.path.dirname(__file__)
DEFAULT_DATA_DIR = "/home/pi/Desktop/offline-setup-12Sep/data/csv"


def _from_env():
    v = os.environ.get("USB_MVP_DATA_DIR")
    return v if v else None


def _from_config_file():
    path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            dd = cfg.get("DATA_DIR")
            if dd:
                return dd
        except Exception:
            pass
    return None


DATA_DIR = _from_env() or _from_config_file() or DEFAULT_DATA_DIR
