
import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
import re

# Use externalized config location with .json extension
CONFIG_DIR = "/home/pi/meter_config"
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(CONFIG_DIR, "device_config.json")
SUPPORTED_MODELS = ["LG6400", "LG+5220", "LG+5310", "EN8410"]

def strip_jsonc_comments(text):
    """Remove // and /* */ style comments from JSONC content."""
    # Remove // line comments
    text = re.sub(r"//.*", "", text)
    # Remove /* block */ comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text

def _extract_devices_structure(data):
    """Normalize various shapes into a flat devices list and remember original shape.

    Returns a tuple: (devices_list, container_kind, container_key)
    - container_kind: 'list' or 'dict'
    - container_key: key name if dict (e.g., 'devices', 'meters', 'items'), else None
    """
    if isinstance(data, list):
        return data, 'list', None
    if isinstance(data, dict):
        for key in ("devices", "meters", "items"):
            v = data.get(key)
            if isinstance(v, list):
                return v, 'dict', key
        # Unknown dict shape -> treat as empty device list but preserve dict
        return [], 'dict', 'devices'
    # Fallback: invalid -> empty list
    return [], 'list', None

def load_config():
    """Load device configuration file from CONFIG_PATH.

    Returns (devices_list, container_kind, container_key)
    """
    if not os.path.exists(CONFIG_PATH):
        return [], 'list', None
    with open(CONFIG_PATH, "r") as f:
        content = strip_jsonc_comments(f.read())
        try:
            data = json.loads(content)
        except Exception:
            return [], 'list', None
    devices, kind, key = _extract_devices_structure(data)
    # Normalize keys so UI logic is robust
    normed = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        name = d.get('name') or d.get('meter_name') or d.get('device_name') or ""
        # Prefer numeric address; fall back to device_id-like keys
        addr = (
            d.get('address', None)
            if 'address' in d else d.get('meter_address', None)
            if 'meter_address' in d else d.get('device_id', None)
        )
        try:
            address = int(addr) if addr is not None else None
        except Exception:
            address = None
        model = d.get('model') or d.get('meter_model') or d.get('type') or ""
        location = d.get('location') or d.get('site') or d.get('plant') or ""
        merged = dict(d)
        merged.setdefault('name', name)
        if address is not None:
            merged['address'] = address
        else:
            merged.setdefault('address', 1)
        merged.setdefault('model', model)
        merged.setdefault('location', location)
        normed.append(merged)
    return normed, kind, key

def save_config(devices, container_kind='list', container_key=None):
    """Persist devices, preserving original container shape when possible."""
    # Ensure directory exists (in case module used standalone)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    payload = None
    if container_kind == 'dict':
        key = container_key or 'devices'
        payload = {key: devices}
    else:
        payload = devices
    # Write strict JSON (no comments)
    with open(CONFIG_PATH, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

class DeviceConfigUI(tk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Device Configuration Tool")
        self.geometry("500x400")
        # Load and remember original container shape
        self.devices, self._container_kind, self._container_key = load_config()
        self.create_widgets()
        self.refresh_list()
        self.grab_set()
        self.lift()
        self.focus_force()
        if parent:
            self.transient(parent)
        self.update()
        self.attributes('-topmost', True)
        self.after(500, lambda: self.attributes('-topmost', False))

    def create_widgets(self):
        self.listbox = tk.Listbox(self, height=10)
        self.listbox.pack(fill=tk.X, padx=10, pady=10)
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Add Device", command=self.add_device).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Edit Device", command=self.edit_device).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Delete Device", command=self.delete_device).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save & Exit", command=self.save_and_exit).pack(side=tk.LEFT, padx=5)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for d in self.devices:
            name = d.get('name', '')
            address = d.get('address', '')
            model = d.get('model', '')
            location = d.get('location', '')
            self.listbox.insert(tk.END, f"{name} (Address: {address}, Model: {model}, Location: {location})")

    def add_device(self):
        device = self.prompt_device()
        if device:
            self.devices.append(device)
            self.refresh_list()

    def edit_device(self):
        idx = self.listbox.curselection()
        if not idx:
            messagebox.showerror("Error", "Select a device to edit.")
            return
        existing = self.devices[idx[0]]
        updated = self.prompt_device(existing)
        if updated:
            # Preserve unknown keys from existing device
            merged = dict(existing)
            merged.update(updated)
            self.devices[idx[0]] = merged
            self.refresh_list()

    def delete_device(self):
        idx = self.listbox.curselection()
        if not idx:
            messagebox.showerror("Error", "Select a device to delete.")
            return
        if messagebox.askyesno("Delete", "Are you sure you want to delete this device?"):
            self.devices.pop(idx[0])
            self.refresh_list()

    def save_and_exit(self):
        save_config(self.devices, self._container_kind, self._container_key)
        messagebox.showinfo("Saved", f"Configuration saved to {CONFIG_PATH}.")
        self.destroy()

    def prompt_device(self, existing=None):
        self.attributes('-topmost', True)
        name = simpledialog.askstring("Meter Name", "Enter meter name:", initialvalue=(existing.get("name") if existing else ""), parent=self)
        if not name:
            self.attributes('-topmost', False)
            return None
        address = simpledialog.askstring("Modbus Address", "Enter Modbus address (number):", initialvalue=(str(existing.get("address")) if existing and existing.get("address") is not None else ""), parent=self)
        if not address or not address.isdigit():
            messagebox.showerror("Error", "Address must be a number.", parent=self)
            self.attributes('-topmost', False)
            return None
        model = simpledialog.askstring("Model", f"Enter model ({', '.join(SUPPORTED_MODELS)}):", initialvalue=(existing.get("model") if existing else ""), parent=self)
        if model not in SUPPORTED_MODELS:
            messagebox.showerror("Error", f"Model must be one of: {', '.join(SUPPORTED_MODELS)}", parent=self)
            self.attributes('-topmost', False)
            return None
        location = simpledialog.askstring("Location", "Enter location:", initialvalue=(existing.get("location") if existing else ""), parent=self)
        self.attributes('-topmost', False)
        if not location:
            return None
        result = {
            "name": name,
            "address": int(address),
            "model": model,
            "location": location
        }
        return result

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = DeviceConfigUI(parent=root)
    app.mainloop()
