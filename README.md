# Random Paste

Make a list -> turn on Paste Cycle -> press Ctrl+V -> get a random item.

A tiny Windows background utility with a dark, compact Qt interface. When
**Paste Cycle** is on, pressing **Ctrl+V** (or a custom hotkey you set)
pastes a random item from your list instead of your real clipboard, then
restores your real clipboard shortly after. When Paste Cycle is off, Ctrl+V
works exactly as normal.

Click **+ Add Items** to paste in a whole batch at once — one item per line
— instead of adding them one at a time. Drag items in the list to reorder
them.

## Running it

This was written and packaged in a Linux sandbox, so the `.exe` couldn't be
compiled here — PyInstaller has to run on the same OS it's building for.
To get a real `RandomPaste.exe`, run the build step below on a Windows
machine. Everything else (the actual app code) is complete and ready to use.

**From source (fastest way to try it), on Windows:**

```
pip install -r requirements.txt
python main.py
```

**To build a standalone .exe, on Windows:**

```
build.bat
```

This installs dependencies and runs PyInstaller, producing
`dist\RandomPaste.exe` — a single file you can copy anywhere, pin to your
taskbar, or set to launch at startup from Settings.

## Files

- `main.py` — the window, item list, settings dialog, and system tray (Qt/PySide6)
- `hotkey_manager.py` — global Ctrl+V interception and item selection
- `clipboard.py` — reliable Unicode/emoji-safe clipboard read/write
- `autostart.py` — "start with Windows" registry toggle
- `storage.py` — saves your list and settings to
  `%APPDATA%\RandomPaste\config.json`

## Notes and known limitations

- **Admin rights:** on some systems, globally hooking a key combo (via the
  `keyboard` library) needs the app to run as Administrator, especially to
  intercept keystrokes going into apps that are themselves elevated (e.g.
  Task Manager, some installers). If Ctrl+V interception silently doesn't
  fire in a specific app, try running RandomPaste.exe as admin.
- **Selection modes:** "Completely Random" picks freely each time,
  "Avoid Repeating" won't pick the same item twice in a row, "Sequential
  Cycle" walks through the list in order. "Allow duplicate selections" is a
  separate switch — turning it off also avoids immediate repeats even in
  Completely Random mode.
- **Empty list:** if your list is empty, Ctrl+V just pastes your real
  clipboard contents, same as if Paste Cycle were off.
- **Clipboard restore:** the app waits ~0.4s after simulating the paste
  before putting your original clipboard contents back, to give the target
  app time to read it. Extremely slow or unusual apps could occasionally
  see a slightly delayed restore, but your original contents are never
  discarded.
- **Reordering:** drag any item in the list to a new position.
