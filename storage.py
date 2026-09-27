"""Persistence for Random Paste: settings + paste list, stored as JSON in
%APPDATA%\\RandomPaste\\config.json (falls back to a local config dir on
other platforms, useful for testing the UI on non-Windows machines)."""

import json
import os
import sys

APP_NAME = "RandomPaste"


def get_config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


CONFIG_PATH = os.path.join(get_config_dir(), "config.json")

DEFAULTS = {
    "items": ["hello", "test message", "lorem ipsum", "random text"],
    "paste_cycle_enabled": False,
    "mode": "random",            # random | avoid_repeat | sequential
    "allow_duplicates": True,
    "case_sensitive": True,
    "intercept_enabled": True,   # global Ctrl+V interception master switch
    "hotkey": "ctrl+v",
    "start_with_windows": False,
    "minimize_to_tray": True,
    "window_geometry": None,
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(DEFAULTS)
            merged.update(data)
            if not isinstance(merged.get("items"), list):
                merged["items"] = list(DEFAULTS["items"])
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def save_config(config):
    try:
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, CONFIG_PATH)
    except OSError:
        pass
