"""'Start with Windows' toggle via the current-user Run registry key.
No-ops safely on non-Windows platforms."""

import sys

APP_NAME = "RandomPaste"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported():
    return sys.platform == "win32"


def set_enabled(enabled, exe_path):
    if not is_supported():
        return
    import winreg
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, '"{}"'.format(exe_path))
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def is_enabled():
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
