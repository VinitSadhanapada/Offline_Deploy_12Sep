README: Enable permissions for SimpleMeterUI (one-time)

Purpose:
- Run this once to allow the `SimpleMeterUI_Admin.desktop` launcher to be double-clicked
  and to let the script it calls execute.

One-line command to run now (single one-time action):
chmod +x "$HOME/Desktop/SimpleMeterUI_Admin.desktop" "$HOME/Desktop/offline-setup-12Sep/one_click_system_py313.sh"

How to verify:
ls -l "$HOME/Desktop/SimpleMeterUI_Admin.desktop" "$HOME/Desktop/offline-setup-12Sep/one_click_system_py313.sh"

You should see executable bits for the owner (e.g. -rwxr-xr-x).

Notes:
- This only fixes permissions. If the script needs missing packages (e.g., Python 3.13), you must install them separately.
- If either file is not in the paths above, update the paths in the chmod command accordingly.
