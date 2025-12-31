#!/usr/bin/env python3
 

#!/usr/bin/env python3
"""
Venv Utilities - Shared Virtual Environment and Pip Management

This module provides utility functions for managing virtual environments
and pip installations that can be used by multiple dashboard scripts.

Functions:
    - check_and_install_system_pip(): Install pip on the system if missing
    - setup_venv_with_pip(): Create venv (optionally with a preferred interpreter) and ensure pip
    - install_packages_in_venv(): Install packages with offline/online fallbacks

Author: Shared utility module
Date: 24/07/25 (updated for Python 3.13 support)
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd, check=True, shell=False):
    """Run a system command and return success, stdout, stderr."""
    try:
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()
        result = subprocess.run(cmd, capture_output=True,
                                text=True, check=check, shell=shell)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def check_and_install_system_pip():
    """Check if pip is available on system and install it if missing."""
    print("🔍 Checking for system pip...")

    success, stdout, stderr = run_command([sys.executable, "-m", "pip", "--version"], check=False)
    if success:
        print("✅ System pip is already available")
        return True

    print("⚠️ System pip not found, attempting to install...")

    methods = [
        ([sys.executable, "-m", "ensurepip", "--default-pip"], "ensurepip"),
        (["sudo", "apt-get", "update"], "apt-update"),
        (["sudo", "apt-get", "install", "-y", "python3-pip"], "apt-install-pip"),
        (["sudo", "yum", "install", "-y", "python3-pip"], "yum-install-pip"),
        (["curl", "https://bootstrap.pypa.io/get-pip.py", "-o", "get-pip.py"], "download-get-pip"),
        ([sys.executable, "get-pip.py"], "install-get-pip"),
    ]

    for i, (cmd, method_name) in enumerate(methods):
        print(f"   Trying method {i+1}: {method_name}...")
        success, stdout, stderr = run_command(cmd, check=False)
        if success:
            print(f"✅ {method_name} successful")
            if method_name in ["apt-install-pip", "yum-install-pip", "install-get-pip", "ensurepip"]:
                success, stdout, stderr = run_command([sys.executable, "-m", "pip", "--version"], check=False)
                if success:
                    print("✅ System pip is now available")
                    if os.path.exists("get-pip.py"):
                        os.remove("get-pip.py")
                    return True
        else:
            print(f"⚠️ {method_name} failed: {stderr}")

    print("❌ Could not install system pip automatically")
    print("Please install pip manually (apt/yum or get-pip.py)")
    return False


def setup_venv_with_pip(venv_dir, force_recreate=False, preferred_python=None):
    """
    Create virtual environment and ensure pip is available.

    Args:
        venv_dir (Path|str): Path to virtual environment directory
        force_recreate (bool): If True, remove existing venv and recreate
        preferred_python (str|None): Absolute path to interpreter to create the venv with

    Returns:
        tuple: (success, python_exe_path)
    """
    venv_path = Path(venv_dir)

    # Remove existing venv if force_recreate is True
    if force_recreate and venv_path.exists():
        print(f"🗑️ Removing existing virtual environment at {venv_path}")
        import shutil
        shutil.rmtree(venv_path)

    # Choose interpreter
    interpreter = preferred_python if preferred_python and Path(preferred_python).exists() else sys.executable

    # Create venv if it doesn't exist
    if not venv_path.exists():
        print("📦 Creating virtual environment...")
        success, stdout, stderr = run_command([interpreter, "-m", "venv", str(venv_path)])
        if not success:
            print(f"❌ Failed to create venv with {interpreter}: {stderr}")
            print("💡 Install python3-venv or try another interpreter path.")
            return False, None
        print("✅ Virtual environment created")
    else:
        print("✅ Virtual environment already exists")

    # Compute python/pip paths
    if os.name == 'nt':
        python_exe = venv_path / "Scripts" / "python.exe"
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"

    # If missing, venv is broken -> recreate once more using chosen interpreter
    if not python_exe.exists():
        print("⚠️ Missing venv/bin/python; recreating venv...")
        import shutil
        try:
            shutil.rmtree(venv_path)
        except Exception as e:
            print(f"❌ Failed to remove broken venv: {e}")
            return False, None
        print("📦 Creating virtual environment...")
        success, stdout, stderr = run_command([interpreter, "-m", "venv", str(venv_path)])
        if not success:
            print(f"❌ Failed to create venv: {stderr}")
            return False, None
        python_exe = venv_path / ("Scripts/python.exe" if os.name == 'nt' else "bin/python")
        pip_exe = venv_path / ("Scripts/pip.exe" if os.name == 'nt' else "bin/pip")

    # Check pip availability in venv
    print("🔍 Checking pip in virtual environment...")
    pip_available = pip_exe.exists()
    if not pip_available:
        success, stdout, stderr = run_command([str(python_exe), "-m", "pip", "--version"], check=False)
        pip_available = success

    if not pip_available:
        print("📦 Installing pip in virtual environment...")
        for cmd, label in [
            ([str(python_exe), "-m", "ensurepip", "--upgrade"], "ensurepip --upgrade"),
            ([str(python_exe), "-m", "ensurepip"], "ensurepip"),
        ]:
            print(f"   Trying: {label}...")
            success, stdout, stderr = run_command(cmd, check=False)
            if success:
                success, stdout, stderr = run_command([str(python_exe), "-m", "pip", "--version"], check=False)
                if success:
                    print("✅ pip is now available in venv")
                    break
        else:
            print("❌ Could not install pip in virtual environment")
            return False, None
    else:
        print("✅ pip is available in virtual environment")

    # Upgrade pip
    print("📦 Upgrading pip in virtual environment...")
    success, stdout, stderr = run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], check=False)
    if not success:
        print(f"⚠️ Pip upgrade failed: {stderr}")

    # Final pip verification
    print("🔍 Final pip verification in venv...")
    success, stdout, stderr = run_command([str(python_exe), "-m", "pip", "--version"], check=False)
    if not success:
        print("❌ pip is not working in venv: ", stderr)
        return False, None
    else:
        print(f"✅ pip working in venv: {stdout.strip()}")

    return True, python_exe


def install_packages_offline(python_exe, packages, offline_dir):
    offline_path = Path(offline_dir)
    if not offline_path.exists():
        print(f"❌ Offline packages directory not found: {offline_path}")
        return False

    print(f"📦 Installing packages offline from: {offline_path.absolute()}")
    package_files = list(offline_path.glob("*.whl")) + list(offline_path.glob("*.tar.gz"))
    if not package_files:
        print("❌ No package files found in offline directory")
        return False

    print(f"🔍 Found {len(package_files)} package files")
    for package in packages:
        print(f"   Installing {package} offline...")
        success, stdout, stderr = run_command([
            str(python_exe), "-m", "pip", "install",
            "--no-index", "--find-links", str(offline_path),
            package
        ], check=False)
        if not success:
            print(f"⚠️ Direct offline install failed for {package}: {stderr}")
            pkg = package.split('==')[0].split('>=')[0].split('<=')[0]
            matches = [f for f in package_files if pkg.lower() in f.name.lower()]
            for mf in matches:
                success, stdout, stderr = run_command([
                    str(python_exe), "-m", "pip", "install",
                    "--no-index", "--find-links", str(offline_path),
                    str(mf)
                ], check=False)
                if success:
                    print(f"✅ {mf.name} installed successfully")
                    break
            else:
                print(f"❌ Failed to install {package} from offline files")
                return False
        else:
            print(f"✅ {package} installed successfully offline")
    return True


def install_packages_online(python_exe, packages):
    print("🌐 Installing packages online...")
    for package in packages:
        print(f"   Installing {package}...")
        success, stdout, stderr = run_command([str(python_exe), "-m", "pip", "install", package], check=False)
        if not success:
            print(f"❌ Failed to install {package}: {stderr}")
            for cmd, label in [
                ([str(python_exe), "-m", "pip", "install", "--user", package], "--user"),
                ([str(python_exe), "-m", "pip", "install", "--no-cache-dir", package], "--no-cache-dir"),
                ([str(python_exe), "-m", "pip", "install", "--upgrade", package], "--upgrade"),
            ]:
                print(f"   Retrying with {label}...")
                success, stdout, stderr = run_command(cmd, check=False)
                if success:
                    print(f"✅ {package} installed with {label}")
                    break
            else:
                print(f"❌ Failed to install {package} with all methods")
                return False
        else:
            print(f"✅ {package} installed successfully")
    return True


def install_packages_in_venv(python_exe, packages, offline_dir=None):
    print("📦 Installing dependencies in virtual environment...")
    if offline_dir:
        return install_packages_offline(python_exe, packages, offline_dir)
    local_offline_dir = Path("offline_packages")
    if local_offline_dir.exists() and list(local_offline_dir.glob("*.whl")):
        choice = 'y'
        if choice.lower().startswith('y'):
            return install_packages_offline(python_exe, packages, local_offline_dir)
    return install_packages_online(python_exe, packages)


def setup_complete_venv_environment(venv_dir, packages, force_recreate=False, offline_dir=None):
    print("🔧 Setting up complete virtual environment...")
    if not offline_dir:
        if not check_and_install_system_pip():
            return False, None
    success, python_exe = setup_venv_with_pip(venv_dir, force_recreate)
    if not success:
        return False, None
    if packages:
        success = install_packages_in_venv(python_exe, packages, offline_dir)
        if not success:
            return False, None
    print("✅ Complete virtual environment setup finished")
    return True, python_exe


if __name__ == "__main__":
    print("🧪 Testing venv utilities...")
    test_venv_dir = Path("test_venv")
    test_packages = ["requests"]
    success, python_exe = setup_complete_venv_environment(test_venv_dir, test_packages, force_recreate=False)
    if success:
        print(f"✅ Test successful! Python executable: {python_exe}")
    else:
        print("❌ Test failed!")
    import shutil
    if test_venv_dir.exists():
        shutil.rmtree(test_venv_dir)
        print("🗑️ Test venv cleaned up")
