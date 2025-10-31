#!/usr/bin/env python3
"""
Venv Utilities - Shared Virtual Environment and Pip Management

This module provides utility functions for managing virtual environments
and pip installations that can be used by multiple dashboard scripts.

Functions:
    - check_and_install_system_pip(): Install pip on the system if missing
    - setup_venv_with_pip(): Create venv and ensure pip is available
    - install_packages_in_venv(): Install packages with multiple fallback methods

Author: Shared utility module
Date: 24/07/25
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

    # First, try to see if pip module is available
    success, stdout, stderr = run_command(
        [sys.executable, "-m", "pip", "--version"], check=False)

    if success:
        print("✅ System pip is already available")
        return True

    print("⚠️ System pip not found, attempting to install...")

    # Try different methods to install pip
    methods = [
        # Method 1: Use ensurepip (built into Python 3.4+)
        ([sys.executable, "-m", "ensurepip", "--default-pip"], "ensurepip"),

        # Method 2: Try apt-get on Debian/Ubuntu systems
        (["sudo", "apt-get", "update"], "apt-update"),
        (["sudo", "apt-get", "install", "-y", "python3-pip"], "apt-install-pip"),

        # Method 3: Try yum on RedHat/CentOS systems
        (["sudo", "yum", "install", "-y", "python3-pip"], "yum-install-pip"),

        # Method 4: Download get-pip.py script
        (["curl", "https://bootstrap.pypa.io/get-pip.py",
         "-o", "get-pip.py"], "download-get-pip"),
        ([sys.executable, "get-pip.py"], "install-get-pip"),
    ]

    for i, (cmd, method_name) in enumerate(methods):
        print(f"   Trying method {i+1}: {method_name}...")
        success, stdout, stderr = run_command(cmd, check=False)

        if success:
            print(f"✅ {method_name} successful")

            # After apt/yum install, verify pip is now available
            if method_name in ["apt-install-pip", "yum-install-pip", "install-get-pip", "ensurepip"]:
                success, stdout, stderr = run_command(
                    [sys.executable, "-m", "pip", "--version"], check=False)
                if success:
                    print("✅ System pip is now available")
                    # Clean up get-pip.py if it exists
                    if os.path.exists("get-pip.py"):
                        os.remove("get-pip.py")
                    return True
        else:
            print(f"⚠️ {method_name} failed: {stderr}")

    print("❌ Could not install system pip automatically")
    print("Please install pip manually:")
    print("  Ubuntu/Debian: sudo apt-get install python3-pip")
    print("  CentOS/RHEL: sudo yum install python3-pip")
    print("  Or download get-pip.py and run: python3 get-pip.py")
    return False


def setup_venv_with_pip(venv_dir, force_recreate=False):
    """
    Create virtual environment and ensure pip is available.

    Args:
        venv_dir (Path): Path to virtual environment directory
        force_recreate (bool): If True, remove existing venv and recreate

    Returns:
        tuple: (success, python_exe_path) - success status and python executable path
    """
    venv_path = Path(venv_dir)

    # Remove existing venv if force_recreate is True
    if force_recreate and venv_path.exists():
        print(f"🗑️ Removing existing virtual environment at {venv_path}")
        import shutil
        shutil.rmtree(venv_path)

    # Create venv if it doesn't exist
    if not venv_path.exists():
        print("📦 Creating virtual environment...")
        success, stdout, stderr = run_command(
            [sys.executable, "-m", "venv", str(venv_path)])
        if not success:
            print(f"❌ Failed to create venv: {stderr}")
            print("💡 On some systems you may need to install python3-venv:")
            print("   Ubuntu/Debian: sudo apt-get install python3-venv")
            print("   CentOS/RHEL: sudo yum install python3-venv")
            return False, None
        print("✅ Virtual environment created")
    else:
        print("✅ Virtual environment already exists")

    # Get python executable path
    if os.name == 'nt':  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:  # Linux/macOS
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"

    # If the expected python executable is missing, the venv is corrupted/incomplete -> recreate
    if not python_exe.exists():
        print("⚠️ Virtual environment appears incomplete (missing venv/bin/python). Recreating venv...")
        import shutil
        try:
            shutil.rmtree(venv_path)
        except Exception as e:
            print(f"❌ Failed to remove broken venv: {e}")
            return False, None
        print("📦 Creating virtual environment...")
        success, stdout, stderr = run_command([sys.executable, "-m", "venv", str(venv_path)])
        if not success:
            print(f"❌ Failed to create venv: {stderr}")
            print("💡 On some systems you may need to install python3-venv:")
            print("   Ubuntu/Debian: sudo apt-get install python3-venv")
            print("   CentOS/RHEL: sudo yum install python3-venv")
            return False, None
        # Recompute paths after recreation
        if os.name == 'nt':
            python_exe = venv_path / "Scripts" / "python.exe"
            pip_exe = venv_path / "Scripts" / "pip.exe"
        else:
            python_exe = venv_path / "bin" / "python"
            pip_exe = venv_path / "bin" / "pip"

    # Comprehensive pip check in venv
    print("🔍 Checking pip in virtual environment...")

    # Method 1: Check if pip executable exists
    pip_available = pip_exe.exists()

    # Method 2: Try to run pip via python -m pip (more reliable)
    if not pip_available:
        success, stdout, stderr = run_command(
            [str(python_exe), "-m", "pip", "--version"], check=False)
        pip_available = success

    if not pip_available:
        print("📦 Installing pip in virtual environment...")

        # Try multiple methods to install pip in venv
        pip_install_methods = [
            # Method 1: Use ensurepip (recommended)
            ([str(python_exe), "-m", "ensurepip", "--upgrade"], "ensurepip --upgrade"),

            # Method 2: Use ensurepip without upgrade flag
            ([str(python_exe), "-m", "ensurepip"], "ensurepip"),

            # Method 3: Use system pip to install into venv site-packages
            ([sys.executable, "-m", "pip", "install", "--target",
             str(venv_path / "lib"), "pip"], "system pip to venv"),

            # Method 4: Copy system pip to venv
            ([sys.executable, "-m", "pip", "install", "--force-reinstall",
             "--target", str(venv_path), "pip"], "force install pip to venv"),
        ]

        for cmd, method_name in pip_install_methods:
            print(f"   Trying: {method_name}...")
            success, stdout, stderr = run_command(cmd, check=False)

            if success:
                print(f"✅ {method_name} successful")
                # Verify pip is now working
                success, stdout, stderr = run_command(
                    [str(python_exe), "-m", "pip", "--version"], check=False)
                if success:
                    print("✅ pip is now available in venv")
                    break
                else:
                    print(
                        f"⚠️ pip installation succeeded but still not working: {stderr}")
            else:
                print(f"⚠️ {method_name} failed: {stderr}")
        else:
            print("❌ Could not install pip in virtual environment")
            print("💡 This might be due to missing python3-venv or python3-dev packages")
            print("   Try: sudo apt-get install python3-venv python3-dev")
            return False, None
    else:
        print("✅ pip is available in virtual environment")

    # Upgrade pip in venv (use python -m pip for reliability)
    print("📦 Upgrading pip in virtual environment...")
    success, stdout, stderr = run_command(
        [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"])
    if not success:
        print(f"⚠️ Pip upgrade failed: {stderr}")
        print("Continuing with existing pip version...")

    # Final verification that pip is working before returning
    print("🔍 Final pip verification in venv...")
    success, stdout, stderr = run_command(
        [str(python_exe), "-m", "pip", "--version"], check=False)
    if not success:
        print("❌ pip is still not working in virtual environment")
        print(f"Error: {stderr}")
        print("💡 Manual fix required. Try:")
        print(f"   cd {venv_path.parent}")
        print(f"   rm -rf {venv_path.name}")
        print("   sudo apt-get install python3-venv python3-dev python3-pip")
        print(f"   python3 -m venv {venv_path.name}")
        print(f"   source {venv_path.name}/bin/activate")
        print("   pip install --upgrade pip")
        return False, None
    else:
        print(f"✅ pip working in venv: {stdout.strip()}")

    return True, python_exe


def download_packages_for_offline_use(packages, download_dir="offline_packages"):
    """
    Download packages and their dependencies for offline installation.

    This should be run on a machine with internet connectivity to prepare
    packages for offline deployment.

    Args:
        packages (list): List of package specifications to download
        download_dir (str): Directory to store downloaded packages

    Returns:
        bool: True if all packages downloaded successfully
    """
    download_path = Path(download_dir)
    download_path.mkdir(exist_ok=True)

    print(
        f"📥 Downloading packages for offline use to: {download_path.absolute()}")

    # Download packages with all dependencies
    success, stdout, stderr = run_command([
        sys.executable, "-m", "pip", "download",
        "--dest", str(download_path),
        "--no-deps"  # We'll handle dependencies separately
    ] + packages, check=False)

    if not success:
        print(
            f"⚠️ Initial download failed, trying with dependencies: {stderr}")

        # Try downloading with dependencies
        success, stdout, stderr = run_command([
            sys.executable, "-m", "pip", "download",
            "--dest", str(download_path)
        ] + packages, check=False)

        if not success:
            print(f"❌ Package download failed: {stderr}")
            return False

    print("✅ Packages downloaded successfully")

    # List downloaded files
    downloaded_files = list(download_path.glob("*.whl")) + \
        list(download_path.glob("*.tar.gz"))
    print(f"📦 Downloaded {len(downloaded_files)} package files:")
    for file in downloaded_files:
        print(f"   - {file.name}")

    # Create requirements file for offline installation
    requirements_file = download_path / "offline_requirements.txt"
    with open(requirements_file, 'w') as f:
        for package in packages:
            f.write(f"{package}\n")

    print(f"📝 Created requirements file: {requirements_file}")

    # Create installation script
    install_script = download_path / "install_offline.py"
    script_content = f'''#!/usr/bin/env python3
"""
Offline Package Installation Script

This script installs packages from the offline_packages directory
without requiring internet connectivity.

Usage:
    python install_offline.py [venv_python_path]
"""

import sys
import subprocess
from pathlib import Path

def install_offline_packages(python_exe=None):
    if python_exe is None:
        python_exe = sys.executable
    
    offline_dir = Path(__file__).parent
    package_files = list(offline_dir.glob("*.whl")) + list(offline_dir.glob("*.tar.gz"))
    
    print(f"🔧 Installing {{len(package_files)}} packages offline...")
    
    for package_file in package_files:
        print(f"   Installing {{package_file.name}}...")
        result = subprocess.run([
            str(python_exe), "-m", "pip", "install", 
            "--no-index", "--find-links", str(offline_dir),
            str(package_file)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ {{package_file.name}} installed")
        else:
            print(f"   ❌ {{package_file.name}} failed: {{result.stderr}}")
    
    print("✅ Offline installation complete")

if __name__ == "__main__":
    python_path = sys.argv[1] if len(sys.argv) > 1 else None
    install_offline_packages(python_path)
'''

    with open(install_script, 'w') as f:
        f.write(script_content)

    print(f"🐍 Created installation script: {install_script}")

    return True


def install_packages_in_venv(python_exe, packages, offline_dir=None):
    """
    Install packages in virtual environment with online/offline support.

    Args:
        python_exe (Path): Path to python executable in venv
        packages (list): List of package specifications to install
        offline_dir (str/Path): Directory containing offline packages (optional)

    Returns:
        bool: True if all packages installed successfully
    """
    print("📦 Installing dependencies in virtual environment...")

    # Check if offline installation is requested
    if offline_dir:
        return install_packages_offline(python_exe, packages, offline_dir)

    # Check if offline packages directory exists locally
    local_offline_dir = Path("offline_packages")
    if local_offline_dir.exists() and list(local_offline_dir.glob("*.whl")):
        print(f"🔍 Found offline packages directory: {local_offline_dir}")
        user_choice = input("Use offline packages? (y/n): ").lower().strip()
        if user_choice in ['y', 'yes']:
            return install_packages_offline(python_exe, packages, local_offline_dir)

    # Online installation
    return install_packages_online(python_exe, packages)


def install_packages_offline(python_exe, packages, offline_dir):
    """
    Install packages from offline directory without internet.

    Args:
        python_exe (Path): Path to python executable in venv
        packages (list): List of package specifications to install
        offline_dir (str/Path): Directory containing offline packages

    Returns:
        bool: True if all packages installed successfully
    """
    offline_path = Path(offline_dir)

    if not offline_path.exists():
        print(f"❌ Offline packages directory not found: {offline_path}")
        return False

    print(f"📦 Installing packages offline from: {offline_path.absolute()}")

    # Get all wheel and tar.gz files
    package_files = list(offline_path.glob("*.whl")) + \
        list(offline_path.glob("*.tar.gz"))

    if not package_files:
        print("❌ No package files found in offline directory")
        return False

    print(f"🔍 Found {len(package_files)} package files")

    # Install packages using --no-index and --find-links
    for package in packages:
        print(f"   Installing {package} offline...")

        # Try to install from local files only
        success, stdout, stderr = run_command([
            str(python_exe), "-m", "pip", "install",
            "--no-index", "--find-links", str(offline_path),
            package
        ], check=False)

        if not success:
            print(f"⚠️ Direct offline install failed for {package}: {stderr}")

            # Try installing specific wheel files that match the package name
            package_name = package.split('==')[0].split('>=')[0].split('<=')[0]
            matching_files = [
                f for f in package_files if package_name.lower() in f.name.lower()]

            if matching_files:
                print(
                    f"   Trying to install specific files for {package_name}...")
                for file in matching_files:
                    success, stdout, stderr = run_command([
                        str(python_exe), "-m", "pip", "install",
                        "--no-index", "--find-links", str(offline_path),
                        str(file)
                    ], check=False)

                    if success:
                        print(f"✅ {file.name} installed successfully")
                        break
                    else:
                        print(f"⚠️ {file.name} failed: {stderr}")
                else:
                    print(f"❌ Failed to install {package} from offline files")
                    return False
            else:
                print(f"❌ No matching files found for {package}")
                return False
        else:
            print(f"✅ {package} installed successfully offline")

    return True


def install_packages_online(python_exe, packages):
    """
    Install packages online with fallback methods.

    Args:
        python_exe (Path): Path to python executable in venv
        packages (list): List of package specifications to install

    Returns:
        bool: True if all packages installed successfully
    """
    print("🌐 Installing packages online...")

    for package in packages:
        print(f"   Installing {package}...")

        # Use python -m pip instead of pip directly for better reliability
        success, stdout, stderr = run_command(
            [str(python_exe), "-m", "pip", "install", package])

        if not success:
            print(f"❌ Failed to install {package}: {stderr}")

            # Try alternative installation methods
            fallback_methods = [
                # Method 1: Try with --user flag
                ([str(python_exe), "-m", "pip", "install",
                 "--user", package], "--user flag"),

                # Method 2: Try with --no-cache-dir
                ([str(python_exe), "-m", "pip", "install",
                 "--no-cache-dir", package], "--no-cache-dir"),

                # Method 3: Try upgrading first
                ([str(python_exe), "-m", "pip", "install",
                 "--upgrade", package], "--upgrade"),
            ]

            package_installed = False
            for cmd, method_name in fallback_methods:
                print(f"   Retrying {package} with {method_name}...")
                success, stdout, stderr = run_command(cmd, check=False)

                if success:
                    print(f"✅ {package} installed with {method_name}")
                    package_installed = True
                    break
                else:
                    print(f"⚠️ {method_name} failed: {stderr}")

            if not package_installed:
                print(f"❌ Failed to install {package} with all methods")
                return False
        else:
            print(f"✅ {package} installed successfully")

    return True


def setup_complete_venv_environment(venv_dir, packages, force_recreate=False, offline_dir=None):
    """
    Complete venv setup: create venv, install pip, install packages.

    Args:
        venv_dir (Path): Path to virtual environment directory
        packages (list): List of packages to install
        force_recreate (bool): If True, recreate venv from scratch
        offline_dir (str/Path): Directory containing offline packages (optional)

    Returns:
        tuple: (success, python_exe_path)
    """
    print("🔧 Setting up complete virtual environment...")

    # Step 1: Ensure system pip is available (skip if offline)
    if not offline_dir:
        if not check_and_install_system_pip():
            return False, None
    else:
        print("🔍 Offline mode - skipping system pip check")

    # Step 2: Create venv with pip
    success, python_exe = setup_venv_with_pip(venv_dir, force_recreate)
    if not success:
        return False, None

    # Step 3: Install packages (online or offline)
    if packages:
        success = install_packages_in_venv(python_exe, packages, offline_dir)
        if not success:
            return False, None

    print("✅ Complete virtual environment setup finished")
    return True, python_exe


if __name__ == "__main__":
    # Test the module
    print("🧪 Testing venv utilities...")

    test_venv_dir = Path("test_venv")
    test_packages = ["requests"]

    success, python_exe = setup_complete_venv_environment(
        test_venv_dir,
        test_packages,
        force_recreate=False
    )

    if success:
        print(f"✅ Test successful! Python executable: {python_exe}")
    else:
        print("❌ Test failed!")

    # Cleanup test venv
    import shutil
    if test_venv_dir.exists():
        shutil.rmtree(test_venv_dir)
        print("🗑️ Test venv cleaned up")
