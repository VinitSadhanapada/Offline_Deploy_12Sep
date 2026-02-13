#!/usr/bin/env python3

# --- Ensure src is always in sys.path (must be first!) ---
import sys
import os
from pathlib import Path


def _find_project_root() -> Path:
    """Find the project root directory by looking for key markers."""
    script_path = Path(__file__).resolve()
    for parent in [script_path.parent, *script_path.parents]:
        if (parent / "src").is_dir() and (parent / "config").is_dir():
            return parent
        if (parent / "venv").is_dir() and (parent / "src").is_dir():
            return parent
        if parent == Path.home() or parent == Path("/"):
            break
    return script_path.parent.parent.parent


PROJECT_ROOT = _find_project_root()
SRC_PATH = str(PROJECT_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
# Also ensure PROJECT_ROOT itself is on sys.path for 'from src' imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import subprocess
import threading
import signal
import json
import re


class OutputWindow(tk.Toplevel):
    def __init__(self, parent, title, stop_callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x250")
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=8)
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 2))
        self.stop_btn = tk.Button(self, text="Stop Script", width=14, cursor="arrow")
        self.stop_btn.pack(pady=(2, 8))
        self.stop_btn.config(command=self._stop_and_close)
        self._parent_stop_callback = stop_callback
        self.protocol("WM_DELETE_WINDOW", self._just_close)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.transient(parent)
        self.update()
        self.attributes('-topmost', True)
        self.after(500, lambda: self.attributes('-topmost', False))

    def insert(self, text):
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def _stop_and_close(self):
        if self._parent_stop_callback:
            self._parent_stop_callback()
        self.destroy()

    def _just_close(self):
        self.destroy()


class SimpleMeterUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Meter Dashboard - Technician UI")
        self.geometry("800x600")
        self.proc = None
        self.output_window = None
        self.reading_interval = self._get_reading_interval()
        self.csv_log_interval = self._get_csv_log_interval()
        self.ap_enabled_var = tk.BooleanVar(value=self._get_ap_enabled_safe())
        self.create_widgets()
        # Refresh AP service state display on startup
        try:
            self._update_ap_service_status()
        except Exception:
            pass
        # RTC check on startup
        self.after(100, self.check_rtc_status)
        ROOT_DIR = str(PROJECT_ROOT)

        # Ensure required offline packages are installed from packages_folder
        def _ensure_offline_packages():
            try:
                import jinja2  # noqa: F401
                return
            except Exception:
                pass
            import glob as _glob
            pkgs = [
                {
                    "module": "MarkupSafe",
                    "glob": os.path.join(ROOT_DIR, "packages_folder", "MarkupSafe-*.whl"),
                },
                {
                    "module": "jinja2",
                    "glob": os.path.join(ROOT_DIR, "packages_folder", "jinja2-*.whl"),
                },
            ]
            for p in pkgs:
                try:
                    wheel_candidates = sorted(_glob.glob(p["glob"]))
                    if not wheel_candidates:
                        continue
                    wheel = wheel_candidates[-1]
                    subprocess.run([
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--no-index",
                        "--find-links",
                        os.path.dirname(wheel),
                        wheel,
                    ], check=False)
                except Exception:
                    continue

        _ensure_offline_packages()

    # ─── Config helpers ───

    def check_rtc_status(self):
        try:
            from src.utils.rtc_module import is_rtc_available
            if is_rtc_available():
                self.bottom_status_label.config(text="RTC detected and working.", fg="green")
            else:
                self.bottom_status_label.config(text="Real Time Clock Module Not Connected", fg="red")
        except Exception as e:
            self.bottom_status_label.config(text=f"RTC check error: {e}", fg="red")

    def _get_reading_interval(self):
        try:
            from src.utils.paths import get_config_dir
            config_path = os.path.join(str(get_config_dir()), "config.json")
            if not os.path.exists(config_path):
                local_json = str(PROJECT_ROOT / "config" / "config.json")
                if not os.path.exists(local_json):
                    local_json = str(PROJECT_ROOT / "config.json")
                config_path = local_json
            with open(config_path, "r") as f:
                content = f.read()
            content = re.sub(r"//.*", "", content)
            config = json.loads(content)
            return int(config.get("READING_INTERVAL", 5))
        except Exception as e:
            print(f"Error reading READING_INTERVAL: {e}")
            return 5

    def _get_csv_log_interval(self):
        """Get CSV log interval from config.json (default 60 seconds)."""
        try:
            from src.utils.paths import get_config_dir
            config_path = os.path.join(str(get_config_dir()), "config.json")
            if not os.path.exists(config_path):
                local_json = str(PROJECT_ROOT / "config" / "config.json")
                if not os.path.exists(local_json):
                    local_json = str(PROJECT_ROOT / "config.json")
                config_path = local_json
            with open(config_path, "r") as f:
                content = f.read()
            content = re.sub(r"//.*", "", content)
            config = json.loads(content)
            return int(config.get("CSV_LOG_INTERVAL", 60))
        except Exception as e:
            print(f"Error reading CSV_LOG_INTERVAL: {e}")
            return 60

    def _set_csv_log_interval(self, value):
        """Set CSV log interval in config.json."""
        try:
            from src.utils.paths import get_config_dir
            config_path = os.path.join(str(get_config_dir()), "config.json")
            if not os.path.exists(config_path):
                local_json = str(PROJECT_ROOT / "config" / "config.json")
                if not os.path.exists(local_json):
                    local_json = str(PROJECT_ROOT / "config.json")
                config_path = local_json

            with open(config_path, "r") as f:
                content = f.read()
            content = re.sub(r"//.*", "", content)
            config = json.loads(content)
            config["CSV_LOG_INTERVAL"] = int(value)

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            self.csv_log_interval = int(value)
            return True
        except Exception as e:
            print(f"Error setting CSV_LOG_INTERVAL: {e}")
            return False

    def _on_csv_interval_change(self):
        """Handle CSV log interval change from UI."""
        try:
            new_val = int(self.csv_interval_var.get())
            # Removed minimum interval restriction; allow values below 10 seconds
            if new_val > 3600:
                messagebox.showwarning("Warning", "Maximum interval is 3600 seconds (1 hour).")
                self.csv_interval_var.set(str(self.csv_log_interval))
                return

            if self._set_csv_log_interval(new_val):
                self.status_label.config(
                    text=f"CSV Log Interval set to {new_val}s. Restart logging for changes to take effect.",
                    fg="green",
                )
                self.output.insert(tk.END, f"\n[Config] CSV_LOG_INTERVAL changed to {new_val} seconds.\n")
                self.output.insert(tk.END, "Note: Restart Manual Run or reboot for changes to take effect.\n")
            else:
                messagebox.showerror("Error", "Failed to save CSV log interval.")
                self.csv_interval_var.set(str(self.csv_log_interval))
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number.")
            self.csv_interval_var.set(str(self.csv_log_interval))

    # ─── JSON / config helpers ───

    def _load_jsonc(self, path):
        try:
            text = open(path, "r", encoding="utf-8").read()
        except Exception:
            return {}

        def _strip(line: str) -> str:
            in_str = False
            esc = False
            out = []
            i = 0
            while i < len(line):
                ch = line[i]
                if ch == '"' and not esc:
                    in_str = not in_str
                if not in_str and i + 1 < len(line) and line[i:i + 2] == "//":
                    break
                esc = (ch == "\\") and not esc
                out.append(ch)
                i += 1
            return "".join(out)

        cleaned = "\n".join(_strip(l) for l in text.splitlines())
        try:
            return json.loads(cleaned or "{}")
        except Exception:
            return {}

    def _save_config_json(self, cfg: dict):
        cfg_path = str(PROJECT_ROOT / "config" / "config.json")
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write config.json: {e}")
            return False

    # ─── AP (Access Point) helpers ───

    def _get_ap_enabled_safe(self) -> bool:
        try:
            cfg_path = str(PROJECT_ROOT / "usb_download_mvp" / "local_config.json")
            if not os.path.exists(cfg_path):
                return False
            cfg = self._load_jsonc(cfg_path)
            ap = cfg.get("usb_ap", {})
            return bool(ap.get("enabled", False))
        except Exception:
            return False

    def _apply_ap_systemd(self, enabled: bool):
        def worker():
            try:
                if enabled:
                    cmd = ["sudo", "-n", "systemctl", "enable", "--now", "usb_ap.service"]
                    self.after(0, lambda: self.output.insert(tk.END, f"\n$ {' '.join(cmd)}\n"))
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    out = proc.stdout or ""
                    if proc.returncode != 0:
                        self.after(0, lambda: self.output.insert(tk.END,
                            f"\n[ERROR] Enabling AP failed (rc={proc.returncode}):\n{out}\n"))
                        self.after(0, lambda: self.status_label.config(
                            text="Failed to enable AP: GUI cannot sudo interactively. "
                                 "Run 'sudo systemctl enable --now usb_ap.service' in a terminal.",
                            fg="red"))
                    else:
                        self.after(0, lambda: self.output.insert(tk.END, f"\n[OK] AP enabled.\n{out}\n"))
                else:
                    cmd_disable = ["sudo", "-n", "systemctl", "disable", "--now", "usb_ap.service"]
                    self.after(0, lambda: self.output.insert(tk.END, f"\n$ {' '.join(cmd_disable)}\n"))
                    proc = subprocess.run(cmd_disable, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    out = proc.stdout or ""
                    if proc.returncode != 0:
                        self.after(0, lambda: self.output.insert(tk.END,
                            f"\n[ERROR] Disabling AP failed (rc={proc.returncode}):\n{out}\n"))
                        self.after(0, lambda: self.status_label.config(
                            text="Failed to disable AP: GUI cannot sudo interactively. "
                                 "Run 'sudo systemctl disable --now usb_ap.service' in a terminal.",
                            fg="red"))
                    else:
                        self.after(0, lambda: self.output.insert(tk.END, f"\n[OK] AP disabled.\n{out}\n"))

                    # Explicitly call enforce_ap_mode.sh stop
                    try:
                        enforce_script = str(PROJECT_ROOT / "usb_download_mvp" / "scripts" / "enforce_ap_mode.sh")
                        stop_cmd = ["sudo", "bash", enforce_script, "stop"]
                        self.after(0, lambda: self.output.insert(tk.END, f"\n$ {' '.join(stop_cmd)}\n"))
                        stop_proc = subprocess.run(stop_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        stop_out = stop_proc.stdout or ""
                        if stop_proc.returncode != 0:
                            self.after(0, lambda: self.output.insert(tk.END,
                                f"\n[WARN] enforce_ap_mode.sh stop returned rc={stop_proc.returncode}:\n{stop_out}\n"))
                        else:
                            self.after(0, lambda: self.output.insert(tk.END,
                                f"\n[OK] enforce_ap_mode.sh stop completed.\n{stop_out}\n"))
                    except Exception as e:
                        self.after(0, lambda: self.output.insert(tk.END,
                            f"\n[EXC] Failed to run enforce_ap_mode.sh stop: {e}\n"))
            except Exception as e:
                self.after(0, lambda: self.output.insert(tk.END, f"\n[EXC] Exception while toggling AP: {e}\n"))
                self.after(0, lambda: self.status_label.config(text=f"Error toggling AP: {e}", fg="red"))
            finally:
                try:
                    self.after(0, lambda: self.ap_toggle.config(state=tk.NORMAL))
                    self.after(0, self._update_ap_service_status)
                except Exception:
                    pass

        try:
            self.ap_toggle.config(state=tk.DISABLED)
        except Exception:
            pass
        threading.Thread(target=worker, daemon=True).start()

    def _update_ap_service_status(self):
        try:
            enabled = self._is_systemd_enabled('usb_ap.service')
            if enabled:
                txt = 'AP Service: enabled'
                fg = 'green'
            else:
                txt = 'AP Service: disabled'
                fg = 'red'
            if hasattr(self, 'ap_service_status_label'):
                self.ap_service_status_label.config(text=txt, fg=fg)
        except Exception:
            if hasattr(self, 'ap_service_status_label'):
                self.ap_service_status_label.config(text='AP Service: unknown', fg='orange')

    def on_toggle_ap(self):
        enabled = bool(self.ap_enabled_var.get())
        cfg_path = str(PROJECT_ROOT / "usb_download_mvp" / "local_config.json")
        try:
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        except Exception:
            pass
        cfg = {}
        try:
            if os.path.exists(cfg_path):
                cfg = self._load_jsonc(cfg_path)
        except Exception:
            cfg = {}
        if "usb_ap" not in cfg:
            cfg["usb_ap"] = {}
        cfg["usb_ap"]["enabled"] = enabled
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            self.status_label.config(
                text=f"AP at boot {'ENABLED' if enabled else 'DISABLED'} (persisted locally)",
                fg="green" if enabled else "orange",
            )
            self._apply_ap_systemd(enabled)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write local config: {e}")

    def _is_systemd_enabled(self, unit: str) -> bool:
        try:
            rc = subprocess.run(
                ["systemctl", "is-enabled", unit],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            return rc.returncode == 0
        except Exception:
            return False

    # ─── Widget creation (called once from __init__) ───

    def create_widgets(self):
        tk.Label(self, text="Simple Meter Dashboard - Technician UI", font=("Arial", 16, "bold")).pack(pady=10)

        self.btn_frame1 = tk.Frame(self)
        self.btn_frame1.pack(pady=5)
        self.csv_frame = tk.Frame(self)
        self.csv_frame.pack(pady=2)
        self.ap_frame = tk.Frame(self)
        self.ap_frame.pack(pady=2)
        self.btn_frame2 = tk.Frame(self)
        self.btn_frame2.pack(pady=5)
        self.btn_frame3 = tk.Frame(self)
        self.btn_frame3.pack(pady=5)

        # ── First row: Setup, Configure, Config editors, Auto-Start ──
        tk.Button(self.btn_frame1, text="Setup Environment", width=18, command=self.setup_env).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame1, text="Configure Devices", width=18, command=self.configure_devices).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame1, text="View/Edit Device Config", width=18, command=self.edit_config).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame1, text="View/Edit System Config", width=20, command=self.edit_system_config).pack(side=tk.LEFT, padx=5)
        self.auto_start_btn = tk.Button(self.btn_frame1, text="Enable Auto-Start", width=18, command=self.auto_start)
        self.auto_start_btn.pack(side=tk.LEFT, padx=5)

        # ── CSV log interval control ──
        tk.Label(self.csv_frame, text="CSV Log Interval (seconds):").pack(side=tk.LEFT, padx=(5, 2))
        self.csv_interval_var = tk.StringVar(value=str(self.csv_log_interval))
        self.csv_interval_entry = tk.Entry(self.csv_frame, textvariable=self.csv_interval_var, width=6)
        self.csv_interval_entry.pack(side=tk.LEFT, padx=2)
        tk.Button(self.csv_frame, text="Apply", width=6, command=self._on_csv_interval_change).pack(side=tk.LEFT, padx=2)
        tk.Label(self.csv_frame, text="(10-3600s, lower = more writes)", fg="gray").pack(side=tk.LEFT, padx=(5, 2))

        # ── AP at boot toggle ──
        tk.Label(self.ap_frame, text="AP at boot:").pack(side=tk.LEFT, padx=(5, 2))
        self.ap_toggle = tk.Checkbutton(self.ap_frame, text="Enable", variable=self.ap_enabled_var, command=self.on_toggle_ap)
        self.ap_toggle.pack(side=tk.LEFT, padx=5)
        self.ap_service_status_label = tk.Label(self.ap_frame, text="AP Service: unknown", fg="orange")
        self.ap_service_status_label.pack(side=tk.LEFT, padx=(8, 4))
        tk.Button(self.ap_frame, text="Refresh", width=8, command=self._update_ap_service_status).pack(side=tk.LEFT, padx=4)

        # ── Second row: Manual Run, Live Readings, Force Stop ──
        self.manual_btn = tk.Button(self.btn_frame2, text="Manual Run", width=18, command=self.manual_run)
        self.manual_btn.pack(side=tk.LEFT, padx=5)
        self.live_btn = tk.Button(self.btn_frame2, text="Live Readings", width=18, command=self.live_readings)
        self.live_btn.pack(side=tk.LEFT, padx=5)
        self.force_stop_btn = tk.Button(
            self.btn_frame2, text="Force Stop Logging", width=24, height=2,
            font=("Arial", 11, "bold"), command=self.force_stop_logging,
        )
        self.force_stop_btn.pack(side=tk.LEFT, padx=5)

        # ── Third row: Reboot, Exit ──
        tk.Button(self.btn_frame3, text="Reboot System", width=18, command=self.reboot_system).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame3, text="Exit", width=10, command=self.destroy).pack(side=tk.LEFT, padx=5)

        # ── Status / output area ──
        self.status_label = tk.Label(self, text="", fg="blue", font=("Arial", 12))
        self.status_label.pack(pady=5)
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=10)
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.bottom_status_label = tk.Label(
            self,
            text="Troubleshooting: If you see errors, check wiring, config, permissions, and logs.",
            fg="red", font=("Arial", 12),
        )
        self.bottom_status_label.pack(pady=5)

        self.check_logging_process()
        self.after(2000, self.periodic_check_logging)

    # ─── Button actions ───

    def reboot_system(self):
        if messagebox.askyesno("Reboot", "Are you sure you want to reboot the Raspberry Pi?"):
            self.run_command(["sudo", "reboot"])

    def edit_config(self):
        from src.utils.paths import get_config_dir
        config_dir = str(get_config_dir())
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "device_config.json")
        if not os.path.exists(config_path):
            try:
                with open(config_path, "w") as f:
                    f.write("[]\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create default config: {e}")
                return
        try:
            os.system(f"geany {config_path} &")
            self.output.insert(tk.END, f"\nOpened {config_path} in Geany editor.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config: {e}")

    def edit_system_config(self):
        """Open the main config.json in the editor."""
        config_path = os.path.join(str(PROJECT_ROOT), "config", "config.json")
        if os.path.exists(config_path):
            try:
                os.system(f"geany {config_path} &")
                self.output.insert(tk.END, f"\nOpened {config_path} in Geany editor.\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open config: {e}")
        else:
            messagebox.showerror("Error", f"Config file {config_path} not found.")

    def configure_devices(self):
        try:
            import importlib.util
            config_path = str(PROJECT_ROOT / "src" / "utils" / "configure_device.py")
            spec = importlib.util.spec_from_file_location("configure_device", config_path)
            config_module = importlib.util.module_from_spec(spec)
            sys.modules["configure_device"] = config_module
            spec.loader.exec_module(config_module)
            config_module.DeviceConfigUI(parent=self)
            self.output.insert(tk.END, "\nOpened Device Configuration Tool in a new window.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Device Configuration Tool: {e}")

    def auto_start(self):
        try:
            script_path = str(PROJECT_ROOT / "scripts" / "setup" / "enable_auto_start.sh")
            self.status_label.config(text="Enabling Auto-Start… this can take a few seconds.", fg="blue")
            try:
                self.config(cursor="watch")
            except Exception:
                pass
            if hasattr(self, "auto_start_btn"):
                self.auto_start_btn.config(state=tk.DISABLED)

            def worker():
                try:
                    env = os.environ.copy()
                    env["PYTHONUNBUFFERED"] = "1"
                    proc = subprocess.Popen(
                        ["sudo", "bash", script_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        env=env,
                    )
                    self.output.insert(tk.END, f"\n[Auto-Start] Running: sudo bash {script_path}\n")
                    self.output.see(tk.END)
                    for line in proc.stdout:
                        self.output.insert(tk.END, line)
                        self.output.see(tk.END)
                    rc = proc.wait()

                    # After enabling auto-start, set RTC from current system time
                    try:
                        set_script = str(PROJECT_ROOT / "src" / "utils" / "set_rtc_from_system.py")
                        if os.path.exists(set_script):
                            proc2 = subprocess.Popen(
                                ["sudo", "python3", set_script],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                            )
                            self.output.insert(tk.END, f"\n[RTC Setup] Running: sudo python3 {set_script}\n")
                            self.output.see(tk.END)
                            for line in proc2.stdout:
                                self.output.insert(tk.END, line)
                                self.output.see(tk.END)
                            rc2 = proc2.wait()
                            if rc2 == 0:
                                self.output.insert(tk.END, "\n[RTC Setup] RTC set from system time.\n")
                            else:
                                self.output.insert(tk.END, f"\n[RTC Setup] Failed with rc={rc2}\n")
                        else:
                            self.output.insert(tk.END, "\n[RTC Setup] No set_rtc_from_system.py found; skipping RTC set.\n")
                    except Exception as e:
                        self.output.insert(tk.END, f"\n[RTC Setup] Exception: {e}\n")

                    def finalize():
                        try:
                            if rc == 0:
                                self.status_label.config(text="Auto-Start enabled successfully (systemd).", fg="green")
                            else:
                                self.status_label.config(text="Auto-Start setup failed. Check output.", fg="red")
                        finally:
                            if hasattr(self, "auto_start_btn"):
                                self.auto_start_btn.config(state=tk.NORMAL)
                            try:
                                self.config(cursor="")
                            except Exception:
                                pass

                    self.after(0, finalize)
                except Exception as e:
                    def on_err():
                        self.status_label.config(text=f"Error running auto-start: {e}", fg="red")
                        if hasattr(self, "auto_start_btn"):
                            self.auto_start_btn.config(state=tk.NORMAL)
                        try:
                            self.config(cursor="")
                        except Exception:
                            pass
                    self.after(0, on_err)

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self.status_label.config(text=f"Error: {e}", fg="red")
            if hasattr(self, "auto_start_btn"):
                self.auto_start_btn.config(state=tk.NORMAL)
            try:
                self.config(cursor="")
            except Exception:
                pass

    # ─── Logging process management ───

    def periodic_check_logging(self):
        self.check_logging_process()
        self.after(2000, self.periodic_check_logging)

    def check_logging_process(self):
        service_active = False
        try:
            svc = subprocess.run(
                ["systemctl", "is-active", "meter-dashboard.service"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            service_active = (svc.returncode == 0 and svc.stdout.strip() == "active")
        except Exception:
            service_active = False

        manual_running = False
        live_running = False
        msg = ""

        if service_active:
            msg = "Auto logging service is running."
        else:
            result = subprocess.run(["ps", "aux"], stdout=subprocess.PIPE, text=True)
            for line in result.stdout.splitlines():
                if "simple_rpi_dashboard.py" in line:
                    line_norm = line.strip().lower()
                    if "--run" in line_norm:
                        manual_running = True
                        msg = "Manual Run is already running!"
                    elif "--print-readings" in line_norm:
                        live_running = True
                        msg = "Live Readings is already running!"

        if service_active or manual_running:
            self.manual_btn.config(state=tk.DISABLED)
        else:
            self.manual_btn.config(state=tk.NORMAL)

        self.live_btn.config(state=tk.NORMAL)
        any_running = service_active or manual_running or live_running
        self.force_stop_btn.config(state=tk.NORMAL if any_running else tk.DISABLED)

        current_text = self.output.get('1.0', 'end-1c')
        lines = current_text.split('\n')
        if lines and (
            lines[0].startswith('Manual Run is already running!')
            or lines[0].startswith('Live Readings is already running!')
            or lines[0].startswith('Auto logging service is running.')
        ):
            lines = lines[1:]
        new_text = '\n'.join(lines)
        self.output.delete('1.0', tk.END)
        if msg:
            self.output.insert('1.0', f"{msg}\n" + new_text)
        else:
            self.output.insert('1.0', new_text)

    def force_stop_logging(self):
        try:
            subprocess.run(
                ["sudo", "systemctl", "stop", "meter-dashboard.service"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except Exception:
            pass
        subprocess.run(
            ["pkill", "-f", "simple_rpi_dashboard.py --run"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.status_label.config(text="Stopped logging (service and any manual runs).", fg="green")
        self.check_logging_process()

    # ─── Command / script execution ───

    def run_command(self, cmd, on_complete=None):
        self.output.insert(tk.END, f"\n--- Running: {' '.join(cmd)} ---\n")
        self.output.see(tk.END)
        threading.Thread(target=self._run_subprocess, args=(cmd, on_complete)).start()

    def _run_subprocess(self, cmd, on_complete=None):
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            for line in proc.stdout:
                self.output.insert(tk.END, line)
                self.output.see(tk.END)
            proc.wait()
            self.output.insert(tk.END, f"\n--- Command finished ---\n")
            self.output.see(tk.END)
            try:
                if callable(on_complete):
                    on_complete()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run command: {e}")

    def run_script_window(self, cmd, title, disable_manual, disable_live, update_interval=None, on_complete=None):
        if self.output_window:
            messagebox.showinfo("Info", "A script is already running.")
            return
        self.status_label.config(text=f"{title} is running...")
        self.manual_btn.config(state=tk.DISABLED if disable_manual else tk.NORMAL)
        self.live_btn.config(state=tk.DISABLED if disable_live else tk.NORMAL)
        self.output_window = OutputWindow(self, title, self.stop_script)
        threading.Thread(target=self._start_and_stream_output, args=(cmd, None, on_complete), daemon=True).start()

    def _start_and_stream_output(self, cmd, update_interval=None, on_complete=None):
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid,
            )
        except TypeError:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if update_interval is not None:
            self._stream_output_interval(update_interval)
        else:
            self._stream_output()
        try:
            if callable(on_complete):
                on_complete()
        except Exception:
            pass

    def _stream_output_interval(self, interval):
        import time
        buffer = []
        last_update = time.time()
        first_flush = False
        try:
            for line in self.proc.stdout:
                buffer.append(line)
                now = time.time()
                if not first_flush:
                    if self.output_window is not None and hasattr(self.output_window, 'output'):
                        try:
                            self.output_window.insert(''.join(buffer))
                        except Exception:
                            pass
                    buffer.clear()
                    last_update = now
                    first_flush = True
                elif now - last_update >= interval:
                    if self.output_window is not None and hasattr(self.output_window, 'output'):
                        try:
                            self.output_window.insert(''.join(buffer))
                        except Exception:
                            pass
                    buffer.clear()
                    last_update = now
            if buffer and self.output_window is not None and hasattr(self.output_window, 'output'):
                try:
                    self.output_window.insert(''.join(buffer))
                except Exception:
                    pass
            self.proc.wait()
            if self.output_window is not None and hasattr(self.output_window, 'output'):
                try:
                    self.output_window.insert("\n--- Command finished ---\n")
                except Exception:
                    pass
        except Exception as e:
            if self.output_window is not None and hasattr(self.output_window, 'output'):
                try:
                    self.output_window.insert(f"\nError: {e}\n")
                except Exception:
                    pass
        finally:
            self.status_label.config(text="")
            self.manual_btn.config(state=tk.NORMAL)
            self.live_btn.config(state=tk.NORMAL)
            if self.output_window is not None:
                try:
                    self.output_window.destroy()
                except Exception:
                    pass
                self.output_window = None
            self.proc = None

    def _stream_output(self):
        try:
            for line in self.proc.stdout:
                if self.output_window is not None:
                    self.output_window.insert(line)
            self.proc.wait()
            if self.output_window is not None:
                self.output_window.insert("\n--- Command finished ---\n")
        except Exception as e:
            if self.output_window is not None:
                self.output_window.insert(f"\nError: {e}\n")
        finally:
            self.status_label.config(text="")
            self.manual_btn.config(state=tk.NORMAL)
            self.live_btn.config(state=tk.NORMAL)
            if self.output_window is not None:
                self.output_window.destroy()
                self.output_window = None
            self.proc = None

    def stop_script(self):
        try:
            if self.proc and self.proc.poll() is None:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                except Exception:
                    try:
                        self.proc.terminate()
                    except Exception:
                        pass
                if self.output_window is not None:
                    self.output_window.insert("\n--- Script stopped by user ---\n")
                self.status_label.config(text="Script stopped.")
            self.manual_btn.config(state=tk.NORMAL)
            self.live_btn.config(state=tk.NORMAL)
        except Exception as e:
            self.status_label.config(text=f"Error stopping script: {e}")
        finally:
            self.proc = None
            if self.output_window is not None:
                self.output_window.destroy()
                self.output_window = None

    # ─── Dashboard launch actions ───

    def setup_env(self):
        dashboard_path = str(PROJECT_ROOT / "src" / "dashboard" / "simple_rpi_dashboard.py")
        self.run_command(
            ["python3", "-u", dashboard_path, "--setup"],
            on_complete=lambda: self.after(100, self.check_rtc_status),
        )

    def manual_run(self):
        dashboard_path = str(PROJECT_ROOT / "src" / "dashboard" / "simple_rpi_dashboard.py")
        venv_py = str(PROJECT_ROOT / "venv" / "bin" / "python")
        venv313_py = str(PROJECT_ROOT / "venv313" / "bin" / "python")
        if os.path.exists(venv313_py):
            venv_py = venv313_py
        cmd = (
            [venv_py, dashboard_path, "--run", "--force-mqtt"]
            if os.path.exists(venv_py)
            else ["python3", dashboard_path, "--run", "--force-mqtt"]
        )
        self.run_script_window(cmd, "Manual Run Output", True, False)

    def live_readings(self):
        LiveReadingsWindow(self, self.reading_interval)



# ─── Live Readings modal window (compact table) ───

class LiveReadingsWindow(tk.Toplevel):
    """
    Compact table: one row per meter, columns for R/Y/B voltage & current.
    All 14 meters visible at once — no scrolling. Values update in-place.
    """

    _SHOW_COLS = ["V_R_Ph", "V_Y_Ph", "V_B_Ph", "A_R_Ph", "A_Y_Ph", "A_B_Ph"]
    _COL_LABELS = ["Meter", "V_R", "V_Y", "V_B", "A_R", "A_Y", "A_B"]

    def __init__(self, parent, reading_interval):
        super().__init__(parent)
        self.title("Live Readings")
        self.geometry("820x560")
        self.min_refresh_interval = 0.5
        self.reading_interval = max(reading_interval, self.min_refresh_interval)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._running = True

        csv_dir = str(PROJECT_ROOT / "data" / "csv")
        self.csv_path = os.path.join(csv_dir, "DATA_ALL.csv")
        try:
            os.makedirs(csv_dir, exist_ok=True)
        except Exception:
            pass

        # Title
        tk.Label(self, text="Live Meter Readings", font=("Arial", 14, "bold")).pack(pady=(8, 4))

        # Table frame
        self.table_frame = tk.Frame(self)
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # Build header row
        for col_idx, label in enumerate(self._COL_LABELS):
            bg = "#2c3e50" if col_idx == 0 else ("#2980b9" if col_idx <= 3 else "#27ae60")
            tk.Label(
                self.table_frame, text=label, font=("Arial", 10, "bold"),
                bg=bg, fg="white", width=10, anchor="center",
                relief="raised", padx=4, pady=4,
            ).grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)

        # Even column distribution
        for col_idx in range(len(self._COL_LABELS)):
            self.table_frame.columnconfigure(col_idx, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="Waiting for data…")
        tk.Label(self, textvariable=self.status_var, fg="gray", anchor="w").pack(
            fill=tk.X, padx=10, pady=(2, 6)
        )

        # Persistent widget refs
        self._header = None
        self._meter_rows = {}      # meter_name -> dict of value labels
        self._meter_order = []     # ordered list of meter names
        self._error_label = None

        self.after(100, self.refresh)

    def _close(self):
        self._running = False
        self.destroy()

    def _add_meter_row(self, meter_name):
        """Add one row to the table grid for a new meter (called once per meter)."""
        row_idx = len(self._meter_order) + 1  # +1 for header
        self._meter_order.append(meter_name)

        # Alternating row colour
        row_bg = "#f7f9fc" if row_idx % 2 == 0 else "#ffffff"

        # Meter name cell
        tk.Label(
            self.table_frame, text=meter_name, font=("Arial", 9, "bold"),
            bg=row_bg, anchor="w", padx=6, pady=3, width=10,
        ).grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=0)

        # Value cells
        value_labels = {}
        for col_idx, col_name in enumerate(self._SHOW_COLS):
            fg = "#2980b9" if col_idx < 3 else "#27ae60"
            lbl = tk.Label(
                self.table_frame, text="—", font=("Arial", 10, "bold"),
                bg=row_bg, fg=fg, anchor="center", padx=4, pady=3, width=10,
            )
            lbl.grid(row=row_idx, column=col_idx + 1, sticky="nsew", padx=1, pady=0)
            value_labels[col_name] = lbl

        self._meter_rows[meter_name] = value_labels

    def refresh(self):
        if not self._running:
            return
        import csv
        from datetime import datetime

        try:
            with open(self.csv_path, "r") as f:
                reader = list(csv.reader(f))

            if self._error_label is not None:
                self._error_label.pack_forget()

            if len(reader) < 2:
                if self._error_label is None:
                    self._error_label = tk.Label(self, text="", fg="orange")
                self._error_label.config(text="No data found in CSV yet.")
                self._error_label.pack()
            else:
                header = reader[0]
                if self._header is None:
                    self._header = header

                # Get latest row per meter
                latest_rows = {}
                for row in reversed(reader[1:]):
                    if len(row) < 2:
                        continue
                    meter_name = row[1]
                    if meter_name not in latest_rows:
                        latest_rows[meter_name] = row

                # Update or create rows
                for meter_name, row in latest_rows.items():
                    if meter_name not in self._meter_rows:
                        self._add_meter_row(meter_name)

                    value_labels = self._meter_rows[meter_name]
                    for param in self._SHOW_COLS:
                        if param in value_labels and param in header:
                            idx = header.index(param)
                            if idx < len(row):
                                value_labels[param].config(text=row[idx])

                self.status_var.set(
                    f"Last updated: {datetime.now().strftime('%H:%M:%S')}  |  {len(latest_rows)} meters"
                )

        except Exception as e:
            if self._error_label is None:
                self._error_label = tk.Label(self, text="", fg="red")
            self._error_label.config(text=f"Error reading CSV: {e}")
            self._error_label.pack()

        if self._running:
            self.after(int(self.reading_interval * 1000), self.refresh)


if __name__ == "__main__":
    app = SimpleMeterUI()
    app.mainloop()

