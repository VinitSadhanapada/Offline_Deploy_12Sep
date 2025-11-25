Offline wheels go here (.whl files only).

How to prepare on a connected machine (option A - on the Raspberry Pi):
- Temporarily connect the Pi to the internet.
- Ensure pip is configured for piwheels (our setup script does this automatically).
- Download wheels for later use:

  pip download --only-binary=:all: -r ../requirements.txt -d ./

How to prepare on a connected x86 machine (option B - cross-download):
- Use pip download with explicit platform and Python/ABI, then copy files to this folder:

  # 32-bit Raspberry Pi OS (armv7l, Python 3.11)
  pip download --only-binary=:all: \
    --platform linux_armv7l --python-version 311 --abi cp311 \
    -r ../requirements.txt -d ./

  # 64-bit Raspberry Pi OS (aarch64, Python 3.11)
  pip download --only-binary=:all: \
    --platform manylinux2014_aarch64 --python-version 311 --abi cp311 \
    -r ../requirements.txt -d ./

Notes:
- Ensure the Python version on the Pi matches the --python-version above (311 for Python 3.11).
- For numpy/pandas, prefer manylinux wheels. If no wheel exists for your combo, build on a Pi once and reuse.
- After populating this folder, you can run the setup script fully offline.
