"""Random Paste — a tiny background utility.

Make a list -> turn on Paste Cycle -> press Ctrl+V -> get a random item.
"""

import os
import sys

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QSystemTrayIcon,
    QMenu,
)

import storage
import autostart
from hotkey_manager import HotkeyManager

DARK_QSS = """
QWidget {
    background-color: #1e1e1e;
    color: #d7d7d7;
    font-family: "Segoe UI", "Cantarell", sans-serif;
    font-size: 10pt;
}
QLabel#title { font-size: 11pt; font-weight: 600; color: #ffffff; }
QLabel#muted { color: #8a8a8a; font-size: 9pt; }
QLabel#hint { color: #8a8a8a; font-size: 9pt; }
QFrame#sep { background-color: #333333; max-height: 1px; min-height: 1px; }

QListWidget {
    background-color: #252526;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 3px;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
    margin: 1px 0;
}
QListWidget::item:selected {
    background-color: #2f5f8f;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background-color: #2c2c2d;
}

QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #444444;
    border-radius: 7px;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #383838; border-color: #4d4d4d; }
QPushButton:pressed { background-color: #262626; }
QPushButton:disabled { color: #666666; background-color: #262626; }

QPushButton#smallBtn { padding: 4px 9px; font-size: 9pt; }

QPushButton#toggleOn {
    background-color: #2e7d32;
    border: 1px solid #3f9142;
    color: #ffffff;
    font-weight: 600;
    font-size: 11pt;
    padding: 10px;
}
QPushButton#toggleOn:hover { background-color: #34903a; }

QPushButton#toggleOff {
    background-color: #2d2d2d;
    border: 1px solid #444444;
    color: #d7d7d7;
    font-weight: 600;
    font-size: 11pt;
    padding: 10px;
}
QPushButton#toggleOff:hover { background-color: #383838; }

QLineEdit, QPlainTextEdit {
    background-color: #262626;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #2f5f8f;
}
QLineEdit:focus, QPlainTextEdit:focus { border-color: #5a92c9; }

QCheckBox, QRadioButton { spacing: 8px; padding: 2px 0; }
QCheckBox::indicator, QRadioButton::indicator { width: 15px; height: 15px; }

QDialog { background-color: #1e1e1e; }

QScrollBar:vertical { background: #1e1e1e; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: #454545; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #545454; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

MODES = [
    ("Completely Random", "random"),
    ("Avoid Repeating", "avoid_repeat"),
    ("Sequential Cycle", "sequential"),
]


def make_app_icon(enabled):
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color = QColor("#2e7d32") if enabled else QColor("#5a5a5a")
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, size - 8, size - 8, 12, 12)
    p.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 20, QFont.Bold)
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignCenter, "RP")
    p.end()
    return QIcon(pm)


class PasteBridge(QObject):
    """Lets the hotkey hook thread (which must not touch Qt widgets
    directly) safely notify the UI thread."""

    pasted = Signal(str)


class BulkAddDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Items")
        self.setMinimumSize(340, 260)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("One item per line. Multi-line entries can be split later with Edit."))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("hello\ntest message\nlorem ipsum\n...")
        layout.addWidget(self.text)
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Add")
        save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.text.setFocus()

    def items(self):
        raw = self.text.toPlainText()
        return [line.strip() for line in raw.split("\n") if line.strip()]


class EditItemDialog(QDialog):
    def __init__(self, current_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit item")
        self.setMinimumSize(300, 180)
        layout = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setPlainText(current_text)
        layout.addWidget(self.text)
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self.text.setFocus()
        cursor = self.text.textCursor()
        cursor.movePosition(cursor.End)
        self.text.setTextCursor(cursor)

    def value(self):
        return self.text.toPlainText()


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumSize(300, 380)
        layout = QVBoxLayout(self)

        layout.addWidget(self._label("Selection mode", bold=True))
        self.mode_group = QButtonGroup(self)
        for label, value in MODES:
            rb = QRadioButton(label)
            rb.setProperty("mode_value", value)
            if config.get("mode", "random") == value:
                rb.setChecked(True)
            self.mode_group.addButton(rb)
            layout.addWidget(rb)

        layout.addWidget(self._sep())

        self.allow_dup_cb = QCheckBox("Allow duplicate selections")
        self.allow_dup_cb.setChecked(config.get("allow_duplicates", True))
        layout.addWidget(self.allow_dup_cb)

        self.case_cb = QCheckBox("Case-sensitive")
        self.case_cb.setChecked(config.get("case_sensitive", True))
        layout.addWidget(self.case_cb)

        self.intercept_cb = QCheckBox("Enable global Ctrl+V interception")
        self.intercept_cb.setChecked(config.get("intercept_enabled", True))
        layout.addWidget(self.intercept_cb)

        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("Hotkey:"))
        self.hotkey_edit = QLineEdit(config.get("hotkey", "ctrl+v"))
        hotkey_row.addWidget(self.hotkey_edit)
        layout.addLayout(hotkey_row)
        layout.addWidget(self._label("e.g. ctrl+v, ctrl+shift+v", muted=True))

        layout.addWidget(self._sep())

        self.startup_cb = QCheckBox("Start Random Paste with Windows")
        self.startup_cb.setChecked(config.get("start_with_windows", False))
        if not autostart.is_supported():
            self.startup_cb.setEnabled(False)
        layout.addWidget(self.startup_cb)

        self.tray_cb = QCheckBox("Minimize to system tray")
        self.tray_cb.setChecked(config.get("minimize_to_tray", True))
        layout.addWidget(self.tray_cb)

        layout.addStretch()

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _label(self, text, bold=False, muted=False):
        lbl = QLabel(text)
        if bold:
            lbl.setObjectName("title")
        if muted:
            lbl.setObjectName("muted")
        return lbl

    def _sep(self):
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setObjectName("sep")
        line.setFrameShape(QFrame.HLine)
        return line

    def selected_mode(self):
        for btn in self.mode_group.buttons():
            if btn.isChecked():
                return btn.property("mode_value")
        return "random"

    def apply_to(self, config):
        config["mode"] = self.selected_mode()
        config["allow_duplicates"] = self.allow_dup_cb.isChecked()
        config["case_sensitive"] = self.case_cb.isChecked()
        config["intercept_enabled"] = self.intercept_cb.isChecked()
        config["hotkey"] = self.hotkey_edit.text().strip().lower() or "ctrl+v"
        config["start_with_windows"] = self.startup_cb.isChecked()
        config["minimize_to_tray"] = self.tray_cb.isChecked()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config = storage.load_config()
        self.bridge = PasteBridge()
        self.bridge.pasted.connect(self._on_item_pasted)

        self.hotkey_mgr = HotkeyManager(
            get_items=lambda: self.config["items"],
            get_settings=lambda: self.config,
            on_paste=lambda item: self.bridge.pasted.emit(item),
        )

        self._build_ui()
        self._build_tray()
        self._apply_hotkey_state()
        self._refresh_toggle_ui()

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        self.setWindowTitle("Random Paste")
        self.resize(340, 440)
        self.setMinimumSize(300, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel("Random Paste")
        title.setObjectName("title")
        top.addWidget(title)
        top.addStretch()
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        top.addWidget(self.status_label)
        root.addLayout(top)

        root.addWidget(self._sep())

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.itemDoubleClicked.connect(self._edit_selected)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        root.addWidget(self.list_widget, 1)

        row_btns = QHBoxLayout()
        add_btn = QPushButton("+ Add Items")
        add_btn.clicked.connect(self._add_items)
        row_btns.addWidget(add_btn)
        for label, handler in (
            ("Edit", self._edit_selected),
            ("Duplicate", self._duplicate_selected),
            ("Delete", self._delete_selected),
        ):
            btn = QPushButton(label)
            btn.setObjectName("smallBtn")
            btn.clicked.connect(handler)
            row_btns.addWidget(btn)
        row_btns.addStretch()
        root.addLayout(row_btns)

        drag_hint = QLabel("Drag items to reorder")
        drag_hint.setObjectName("muted")
        root.addWidget(drag_hint)

        root.addWidget(self._sep())

        settings_row = QHBoxLayout()
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._open_settings)
        settings_row.addWidget(settings_btn)
        settings_row.addStretch()
        root.addLayout(settings_row)

        self.toggle_btn = QPushButton("Paste Cycle: OFF")
        self.toggle_btn.clicked.connect(self._toggle_paste_cycle)
        root.addWidget(self.toggle_btn)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("hint")
        self.hint_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.hint_label)

        self._refresh_list()

        geo = self.config.get("window_geometry")
        if geo and len(geo) == 4:
            self.setGeometry(*geo)

    def _sep(self):
        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setObjectName("sep")
        line.setFrameShape(QFrame.HLine)
        return line

    # ------------------------------------------------------------ helpers

    def _refresh_list(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item in self.config["items"]:
            preview = item.replace("\n", " \u23ce ")
            if len(preview) > 70:
                preview = preview[:67] + "..."
            self.list_widget.addItem(QListWidgetItem(preview or "(empty)"))
        self.list_widget.blockSignals(False)

    def _on_rows_moved(self, parent, start, end, dest, row):
        # Reconstruct self.config["items"] to match the widget's new
        # visual order (drag-drop already moved the QListWidgetItems).
        new_order = []
        old_items = self.config["items"]
        used = [False] * len(old_items)
        for i in range(self.list_widget.count()):
            text = self.list_widget.item(i).text()
            for j, orig in enumerate(old_items):
                if not used[j]:
                    preview = orig.replace("\n", " \u23ce ")
                    if len(preview) > 70:
                        preview = preview[:67] + "..."
                    if preview == text or (not preview and text == "(empty)"):
                        new_order.append(orig)
                        used[j] = True
                        break
        if len(new_order) == len(old_items):
            self.config["items"] = new_order
            self._save()

    def _refresh_toggle_ui(self):
        enabled = self.config["paste_cycle_enabled"]
        self.toggle_btn.setObjectName("toggleOn" if enabled else "toggleOff")
        self.toggle_btn.setText("Paste Cycle: {}".format("ON" if enabled else "OFF"))
        self.style().unpolish(self.toggle_btn)
        self.style().polish(self.toggle_btn)
        self.status_label.setText("Paste Cycle ON" if enabled else "Paste Cycle OFF")
        hotkey_display = self.config.get("hotkey", "ctrl+v").replace("+", " + ").title()
        self.hint_label.setText("{} \u2192 Random item".format(hotkey_display))
        if getattr(self, "tray", None):
            self.tray.setIcon(make_app_icon(enabled))
            self._rebuild_tray_menu()

    def _save(self):
        storage.save_config(self.config)

    # -------------------------------------------------------- item CRUD

    def _add_items(self):
        dlg = BulkAddDialog(self)
        if dlg.exec() == QDialog.Accepted:
            new_items = dlg.items()
            if new_items:
                self.config["items"].extend(new_items)
                self._refresh_list()
                self._save()

    def _selected_row(self):
        row = self.list_widget.currentRow()
        return row if row >= 0 else None

    def _edit_selected(self):
        row = self._selected_row()
        if row is None:
            return
        dlg = EditItemDialog(self.config["items"][row], self)
        if dlg.exec() == QDialog.Accepted:
            new_val = dlg.value()
            if new_val.strip():
                self.config["items"][row] = new_val
                self._refresh_list()
                self.list_widget.setCurrentRow(row)
                self._save()

    def _duplicate_selected(self):
        row = self._selected_row()
        if row is None:
            return
        self.config["items"].insert(row + 1, self.config["items"][row])
        self._refresh_list()
        self.list_widget.setCurrentRow(row + 1)
        self._save()

    def _delete_selected(self):
        row = self._selected_row()
        if row is None:
            return
        del self.config["items"][row]
        self._refresh_list()
        self._save()

    # ------------------------------------------------------------ toggle

    def _toggle_paste_cycle(self):
        self.config["paste_cycle_enabled"] = not self.config["paste_cycle_enabled"]
        self.hotkey_mgr.reset_sequence()
        self._apply_hotkey_state()
        self._refresh_toggle_ui()
        self._save()

    def _apply_hotkey_state(self):
        if self.config["paste_cycle_enabled"] and self.config.get("intercept_enabled", True):
            self.hotkey_mgr.set_hotkey(self.config.get("hotkey", "ctrl+v"))
        else:
            self.hotkey_mgr.stop()

    def _on_item_pasted(self, item):
        preview = item.replace("\n", " ")[:40]
        self.status_label.setText("Pasted: {}".format(preview))

    # ---------------------------------------------------------- settings

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply_to(self.config)
            if autostart.is_supported():
                try:
                    exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
                    autostart.set_enabled(self.config["start_with_windows"], exe_path)
                except Exception:
                    pass
            self.hotkey_mgr.reset_sequence()
            self._apply_hotkey_state()
            self._refresh_toggle_ui()
            self._save()

    # -------------------------------------------------------------- tray

    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_app_icon(self.config["paste_cycle_enabled"]), self)
        self.tray.setToolTip("Random Paste")
        self._rebuild_tray_menu()
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _rebuild_tray_menu(self):
        menu = QMenu()
        enabled = self.config["paste_cycle_enabled"]
        toggle_action = QAction("Paste Cycle: {}".format("ON" if enabled else "OFF"), self)
        toggle_action.triggered.connect(self._toggle_paste_cycle)
        menu.addAction(toggle_action)
        open_action = QAction("Open Random Paste", self)
        open_action.triggered.connect(self._show_window)
        menu.addAction(open_action)
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self._show_window()

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # -------------------------------------------------------------- exit

    def closeEvent(self, event):
        geo = self.geometry()
        self.config["window_geometry"] = [geo.x(), geo.y(), geo.width(), geo.height()]
        self._save()
        if self.config.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
        else:
            event.accept()
            self._quit()

    def _quit(self):
        self.hotkey_mgr.stop()
        self.tray.hide()
        QApplication.instance().quit()


def main():
    if sys.platform != "win32":
        print(
            "Note: Random Paste's global hotkey and Windows-specific features "
            "(tray, autostart) only work on Windows. The UI below runs "
            "cross-platform for preview/testing purposes."
        )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(DARK_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
