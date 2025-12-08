#!/usr/bin/env python3

import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import subprocess
import threading
import os
import signal
import json
import re


class OutputWindow(tk.Toplevel):
    def __init__(self, parent, title, stop_callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x250")
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=8)
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,2))
        self.stop_btn = tk.Button(self, text="Stop Script", width=14, cursor="arrow")
        self.stop_btn.pack(pady=(2,8))
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
    def reboot_system(self):
        if messagebox.askyesno("Reboot", "Are you sure you want to reboot the Raspberry Pi?"):
            self.run_command(["sudo", "reboot"])
    def edit_config(self):
        # Use externalized config location
        config_dir = "/home/pi/meter_config"
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "device_config.json")
        # Create a default file if missing so the editor opens something meaningful
        if not os.path.exists(config_path):
            try:
                # Create a minimal valid JSON array
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
    def configure_devices(self):
        try:
            import sys
            import importlib.util
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configure_device.py")
            spec = importlib.util.spec_from_file_location("configure_device", config_path)
            config_module = importlib.util.module_from_spec(spec)
            sys.modules["configure_device"] = config_module
            spec.loader.exec_module(config_module)
            config_window = config_module.DeviceConfigUI(parent=self)
            self.output.insert(tk.END, "\nOpened Device Configuration Tool in a new window.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Device Configuration Tool: {e}")
    def auto_start(self):
        # Run enable_auto_start.sh off the main thread and show immediate feedback
        try:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enable_auto_start.sh")
            # Immediate UI feedback and disable button to avoid double-clicks
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

                    # After enabling auto-start, set RTC from current system time (one-off)
                    try:
                        set_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "set_rtc_from_system.py")
                        if os.path.exists(set_script):
                            # Run as root to ensure I2C access and write permission
                            proc2 = subprocess.Popen(["sudo", "python3", set_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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
    def __init__(self):
        super().__init__()
        self.title("Simple Meter Dashboard - Technician UI")
        self.geometry("800x600")
        self.proc = None
        self.output_window = None
        self.reading_interval = self._get_reading_interval()
        self.cloud_enabled_var = tk.BooleanVar(value=self._get_cloud_enabled_safe())
        self.create_widgets()
        # Refresh cloud service state display on startup
        try:
            self._update_cloud_service_status()
        except Exception:
            pass
        # RTC check on startup
        self.after(100, self.check_rtc_status)
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

        # Ensure required offline packages are installed from packages_folder
        def _ensure_offline_packages():
            try:
                import jinja2  # noqa: F401
                return
            except Exception:
                pass
            # Install required wheels strictly from local packages_folder (offline)
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
            import glob
            for p in pkgs:
                try:
                    wheel_candidates = sorted(glob.glob(p["glob"]))
                    if not wheel_candidates:
                        continue
                    wheel = wheel_candidates[-1]
                    # Use current interpreter (venv if active), install offline
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

    def check_rtc_status(self):
        import subprocess
        result = subprocess.run(["python3", "rtc_new.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            self.bottom_status_label.config(text="Real Time Clock Module Not Connected", fg="red")
        else:
            self.bottom_status_label.config(text="RTC detected and working.", fg="green")

    def _get_reading_interval(self):
        try:
            # Prefer externalized main config (.json)
            config_path = os.path.join("/home/pi/meter_config", "config.json")
            if not os.path.exists(config_path):
                # fallback to local copy so UI remains usable
                # prefer local .json, then .jsonc for backward compatibility
                local_dir = os.path.dirname(os.path.abspath(__file__))
                local_json = os.path.join(local_dir, "config.json")
                config_path = local_json
            with open(config_path, "r") as f:
                content = f.read()
            # Remove comments
            content = re.sub(r"//.*", "", content)
            config = json.loads(content)
            return int(config.get("READING_INTERVAL", 5))
        except Exception as e:
            print(f"Error reading READING_INTERVAL: {e}")
            return 5

    # --- Cloud sync enable/disable helpers ---
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
                if not in_str and i + 1 < len(line) and line[i:i+2] == "//":
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
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write config.json: {e}")
            return False

    def _get_cloud_enabled_safe(self) -> bool:
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            cfg = self._load_jsonc(cfg_path)
            cloud = cfg.get("cloud_sync", {})
            return bool(cloud.get("enabled", False))
        except Exception:
            return False

    def _apply_cloud_systemd(self, enabled: bool):
        # Enable/disable associated services so behavior persists across reboots
        try:
            if enabled:
                cmds = [
                    ["sudo", "systemctl", "enable", "--now", "cloud_sync.timer"],
                    ["sudo", "systemctl", "enable", "--now", "netwatch-trigger.service"],
                ]
            else:
                cmds = [
                    ["sudo", "systemctl", "disable", "--now", "cloud_sync.timer"],
                    ["sudo", "systemctl", "disable", "--now", "netwatch-trigger.service"],
                ]
            for cmd in cmds:
                self.output.insert(tk.END, f"\n$ {' '.join(cmd)}\n")
                self.output.see(tk.END)
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except Exception as e:
            self.output.insert(tk.END, f"\n[WARN] Failed to update services: {e}\n")
            self.output.see(tk.END)
        finally:
            # Refresh the UI display of service state
            try:
                self._update_cloud_service_status()
            except Exception:
                pass

    def _is_systemd_enabled(self, unit: str) -> bool:
        try:
            rc = subprocess.run(["systemctl", "is-enabled", unit], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return rc.returncode == 0
        except Exception:
            return False

    def _update_cloud_service_status(self):
        # Update the small label next to the cloud toggle to show whether services are enabled
        try:
            timer_enabled = self._is_systemd_enabled('cloud_sync.timer')
            netwatch_enabled = self._is_systemd_enabled('netwatch-trigger.service')
            if timer_enabled and netwatch_enabled:
                txt = 'Services: enabled'
                fg = 'green'
            elif timer_enabled or netwatch_enabled:
                txt = 'Services: partially enabled'
                fg = 'orange'
            else:
                txt = 'Services: disabled'
                fg = 'red'
            if hasattr(self, 'cloud_service_status_label'):
                self.cloud_service_status_label.config(text=txt, fg=fg)
        except Exception as e:
            if hasattr(self, 'cloud_service_status_label'):
                self.cloud_service_status_label.config(text='Services: unknown', fg='orange')

    def on_toggle_cloud_sync(self):
        enabled = bool(self.cloud_enabled_var.get())
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        cfg = self._load_jsonc(cfg_path)
        if "cloud_sync" not in cfg:
            cfg["cloud_sync"] = {}
        cfg["cloud_sync"]["enabled"] = enabled
        if self._save_config_json(cfg):
            self.status_label.config(text=f"Cloud Backup {'ENABLED' if enabled else 'DISABLED'} (persisted)", fg=("green" if enabled else "orange"))
            # Apply systemd state so checks only run when active and persist across reboots
            self._apply_cloud_systemd(enabled)

    def create_widgets(self):
        tk.Label(self, text="Simple Meter Dashboard - Technician UI", font=("Arial", 16, "bold")).pack(pady=10)
        self.btn_frame1 = tk.Frame(self)
        self.btn_frame1.pack(pady=5)
        # Cloud backup toggle row
        self.cloud_frame = tk.Frame(self)
        self.cloud_frame.pack(pady=2)
        self.btn_frame2 = tk.Frame(self)
        self.btn_frame2.pack(pady=5)
        self.btn_frame3 = tk.Frame(self)
        self.btn_frame3.pack(pady=5)

        # First row: Setup Environment, Configure Devices, View/Edit Config, Enable Auto-Start
        tk.Button(self.btn_frame1, text="Setup Environment", width=18, command=self.setup_env).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame1, text="Configure Devices", width=18, command=self.configure_devices).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame1, text="View/Edit Config", width=18, command=self.edit_config).pack(side=tk.LEFT, padx=5)
        self.auto_start_btn = tk.Button(self.btn_frame1, text="Enable Auto-Start", width=18, command=self.auto_start)
        self.auto_start_btn.pack(side=tk.LEFT, padx=5)

        # Cloud backup toggle
        tk.Label(self.cloud_frame, text="Online Backup:").pack(side=tk.LEFT, padx=(5,2))
        self.cloud_toggle = tk.Checkbutton(self.cloud_frame, text="Enable", variable=self.cloud_enabled_var, command=self.on_toggle_cloud_sync)
        self.cloud_toggle.pack(side=tk.LEFT, padx=5)
        # Small status label showing whether cloud-related services are enabled in systemd
        self.cloud_service_status_label = tk.Label(self.cloud_frame, text="Services: unknown", fg="orange")
        self.cloud_service_status_label.pack(side=tk.LEFT, padx=(8,4))
        # Refresh button to re-query systemd state
        tk.Button(self.cloud_frame, text="Refresh", width=8, command=self._update_cloud_service_status).pack(side=tk.LEFT, padx=4)

        # Second row: Manual Run, Live Readings, Force Stop Logging (make button larger)
        self.manual_btn = tk.Button(self.btn_frame2, text="Manual Run", width=18, command=self.manual_run)
        self.manual_btn.pack(side=tk.LEFT, padx=5)
        self.live_btn = tk.Button(self.btn_frame2, text="Live Readings", width=18, command=self.live_readings)
        self.live_btn.pack(side=tk.LEFT, padx=5)
        self.force_stop_btn = tk.Button(self.btn_frame2, text="Force Stop Logging", width=24, height=2, font=("Arial", 11, "bold"), command=self.force_stop_logging)
        self.force_stop_btn.pack(side=tk.LEFT, padx=5)

        # Third row: Reboot System, Exit
        tk.Button(self.btn_frame3, text="Reboot System", width=18, command=self.reboot_system).pack(side=tk.LEFT, padx=5)
        tk.Button(self.btn_frame3, text="Exit", width=10, command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(self, text="", fg="blue", font=("Arial", 12))
        self.status_label.pack(pady=5)
        self.output = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=10)
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.bottom_status_label = tk.Label(self, text="Troubleshooting: If you see errors, check wiring, config, permissions, and logs.", fg="red", font=("Arial", 12))
        self.bottom_status_label.pack(pady=5)
        self.check_logging_process()
        self.after(2000, self.periodic_check_logging)

    def periodic_check_logging(self):
        self.check_logging_process()
        self.after(2000, self.periodic_check_logging)

    def check_logging_process(self):
        # Prefer authoritative service state to avoid mislabeling service restarts as Manual Run
        import subprocess
        service_active = False
        try:
            svc = subprocess.run(["systemctl", "is-active", "meter-dashboard.service"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            service_active = (svc.returncode == 0 and svc.stdout.strip() == "active")
        except Exception:
            service_active = False

        manual_running = False
        live_running = False
        msg = ""

        if service_active:
            msg = "Auto logging service is running."
        else:
            # Fallback: check processes for manual runs or live readings
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

        # Disable Manual Run when service is active or manual already running
        if service_active or manual_running:
            self.manual_btn.config(state=tk.DISABLED)
        else:
            self.manual_btn.config(state=tk.NORMAL)

        # Live readings can always be opened
        self.live_btn.config(state=tk.NORMAL)
        # Force stop available when either service or manual/live is running
        any_running = service_active or manual_running or live_running
        self.force_stop_btn.config(state=tk.NORMAL if any_running else tk.DISABLED)

        # Show process/service status always at the top of output area
        current_text = self.output.get('1.0', 'end-1c')
        lines = current_text.split('\n')
        if lines and (lines[0].startswith('Manual Run is already running!') or lines[0].startswith('Live Readings is already running!') or lines[0].startswith('Auto logging service is running.')):
            lines = lines[1:]
        new_text = '\n'.join(lines)
        self.output.delete('1.0', tk.END)
        if msg:
            self.output.insert('1.0', f"{msg}\n" + new_text)
        else:
            self.output.insert('1.0', new_text)
        
    def force_stop_logging(self):
        import subprocess
        # Stop systemd service first (if active), then kill any manual runs as fallback
        try:
            subprocess.run(["sudo", "systemctl", "stop", "meter-dashboard.service"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except Exception:
            pass
        subprocess.run(["pkill", "-f", "simple_rpi_dashboard.py --run"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.status_label.config(text="Stopped logging (service and any manual runs).", fg="green")
        self.check_logging_process()

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
        # Always stream line-by-line for both Manual Run and Live Readings
        threading.Thread(target=self._start_and_stream_output, args=(cmd, None, on_complete), daemon=True).start()

    def _start_and_stream_output(self, cmd, update_interval=None, on_complete=None):
        # Start the subprocess in its own process group so signals sent to the UI
        # (or its parent process) do not automatically propagate to the dashboard.
        # This prevents the dashboard from receiving SIGTERM when the UI is closed.
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid,
            )
        except TypeError:
            # Windows or older environments may not support preexec_fn; fall back
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if update_interval is not None:
            self._stream_output_interval(update_interval)
        else:
            self._stream_output()
        # Call completion callback after process output handling
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
                # Flush immediately on first line
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
            # Flush any remaining output
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
                    # Terminate the whole process group so child processes are cleaned up.
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

    def setup_env(self):
        dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simple_rpi_dashboard.py")
        # Stream setup logs to the main output area (no modal) and refresh RTC status when done
        self.run_command(["python3", "-u", dashboard_path, "--setup"], on_complete=lambda: self.after(100, self.check_rtc_status))

    def manual_run(self):
        # Only disable Manual Run button, keep Live Readings enabled
        dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simple_rpi_dashboard.py")
        # Prefer using the local venv python when available so behavior matches CLI
        venv_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")
        cmd = [venv_py, dashboard_path, "--run", "--force-mqtt"] if os.path.exists(venv_py) else ["python3", dashboard_path, "--run", "--force-mqtt"]
        # Force-enable MQTT publishing during Manual Run so results are pushed to the broker
        self.run_script_window(cmd, "Manual Run Output", True, False)

    def live_readings(self):
        # Open a modal window to show live readings from CSV
        LiveReadingsWindow(self, self.reading_interval)

# New modal window for tabular live readings
class LiveReadingsWindow(tk.Toplevel):
    def __init__(self, parent, reading_interval):
        import glob
        import tkinter.ttk as ttk
        super().__init__(parent)
        self.title("Live Readings Table")
        self.geometry("1000x700")
        self.reading_interval = reading_interval
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._running = True
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Use single consolidated CSV file
        csv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csv")
        single_csv = os.path.join(csv_dir, "readings_all.csv")

        # Ensure CSV directory exists and provide a minimal CSV file if missing
        try:
            os.makedirs(csv_dir, exist_ok=True)
            if not os.path.exists(single_csv):
                import csv as _csv
                with open(single_csv, "w", newline='') as _f:
                    writer = _csv.writer(_f)
                    # Minimal header expected by MeterManager/UI
                    writer.writerow(["Device_ID", "Meter_Name", "Time", "Model"])
        except Exception:
            # Best-effort: continue without blocking the UI
            pass
        self.tabs = {}
        tab = tk.Frame(self.notebook)
        # Add a canvas and scrollbar to the tab for scrolling
        canvas = tk.Canvas(tab)
        scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.notebook.add(tab, text="readings_all")
        self.tabs[single_csv] = scroll_frame
        self.after(100, self.refresh)

    def _close(self):
        self._running = False
        self.destroy()

    def refresh(self):
        if not self._running:
            return
        import csv
        for csv_path, scroll_frame in self.tabs.items():
            for widget in scroll_frame.winfo_children():
                widget.destroy()
            try:
                with open(csv_path, "r") as f:
                    reader = list(csv.reader(f))
                if len(reader) < 2:
                    tk.Label(scroll_frame, text="No data found in CSV.", fg="red").pack()
                else:
                    header = reader[0]
                    latest_rows = {}
                    # Find latest row for each meter by Meter_Name
                    for row in reversed(reader[1:]):
                        meter_name = row[1]
                        if meter_name not in latest_rows:
                            latest_rows[meter_name] = row
                    for meter_name, row in latest_rows.items():
                        meter_frame = tk.LabelFrame(scroll_frame, text=f"Meter: {meter_name}", padx=8, pady=8)
                        meter_frame.pack(fill=tk.X, padx=6, pady=6)
                        table = tk.Frame(meter_frame)
                        table.pack()
                        for i, param in enumerate(header):
                            if param in ["Device_ID", "Meter_Name", "Time", "Model"]:
                                continue
                            tk.Label(table, text=param, width=22, anchor="w", font=("Arial", 10)).grid(row=i, column=0, sticky="w")
                            tk.Label(table, text=row[i], width=18, anchor="w", font=("Arial", 10, "bold"), fg="blue").grid(row=i, column=1, sticky="w")
            except Exception as e:
                tk.Label(scroll_frame, text=f"Error reading CSV: {e}", fg="red").pack()
        if self._running:
            self.after(self.reading_interval * 1000, self.refresh)


    def configure_devices(self):
        try:
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location("configure_device", "configure_device.py")
            config_module = importlib.util.module_from_spec(spec)
            sys.modules["configure_device"] = config_module
            spec.loader.exec_module(config_module)
            config_window = config_module.DeviceConfigUI(parent=self)
            self.output.insert(tk.END, "\nOpened Device Configuration Tool in a new window.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Device Configuration Tool: {e}")

    def edit_config(self):
        config_path = "/home/pi/meter_config/device_config.json"
        if os.path.exists(config_path):
            try:
                os.system(f"geany {config_path} &")
                self.output.insert(tk.END, f"\nOpened {config_path} in Geany editor.\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open config: {e}")
        else:
            messagebox.showerror("Error", f"Config file {config_path} not found.")

    def view_logs(self):
        # Open the most recent dashboard log in logs/
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        try:
            if not os.path.isdir(logs_dir):
                self.output.insert(tk.END, f"\nLogs directory {logs_dir} not found.\n")
                return
            log_files = [os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.endswith('.log')]
            if not log_files:
                self.output.insert(tk.END, f"\nNo .log files found in {logs_dir}.\n")
                return
            latest = max(log_files, key=lambda p: os.path.getmtime(p))
            os.system(f"geany {latest} &")
            self.output.insert(tk.END, f"\nOpened {latest} in Geany editor.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open log: {e}")

    def system_status(self):
        self.output.insert(tk.END, "\n--- System Status ---\n")
        try:
            disk = subprocess.check_output(["df", "-h", "."], text=True)
            self.output.insert(tk.END, f"Disk Space:\n{disk}\n")
            cron = subprocess.check_output(["crontab", "-l"], text=True)
            self.output.insert(tk.END, f"Cron Jobs:\n{cron}\n")
            self.output.insert(tk.END, "Check if user is in 'dialout' group for serial access.\n")
        except Exception as e:
            self.output.insert(tk.END, f"Error checking system status: {e}\n")
        self.output.see(tk.END)

    def backup_data(self):
        # Let the user choose any CSV from the consolidated data/csv directory
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csv")
        if not os.path.isdir(base_dir):
            self.output.insert(tk.END, f"\nCSV directory {base_dir} not found.\n")
            return
        src = filedialog.askopenfilename(initialdir=base_dir, title="Select CSV to Backup", filetypes=[("CSV Files", "*.csv")])
        if not src:
            return
        dest = filedialog.asksaveasfilename(title="Save CSV Data As", defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if dest:
            try:
                import shutil
                shutil.copy(src, dest)
                self.output.insert(tk.END, f"\nCSV data backed up to {dest}\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to backup data: {e}")

    def restore_defaults(self):
        # Restore defaults into externalized config directory
        config_dir = "/home/pi/meter_config"
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "device_config.json")
        default_content = "[]\n"
        try:
            with open(config_path, "w") as f:
                f.write(default_content)
            self.output.insert(tk.END, f"\nRestored {config_path} to default guidance state.\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore defaults: {e}")

    def reboot_system(self):
        if messagebox.askyesno("Reboot", "Are you sure you want to reboot the Raspberry Pi?"):
            self.run_command(["sudo", "reboot"])

if __name__ == "__main__":
    app = SimpleMeterUI()
    app.mainloop()
