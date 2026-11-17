"""Exercise the shipped interpreter and libraries, never the checkout's application modules."""

import json
import os
import runpy
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication

import reed_reader
from reed_reader.formats import import_file
from reed_reader.jobs import Jobs
from reed_reader.reader import Reader
from reed_reader.settings import Settings
from reed_reader.storage import Library
from reed_reader.weread_browser import OfficialPage, remove_browser_data
from reed_reader.weread_window import WeReadWindow

HTML = """<!doctype html><html><body class="wr_page_reader">
<div class="readerContent"><div class="app_content"><div class="readerChapterContent">
<div class="renderTargetContainer"><div class="wr_canvasContainer"><canvas width="816" height="900"></canvas></div></div>
</div></div></div><script>let c=document.querySelector('canvas').getContext('2d');
c.fillStyle='#dddddd';c.font='24px sans-serif';
for(let y=32;y<900;y+=40)c.fillText('Reed Reader — original package smoke test',8,y);
</script></body></html>"""


def until(app, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        loop = QEventLoop()
        QTimer.singleShot(20, loop.quit)
        loop.exec()
    raise TimeoutError("Packaged application did not reach the expected state")


def verify_cli(bundle, root):
    command = bundle / "reed-reader"
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": "/nonexistent"}
    result = subprocess.check_output([command, "--version"], env=environment, text=True, timeout=15)
    assert reed_reader.__version__ in result
    data = root / "ipc"
    with (root / "ipc.log").open("w+") as log:
        process = subprocess.Popen([command, "--data-dir", data, "--demo"], env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while not (data / "library.sqlite3").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Packaged CLI failed to start")
                time.sleep(0.05)
            # IPC server is created after Application initialization.
            for _ in range(100):
                hidden = subprocess.run([command, "--data-dir", data, "--hide"], env=environment,
                                        stdout=log, stderr=log, timeout=10)
                if hidden.returncode == 0:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError("Packaged IPC server did not start")
            subprocess.run([command, "--data-dir", data, "--quit"], env=environment, check=True, timeout=15)
            assert process.wait(timeout=20) == 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            log.seek(0)
            messages = log.read()
            if "Traceback" in messages:
                raise RuntimeError(messages)


def main():
    bundle = Path(sys.argv[1]).resolve()
    assert Path(sys.executable).resolve().is_relative_to(bundle)
    assert Path(reed_reader.__file__).resolve().is_relative_to(bundle)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    temporary = tempfile.TemporaryDirectory(prefix="reed-package-test-")
    root = Path(temporary.name)
    settings = Settings(root / "settings.json")
    library = Library(root / "library.sqlite3")
    jobs = Jobs()
    reader = Reader(library, settings, jobs)
    web = WeReadWindow(settings, root)
    # Only this verification process permits its locally generated data: document.
    original = OfficialPage.acceptNavigationRequest
    OfficialPage.acceptNavigationRequest = lambda page, url, kind, main: (
        url.scheme() == "data" or original(page, url, kind, main))
    report = {"version": reed_reader.__version__, "platform": app.platformName()}
    try:
        fixture = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/book_fixtures.py"))
        text = root / "original.txt"
        text.write_text("第一章 开始\n这是安装包原创测试内容。\n" * 20)
        for path in (text, fixture["epub"](root / "original.epub"), fixture["mobi"](root / "original.mobi")):
            digest, book = import_file(path)
            assert book.chapters
            library.add(digest, book)
        reader.open_book(digest)
        assert reader.isVisible()
        reader.hide()
        web.show()
        loaded = []
        web.view.loadFinished.connect(loaded.append)
        web.view.setHtml(HTML, QUrl("https://weread.qq.com/web/reader/package_fixture"))
        until(app, lambda: bool(loaded))
        assert loaded[-1]
        web.toggle_mini()
        until(app, lambda: not web._fish_pending)
        assert web.mini and web.height() <= 160, web.banner.text()
        pixels = []
        web.page.runJavaScript("document.querySelector('canvas').getContext('2d').getImageData(0,0,816,100).data.some(v=>v>0)",
                               pixels.append)
        until(app, lambda: bool(pixels))
        assert pixels == [True]
        web.hide()
        web.set_fish_mode(False)
        assert not web.isVisible()
        verify_cli(bundle, root)
        report.update(relocated_runtime=True, txt_epub_mobi=True, webengine_canvas=True,
                      transparent_mode=True, hide_stays_hidden=True, cli_ipc_quit=True)
        print(json.dumps(report, indent=2))
    finally:
        reader.hide()
        reader.timer.stop()
        web.shutdown()
        jobs.pool.waitForDone()
        library.close()
        remove_browser_data(root)
        temporary.cleanup()


if __name__ == "__main__":
    main()
