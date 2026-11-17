"""Process lifecycle, tray, IPC and application shortcuts."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon

from .jobs import Jobs
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
        self.settings = Settings(config / "settings.json")
        self.library = Library(root / "library.sqlite3")
        self.jobs = Jobs(self)
        self.reader = Reader(self.library, self.settings, self.jobs)
        self.window = MainWindow(self.library, self.settings, self.jobs, self.reader)
        self.global_keys = GlobalKeys(self)
        self.global_keys.triggered.connect(self.action)
        self.shortcuts = []
        self.window.preferences_changed.connect(self.configure_keys)
        self.window.exit_requested.connect(self.quit)
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("苇读 · Reed Reader")
        menu = QMenu()
        menu.addAction("打开书架", self.window.show_shelf)
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
        if self.settings.warning:
            self.window.notify(self.settings.warning)

    def configure_keys(self):
        for shortcut in self.shortcuts:
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self.shortcuts = []
        prefs = self.settings.preferences
        bindings = {"previous": prefs.previous_key, "next": prefs.next_key,
                    "toggle": prefs.toggle_key, "hide": prefs.panic_key}
        status = self.global_keys.configure(bindings)
        if self.global_keys.display is None:
            for action, sequence in bindings.items():
                shortcut = QShortcut(QKeySequence(sequence), self.window)
                shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
                shortcut.activated.connect(lambda a=action: self.action(a))
                self.shortcuts.append(shortcut)
        self.window.notify(status)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.window.show_shelf()

    def action(self, command):
        if command == "hide":
            # Hide modal/settings windows too; restoration always has an IPC/tray path.
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog):
                    widget.reject()
                else:
                    widget.hide()
        elif command == "toggle":
            if self.reader.isVisible():
                self.reader.hide()
            elif self.reader.book_id:
                self.reader.show()
                self.reader.raise_()
            else:
                self.window.continue_reading()
        elif command in {"next", "previous"}:
            self.reader.turn(1 if command == "next" else -1)
        elif command == "mini":
            if not self.reader.book_id:
                self.window.continue_reading()
            self.reader.toggle_mini()
        elif command == "demo":
            self.window.open_demo()
        elif command == "show":
            self.window.show_shelf()

    def dispatch(self, message):
        files = message.get("files", [])
        if isinstance(files, list) and all(isinstance(p, str) for p in files):
            if files:
                self.window.import_paths([Path(p) for p in files])
                self.window.show_shelf()
        command = message.get("command", "show")
        if command in {"hide", "toggle", "next", "previous", "mini", "demo", "show"}:
            self.action(command)

    def quit(self):
        self.reader.save_geometry()
        self.settings.local["main_geometry"] = bytes(self.window.saveGeometry().toBase64()).decode()
        try:
            self.settings.save()
        except OSError as exc:
            print(f"设置保存失败：{exc}", file=sys.stderr)
        self.global_keys.close()
        self.tray.hide()
        self.app.quit()

    def cleanup(self):
        self.jobs.pool.clear()
        self.jobs.pool.waitForDone()
        self.global_keys.close()
        self.library.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="苇读 · Linux 原生轻量阅读器")
    parser.add_argument("files", nargs="*", help="导入 TXT / EPUB / MOBI")
    group = parser.add_mutually_exclusive_group()
    for action in ("toggle", "hide", "next", "previous", "show", "mini", "demo"):
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
    command = next((a for a in ("toggle", "hide", "next", "previous", "show", "mini", "demo") if getattr(args, a)), "show")
    name = "reed-reader-" + hashlib.sha256(f"{os.getuid()}:{root}".encode()).hexdigest()[:20]
    message = {"command": command, "files": [str(Path(p).expanduser().resolve()) for p in args.files]}
    if forward(name, message):
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
