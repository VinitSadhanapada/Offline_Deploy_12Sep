#!/usr/bin/env bash
# one_click_system_py313.sh
# Use system-installed Python 3.13.x to create a fresh venv, install offline wheels, smoke test.
# Optional: enable services.
# Safe for repeat runs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SYS="python3"
VENV_DIR="${SCRIPT_DIR}/venv"
PACKAGES_DIR="${SCRIPT_DIR}/packages_folder"
ENABLE_SERVICES=0
START_UI=0
ALLOW_SUDO=0
REQUIRED_MAJOR=3
REQUIRED_MINOR=13

# Optional offline runtime tarball candidates (prebuilt Python 3.13.5)
RUNTIME_TARBALL=""
for cand in \
  "${SCRIPT_DIR}/python313_runtime.tar.gz" \
  "${SCRIPT_DIR}/dist_minimal/python313_runtime.tar.gz" \
  "${SCRIPT_DIR}/packages_folder/python313_runtime.tar.gz"; do
  [[ -f "$cand" ]] && { RUNTIME_TARBALL="$cand"; break; }
done

for arg in "$@"; do
  case "$arg" in
    --enable-services) ENABLE_SERVICES=1 ;;
    --start-ui) START_UI=1 ;;
    --allow-sudo) ALLOW_SUDO=1 ;;
    --venv-name=*) VENV_DIR="${SCRIPT_DIR}/${arg#*=}" ;;
    -h|--help)
      cat <<EOF
Usage: ./one_click_system_py313.sh [--enable-services] [--venv-name=name]

Steps:
  1) Verify system python3 is >= ${REQUIRED_MAJOR}.${REQUIRED_MINOR}
  2) Create/repair venv under project folder
  3) Upgrade pip
  4) Offline install wheels from packages_folder
  5) Smoke test (Python, numpy, pandas)
  6) Optionally enable dashboard service

Requirements:
  - packages_folder contains cp313 wheels for target architecture
EOF
      exit 0
      ;;
  esac
done

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
info() { color 36 "[INFO] $1"; }
ok()   { color 32 "[OK] $1"; }
warn() { color 33 "[WARN] $1"; }
err()  { color 31 "[ERROR] $1"; }

require() { command -v "$1" >/dev/null 2>&1 || { err "Missing required command: $1"; exit 1; }; }

install_runtime_if_needed() {
  # Ensure we have an adequate python3; if not, and a runtime tarball is present, install it under /usr/local
  local have_py=1 ver major minor
  if ! command -v "$PY_SYS" >/dev/null 2>&1; then
    have_py=0
  fi
  if [ "$have_py" -eq 1 ]; then
    ver=$($PY_SYS -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")') || have_py=0
  fi
  if [ "$have_py" -eq 1 ]; then
    major=${ver%%.*}
    minor=${ver##*.}
  else
    major=0; minor=0
  fi

  if [ "$major" -lt "$REQUIRED_MAJOR" ] || { [ "$major" -eq "$REQUIRED_MAJOR" ] && [ "$minor" -lt "$REQUIRED_MINOR" ]; }; then
    if [[ -n "$RUNTIME_TARBALL" ]]; then
      info "System python3 is ${ver:-missing}; offline runtime tarball found: $RUNTIME_TARBALL"
      # First try extracting the runtime locally inside the project (no sudo) so first-run on a fresh image
      # can be passwordless. If that fails, fall back to installing under /usr/local (requires sudo).
      local local_root="${SCRIPT_DIR}"
      local local_install_dir="${local_root}/python-3.13.5"
      info "Attempting project-local extraction to: $local_install_dir"
      rm -rf "$local_install_dir" || true
      if tar -tzf "$RUNTIME_TARBALL" >/dev/null 2>&1; then
        if tar -xzf "$RUNTIME_TARBALL" -C "$local_root"; then
          # Try to find python3.13 in extracted tree
          local pybin=""
          for guess in \
            "$local_install_dir/bin/python3.13" \
            "$local_root/python3.13.5/bin/python3.13" \
            $local_root/python-3.13*/bin/python3.13 \
            $local_root/*3.13*/bin/python3.13; do
            for g in $guess; do
              [[ -x "$g" ]] && { pybin="$g"; break; }
            done
            [[ -n "$pybin" ]] && break
          done
          if [[ -n "$pybin" ]]; then
            PY_SYS="$pybin"
            info "Using project-local runtime: $PY_SYS"
            return
          else
            warn "Could not locate python3.13 in project-local extraction; cleaning up and falling back to system install"
            rm -rf "$local_install_dir" || true
          fi
        else
          warn "Project-local extraction failed; will try system-wide install as fallback"
        fi
      else
        warn "Runtime tarball appears invalid: $RUNTIME_TARBALL; will try system-wide install as fallback"
      fi

      # Fallback to system-wide install (existing behavior). Only allowed when user passed --allow-sudo.
      if [[ "$ALLOW_SUDO" -ne 1 ]]; then
        err "Project-local extraction failed and system-wide install requires sudo."
        err "Re-run with --allow-sudo to permit system-wide install, or provide a valid runtime tarball in the project to avoid sudo."
        exit 1
      fi
      info "Falling back to system-wide install under /usr/local (requires sudo)"
      require sudo
      local dest_root="/usr/local"
      local install_dir="${dest_root}/python-3.13.5"
      sudo mkdir -p "$dest_root"
      sudo tar -xzf "$RUNTIME_TARBALL" -C "$dest_root"
      # Try common locations to find python3.13 in extracted tree
      local pybin=""
      for guess in \
        "$install_dir/bin/python3.13" \
        "$dest_root/python3.13.5/bin/python3.13" \
        $dest_root/python-3.13*/bin/python3.13 \
        $dest_root/*3.13*/bin/python3.13; do
        for g in $guess; do
          [[ -x "$g" ]] && { pybin="$g"; break; }
        done
        [[ -n "$pybin" ]] && break
      done
      if [[ -z "$pybin" ]]; then
        err "Could not locate python3.13 in extracted runtime. Please verify tarball contents."; exit 1
      fi
      local prefix
      prefix=$(dirname "$pybin"); prefix=$(dirname "$prefix")
      sudo ln -sfn "$pybin" /usr/local/bin/python3.13
      if [[ -x "$prefix/bin/pip3.13" ]]; then
        sudo ln -sfn "$prefix/bin/pip3.13" /usr/local/bin/pip3.13
      elif [[ -x "$prefix/bin/pip3" ]]; then
        sudo ln -sfn "$prefix/bin/pip3" /usr/local/bin/pip3.13
      fi
      PY_SYS="/usr/local/bin/python3.13"
      info "Installed runtime. Using: $PY_SYS"
    else
      err "python3 must be >= ${REQUIRED_MAJOR}.${REQUIRED_MINOR} and no offline runtime tarball found."; exit 1
    fi
  else
    info "System python3 version: $ver"
  fi
}

prepare_venv() {
  if [[ -d "$VENV_DIR" && -x "$VENV_DIR/bin/python" ]]; then
    local v
    v=$($VENV_DIR/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' || true)
    if [[ "$v" != "${REQUIRED_MAJOR}.${REQUIRED_MINOR}" ]]; then
      warn "Existing venv uses Python $v; recreating for ${REQUIRED_MAJOR}.${REQUIRED_MINOR}"
      rm -rf "$VENV_DIR"
    else
      info "Existing venv already on ${REQUIRED_MAJOR}.${REQUIRED_MINOR}"; return
    fi
  fi
  info "Creating venv: $VENV_DIR"
  $PY_SYS -m venv "$VENV_DIR"
  info "Upgrading pip"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
}

offline_install() {
  [[ -d "$PACKAGES_DIR" ]] || { err "packages_folder missing: $PACKAGES_DIR"; exit 1; }
  info "Installing offline wheels"
  "$VENV_DIR/bin/python" -m pip install --no-index --find-links="$PACKAGES_DIR" \
    numpy pandas pymodbus pyserial paho-mqtt termcolor python-dateutil tzdata six pytz || {
      err "Offline install failed; verify cp313 wheels exist."; exit 1; }
}

smoke_test() {
  info "Running smoke test"
  "$VENV_DIR/bin/python" - <<'PY'
import sys
print(sys.version)
try:
    import numpy, pandas
    print("numpy", numpy.__version__, "pandas", pandas.__version__)
except Exception as e:
    print("Smoke test failed:", e)
    raise
PY
  ok "Smoke test passed"
}

enable_services() {
  if [[ "$ENABLE_SERVICES" -eq 1 ]]; then
    if [[ -f "${SCRIPT_DIR}/enable_auto_start.sh" ]]; then
      info "Enabling dashboard service using venv interpreter"
      sudo bash "${SCRIPT_DIR}/enable_auto_start.sh" --dashboard
      ok "Service enabled"
    else
      warn "enable_auto_start.sh not found; skipping service setup"
    fi
  fi
}

main() {
  install_runtime_if_needed
  prepare_venv
  offline_install
  smoke_test
  enable_services
  echo
  ok "System Python 3.13 venv setup complete. Run dashboard:"
      echo "  ${VENV_DIR}/bin/python simple_rpi_dashboard.py --run"
}

main "$@"

# If requested, after successful setup launch the GUI using venv python
if [[ "$START_UI" -eq 1 ]]; then
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    info "Launching Simple Meter UI using: ${VENV_DIR}/bin/python"
    exec "${VENV_DIR}/bin/python" simple_meter_ui.py
  else
    err "Venv python not found; cannot launch UI"
    exit 1
  fi
fi
