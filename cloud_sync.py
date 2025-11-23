#!/usr/bin/env python3
"""
Cloud Sync Service

Purpose:
- When network is available, push CSV files from data/csv to a remote destination.
- Supports methods:
  - rclone (preferred, if installed and remote configured)
  - rsync over SSH (if rsync installed)
  - scp fallback (simple copy; may overwrite)

Config (config.json):
cloud_sync: {
  enabled: true|false,
  method: "rclone"|"rsync"|"scp",
  interval_minutes: 10,
  network_test_host: "8.8.8.8",
  network_test_port: 53,
  // rclone
  rclone_remote: "myremote:",
  dest_path: "offline-dashboard/data/csv",
  // rsync/scp
  rsync_target: "user@host:/path",
  ssh_key: "/home/pi/.ssh/id_rsa",
  ssh_port: 22
}

CLI:
--run-once: one sync attempt then exit
--dry-run: show what would run without executing

Logs: logs/cloud_sync.log
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parent
DATA_CSV = ROOT / "data" / "csv"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "cloud_sync.log"
STATE_FILE = LOGS_DIR / ".cloud_sync_state.json"


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
    text = path.read_text(encoding="utf-8")
    def _strip(line: str) -> str:
        in_str = False
        escaped = False
        out = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"' and not escaped:
                in_str = not in_str
            if not in_str and i + 1 < len(line) and line[i:i+2] == "//":
                break
            escaped = (ch == "\\") and not escaped
            out.append(ch)
            i += 1
        return "".join(out)
    cleaned = "\n".join(_strip(l) for l in text.splitlines())
    return json.loads(cleaned or "{}")


def load_config() -> Dict:
    alt = Path("/home/pi/meter_config/config.json")
    cfg_path = alt if alt.exists() else (ROOT / "config.json")
    if not cfg_path.exists():
        return {}
    try:
        return load_jsonc(cfg_path)
    except Exception as e:
        log(f"[WARN] Failed to parse config.json: {e}")
        return {}


def network_available(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def run(cmd: list[str], dry_run: bool = False) -> int:
    if dry_run:
        log(f"[DRY] Would run: {' '.join(cmd)}")
        return 0
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.stdout:
            for line in proc.stdout.splitlines():
                log(f"[CMD] {line}")
        return proc.returncode
    except Exception as e:
        log(f"[ERROR] Failed to run {' '.join(cmd)}: {e}")
        return 1


def atomic_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with src.open("rb") as s, tmp.open("wb") as d:
        shutil.copyfileobj(s, d, length=1024 * 1024)
        d.flush()
        os.fsync(d.fileno())
    tmp.replace(dst)


def create_snapshots(cfg: Dict) -> Path:
    """
    Create stable copies of CSVs under a snapshot directory and return the snapshot path.
    Uses a small state file to avoid re-copying unchanged files.
    """
    snap_cfg = cfg.get("cloud_sync", {}).get("snapshot_mode", {})
    snap_rel = snap_cfg.get("snapshot_dir", "data/snapshots/csv")
    state_rel = snap_cfg.get("state_file", "logs/.cloud_snapshot_state.json")
    snapshot_dir = ROOT / snap_rel
    state_file = ROOT / state_rel

    try:
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    except Exception:
        state = {}

    for src in sorted(DATA_CSV.glob("*.csv")):
        try:
            st = src.stat()
        except FileNotFoundError:
            continue
        key = src.name
        prev = state.get(key)
        if prev and int(prev.get("mtime", 0)) == int(st.st_mtime) and int(prev.get("size", -1)) == int(st.st_size):
            # unchanged
            continue
        dst = snapshot_dir / src.name
        try:
            atomic_copy(src, dst)
            state[key] = {"mtime": int(st.st_mtime), "size": int(st.st_size)}
            log(f"[SNAP] Copied {src.name} -> {dst}")
        except Exception as e:
            log(f"[WARN] Snapshot failed for {src}: {e}")

    try:
        tmp = state_file.with_suffix(state_file.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(state_file)
    except Exception as e:
        log(f"[WARN] Failed to write snapshot state: {e}")

    return snapshot_dir


def _fmt_min_age(seconds: int) -> str:
    # rclone accepts durations like 30s, 2m, 1h; keep it simple with seconds
    return f"{max(0, int(seconds))}s"


def sync_rclone(cfg: Dict, dry_run: bool) -> int:
    remote = cfg.get("rclone_remote")
    dest_path = cfg.get("dest_path", "offline-dashboard/data/csv")
    rclone = which("rclone")
    if not rclone:
        log("[WARN] rclone not found; cannot use method=rclone")
        return 2
    if not remote:
        log("[WARN] rclone_remote not set in cloud_sync config")
        return 2
    # Decide source path: direct CSV folder or snapshot dir if enabled
    cloud = cfg  # already cloud_sync dict
    snapshot_cfg = cloud.get("snapshot_mode", {})
    use_snap = bool(snapshot_cfg.get("enabled", False))
    if use_snap:
        snap_dir = create_snapshots({"cloud_sync": {"snapshot_mode": snapshot_cfg}})
        src = str(snap_dir)
    else:
        src = str(DATA_CSV)
    dest = f"{remote.rstrip(':')}:/{dest_path.strip('/')}"
    cmd = [rclone, "copy", src, dest,
           "--create-empty-src-dirs",
           "--transfers", "2",
           "--checkers", "4",
           "--fast-list"]

    # Skip files that are still being written by requiring a minimum age
    min_age_sec = int(cfg.get("min_age_seconds", 60))
    if min_age_sec > 0:
        cmd += ["--min-age", _fmt_min_age(min_age_sec)]
    return run(cmd, dry_run=dry_run)


def sync_rsync(cfg: Dict, dry_run: bool) -> int:
    target = cfg.get("rsync_target")
    key = cfg.get("ssh_key")
    port = int(cfg.get("ssh_port", 22))
    rsync = which("rsync")
    if not rsync:
        log("[WARN] rsync not found; cannot use method=rsync")
        return 2
    if not target:
        log("[WARN] rsync_target not set in cloud_sync config")
        return 2
    ssh_cmd = f"ssh -p {port}"
    if key:
        ssh_cmd += f" -i {key}"
    src = str(DATA_CSV) + "/"
    dest = target
    cmd = [rsync, "-av", "--ignore-existing", "-e", ssh_cmd, src, dest]
    return run(cmd, dry_run=dry_run)


def sync_scp(cfg: Dict, dry_run: bool) -> int:
    target = cfg.get("rsync_target")  # reuse format user@host:/path
    key = cfg.get("ssh_key")
    port = int(cfg.get("ssh_port", 22))
    scp = which("scp")
    if not scp:
        log("[WARN] scp not found; cannot use method=scp")
        return 2
    if not target:
        log("[WARN] rsync_target (scp target) not set in cloud_sync config")
        return 2
    # Copy each CSV; may overwrite on remote
    code = 0
    for csv in sorted(DATA_CSV.glob("*.csv")):
        cmd = [scp, "-P", str(port)]
        if key:
            cmd += ["-i", key]
        cmd += [str(csv), target]
        rc = run(cmd, dry_run=dry_run)
        code = rc or code
    return code


def do_sync(cfg: Dict, dry_run: bool) -> int:
    cloud = cfg.get("cloud_sync", {})
    method = (cloud.get("method") or "rclone").lower()
    if method == "rclone":
        return sync_rclone({**cloud}, dry_run)
    if method == "rsync":
        return sync_rsync({**cloud}, dry_run)
    if method == "scp":
        return sync_scp({**cloud}, dry_run)
    log(f"[WARN] Unknown cloud_sync.method={method}")
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cloud sync for CSV files")
    ap.add_argument("--run-once", action="store_true", help="Perform one sync attempt and exit")
    ap.add_argument("--dry-run", action="store_true", help="Show commands without executing")
    args = ap.parse_args(argv)

    cfg = load_config()
    cloud = cfg.get("cloud_sync", {})
    enabled = bool(cloud.get("enabled", False))
    interval_min = int(cloud.get("interval_minutes", 10))
    interval_sec = cloud.get("interval_seconds")
    try:
        interval_sec = int(interval_sec) if interval_sec is not None else None
    except Exception:
        interval_sec = None
    test_host = cloud.get("network_test_host", "8.8.8.8")
    test_port = int(cloud.get("network_test_port", 53))

    if not enabled:
        log("[INFO] cloud_sync.enabled is false; exiting")
        return 0

    if not DATA_CSV.exists():
        DATA_CSV.mkdir(parents=True, exist_ok=True)

    def attempt() -> int:
        start_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not network_available(test_host, test_port, timeout=2.0):
            log("[INFO] Network not available; will retry later")
            rc = 3
        else:
            rc = do_sync(cfg, args.dry_run)
        if rc == 0:
            log("[OK] Cloud sync completed")
            # Persist last successful sync metadata
            try:
                state = {}
                if STATE_FILE.exists():
                    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) or {}
                state.update({
                    "last_success_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "last_start_utc": start_ts,
                })
                tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
                tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
                tmp.replace(STATE_FILE)
            except Exception as e:
                log(f"[WARN] Failed to write sync state: {e}")
        else:
            log(f"[WARN] Cloud sync exit code {rc}")
        return rc

    if args.run_once:
        attempt()
        return 0

    # Daemon-style loop (if run as a simple service instead of a timer)
    effective_sleep = interval_sec if interval_sec and interval_sec > 0 else int(interval_min * 60)
    unit = "s" if interval_sec else "m"
    shown = interval_sec if interval_sec else interval_min
    log(f"[INFO] Cloud sync loop started; interval={shown}{unit}")
    while True:
        attempt()
        for _ in range(effective_sleep):
            time.sleep(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
