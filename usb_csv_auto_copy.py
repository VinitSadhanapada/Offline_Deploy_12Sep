#!/usr/bin/env python3
"""
USB CSV Auto-Copy Service

Purpose:
- Detect mounted USB drives and copy new/updated CSV files from data/csv to the USB.
- Safe, idempotent copies using per-device state and atomic temp files.
- Config-driven via config.json under key "usb_copy".

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
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parent
DATA_CSV = ROOT / "data" / "csv"
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "usb_copy.log"
STATE_FILE = LOGS_DIR / ".usb_copy_state.json"
DEFAULT_COPY_MODE = "merge"  # overwrite | skip-identical | merge
LOCK_FILE = LOGS_DIR / ".usb_copy.lock"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    print(line, end="")


def acquire_singleton_lock() -> bool:
    """Ensure only one daemon instance runs by using a lock file with PID.
    Returns True if this process acquired the lock, False if another active PID holds it.
    """
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            try:
                pid = int(LOCK_FILE.read_text().strip() or "0")
            except Exception:
                pid = 0
            if pid > 0:
                try:
                    os.kill(pid, 0)
                    log(f"[WARN] Another usb copy daemon running (pid={pid}); exiting")
                    return False
                except Exception:
                    # Stale lock, proceed to take over
                    pass
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    except Exception:
        # If lock management fails, allow start rather than block usage
        return True


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
    alt = Path("/home/pi/meter_config/config.json")
    cfg_path = alt if alt.exists() else (ROOT / "config.json")
    if not cfg_path.exists():
        return {}
    try:
        cfg = load_jsonc(cfg_path)
        return cfg or {}
    except Exception as e:
        log(f"[WARN] Failed to parse config.json: {e}")
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


def file_hash(p: Path, chunk_size: int = 1024 * 1024) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def files_identical(a: Path, b: Path) -> bool:
    try:
        sa, sb = a.stat(), b.stat()
        if sa.st_size != sb.st_size:
            return False
        # Fast path: if mtimes and sizes match, treat as identical
        if int(sa.st_mtime) == int(sb.st_mtime):
            return True
        # Thorough check: hash both
        return file_hash(a) == file_hash(b)
    except Exception:
        return False


def atomic_write_bytes(dst: Path, data: bytes):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(dst)


def merge_csv_files(src: Path, dst: Path) -> bool:
    """Merge CSV rows from src into dst, de-duplicating rows.
    Returns True on success, False on failure. Keeps header from dst if exists,
    else from src. If headers mismatch, falls back to overwrite by returning False.
    """
    import csv
    try:
        # Read headers
        src_rows: list[list[str]] = []
        dst_rows: list[list[str]] = []
        src_header: list[str] = []
        dst_header: list[str] = []

        if dst.exists():
            with dst.open("r", newline="", encoding="utf-8") as f:
                r = csv.reader(f)
                for i, row in enumerate(r):
                    if i == 0:
                        dst_header = row
                    else:
                        dst_rows.append(row)
        with src.open("r", newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            for i, row in enumerate(r):
                if i == 0:
                    src_header = row
                else:
                    src_rows.append(row)

        header: list[str]
        if dst_header and src_header and dst_header != src_header:
            # Header mismatch; avoid unsafe merge
            return False
        header = dst_header or src_header
        # Build set of tuples for fast dedupe
        seen = set()
        merged: list[list[str]] = []
        for row in dst_rows:
            t = tuple(row)
            if t not in seen:
                seen.add(t)
                merged.append(row)
        for row in src_rows:
            t = tuple(row)
            if t not in seen:
                seen.add(t)
                merged.append(row)

        # Optional: sort by Time column if present
        time_idx = None
        try:
            if header:
                time_idx = header.index("Time")
        except ValueError:
            time_idx = None
        if time_idx is not None:
            try:
                from datetime import datetime
                merged.sort(key=lambda r: datetime.fromisoformat(r[time_idx]) if r[time_idx] else "")
            except Exception:
                # If parse fails, leave original order
                pass

        # Write back atomically
        import io
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        if header:
            w.writerow(header)
        for row in merged:
            w.writerow(row)
        atomic_write_bytes(dst, out.getvalue().encode("utf-8"))
        return True
    except Exception:
        return False


def remove_duplicate_variants(dest_dir: Path, base_name: str):
    """Remove only underscore-number variants (e.g., name_1.csv, name_2.csv).
    Do not delete (1), Copy, or other variant styles.
    """
    stem, suffix = os.path.splitext(base_name)
    try:
        # Enumerate all files with the same suffix in dest_dir and match by regex
        import re
        canonical = dest_dir / base_name
        # Only match underscore-number suffix variants
        underscore_pat = re.compile(rf"^{re.escape(stem)}_\d+{re.escape(suffix)}$", flags=re.IGNORECASE)
        def is_variant(name: str) -> bool:
            return name != base_name and bool(underscore_pat.match(name))

        for p in dest_dir.glob(f"*{suffix}"):
            try:
                name = p.name
                if is_variant(name):
                    p.unlink()
            except Exception:
                pass
    except Exception:
        pass

def normalize_and_cleanup_variants(dest_dir: Path, base_name: str):
    """Normalize only underscore-number variants to canonical name when needed.
    Do not delete remaining variants; preserve originals.
    """
    stem, suffix = os.path.splitext(base_name)
    import re
    canonical = dest_dir / base_name
    # Only consider underscore-number variants
    pat = re.compile(rf"^{re.escape(stem)}_\d+{re.escape(suffix)}$", flags=re.IGNORECASE)
    variants = []
    for p in dest_dir.glob(f"*{suffix}"):
        name = p.name
        if name == base_name:
            continue
        if pat.match(name):
            variants.append(p)
    if not variants:
        return
    # Choose the newest variant as source for canonical
    try:
        newest = max(variants, key=lambda x: x.stat().st_mtime)
    except Exception:
        newest = variants[0]
    try:
        if not canonical.exists():
            newest.rename(canonical)
    except Exception:
        # If rename fails, leave as-is
        pass
    # Do not remove other variants aggressively; preserve existing files

def post_scan_variant_check(dest_dir: Path):
    """After copy, normalize only underscore-number variants; no aggressive deletions."""
    try:
        if not dest_dir.exists():
            return
        import re
        def canonical_name(name: str) -> str:
            stem, suffix = os.path.splitext(name)
            # Only strip underscore-number suffix like _1, _2
            s = re.sub(r"_\d+$", "", stem)
            return f"{s}{suffix}"

        groups = {}
        for p in dest_dir.glob("*.csv"):
            cn = canonical_name(p.name)
            groups.setdefault(cn, []).append(p.name)

        for cn, names in groups.items():
            # Only run conservative normalization (no deletions of valid files)
            normalize_and_cleanup_variants(dest_dir, cn)
    except Exception:
        pass


def sync_filesystem(mount_point: Path):
    """Force-flush filesystem buffers for the mounted device.
    Uses os.sync() as a fallback; on Linux attempts syncfs via shell.
    """
    try:
        # Best-effort: call sync for the entire system (fast on idle)
        os.sync()
    except Exception:
        pass
    try:
        # Try Linux-specific sync of the mount using the `sync` command
        # This still flushes globally; acceptable for Pi usage.
        subprocess.run(["sync"], check=False)
    except Exception:
        pass


def write_done_marker(dest_root: Path, copied: int):
    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        marker = dest_root / "COPY_DONE.txt"
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        content = (
            f"Copy completed at {ts}\n"
            f"Files copied: {copied}\n"
            f"Source: {DATA_CSV}\n"
        )
        marker.write_text(content, encoding="utf-8")
    except Exception as e:
        log(f"[WARN] Failed to write marker file: {e}")


def write_error_marker(dest_root: Path, failed: List[str]):
    try:
        dest_root.mkdir(parents=True, exist_ok=True)
        marker = dest_root / "ERRORS.json"
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        obj = {"time": ts, "failed_files": failed}
        marker.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        # Also append to a global errors log
        try:
            with (LOGS_DIR / "usb_copy_errors.log").open("a", encoding="utf-8") as ef:
                ef.write(f"[{ts}] Failed files on {dest_root}: {failed}\n")
        except Exception:
            pass
    except Exception as e:
        log(f"[WARN] Failed to write error marker file: {e}")


def is_mount_busy(mount_point: Path) -> bool:
    """Return True if any process has open files under mount_point.
    Tries `lsof` then `fuser`, then /proc scan as fallback.
    """
    try:
        if shutil.which("lsof"):
            p = subprocess.run(["lsof", "+D", str(mount_point)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            out = p.stdout.strip()
            # lsof prints header; more than one line means busy
            return bool(out and len(out.splitlines()) > 1)
    except Exception:
        pass
    try:
        if shutil.which("fuser"):
            p = subprocess.run(["fuser", "-m", str(mount_point)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            out = p.stdout.strip()
            return bool(out)
    except Exception:
        pass

    # Fallback: scan /proc/*/fd for symlinks under mount_point
    try:
        mp = str(mount_point)
        for pid in [d for d in os.listdir('/proc') if d.isdigit()]:
            fd_dir = f"/proc/{pid}/fd"
            if not os.path.isdir(fd_dir):
                continue
            try:
                for fd in os.listdir(fd_dir):
                    try:
                        target = os.readlink(os.path.join(fd_dir, fd))
                        if target.startswith(mp):
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return False


def wait_for_quiescent(mount_point: Path, checks: int, interval: float, timeout: int) -> (bool, float):
    """Wait up to `timeout` seconds for `checks` consecutive non-busy samples.
    Returns tuple (busy_final, waited_seconds). busy_final is True when the
    mount is still considered busy after timeout, False when quiescent.
    """
    start = time.time()
    consecutive = 0
    waited = 0.0
    # Sample until timeout is reached
    while (time.time() - start) < float(timeout):
        try:
            busy = is_mount_busy(mount_point)
        except Exception:
            busy = False
        if not busy:
            consecutive += 1
            if consecutive >= checks:
                return (False, waited)
        else:
            # busy -> reset consecutive counter
            consecutive = 0
        time.sleep(interval)
        waited += interval
    # Final assessment
    try:
        busy_final = is_mount_busy(mount_point)
    except Exception:
        busy_final = False
    return (busy_final, waited)


def eject_device(mount_point: Path, device: str) -> bool:
    """Attempt to unmount and power off the USB device safely.
    Returns True on success (unmounted), False otherwise.
    """
    # First, flush writes
    sync_filesystem(mount_point)
    ok = False
    # Try udisksctl if available (clean power-off)
    try:
        if shutil.which("udisksctl"):
            subprocess.run(["udisksctl", "unmount", "-b", device], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ok = True
            try:
                subprocess.run(["udisksctl", "power-off", "-b", device], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            except Exception:
                pass
    except subprocess.CalledProcessError as e:
        log(f"[WARN] udisksctl unmount failed: {e}")
    except Exception as e:
        log(f"[WARN] udisksctl not usable: {e}")

    # Fallback to umount by mount point
    if not ok:
        try:
            subprocess.run(["/bin/umount", "-l", str(mount_point)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ok = True
        except subprocess.CalledProcessError as e:
            log(f"[WARN] umount failed: {e}")
        except Exception as e:
            log(f"[WARN] umount error: {e}")

    # Small delay to allow kernel to settle
    time.sleep(1.0)
    return ok


def scan_and_copy(mount: UsbMount, cfg: Dict, dry_run: bool = False) -> (int, List[str]):
    """Return tuple (num_copied, failed_files) for this mount.
    In dry-run mode returns (planned_count, []).
    """
    usb_cfg = cfg.get("usb_copy", {})
    dest_root_name = usb_cfg.get("dest_root_name", "OfflineDashboard")
    subfolder = usb_cfg.get("subfolder", "data/csv")
    min_free_mb = int(usb_cfg.get("min_free_mb", 50))
    copy_mode = str(usb_cfg.get("copy_mode", DEFAULT_COPY_MODE)).strip().lower()
    if copy_mode not in {"overwrite", "skip-identical", "merge"}:
        copy_mode = DEFAULT_COPY_MODE
    always_copy = bool(usb_cfg.get("always_copy_on_insert", False))
    dedupe_variants = True  # hard-enable variant cleanup without config change

    # Prefer legacy COPIED_DATA root if present, else configured root
    preferred_legacy_root = mount.mount_point / "COPIED_DATA"
    if preferred_legacy_root.exists():
        dest_root = preferred_legacy_root
    else:
        dest_root = mount.mount_point / dest_root_name
    dest_dir = dest_root / subfolder

    state = load_state()
    dev_state = state.setdefault(mount.id, {})

    if not ensure_free_space(dest_root, min_free_mb):
        log(f"[WARN] {mount.mount_point} low on space (<{min_free_mb} MB); skipping")
        return 0

    # Unconditional pre-pass: remove duplicate variants for all known source files
    # Sweep both configured dest_dir and legacy COPIED_DATA/data/csv to ensure cleanup.
    try:
        legacy_dir = mount.mount_point / "COPIED_DATA" / "data" / "csv"
        for target_dir in (dest_dir, legacy_dir):
            for src in sorted(DATA_CSV.glob("*.csv")):
                if src.name == "readings_all.csv":
                    continue
                remove_duplicate_variants(target_dir, src.name)
                normalize_and_cleanup_variants(target_dir, src.name)
    except Exception:
        pass

    copied = 0
    planned = 0  # for dry-run
    failed: List[str] = []
    for src in sorted(DATA_CSV.glob("*.csv")):
        try:
            # Skip consolidated file not needed on USB
            if src.name == "readings_all.csv":
                continue
            rel = src.relative_to(DATA_CSV)
        except Exception:
            rel = Path(src.name)
        key = str(rel)
        stat = src.stat()
        prev = dev_state.get(key, {})
        need = False
        if always_copy:
            need = True
        else:
            if not prev:
                need = True
            else:
                if int(prev.get("mtime", 0)) < int(stat.st_mtime) or int(prev.get("size", -1)) != int(stat.st_size):
                    need = True

        dst = dest_dir / rel
        # If destination file is missing (e.g., was manually deleted), force copy
        if not dst.exists():
            need = True
        if dedupe_variants:
            # Ensure we don't keep numbered duplicate variants on destination
            remove_duplicate_variants(dest_dir, dst.name)

        if need:
            if dry_run:
                action = "overwrite" if copy_mode == "overwrite" else ("merge" if copy_mode == "merge" else "skip-identical/overwrite")
                log(f"[DRY] Would process {src} -> {dst} (mode={copy_mode}, action={action})")
                planned += 1
            else:
                try:
                    if dst.exists():
                        if copy_mode == "skip-identical":
                            if files_identical(src, dst):
                                # Up-to-date by content; just update state
                                dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                                log(f"[SKIP] Identical {src.name}; nothing to do")
                            else:
                                atomic_copy(src, dst)
                                dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                                copied += 1
                                log(f"[OK] Overwrote {dst.name} (content changed)")
                        elif copy_mode == "merge":
                            if files_identical(src, dst):
                                dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                                log(f"[SKIP] Identical {src.name}; nothing to merge")
                            else:
                                if merge_csv_files(src, dst):
                                    dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                                    copied += 1
                                    log(f"[OK] Merged into {dst.name}")
                                else:
                                    # Fallback to overwrite on merge failure
                                    atomic_copy(src, dst)
                                    dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                                    copied += 1
                                    log(f"[OK] Overwrote {dst.name} (merge unsupported)")
                        else:  # overwrite
                            atomic_copy(src, dst)
                            dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                            copied += 1
                            log(f"[OK] Overwrote {dst.name}")
                    else:
                        # Fresh copy
                        atomic_copy(src, dst)
                        dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                        copied += 1
                        log(f"[OK] Copied {src.name} -> {dst}")
                except Exception as e:
                    log(f"[ERROR] Failed to process {src} -> {dst}: {e}")
                    failed.append(str(src.name))
        else:
            # log(f"[SKIP] Up-to-date {src.name}")
            pass

    save_state(state)
    if dry_run and planned:
        log(f"[DRY] Copy pass would copy {planned} file(s) to {mount.mount_point}")
    return (planned, []) if dry_run else (copied, failed)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="USB CSV auto copy")
    ap.add_argument("--once", action="store_true", help="Run one pass and exit")
    ap.add_argument("--daemon", action="store_true", help="Run continuously (default when service)")
    ap.add_argument("--interval", type=int, default=None, help="Polling interval seconds")
    ap.add_argument("--dry-run", action="store_true", help="Log actions without writing")
    ap.add_argument("--test-mount", type=str, default=None, help="Treat this path as a USB mount for testing")
    ap.add_argument("--check-only", action="store_true", help="Only run duplicate cleanup on destination without copying")
    args = ap.parse_args(argv)

    # Singleton guard when running as daemon
    if args.daemon:
        if not acquire_singleton_lock():
            return 0

    cfg = load_config()
    usb_cfg = cfg.get("usb_copy", {})
    enabled = bool(usb_cfg.get("enabled", False))
    poll_interval = int(args.interval or usb_cfg.get("poll_interval_sec", 5))
    cooldown_sec = int(usb_cfg.get("cooldown_seconds", 600))  # throttle repeats while USB stays inserted
    mount_settle_sec = int(usb_cfg.get("mount_settle_seconds", 2))
    sync_after = bool(usb_cfg.get("sync_after_copy", True))
    eject_after = bool(usb_cfg.get("eject_after_copy", False))
    write_marker = bool(usb_cfg.get("write_done_marker", True))
    min_rw_seconds = int(usb_cfg.get("min_rw_seconds", 30))
    quiesce_wait_seconds = int(usb_cfg.get("quiesce_wait_seconds", 120))
    # Conservative eject: require N consecutive non-busy checks before ejecting
    # Default disabled to preserve original behavior (simple quiesce then eject)
    conservative_eject = bool(usb_cfg.get("conservative_eject", False))
    conservative_eject_checks = int(usb_cfg.get("conservative_eject_checks", 3))
    conservative_eject_interval = float(usb_cfg.get("conservative_eject_interval", 1.0))
    debug_mode = bool(usb_cfg.get("debug", False))

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
                # Allow the automounter a brief moment to settle
                if mount_settle_sec > 0:
                    time.sleep(mount_settle_sec)
                start_ts = time.time()
                if args.check_only:
                    # Just run cleanup on destination
                    dest_root_name = usb_cfg.get("dest_root_name", "OfflineDashboard")
                    subfolder = usb_cfg.get("subfolder", "data/csv")
                    dest_dir = (m.mount_point / dest_root_name / subfolder)
                    post_scan_variant_check(dest_dir)
                    log(f"[INFO] Check-only cleanup done on {dest_dir}")
                    continue
                n, failed = scan_and_copy(m, cfg, dry_run=args.dry_run)
                total += n
                # Always run a post-scan duplicate check on destination
                try:
                    cfg_usb = cfg.get("usb_copy", {})
                    dest_root_name = cfg_usb.get("dest_root_name", "OfflineDashboard")
                    subfolder = cfg_usb.get("subfolder", "data/csv")
                    dest_dir = (m.mount_point / dest_root_name / subfolder)
                    # Run cleanup on both configured path and legacy COPIED_DATA
                    post_scan_variant_check(dest_dir)
                    post_scan_variant_check(mount.mount_point / "COPIED_DATA" / "data" / "csv")
                except Exception:
                    pass
                if n and not args.dry_run:
                    log(f"[INFO] {n} file(s) copied to {m.mount_point}")
                    # Enforce minimum read/write dwell time
                    elapsed = time.time() - start_ts
                    if elapsed < min_rw_seconds:
                        to_wait = min_rw_seconds - elapsed
                        log(f"[INFO] Waiting {to_wait:.1f}s to satisfy min_rw_seconds={min_rw_seconds}")
                        time.sleep(to_wait)

                    # Wait for other processes to finish (quiesce) up to timeout
                    if conservative_eject:
                        busy, qu_waited = wait_for_quiescent(m.mount_point, conservative_eject_checks, conservative_eject_interval, quiesce_wait_seconds)
                        if debug_mode:
                            log(f"[DEBUG] Quiesce result: busy={busy} waited={qu_waited:.1f}s checks={conservative_eject_checks} interval={conservative_eject_interval}s")
                    else:
                        qu_waited = 0
                        busy = is_mount_busy(m.mount_point)
                        while busy and qu_waited < quiesce_wait_seconds:
                            log(f"[INFO] Mount busy (other processes accessing). Waiting... {qu_waited}/{quiesce_wait_seconds}s")
                            time.sleep(1)
                            qu_waited += 1
                            busy = is_mount_busy(m.mount_point)

                    # If we had any failures, write an error marker and skip eject
                    if failed:
                        log(f"[WARN] {len(failed)} file(s) failed to copy: {failed}. Leaving device mounted for inspection.")
                        try:
                            write_error_marker(m.mount_point / usb_cfg.get("dest_root_name", "OfflineDashboard"), failed)
                        except Exception as e:
                            log(f"[WARN] Failed to write error marker: {e}")
                    else:
                        # All good: write marker, flush, and optionally eject
                        if write_marker:
                            try:
                                write_done_marker(m.mount_point / usb_cfg.get("dest_root_name", "OfflineDashboard"), n)
                            except Exception as e:
                                log(f"[WARN] Marker write failed: {e}")
                        if sync_after:
                            sync_filesystem(m.mount_point)
                        if eject_after:
                            log(f"[DEBUG] Eject decision: failed={len(failed)} elapsed={elapsed:.1f}s busy={busy} eject_after={eject_after} quiesce_wait_seconds={quiesce_wait_seconds}")
                            if not busy:
                                if eject_device(m.mount_point, m.device):
                                    log(f"[INFO] Safely ejected {m.device} ({m.mount_point})")
                                else:
                                    log(f"[WARN] Could not eject {m.device}; please remove safely")
                            else:
                                log(f"[WARN] Mount still busy after {quiesce_wait_seconds}s; not ejecting to avoid corruption")
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
    last_insert_ts: float = 0.0

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
                            # Debounce rapid duplicate insert triggers (hardcoded safe value)
                            debounce = 2.0
                            if (now - last_insert_ts) < debounce:
                                # Skip duplicate trigger; will run after cooldown if needed
                                continue
                            last_insert_ts = now
                            log(f"[INFO] USB inserted -> triggering copy for {m.mount_point}")
                        try:
                            # Allow the automounter a brief moment to settle
                            if mount_settle_sec > 0 and insertion_event:
                                time.sleep(mount_settle_sec)
                            start_ts = time.time()
                            n, failed = scan_and_copy(m, cfg, dry_run=args.dry_run)
                            last_copied[m.id] = now
                            # Run a post-scan duplicate check even if n==0
                            try:
                                cfg_usb = cfg.get("usb_copy", {})
                                dest_root_name = cfg_usb.get("dest_root_name", "OfflineDashboard")
                                subfolder = cfg_usb.get("subfolder", "data/csv")
                                dest_dir = (m.mount_point / dest_root_name / subfolder)
                                post_scan_variant_check(dest_dir)
                                post_scan_variant_check(mount.mount_point / "COPIED_DATA" / "data" / "csv")
                            except Exception:
                                pass
                            if n and not args.dry_run:
                                log(f"[INFO] {n} file(s) copied to {m.mount_point}")
                                # Enforce minimum read/write dwell time
                                elapsed = time.time() - start_ts
                                if elapsed < min_rw_seconds:
                                    to_wait = min_rw_seconds - elapsed
                                    log(f"[DEBUG] Post-copy elapsed={elapsed:.1f}s to_wait={to_wait:.1f}s min_rw_seconds={min_rw_seconds}")
                                    log(f"[INFO] Waiting {to_wait:.1f}s to satisfy min_rw_seconds={min_rw_seconds}")
                                    time.sleep(to_wait)

                                # Wait for other processes to finish (quiesce)
                                if conservative_eject:
                                    busy, qu_waited = wait_for_quiescent(m.mount_point, conservative_eject_checks, conservative_eject_interval, quiesce_wait_seconds)
                                    if debug_mode:
                                        log(f"[DEBUG] Quiesce result: busy={busy} waited={qu_waited:.1f}s checks={conservative_eject_checks} interval={conservative_eject_interval}s")
                                else:
                                    qu_waited = 0
                                    busy = is_mount_busy(m.mount_point)
                                    while busy and qu_waited < quiesce_wait_seconds:
                                        log(f"[INFO] Mount busy (other processes accessing). Waiting... {qu_waited}/{quiesce_wait_seconds}s")
                                        time.sleep(1)
                                        qu_waited += 1
                                        busy = is_mount_busy(m.mount_point)

                                if failed:
                                    log(f"[WARN] {len(failed)} file(s) failed to copy: {failed}. Leaving device mounted for inspection.")
                                    try:
                                        write_error_marker(m.mount_point / usb_cfg.get("dest_root_name", "OfflineDashboard"), failed)
                                    except Exception as e:
                                        log(f"[WARN] Failed to write error marker: {e}")
                                else:
                                    if write_marker:
                                        try:
                                            write_done_marker(m.mount_point / usb_cfg.get("dest_root_name", "OfflineDashboard"), n)
                                        except Exception as e:
                                            log(f"[WARN] Marker write failed: {e}")
                                    if sync_after:
                                        sync_filesystem(m.mount_point)
                                    if eject_after:
                                        log(f"[DEBUG] Main-loop eject decision before action: failed={len(failed)} elapsed={elapsed:.1f}s busy={busy} eject_after={eject_after} quiesce_wait_seconds={quiesce_wait_seconds}")
                                        if not busy:
                                            if eject_device(m.mount_point, m.device):
                                                log(f"[INFO] Safely ejected {m.device} ({m.mount_point})")
                                            else:
                                                log(f"[WARN] Could not eject {m.device}; please remove safely")
                                        else:
                                            log(f"[WARN] Mount still busy after {quiesce_wait_seconds}s; not ejecting to avoid corruption")
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
