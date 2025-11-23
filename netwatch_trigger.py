#!/usr/bin/env python3
"""
Network Watch Trigger

Watches for internet connectivity (TCP connect to host:port). When it flips
from offline -> online, triggers a one-off cloud sync.

Config keys used: cloud_sync.network_test_host, cloud_sync.network_test_port
Logs are sent to stdout; service unit will capture in journal.
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_jsonc(path: Path):
    import json
    txt = path.read_text(encoding="utf-8")
    def strip(line: str) -> str:
        in_str = False
        esc = False
        out = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and not esc:
                in_str = not in_str
            if not in_str and i+1 < len(line) and line[i:i+2] == "//":
                break
            esc = (ch == "\\") and not esc
            out.append(ch)
            i += 1
        return "".join(out)
    cleaned = "\n".join(strip(l) for l in txt.splitlines())
    return json.loads(cleaned or "{}")


def net_up(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    alt = Path("/home/pi/meter_config/config.jsonc")
    cfg = load_jsonc(alt if alt.exists() else (ROOT / "config.jsonc"))
    cloud = cfg.get("cloud_sync", {})
    enabled = bool(cloud.get("enabled", False))
    if not enabled:
        print("[netwatch] cloud_sync.enabled is false; exiting without network checks")
        return 0
    host = cloud.get("network_test_host", "8.8.8.8")
    port = int(cloud.get("network_test_port", 53))
    poll = 5
    was_up = None
    print(f"[netwatch] watching connectivity to {host}:{port} every {poll}s")
    while True:
        up = net_up(host, port, timeout=2.0)
        if was_up is None:
            state = "online" if up else "offline"
            print(f"[netwatch] initial state: {state}")
        elif (not was_up) and up:
            print("[netwatch] connectivity restored; triggering cloud sync")
            try:
                subprocess.run(["/usr/bin/python3", str(ROOT / "cloud_sync.py"), "--run-once"], check=False)
            except Exception as e:
                print(f"[netwatch] failed to invoke cloud_sync: {e}")
        was_up = up
        time.sleep(poll)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
