"""Opt-in live official-site smoke check; no accounts, cookies or book text recorded."""

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from reed_reader.settings import Settings
from reed_reader.style import STYLE, app_icon
from reed_reader.weread_browser import remove_browser_data
from reed_reader.weread_window import WeReadWindow


def main():
    app = QApplication([])
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    temporary = tempfile.TemporaryDirectory(prefix="reed-weread-check-")
    root = Path(temporary.name)
    window = WeReadWindow(Settings(root / "settings.json"), root)
    report = {"logged_in": False, "profile": "temporary", "loads": []}
    captured = False

    def loaded(ok):
        nonlocal captured
        report["loads"].append({"ok": ok, "host": window.view.url().host()})
        if ok and not captured:
            captured = True
            QTimer.singleShot(5000, inspect)

    def inspect():
        # Only boolean UI presence, never a DOM dump or credentials.
        window.page.runJavaScript('JSON.stringify({title:document.title, loginControl:document.body.innerText.includes("登录"), qrFrame:!!document.querySelector("iframe")})', verify)

    def verify(value):
        report["official_ui"] = json.loads(value)
        assert window.view.url().host() == "weread.qq.com"
        assert report["official_ui"]["loginControl"]
        report["official_load"] = True
        QTimer.singleShot(300, finish)

    def finish():
        report["full_window_size"] = [window.width(), window.height()]
        report["fish_mode"] = "requires a visible reader; verified separately"
        window.opacity.setValue(70)
        assert abs(window.windowOpacity() - 0.7) < 0.01
        window.hide()
        assert not window.isVisible()
        window.open()
        assert window.isVisible()
        report["hide_restore"] = True
        report["window_opacity"] = True
        report["authenticated_reading"] = "not tested; user scan required"
        output = Path(__file__).resolve().parents[1] / "docs/weread-verification.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        app.exit(0)

    window.view.loadFinished.connect(loaded)
    window.open()
    QTimer.singleShot(45000, lambda: app.exit(2))
    try:
        return app.exec()
    finally:
        window.shutdown()
        window.hide()
        remove_browser_data(root)
        temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
