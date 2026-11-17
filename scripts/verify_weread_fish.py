"""Native visual regression with original synthetic text; no login or network."""

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer, QUrl
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from reed_reader.settings import Settings
from reed_reader.style import STYLE
from reed_reader.weread_browser import OfficialPage, remove_browser_data
from reed_reader.weread_window import WeReadWindow

HTML = '''<!doctype html><html><head><style>
body {background:#262628;margin:0}.app_content{width:760px;padding:72px;margin:auto;background:#1c1c1d}
.navBarOffset{height:100px}.chapterTitle{height:57px}.readerTopBar{height:72px}.readerFooter{height:80px}
</style></head><body class="wr_page_reader"><div class="readerContent"><div class="app_content">
<div class="readerTopBar">网站导航测试</div><div class="navBarOffset"></div>
<div class="readerChapterContent"><div class="chapterTitle">章节标题测试</div>
<div class="renderTargetContainer"><div class="wr_canvasContainer"><canvas width="816" height="900"></canvas></div></div>
</div><div class="readerFooter">翻页测试</div></div><div class="readerControls">工具栏测试</div></div>
<script>const c=document.querySelector('canvas').getContext('2d');c.font='22px sans-serif';c.fillStyle='#dddddd';
const text=['窗外的风轻轻吹过，一页故事，留给自己片刻的安静。','不用占据整个屏幕，文字就浮在工作窗口上。','鼠标移入显示操作，Ctrl+M 随时回到完整阅读窗口。'];
for(let y=34,i=0;y<900;y+=40,i++)c.fillText(text[i%text.length],8,y);</script></body></html>'''


def main():
    original = OfficialPage.acceptNavigationRequest

    def fixture_navigation(page, url, navigation_type, is_main_frame):
        return url.scheme() == "data" or original(page, url, navigation_type, is_main_frame)

    OfficialPage.acceptNavigationRequest = fixture_navigation
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    temporary = tempfile.TemporaryDirectory(prefix="reed-fish-visual-")
    root = Path(temporary.name)
    window = WeReadWindow(Settings(root / "settings.json"), root)
    backdrop = QWidget()
    backdrop.setWindowTitle("苇读视觉验证 · 原创测试文字")
    backdrop.setStyleSheet("QWidget {background:#f1f5ef;color:#5d6e60;} QLabel {font-size:14px;}")
    layout = QVBoxLayout(backdrop)
    layout.setContentsMargins(28, 20, 28, 20)
    title = QLabel("一个普通的工作窗口")
    title.setStyleSheet("font-size:22px;font-weight:600;color:#9cab9d;")
    layout.addWidget(title)
    layout.addStretch()
    layout.addWidget(QLabel("苇读 · 摸鱼模式    /    原创测试文本 · 背景透明，字形保持清晰"))
    backdrop.resize(960, 280)
    backdrop.show()
    window.show()
    report = {"content": "original synthetic HTML/canvas; no account or network"}

    def loaded(ok):
        assert ok
        window.toggle_mini()
        QTimer.singleShot(600, inspect)

    def inspect():
        assert window.mini, window.banner.text()
        assert window.height() <= 160
        assert not window.header.isVisible() and not window.tools.isVisible()
        window.move(backdrop.mapToGlobal(QPoint(60, 80)))
        window.raise_()
        window.fish_controls.hide()
        QTimer.singleShot(500, capture)

    def capture():
        output = Path(__file__).resolve().parents[1] / "docs"
        image = window.grab().toImage()
        alpha = [image.pixelColor(x, y).alpha() for y in range(image.height()) for x in range(image.width())]
        empty = sum(value == 0 for value in alpha)
        ink = len(alpha) - empty
        assert empty > len(alpha) * 0.7, f"background not transparent: {empty}/{len(alpha)}"
        assert ink > 1000, f"glyphs missing from viewport: {ink} pixels"
        report.update(size=[window.width(), window.height()], transparent_pixels=empty,
                      rendered_ink_pixels=ink, whole_window_opacity=window.windowOpacity())
        pos = backdrop.mapToGlobal(QPoint(0, 0))
        screenshot = app.primaryScreen().grabWindow(0, pos.x(), pos.y(), backdrop.width(), backdrop.height())
        screenshot.save(str(output / "screenshots/weread-fish-demo.png"))
        window.toggle_mini()
        assert not window.mini and window.header.isVisible()
        report["restore_full_window"] = True
        (output / "weread-fish-visual.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        app.exit(0)

    window.view.loadFinished.connect(loaded)
    window.view.setHtml(HTML, QUrl("https://weread.qq.com/web/reader/original_fixture"))
    QTimer.singleShot(10000, lambda: app.exit(2))
    try:
        return app.exec()
    finally:
        window.shutdown()
        window.hide()
        backdrop.hide()
        remove_browser_data(root)
        temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
