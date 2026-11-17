"""WeRead integration tests use synthetic HTML and temporary browser profiles only."""

import pytest
from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtWidgets import QWidget

from reed_reader.app import Application
from reed_reader.settings import Settings
from reed_reader.weread_browser import OfficialPage
from reed_reader.weread_policy import SHELF_URL, allowed_navigation, input_url, resume_url
from reed_reader.weread_window import WeReadWindow


@pytest.fixture(autouse=True)
def permit_synthetic_html_only_in_tests(monkeypatch):
    original = OfficialPage.acceptNavigationRequest

    def accept(page, url, navigation_type, is_main_frame):
        if url.scheme() == "data":
            return True
        return original(page, url, navigation_type, is_main_frame)

    monkeypatch.setattr(OfficialPage, "acceptNavigationRequest", accept)


@pytest.mark.parametrize("url", [
    "https://weread.qq.com/", "https://weread.qq.com/web/reader/abc123",
    "https://open.weixin.qq.com/connect/qrconnect?state=fixture", "https://weread.qq.com:443/web/shelf",
])
def test_official_navigation(url):
    assert allowed_navigation(url)


@pytest.mark.parametrize("url", [
    "https://weread.qq.com.evil.test/", "https://evil.test/?next=https://weread.qq.com",
    "https://weread.qq.com@evil.test/", "https://user@weread.qq.com/",
    "https://@weread.qq.com/",
    "http://weread.qq.com/", "file:///tmp/book", "javascript:alert(1)",
    "https://weread.qq.com:999/", "https://weread.qq.com:broken/", "https://weread.qq.com\\@evil.test/",
    "https://weread.qq.com/\n", "https://weread.qq.com./", None,
])
def test_non_official_navigation_rejected(url):
    assert not allowed_navigation(url)


def test_only_book_paths_are_retained_without_auth_query():
    assert input_url("weread.qq.com/web/reader/abc") == "https://weread.qq.com/web/reader/abc"
    assert resume_url("https://weread.qq.com/web/reader/abc?code=secret#token") == "https://weread.qq.com/web/reader/abc"
    assert resume_url("https://open.weixin.qq.com/connect/oauth2?code=secret") == SHELF_URL
    assert resume_url("https://weread.qq.com/login?code=secret") == SHELF_URL
    assert resume_url(None) == SHELF_URL
    with pytest.raises(ValueError):
        input_url("https://open.weixin.qq.com/")


@pytest.fixture
def web_window(qtbot, tmp_path):
    settings = Settings(tmp_path / "settings.json")
    window = WeReadWindow(settings, tmp_path)
    qtbot.addWidget(window)
    yield window
    window.shutdown()
    window.hide()


def load_html(qtbot, window, body="<p>本地测试页面</p>"):
    with qtbot.waitSignal(window.view.loadFinished, timeout=8000) as signal:
        window.view.setHtml('<!doctype html><html><body class="wr_page_reader">' + body + "</body></html>",
                            QUrl("https://weread.qq.com/web/reader/reed_test"))
    assert signal.args == [True]


def evaluate(qtbot, page, script):
    result = []
    page.runJavaScript(script, lambda value: result.append(value))
    qtbot.waitUntil(lambda: bool(result), timeout=5000)
    return result[0]


def test_pending_fish_style_cannot_undo_emergency_hide(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, READER_FIXTURE)
    window.toggle_mini()
    window.hide()
    qtbot.waitUntil(lambda: not window._fish_pending)
    assert window.mini and not window.isVisible()
    window.set_fish_mode(False)
    assert not window.isVisible()


@pytest.mark.parametrize("mini", [False, True])
def test_middle_inside_official_view_hides_all(qtbot, qapp, tmp_path, mini):
    instance = Application(qapp, tmp_path, tmp_path / "config")
    qtbot.addWidget(instance.window)
    qtbot.addWidget(instance.reader)
    web = WeReadWindow(instance.settings, tmp_path)
    qtbot.addWidget(web)
    instance.web_reader = web
    try:
        web.show()
        instance.window.show()
        load_html(qtbot, web, READER_FIXTURE)
        if mini:
            web.toggle_mini()
            qtbot.waitUntil(lambda: web.mini)
        qtbot.mouseClick(web.view.focusProxy() or web.view, Qt.MouseButton.MiddleButton)
        assert not web.isVisible() and not instance.window.isVisible()
    finally:
        instance.cleanup()


def test_lazy_browser_has_no_request_until_open(qtbot, qapp, tmp_path):
    instance = Application(qapp, tmp_path, tmp_path / "config")
    qtbot.addWidget(instance.reader)
    qtbot.addWidget(instance.window)
    assert instance.web_reader is None
    assert not (tmp_path / "weread").exists()
    instance.cleanup()


def test_window_state_opacity_zoom_and_minimize(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, READER_FIXTURE)
    window.opacity.setValue(60)
    assert window.windowOpacity() == pytest.approx(0.6, abs=0.01)
    window.toggle_mini()
    qtbot.waitUntil(lambda: window.mini)
    assert not window.navigation.isVisible() and not window.tools.isVisible()
    assert not window.header.isVisible()
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.height() <= 160
    assert window.windowOpacity() == 1.0, "fish ink and backdrop are independent of whole-window opacity"
    window.change_zoom(0.2)
    assert window.view.zoomFactor() == pytest.approx(1.2)
    window.hide()
    assert window.settings.local["weread_opacity"] == 60
    assert "weread_fish_geometry" in window.settings.local
    window.toggle_mini()
    assert not window.mini
    assert window.windowOpacity() == pytest.approx(0.6, abs=0.01)
    window.toggle_fullscreen()
    assert window.isFullScreen()
    window.escape()
    assert not window.isFullScreen()


def test_browser_scroll_shortcut_reaches_chromium(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, '<div style="height:9000px">原创测试页面</div>')
    assert evaluate(qtbot, window.page, "window.scrollY") == 0
    window.turn(1)
    qtbot.waitUntil(lambda: window.page.scrollPosition().y() > 0, timeout=3000)
    window.hide()
    before = window.page.scrollPosition().y()
    window.turn(1)
    qtbot.wait(50)
    assert window.page.scrollPosition().y() == before


def test_profile_persists_and_explicit_clear_removes_site_data(qtbot, tmp_path, monkeypatch):
    settings = Settings(tmp_path / "settings.json")
    first = WeReadWindow(settings, tmp_path)
    qtbot.addWidget(first)
    first.show()
    load_html(qtbot, first)
    assert not first.profile.isOffTheRecord()
    assert (tmp_path / "weread/profile").stat().st_mode & 0o777 == 0o700
    evaluate(qtbot, first.page, 'localStorage.setItem("reed_test_marker", "only_synthetic_data"); true')
    first.shutdown()
    first.hide()
    second = WeReadWindow(settings, tmp_path)
    qtbot.addWidget(second)
    try:
        second.show()
        load_html(qtbot, second)
        assert evaluate(qtbot, second.page, 'localStorage.getItem("reed_test_marker")') == "only_synthetic_data"
        # Clearing must never navigate to the live site during an automated test.
        monkeypatch.setattr(second, "navigate", lambda value: None)
        second.clear_session()
        load_html(qtbot, second)
        assert evaluate(qtbot, second.page, 'localStorage.getItem("reed_test_marker") === null') is True
    finally:
        second.shutdown()
        second.hide()


def test_credentials_are_not_saved_in_settings(web_window):
    web_window.url_changed(QUrl("https://weread.qq.com/web/reader/abc?code=secret"))
    assert web_window.settings.local["weread_url"] == "https://weread.qq.com/web/reader/abc"
    assert "secret" not in web_window.address.text()
    assert web_window.address.text() == "https://weread.qq.com/web/reader/abc"
    assert "weread" not in web_window.settings.export()


def test_global_commands_follow_last_active_reader(qtbot, qapp, tmp_path):
    class FakeWebReader(QWidget):
        def __init__(self):
            super().__init__()
            self.turns = []
            self.mini = False

        def open(self):
            self.show()

        def turn(self, direction):
            self.turns.append(direction)

        def toggle_mini(self):
            self.mini = not self.mini

        def shutdown(self):
            self.hide()

        def save_geometry(self):
            pass

    instance = Application(qapp, tmp_path, tmp_path / "config")
    qtbot.addWidget(instance.window)
    qtbot.addWidget(instance.reader)
    web = FakeWebReader()
    qtbot.addWidget(web)
    instance.web_reader = web
    try:
        instance.eventFilter(web, QEvent(QEvent.Type.WindowActivate))
        instance.action("toggle")
        assert web.isVisible()
        instance.action("next")
        instance.action("previous")
        assert web.turns == [1, -1]
        instance.action("mini")
        assert web.mini
        instance.action("hide")
        assert not web.isVisible()
        instance.action("toggle")
        assert web.isVisible()
        instance.window.open_demo()
        instance.eventFilter(instance.reader, QEvent(QEvent.Type.WindowActivate))
        instance.action("toggle")
        assert not instance.reader.isVisible()
        assert web.isVisible(), "switching back to local books must not target WeRead"
    finally:
        instance.cleanup()


READER_FIXTURE = '''
<style>
body {background:rgb(38,38,40);margin:0;}
.readerContent .app_content {background:rgb(28,28,29);width:760px;padding:72px;margin:auto;}
.readerTopBar {height:72px; background:#333;}
.readerControls {height:50px;background:#333;}
.readerFooter {height:70px;}
.navBarOffset {height:100px;}
.chapterTitle {height:57px;}
.renderTargetContent {display:none;}
</style>
<div class="readerContent"><div class="app_content">
<div class="readerTopBar">官方导航测试</div><div class="navBarOffset"></div>
<div class="readerChapterContent"><div class="chapterTitle">测试章节标题</div>
<div class="renderTargetContainer"><div class="wr_canvasContainer"><canvas id="ink" width="600" height="2200"></canvas></div></div>
<div class="renderTargetContent">隐藏的测试内容，样式不得将其显示。</div>
</div><div class="readerFooter"><button>下一章</button></div></div>
<div class="readerControls">页面控件测试</div></div>
<div id="paywall" style="display:none">权限弹窗测试</div>
<script>const ctx=document.querySelector('canvas').getContext('2d'); ctx.fillStyle='#dddddd'; ctx.font='24px sans-serif';
for(let y=40;y<2200;y+=50) ctx.fillText('这是一行原创测试文字。透明阅读条保留清晰字形。',8,y);</script>
'''


def test_fish_presentation_reversible_without_revealing_hidden_content(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, READER_FIXTURE)
    window.toggle_mini()
    qtbot.waitUntil(lambda: window.mini)
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.body).backgroundColor') == 'rgba(0, 0, 0, 0)'
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.querySelector(".readerTopBar")).display') == 'none'
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.querySelector(".renderTargetContent")).display') == 'none'
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.querySelector("#paywall")).display') == 'none'
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.querySelector("canvas")).filter') == 'brightness(0)'
    assert window.page.backgroundColor().alpha() == 0
    assert evaluate(qtbot, window.page, 'document.querySelector("canvas").getBoundingClientRect().top < innerHeight') is True
    window.set_fish_option('weread_fish_light', True)
    qtbot.waitUntil(lambda: not window._fish_pending)
    assert 'invert(1)' in evaluate(qtbot, window.page, 'getComputedStyle(document.querySelector("canvas")).filter')
    window.toggle_mini()
    assert not window.mini
    qtbot.waitUntil(lambda: window.header.isVisible())
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.body).backgroundColor') == 'rgb(38, 38, 40)'
    assert evaluate(qtbot, window.page, 'getComputedStyle(document.querySelector(".readerTopBar")).display') == 'block'
    assert evaluate(qtbot, window.page, 'document.getElementById("reed-fish-style") === null') is True


def test_fish_mode_requires_visible_reader_and_never_unhides_source(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, '<div>未登录页面</div>')
    window.toggle_mini()
    qtbot.waitUntil(lambda: not window._fish_pending)
    assert not window.mini
    assert window.banner.isVisible()
    load_html(qtbot, window, READER_FIXTURE.replace('id="ink"', 'id="ink" style="display:none"'))
    window.toggle_mini()
    qtbot.waitUntil(lambda: not window._fish_pending)
    assert not window.mini
    assert '正文尚未显示' in window.banner.text()


def test_fish_scroll_advances_with_small_viewport(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, READER_FIXTURE)
    window.toggle_mini()
    qtbot.waitUntil(lambda: window.mini)
    qtbot.wait(400)  # Complete the one-shot position restoration after official reflow.
    window.turn(1)
    qtbot.waitUntil(lambda: window.page.scrollPosition().y() > 0)
    assert 0 < window.page.scrollPosition().y() <= window.height()


def test_leaving_reader_restores_full_window(qtbot, web_window):
    window = web_window
    window.show()
    load_html(qtbot, window, READER_FIXTURE)
    window.toggle_mini()
    qtbot.waitUntil(lambda: window.mini)
    window.url_changed(QUrl("https://weread.qq.com/web/shelf"))
    assert not window.mini
    assert window.header.isVisible() and window.navigation.isVisible()
