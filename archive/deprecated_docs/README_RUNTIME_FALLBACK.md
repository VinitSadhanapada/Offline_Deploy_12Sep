# Python 3.13 Runtime Fallback (Offline)

This bundle can optionally include a prebuilt Python 3.13.5 runtime tarball so new devices without Python 3.13 can be set up fully offline.

## How it works
- The script `one_click_system_py313.sh` checks the system `python3`.
- If `python3` is < 3.13 and a file named `python313_runtime.tar.gz` is present (in this folder, `dist_minimal/`, or `packages_folder/`), it will:
  - Extract it into `/usr/local` (requires sudo)
  - Locate `bin/python3.13` inside the extracted directory
  - Symlink `/usr/local/bin/python3.13` (and `pip3.13` if present)
  - Use that interpreter to create the venv and install offline wheels

Your system `python3` in `/usr/bin` is not modified; we add `/usr/local/bin/python3.13` alongside it.

## Tarball naming and expected contents
- Name the file: `python313_runtime.tar.gz`
- Expected contents after extraction (examples):
  - `/usr/local/python-3.13.5/bin/python3.13` (preferred)
  - or `/usr/local/python3.13.5/bin/python3.13`
  - or a similar top-level folder that contains `bin/python3.13`
- The tarball should be built on the same architecture (e.g., aarch64 for 64‑bit Raspberry Pi OS) so wheels and glibc are compatible.

## Creating the tarball (one known-good approach)
On a Raspberry Pi with Python 3.13 already installed (or built):

1. Stage a portable prefix under `/usr/local/python-3.13.5` (or similar) that contains:
   - `bin/python3.13`, `bin/pip3.13`
   - `lib/python3.13/...`
   - `include/python3.13/...`
2. Package it:

```bash
sudo tar -C /usr/local -czf ~/python313_runtime.tar.gz python-3.13.5
```

Then place `python313_runtime.tar.gz` next to `one_click_system_py313.sh` (or in `dist_minimal/` or `packages_folder/`).

> Tip: If you previously produced a runtime tarball for Python 3.11, follow the same process for 3.13.5. The script accepts any layout that leads to a `bin/python3.13` inside the extracted folder.

## Usage

- Fast path (already on 3.13):
  - No tarball needed. Just run:

```bash
./one_click_system_py313.sh --enable-services
```

- Fallback path (not on 3.13):
  - Copy `python313_runtime.tar.gz` into this folder (or `dist_minimal/`).
  - Run the same command; the script will install the runtime automatically:

```bash
./one_click_system_py313.sh --enable-services
```

## Notes
- Requires sudo to extract into `/usr/local` and create symlinks in `/usr/local/bin`.
- We do not overwrite `/usr/bin/python3`. The venv is always created and used for the app.
- The tarball is optional. Keep it in your minimal bundle if you expect devices without Python 3.13.
