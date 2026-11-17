"""Native X11 integration check. Uses only temporary data and owned windows."""

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from Xlib import XK, X, display
from Xlib.ext import xtest

from reed_reader.app import CommandServer, forward
from reed_reader.demo import demo_book
from reed_reader.jobs import Jobs
from reed_reader.platform import GlobalKeys, set_opacity
from reed_reader.reader import Reader
from reed_reader.settings import Settings
from reed_reader.storage import Library
from reed_reader.style import STYLE, app_icon
from reed_reader.window import MainWindow


def main():
    app = QApplication([])
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    evidence = {}
    temp = tempfile.TemporaryDirectory(prefix="reed-native-")
    root = Path(temp.name)
    library = Library(root / "library.db")
    library.add("de000000", demo_book())
    settings = Settings(root / "settings.json")
    jobs = Jobs()
    reader = Reader(library, settings, jobs)
    window = MainWindow(library, settings, jobs, reader)
    outputs = Path(__file__).resolve().parents[1] / "docs/screenshots"
    outputs.mkdir(parents=True, exist_ok=True)
    keys = GlobalKeys()
    triggered = []
    keys.triggered.connect(triggered.append)
    commands = []
    server = CommandServer("reed-native-" + root.name)
    server.received.connect(commands.append)
    window.show()

    def capture_shelf():
        window.grab().save(str(outputs / "bookshelf.png"))
        reader.open_book("de000000")
        QTimer.singleShot(300, capture_reader)

    def capture_reader():
        reader.grab().save(str(outputs / "reader.png"))
        reader.toggle_mini()
        QTimer.singleShot(300, capture_mini)

    def capture_mini():
        reader.grab().save(str(outputs / "mini.png"))
        evidence["mini_size"] = [reader.width(), reader.height()]
        assert reader.height() < 300, evidence
        window.hide()
        assert reader.isVisible()
        evidence["independent_reader"] = True
        result = keys.configure({"probe": "Ctrl+Alt+Y"})
        assert keys.display is not None, result
        # Focus a separate owned window, so the key cannot be an in-reader shortcut.
        sentinel.show()
        sentinel.activateWindow()
        QTimer.singleShot(200, send_key)

    def send_key():
        connection = display.Display()
        codes = [connection.keysym_to_keycode(XK.string_to_keysym(k)) for k in ["Control_L", "Alt_L", "y"]]
        for code in codes:
            xtest.fake_input(connection, X.KeyPress, code)
        for code in reversed(codes):
            xtest.fake_input(connection, X.KeyRelease, code)
        connection.sync()
        connection.close()
        assert forward("reed-native-" + root.name, {"command": "toggle"})
        QTimer.singleShot(250, verify)

    def verify():
        assert triggered == ["probe"], triggered
        assert commands == [{"command": "toggle"}], commands
        evidence["x11_global_shortcut"] = triggered
        evidence["single_instance_ipc"] = commands
        own_id = int(reader.winId())
        set_opacity(own_id, 65)
        connection = display.Display()
        own = connection.create_resource_object("window", own_id)
        prop = own.get_full_property(connection.intern_atom("_NET_WM_WINDOW_OPACITY"), X.AnyPropertyType)
        assert abs(int(prop.value[0]) / 0xFFFFFFFF - 0.65) < 0.001
        set_opacity(own_id, 100)
        assert own.get_full_property(connection.intern_atom("_NET_WM_WINDOW_OPACITY"), X.AnyPropertyType) is None
        connection.close()
        evidence["owned_window_opacity_set_and_reset"] = True
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        (outputs.parent / "x11-verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        app.exit(0)

    sentinel = QWidget()
    sentinel.setWindowTitle("Reed test focus window")
    sentinel.resize(200, 80)
    QTimer.singleShot(400, capture_shelf)
    QTimer.singleShot(10000, lambda: app.exit(2))
    result = app.exec()
    keys.close()
    jobs.pool.waitForDone()
    library.close()
    temp.cleanup()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
