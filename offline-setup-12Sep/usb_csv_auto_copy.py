#!/usr/bin/env python3
"""
USB CSV Auto-Copy Service

Purpose:
- Detect mounted USB drives and copy new/updated CSV files from data/csv to the USB.
- Safe, idempotent copies using per-device state and atomic temp files.
- Config-driven via config.jsonc under key "usb_copy".

CLI:
- --once: run a single scan/copy pass and exit
- --daemon: run continuously (default if launched by systemd service)
- --interval SECONDS: polling interval (overrides config)
- --dry-run: log actions without copying
- --test-mount PATH: treat PATH as a mounted USB (helps local testing)

Logs: logs/usb_copy.log
State: logs/.usb_copy_state.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parent
DATA_CSV = ROOT / "data" / "csv"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "usb_copy.log"
STATE_FILE = LOGS_DIR / ".usb_copy_state.json"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line, end="")


def load_jsonc(path: Path) -> Dict:
    """Load JSON-with-//-comments by stripping comments first."""
    text = path.read_text(encoding="utf-8")
    # Remove // comments, but keep http:// style by removing only when // is not preceded by ':'
    # Simpler: remove any // to end of line that is not in quotes.
    def _strip(line: str) -> str:
        in_str = False
        escaped = False
        result = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and not escaped:
                in_str = not in_str
            if not in_str and i + 1 < len(line) and line[i:i+2] == "//":
                break
            escaped = (ch == "\\") and not escaped
            result.append(ch)
            i += 1
        return "".join(result)

    cleaned = "\n".join(_strip(l) for l in text.splitlines())
    return json.loads(cleaned or "{}")


def load_config() -> Dict:
    alt = Path("/home/pi/meter_config/config.jsonc")
    cfg_path = alt if alt.exists() else (ROOT / "config.jsonc")
    if not cfg_path.exists():
        return {}
    try:
        cfg = load_jsonc(cfg_path)
        return cfg or {}
    except Exception as e:
        log(f"[WARN] Failed to parse config.jsonc: {e}")
        return {}


@dataclass
class UsbMount:
    device: str
    mount_point: Path
    fs_type: str
    uuid: Optional[str] = None
    label: Optional[str] = None

    @property
    def id(self) -> str:
        return self.uuid or self.label or self.device


def list_usb_mounts(extra_mount: Optional[Path] = None) -> List[UsbMount]:
    mounts: List[UsbMount] = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                dev, mnt, fs = parts[0], parts[1], parts[2]
                # Typical USB block devices: /dev/sdXN, /dev/sdX
                if re.match(r"^/dev/sd[a-z][0-9]*$", dev) and (
                    mnt.startswith("/media/") or mnt.startswith("/mnt/") or mnt.startswith("/run/media/")
                ):
                    mounts.append(UsbMount(device=dev, mount_point=Path(mnt), fs_type=fs))
    except Exception as e:
        log(f"[WARN] Unable to read /proc/mounts: {e}")

    # Attach UUID/label if possible
    for m in mounts:
        by_uuid = Path("/dev/disk/by-uuid")
        if by_uuid.is_dir():
            for entry in by_uuid.iterdir():
                try:
                    if entry.is_symlink() and os.path.realpath(entry) == m.device:
                        m.uuid = entry.name
                        break
                except Exception:
                    pass
        if not m.uuid:
            # Try blkid
            try:
                import subprocess

                out = subprocess.check_output(["blkid", m.device], text=True, stderr=subprocess.DEVNULL)
                m.label = None
                m.uuid = None
                m.label = re.search(r"LABEL=\"([^\"]+)\"", out or "") or None
                m.uuid = re.search(r"UUID=\"([^\"]+)\"", out or "") or None
                if m.label:
                    m.label = m.label.group(1)
                if m.uuid:
                    m.uuid = m.uuid.group(1)
            except Exception:
                pass

    if extra_mount and extra_mount.exists():
        mounts.append(UsbMount(device=str(extra_mount), mount_point=extra_mount, fs_type="testfs", uuid=f"TEST-{extra_mount.name}"))

    return mounts


def load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: Dict):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_FILE)


def ensure_free_space(path: Path, min_free_mb: int) -> bool:
    try:
        usage = shutil.disk_usage(str(path))
        return usage.free >= (min_free_mb * 1024 * 1024)
    except Exception:
        return True


def atomic_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with src.open("rb") as s, tmp.open("wb") as d:
        shutil.copyfileobj(s, d, length=1024 * 1024)
        d.flush()
        os.fsync(d.fileno())
    tmp.replace(dst)


def scan_and_copy(mount: UsbMount, cfg: Dict, dry_run: bool = False) -> int:
    """Return number of files copied (or would copy in dry-run) for this mount."""
    usb_cfg = cfg.get("usb_copy", {})
    dest_root_name = usb_cfg.get("dest_root_name", "OfflineDashboard")
    subfolder = usb_cfg.get("subfolder", "data/csv")
    min_free_mb = int(usb_cfg.get("min_free_mb", 50))

    dest_root = mount.mount_point / dest_root_name
    dest_dir = dest_root / subfolder

    state = load_state()
    dev_state = state.setdefault(mount.id, {})

    if not ensure_free_space(dest_root, min_free_mb):
        log(f"[WARN] {mount.mount_point} low on space (<{min_free_mb} MB); skipping")
        return 0

    copied = 0
    planned = 0  # for dry-run
    for src in sorted(DATA_CSV.glob("*.csv")):
        try:
            rel = src.relative_to(DATA_CSV)
        except Exception:
            rel = Path(src.name)
        key = str(rel)
        stat = src.stat()
        prev = dev_state.get(key, {})
        need = False
        if not prev:
            need = True
        else:
            if int(prev.get("mtime", 0)) < int(stat.st_mtime) or int(prev.get("size", -1)) != int(stat.st_size):
                need = True

        dst = dest_dir / rel
        if not dst.exists():
            need = True

        if need:
            if dry_run:
                log(f"[DRY] Would copy {src} -> {dst}")
                planned += 1
            else:
                try:
                    atomic_copy(src, dst)
                    dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                    copied += 1
                    log(f"[OK] Copied {src.name} -> {dst}")
                except Exception as e:
                    log(f"[ERROR] Failed to copy {src} -> {dst}: {e}")
        else:
            # log(f"[SKIP] Up-to-date {src.name}")
            pass

    save_state(state)
    if dry_run and planned:
        log(f"[DRY] Copy pass would copy {planned} file(s) to {mount.mount_point}")
    return planned if dry_run else copied


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="USB CSV auto copy")
    ap.add_argument("--once", action="store_true", help="Run one pass and exit")
    ap.add_argument("--daemon", action="store_true", help="Run continuously (default when service)")
    ap.add_argument("--interval", type=int, default=None, help="Polling interval seconds")
    ap.add_argument("--dry-run", action="store_true", help="Log actions without writing")
    ap.add_argument("--test-mount", type=str, default=None, help="Treat this path as a USB mount for testing")
    args = ap.parse_args(argv)

    cfg = load_config()
    usb_cfg = cfg.get("usb_copy", {})
    enabled = bool(usb_cfg.get("enabled", False))
    poll_interval = int(args.interval or usb_cfg.get("poll_interval_sec", 5))
    cooldown_sec = int(usb_cfg.get("cooldown_seconds", 600))  # throttle repeats while USB stays inserted

    if not enabled:
        log("[INFO] usb_copy.enabled is false; exiting")
        return 0

    if not DATA_CSV.exists():
        DATA_CSV.mkdir(parents=True, exist_ok=True)

    stop = False

    def _sigterm(_sig, _frm):
        nonlocal stop
        stop = True
        log("[INFO] Received stop signal; exiting loop")

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    extra = Path(args.test_mount).resolve() if args.test_mount else None

    def one_pass() -> int:
        """Single immediate pass without cooldown gating (used by --once)."""
        mounts = list_usb_mounts(extra)
        if not mounts:
            log("[INFO] No USB mount detected")
            return 0
        total = 0
        for m in mounts:
            if not m.mount_point.exists():
                continue
            try:
                n = scan_and_copy(m, cfg, dry_run=args.dry_run)
                total += n
                if n and not args.dry_run:
                    log(f"[INFO] {n} file(s) copied to {m.mount_point}")
                elif n and args.dry_run:
                    log(f"[INFO] Dry-run: {n} file(s) would be copied to {m.mount_point}")
            except Exception as e:
                log(f"[ERROR] Error processing {m.mount_point}: {e}")
        return total

    if args.once and not args.daemon:
        one_pass()
        return 0

    log(f"[INFO] USB copy service started; interval={poll_interval}s, cooldown={cooldown_sec}s")

    # Track transition from no USB -> USB and last copy attempt per mount
    prev_had_mounts = False
    last_copied: Dict[str, float] = {}

    while not stop:
        try:
            mounts = list_usb_mounts(extra)
            had_mounts = bool(mounts)
            insertion_event = had_mounts and not prev_had_mounts
            now = time.time()

            if not mounts:
                log("[INFO] No USB mount detected")
            else:
                for m in mounts:
                    if not m.mount_point.exists():
                        continue
                    last = last_copied.get(m.id, 0)
                    allow = insertion_event or ((now - last) >= cooldown_sec)
                    if allow:
                        if insertion_event:
                            log(f"[INFO] USB inserted -> triggering copy for {m.mount_point}")
                        try:
                            n = scan_and_copy(m, cfg, dry_run=args.dry_run)
                            last_copied[m.id] = now
                            if n and not args.dry_run:
                                log(f"[INFO] {n} file(s) copied to {m.mount_point}")
                            elif n and args.dry_run:
                                log(f"[INFO] Dry-run: {n} file(s) would be copied to {m.mount_point}")
                        except Exception as e:
                            log(f"[ERROR] Error processing {m.mount_point}: {e}")
                    # else: within cooldown; skip quietly to avoid log spam

            prev_had_mounts = had_mounts
        except Exception as e:
            log(f"[ERROR] Loop error: {e}")

        for _ in range(poll_interval):
            if stop:
                break
            time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
