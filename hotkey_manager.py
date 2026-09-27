"""Global hotkey (default Ctrl+V) interception.

When Paste Cycle is ON, pressing the hotkey:
  1. remembers the user's real clipboard contents
  2. picks an item from the list (per the selection mode)
  3. puts that item on the clipboard
  4. briefly un-registers the hotkey and sends the real paste combo
     through to whatever app is focused, then re-registers
  5. restores the user's original clipboard shortly after, once the
     target app has had a chance to read the pasted text

When Paste Cycle is OFF, the hotkey is never registered, so Ctrl+V
(or whatever combo is configured) behaves exactly as normal.

Runs on a background thread owned by the `keyboard` library — callers
must not touch Tk widgets directly from callbacks passed in here.
"""

import random
import threading
import time

import keyboard

import clipboard

RESTORE_DELAY_SECONDS = 0.4


class HotkeyManager:
    def __init__(self, get_items, get_settings, on_paste=None):
        """
        get_items: callable -> list[str], current paste list (called fresh
            each time, so edits made in the UI take effect immediately)
        get_settings: callable -> dict with mode/allow_duplicates/case_sensitive
        on_paste: optional callback(item) fired after each cycled paste;
            invoked from the hook thread, so marshal to the UI thread yourself
        """
        self._get_items = get_items
        self._get_settings = get_settings
        self._on_paste = on_paste
        self._hotkey_handle = None
        self._current_hotkey = None
        self._sequential_index = 0
        self._last_item = None
        self._lock = threading.Lock()

    # ---- public API ----

    def set_hotkey(self, hotkey):
        """(Re)registers the intercepted hotkey. Pass None/'' to disable."""
        self._unregister()
        if not hotkey:
            return
        self._current_hotkey = hotkey
        self._register()

    def stop(self):
        self._unregister()
        self._current_hotkey = None

    def reset_sequence(self):
        with self._lock:
            self._sequential_index = 0
            self._last_item = None

    # ---- internals ----

    def _register(self):
        if not self._current_hotkey:
            return
        try:
            self._hotkey_handle = keyboard.add_hotkey(
                self._current_hotkey,
                self._on_hotkey,
                suppress=True,
                trigger_on_release=False,
            )
        except Exception:
            self._hotkey_handle = None

    def _unregister(self):
        if self._hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_handle)
            except (KeyError, ValueError):
                pass
        self._hotkey_handle = None

    def _normalize(self, text, case_sensitive):
        return text if case_sensitive else text.lower()

    def _pick_item(self, items, settings):
        if not items:
            return None
        mode = settings.get("mode", "random")
        allow_dup = settings.get("allow_duplicates", True)
        case_sensitive = settings.get("case_sensitive", True)

        if mode == "sequential":
            idx = self._sequential_index % len(items)
            self._sequential_index += 1
            choice = items[idx]
            self._last_item = choice
            return choice

        avoid_repeat = mode == "avoid_repeat" or not allow_dup
        if avoid_repeat and len(items) > 1 and self._last_item is not None:
            last_norm = self._normalize(self._last_item, case_sensitive)
            pool = [i for i in items if self._normalize(i, case_sensitive) != last_norm]
            choice = random.choice(pool) if pool else random.choice(items)
        else:
            choice = random.choice(items)

        self._last_item = choice
        return choice

    def _on_hotkey(self):
        with self._lock:
            items = list(self._get_items())
            settings = dict(self._get_settings())
            item = self._pick_item(items, settings)

        if not item:
            # Empty list: fall through to a normal paste of whatever is
            # already on the clipboard.
            self._simulate_real_paste()
            return

        original = clipboard.get_text()
        clipboard.set_text(item)
        self._simulate_real_paste()

        if self._on_paste:
            try:
                self._on_paste(item)
            except Exception:
                pass

        def restore():
            time.sleep(RESTORE_DELAY_SECONDS)
            if original is not None:
                clipboard.set_text(original)

        threading.Thread(target=restore, daemon=True).start()

    def _simulate_real_paste(self):
        # Un-register first so our own synthesized key-down/up doesn't
        # re-trigger this same handler (the hook sees synthesized events
        # too), then restore the hotkey right after.
        hotkey = self._current_hotkey
        self._unregister()
        try:
            keyboard.send(hotkey or "ctrl+v")
        except Exception:
            pass
        finally:
            self._current_hotkey = hotkey
            self._register()
