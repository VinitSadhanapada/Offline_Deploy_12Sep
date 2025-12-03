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


def unique_destination_path(dst: Path) -> Path:
    """Return a non-overwriting destination path by appending _N before extension.
    Example: file.csv -> file_1.csv, file_2.csv, ...
    """
    if not dst.exists():
        return dst
    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    n = 1
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


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
    always_copy = bool(usb_cfg.get("always_copy_on_insert", False))

    dest_root = mount.mount_point / dest_root_name
    dest_dir = dest_root / subfolder

    state = load_state()
    dev_state = state.setdefault(mount.id, {})

    if not ensure_free_space(dest_root, min_free_mb):
        log(f"[WARN] {mount.mount_point} low on space (<{min_free_mb} MB); skipping")
        return 0

    copied = 0
    planned = 0  # for dry-run
    failed: List[str] = []
    for src in sorted(DATA_CSV.glob("*.csv")):
        try:
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
        # When copying, never overwrite; get a unique path if destination exists
        final_dst = dst if not dst.exists() else unique_destination_path(dst)

        if need:
            if dry_run:
                log(f"[DRY] Would copy {src} -> {final_dst}")
                planned += 1
            else:
                try:
                    atomic_copy(src, final_dst)
                    dev_state[key] = {"mtime": int(stat.st_mtime), "size": int(stat.st_size)}
                    copied += 1
                    log(f"[OK] Copied {src.name} -> {final_dst}")
                except Exception as e:
                    log(f"[ERROR] Failed to copy {src} -> {final_dst}: {e}")
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
    args = ap.parse_args(argv)

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
                n, failed = scan_and_copy(m, cfg, dry_run=args.dry_run)
                total += n
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
                            # Allow the automounter a brief moment to settle
                            if mount_settle_sec > 0 and insertion_event:
                                time.sleep(mount_settle_sec)
                            start_ts = time.time()
                            n, failed = scan_and_copy(m, cfg, dry_run=args.dry_run)
                            last_copied[m.id] = now
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
