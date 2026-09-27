"""Clipboard helpers. Uses pywin32 for reliable Unicode/emoji text on
Windows (CF_UNICODETEXT), falling back to pyperclip if pywin32 isn't
available or we're not on Windows (e.g. while developing the UI)."""

import sys

_HAVE_WIN32 = False
if sys.platform == "win32":
    try:
        import win32clipboard
        import win32con
        _HAVE_WIN32 = True
    except ImportError:
        _HAVE_WIN32 = False

if not _HAVE_WIN32:
    try:
        import pyperclip
    except ImportError:
        pyperclip = None


def get_text():
    """Returns the current clipboard text, or None if unavailable/non-text."""
    if _HAVE_WIN32:
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return None
    if pyperclip is None:
        return None
    try:
        return pyperclip.paste()
    except Exception:
        return None


def set_text(text):
    """Sets the clipboard text. Returns True on success."""
    if text is None:
        return False
    if _HAVE_WIN32:
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            return True
        except Exception:
            return False
    if pyperclip is None:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False
