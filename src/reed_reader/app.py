"""Process lifecycle, tray, IPC and application shortcuts."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon, QWidget

from . import __version__
from .jobs import Jobs
from .mouse_shortcut import MiddleButtonShortcut
from .platform import GlobalKeys
from .reader import Reader
from .settings import Settings, config_directory, data_directory
from .storage import Library
from .style import STYLE, app_icon
from .window import MainWindow


class CommandServer(QObject):
    received = Signal(dict)

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.connections = {}
        self.server.newConnection.connect(self.accept)
        if not self.server.listen(name):
            QLocalServer.removeServer(name)
            if not self.server.listen(name):
                raise RuntimeError(f"无法建立单实例通信：{self.server.errorString()}")

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self.read(s))
            socket.disconnected.connect(lambda s=socket: self.release(s))
            self.read(socket)

    def read(self, socket):
        data = self.connections[socket]
        data.extend(bytes(socket.readAll()))
        if len(data) > 65536:
            socket.disconnectFromServer()
            return
        if b"\n" not in data:
            return
        try:
            message = json.loads(bytes(data).split(b"\n", 1)[0])
            if isinstance(message, dict):
                self.received.emit(message)
        except (ValueError, UnicodeError):
            pass  # Malformed IPC input is rejected; no action is dispatched.
        socket.disconnectFromServer()

    def release(self, socket):
        self.connections.pop(socket, None)
        socket.deleteLater()


def forward(name: str, message: dict) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(250):
        return False
    socket.write(json.dumps(message).encode() + b"\n")
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    return True


class Application(QObject):
    def __init__(self, app, root, config):
        super().__init__()
        self.app = app
        self.data_root = root
        self._closing = False
        self.settings = Settings(config / "settings.json")
        self.library = Library(root / "library.sqlite3")
        self.jobs = Jobs(self)
        self.reader = Reader(self.library, self.settings, self.jobs)
        self.web_reader = None
        self.active_reader = self.reader
        self.window = MainWindow(self.library, self.settings, self.jobs, self.reader)
        self.window.weread_requested.connect(self.open_weread)
        self.global_keys = GlobalKeys(self)
        self.global_keys.triggered.connect(self.action)
        self.fallback_keys = {}
        self._filter_refresh_pending = False
        self.middle_button = MiddleButtonShortcut(self)
        self.middle_button.pressed.connect(lambda: self.action("hide"))
        self.window.preferences_changed.connect(self.configure_keys)
        self.window.exit_requested.connect(self.quit)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("苇读 · Reed Reader")
        menu = QMenu()
        menu.addAction("打开书架", self.window.show_shelf)
        menu.addAction("微信读书", self.open_weread)
        menu.addAction("显示 / 隐藏阅读器", lambda: self.action("toggle"))
        menu.addAction("立即隐藏全部", lambda: self.action("hide"))
        menu.addSeparator()
        menu.addAction("退出", self.quit)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.window.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.window.tray_available:
            self.tray.show()
        self.configure_keys()
        self.install_input_filters()
        self.app.focusChanged.connect(self.install_input_filters)
        if self.settings.warning:
            self.window.notify(self.settings.warning)

    def configure_keys(self):
        prefs = self.settings.preferences
        bindings = {"previous": prefs.previous_key, "next": prefs.next_key,
                    "toggle": prefs.toggle_key, "hide": prefs.panic_key, "hide_alt": prefs.panic_alt_key}
        status = self.global_keys.configure(bindings)
        registered = set(self.global_keys.bindings.values())
        self.fallback_keys = {QKeySequence(sequence).toString(): action for action, sequence in bindings.items()
                              if action not in registered}
        if prefs.global_middle_hide:
            status += " " + self.middle_button.start()
        else:
            self.middle_button.close()
            status += " 鼠标中键：仅苇读窗口内隐藏。"
        self.window.notify(status)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.window.show_shelf()

    def install_input_filters(self, *_):
        self._filter_refresh_pending = False
        if self._closing:
            return
        # Avoid an application-wide Python filter: Qt WebEngine destroys private
        # QObjects during reparenting, which PySide cannot safely wrap (Qt 6.12).
        # Filter the live widgets only, including the web view's input proxy.
        for root in QApplication.topLevelWidgets():
            root.installEventFilter(self)
            for child in root.findChildren(QWidget):
                child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if self._closing:
            return False
        if event.type() == QEvent.Type.ChildAdded and not self._filter_refresh_pending:
            self._filter_refresh_pending = True
            QTimer.singleShot(0, self.install_input_filters)
        if event.type() == QEvent.Type.WindowActivate and watched in (self.reader, self.web_reader):
            self.active_reader = watched
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.MiddleButton:
            self.action("hide")
            return True
        if event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            action = self.fallback_keys.get(QKeySequence(event.keyCombination()).toString())
            if action:
                event.accept()
                if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                    self.action(action)
                return True
        return super().eventFilter(watched, event)

    def open_weread(self):
        if self.web_reader is None:
            # Do not create a browser profile or make web requests during local reading.
            from .weread_window import WeReadWindow

            self.web_reader = WeReadWindow(self.settings, self.data_root)
            self.web_reader.shelf_requested.connect(self.window.show_shelf)
            self.install_input_filters()
        self.active_reader = self.web_reader
        self.web_reader.open()

    def action(self, command):
        if command in {"hide", "hide_alt"}:
            # Hide modal/settings windows too; restoration always has an IPC/tray path.
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog):
                    widget.reject()
                else:
                    widget.hide()
        elif command == "toggle":
            target = self.active_reader
            if target.isVisible() and not target.isMinimized():
                target.hide()
            elif target is self.web_reader:
                target.open()
            elif target.book_id:
                target.showNormal()
                target.raise_()
            else:
                self.window.continue_reading()
        elif command in {"next", "previous"}:
            self.active_reader.turn(1 if command == "next" else -1)
        elif command == "mini":
            if self.active_reader is self.reader and not self.reader.book_id:
                self.window.continue_reading()
            self.active_reader.toggle_mini()
        elif command == "weread":
            self.open_weread()
        elif command == "demo":
            self.window.open_demo()
        elif command == "show":
            self.window.show_shelf()
        elif command == "quit":
            self.quit()

    def dispatch(self, message):
        files = message.get("files", [])
        if isinstance(files, list) and all(isinstance(p, str) for p in files):
            if files:
                self.window.import_paths([Path(p) for p in files])
                self.window.show_shelf()
        command = message.get("command", "show")
        if command in {"hide", "toggle", "next", "previous", "mini", "demo", "show", "weread", "quit"}:
            self.action(command)

    def quit(self):
        if self._closing:
            return
        self._closing = True
        self.reader.save_geometry()
        if self.web_reader is not None:
            self.web_reader.save_geometry()
        self.settings.local["main_geometry"] = bytes(self.window.saveGeometry().toBase64()).decode()
        try:
            self.settings.save()
        except OSError as exc:
            print(f"设置保存失败：{exc}", file=sys.stderr)
        self.global_keys.close()
        self.middle_button.close()
        self.tray.hide()
        self.app.quit()

    def cleanup(self):
        self._closing = True
        self.app.focusChanged.disconnect(self.install_input_filters)
        self.middle_button.close()
        self.reader.timer.stop()
        self.window.refresh_timer.stop()
        if self.web_reader is not None:
            self.web_reader.shutdown()
        self.jobs.pool.clear()
        self.jobs.pool.waitForDone()
        self.global_keys.close()
        self.library.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="苇读 · Linux 原生轻量阅读器")
    parser.add_argument("--version", action="version", version=f"Reed Reader {__version__}")
    parser.add_argument("files", nargs="*", help="导入 TXT / EPUB / MOBI")
    group = parser.add_mutually_exclusive_group()
    for action in ("toggle", "hide", "next", "previous", "show", "mini", "demo", "weread", "quit"):
        group.add_argument("--" + action, action="store_true")
    parser.add_argument("--data-dir", type=Path, help="使用独立数据目录（测试/便携模式）")
    args = parser.parse_args(argv)
    root = (args.data_dir or data_directory()).expanduser().resolve()
    config = root / "config" if args.data_dir else config_directory()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("reed-reader")
    app.setApplicationDisplayName("苇读")
    app.setOrganizationName("ReedReader")
    app.setDesktopFileName("reed-reader")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLE)
    command = next((a for a in ("toggle", "hide", "next", "previous", "show", "mini", "demo", "weread", "quit") if getattr(args, a)), "show")
    name = "reed-reader-" + hashlib.sha256(f"{os.getuid()}:{root}".encode()).hexdigest()[:20]
    message = {"command": command, "files": [str(Path(p).expanduser().resolve()) for p in args.files]}
    if forward(name, message):
        return 0
    if command == "quit":
        return 0
    if command in {"hide", "next", "previous"}:
        print("苇读尚未运行。", file=sys.stderr)
        return 1
    application = Application(app, root, config)
    server = CommandServer(name, app)
    server.received.connect(application.dispatch)
    QTimer.singleShot(0, lambda: application.dispatch(message))
    try:
        return app.exec()
    finally:
        application.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
