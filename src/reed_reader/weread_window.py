"""Independent official WeRead web window with Reed desktop controls."""

import json
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import QByteArray, QEvent, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QKeyEvent, QKeySequence, QPainter, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizeGrip,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import delete

from .reader import DragBar
from .weread_browser import OfficialPage, configure_page, make_profile, remove_browser_data
from .weread_chrome import FishControls
from .weread_policy import HOME_URL, SHELF_URL, allowed_navigation, input_url, resume_url
from .weread_presentation import presentation_script, scroll_script


class WeReadWindow(QWidget):
    shelf_requested = Signal()

    def __init__(self, settings, data_root, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.mini = False
        self._shutdown = False
        self._started = False
        self._fish_pending = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("微信读书 · 苇读")
        self.setMinimumSize(440, 320)
        self.resize(1100, 780)
        root = QVBoxLayout(self)
        self.root_layout = root
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)
        self.header = DragBar()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(3, 0, 0, 0)
        brand = QLabel("微信读书")
        brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(brand, 1)
        self.compact_button = QPushButton("摸鱼模式")
        self.compact_button.clicked.connect(self.toggle_mini)
        for label, callback in [("苇读书架", self.shelf_requested.emit), ("隐藏", self.hide)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            header.addWidget(button)
        header.addWidget(self.compact_button)
        root.addWidget(self.header)
        self.navigation = QWidget()
        navigation = QHBoxLayout(self.navigation)
        navigation.setContentsMargins(0, 0, 0, 0)
        self.back_button = QPushButton("←")
        self.back_button.setToolTip("后退")
        self.forward_button = QPushButton("→")
        self.forward_button.setToolTip("前进")
        self.reload_button = QPushButton("刷新")
        self.address = QLineEdit()
        self.address.setPlaceholderText("粘贴微信读书书籍链接…")
        self.address.returnPressed.connect(self.open_address)
        navigation.addWidget(self.back_button)
        navigation.addWidget(self.forward_button)
        navigation.addWidget(self.reload_button)
        navigation.addWidget(self.address, 1)
        shelf = QPushButton("微信书架")
        shelf.clicked.connect(lambda: self.navigate(SHELF_URL))
        navigation.addWidget(shelf)
        root.addWidget(self.navigation)
        self.banner = QLabel("登录与阅读由微信读书官网提供。使用微信扫码后，在官方书架选择小说。")
        self.banner.setWordWrap(True)
        root.addWidget(self.banner)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        root.addWidget(self.progress)
        self.view = QWebEngineView()
        self.view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view.setStyleSheet("background: transparent;")
        # Explicit shutdown destroys page before profile, so Chromium can flush the session.
        self.data_root = data_root
        self._create_page()
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        root.addWidget(self.view, 1)
        self.tools = QWidget()
        tools = QHBoxLayout(self.tools)
        tools.setContentsMargins(0, 0, 0, 0)
        self.on_top = QCheckBox("置顶")
        self.on_top.setChecked(bool(settings.local.get("weread_top", True)))
        self.on_top.toggled.connect(self.change_top)
        tools.addWidget(self.on_top)
        tools.addWidget(QLabel("不透明度"))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(20, 100)
        self.opacity.setValue(self.local_number("weread_opacity", 100, 20, 100))
        self.opacity.setMaximumWidth(100)
        self.opacity.valueChanged.connect(lambda value: self.setWindowOpacity(value / 100))
        tools.addWidget(self.opacity)
        for text, callback in [("−", lambda: self.change_zoom(-0.1)), ("＋", lambda: self.change_zoom(0.1))]:
            button = QPushButton(text)
            button.setToolTip("页面缩放")
            button.clicked.connect(callback)
            tools.addWidget(button)
        self.zoom_label = QLabel()
        tools.addWidget(self.zoom_label)
        tools.addStretch()
        external = QPushButton("浏览器打开")
        external.clicked.connect(self.open_external)
        tools.addWidget(external)
        self.clear_button = QPushButton("清除登录")
        self.clear_button.clicked.connect(self.confirm_clear_session)
        tools.addWidget(self.clear_button)
        tools.addWidget(QSizeGrip(self))
        root.addWidget(self.tools)
        self.fish_controls = FishControls(self)
        self.back_button.clicked.connect(self.view.back)
        self.forward_button.clicked.connect(self.view.forward)
        self.reload_button.clicked.connect(self.view.reload)
        self.view.loadStarted.connect(self.load_started)
        self.view.loadProgress.connect(self.progress.setValue)
        self.view.loadFinished.connect(self.load_finished)
        self.view.urlChanged.connect(self.url_changed)
        self.shortcuts = []
        for sequence, callback in [("Escape", self.escape), ("Ctrl+M", self.toggle_mini),
                                   ("F11", self.toggle_fullscreen), ("Ctrl+R", self.view.reload),
                                   ("Ctrl+L", lambda: (self.address.setFocus(), self.address.selectAll()))]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        self.view.setZoomFactor(self.local_number("weread_zoom", 100, 50, 200) / 100)
        self.update_zoom_label()
        self.change_top(self.on_top.isChecked())
        self.setWindowOpacity(self.opacity.value() / 100)
        self.restore_geometry()

    def _create_page(self):
        self.profile = make_profile(self.data_root, self, self.settings.local.get("weread_profile_id", ""))
        self.page = OfficialPage(self.profile, self.view)
        configure_page(self.page)
        self.view.setPage(self.page)
        self.page.navigation_blocked.connect(self.show_message)
        self.page.newWindowRequested.connect(self.open_popup)
        self.page.fullScreenRequested.connect(self.fullscreen_request)
        self.page.renderProcessTerminated.connect(lambda *_: self.show_message("网页进程已停止，请点击刷新。也可以使用“浏览器打开”。"))

    def local_number(self, key, default, low, high):
        value = self.settings.local.get(key, default)
        return max(low, min(high, value)) if type(value) is int else default

    def show_message(self, text):
        self.banner.setText(text)
        if self.mini:
            self.fish_controls.notice(text)
        else:
            self.banner.show()

    def open(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if not self._started:
            self.navigate(resume_url(self.settings.local.get("weread_url", SHELF_URL)))

    def navigate(self, value):
        try:
            value = input_url(value)
        except ValueError as exc:
            self.show_message(str(exc))
            return
        self._started = True
        self.view.load(QUrl(value))

    def open_address(self):
        self.navigate(self.address.text())

    def open_popup(self, request):
        # Official links open in this same protected view, never a second unmanaged window.
        if allowed_navigation(request.requestedUrl().toString()):
            request.openIn(self.page)
        else:
            self.show_message("页面试图打开其他网站；如需继续，请使用“浏览器打开”。")

    def load_started(self):
        self.progress.setVisible(not self.mini)
        self.progress.setValue(0)
        self.show_message("正在连接微信读书…")

    def load_finished(self, ok):
        self.progress.hide()
        self.back_button.setEnabled(self.view.history().canGoBack())
        self.forward_button.setEnabled(self.view.history().canGoForward())
        if ok:
            self.show_message("微信读书官网 · 扫码登录后选择书籍；账号权限、书架与阅读进度由官网管理。")
            if self.mini:
                self.banner.hide()
                self.apply_fish_style()
        else:
            if self.mini:
                self.set_fish_mode(False)
            self.show_message("页面未能加载。请检查网络后刷新；若官网限制内嵌浏览器，可点击“浏览器打开”。")

    def url_changed(self, url):
        # Keep auth query parameters out of app preferences and the native address field.
        parsed = urlsplit(url.toString())
        visible = urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1], parsed.path, "", ""))
        self.address.setText(visible)
        if url.host() == "weread.qq.com" and url.path().startswith("/web/reader/"):
            self.settings.local["weread_url"] = resume_url(url.toString())
        elif self.mini:
            self.page.runJavaScript(presentation_script(False))
            self.set_fish_mode(False)

    def turn(self, direction):
        # Deliver an actual page-scroll key to Chromium, without reading or rewriting the DOM.
        if not self.isVisible():
            return
        if self.mini:
            self.page.runJavaScript(scroll_script(direction))
            return
        target = self.view.focusProxy() or self.view
        key = Qt.Key.Key_PageDown if direction > 0 else Qt.Key.Key_PageUp
        QApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
        QApplication.sendEvent(target, QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier))

    def change_top(self, checked):
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked or self.mini)
        if visible:
            self.show()

    def change_zoom(self, amount):
        self.view.setZoomFactor(max(0.5, min(2.0, round(self.view.zoomFactor() + amount, 2))))
        self.update_zoom_label()

    def update_zoom_label(self):
        self.zoom_label.setText(f"{self.view.zoomFactor():.0%}")

    def toggle_mini(self):
        if self._fish_pending:
            return
        if self.mini:
            self.page.runJavaScript(presentation_script(False))
            self.set_fish_mode(False)
        else:
            self.apply_fish_style(enter=True)

    def apply_fish_style(self, enter=False):
        self._fish_pending = True
        code = presentation_script(True, bool(self.settings.local.get("weread_fish_light", False)),
                                   self.local_number("weread_fish_ink", 95, 20, 100))

        def applied(value):
            self._fish_pending = False
            if self._shutdown:
                return
            result = json.loads(value) if isinstance(value, str) and value else {}
            if result.get("ok"):
                if enter:
                    self.set_fish_mode(True)
            else:
                if self.mini:
                    self.set_fish_mode(False)
                self.show_message(result.get("reason", "摸鱼模式未能启用，请刷新后重试。"))

        self.page.runJavaScript("JSON.stringify(" + code + ")", applied)

    def set_fish_mode(self, enabled):
        visible = self.isVisible()
        if self.isFullScreen() and visible:
            self.showNormal()
        self.save_geometry()
        self.hide()
        self.mini = enabled
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint if self.mini else Qt.WindowType.Window
        if self.mini or self.on_top.isChecked():
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        for widget in (self.header, self.navigation, self.banner, self.tools):
            widget.setVisible(not self.mini)
        self.progress.hide()
        self.root_layout.setContentsMargins(*((0, 0, 0, 0) if self.mini else (8, 6, 8, 6)))
        self.root_layout.setSpacing(0 if self.mini else 5)
        self.setMinimumSize(300, 60) if self.mini else self.setMinimumSize(440, 320)
        self.setWindowOpacity(1.0 if self.mini else self.opacity.value() / 100)
        self.page.setBackgroundColor(QColor(0, 0, 0, 0) if self.mini else QColor("white"))
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu if self.mini else Qt.ContextMenuPolicy.DefaultContextMenu)
        if self.mini:
            self.view.customContextMenuRequested.connect(self.fish_controls.menu)
        else:
            self.view.customContextMenuRequested.disconnect(self.fish_controls.menu)
        self.restore_geometry()
        # Navigation/style callbacks can finish after the emergency hide key.
        # Changing presentation must never reveal a hidden window.
        if visible:
            self.show()
        self.fish_controls.hide()
        self.fish_controls.position()
        self.update()

    def set_fish_option(self, key, value):
        self.settings.local[key] = value
        self.apply_fish_style()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.mini:
            light = self.settings.local.get("weread_fish_light", False)
            color = QColor("#152018" if light else "#f7f8f4")
            color.setAlphaF(self.local_number("weread_fish_background", 0, 0, 100) / 100)
        else:
            color = QColor("#f7f8f4")
        painter.fillRect(self.rect(), color)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "fish_controls"):
            self.fish_controls.position()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.fish_controls.show()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        QTimer.singleShot(120, self.fish_controls.hide_if_outside)

    def save_geometry(self):
        if not self.isFullScreen():
            key = "weread_fish_geometry" if self.mini else "weread_geometry"
            self.settings.local[key] = bytes(self.saveGeometry().toBase64()).decode()
        self.settings.local.update(weread_top=self.on_top.isChecked(),
                                   weread_opacity=self.opacity.value(),
                                   weread_zoom=round(self.view.zoomFactor() * 100))

    def restore_geometry(self):
        key = "weread_fish_geometry" if self.mini else "weread_geometry"
        value = self.settings.local.get(key)
        if isinstance(value, str):
            self.restoreGeometry(QByteArray.fromBase64(value.encode()))
        else:
            if self.mini:
                self.resize(840, 130)
                screen = self.screen().availableGeometry()
                self.move(screen.center().x() - self.width() // 2, screen.bottom() - self.height() - 24)
            else:
                self.resize(1100, 780)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            if self.mini:
                self.toggle_mini()
            self.save_geometry()
            self.showFullScreen()

    def fullscreen_request(self, request):
        request.accept()
        self.showFullScreen() if request.toggleOn() else self.showNormal()

    def escape(self):
        self.showNormal() if self.isFullScreen() else self.hide()

    def open_external(self):
        value = self.view.url().toString()
        # External browser has its own login. Do not transfer this window's OAuth state.
        value = resume_url(value) if value != HOME_URL else HOME_URL
        if not QDesktopServices.openUrl(QUrl(value)):
            self.show_message("无法启动默认浏览器，请手动访问 https://weread.qq.com/ 。")

    def confirm_clear_session(self):
        answer = QMessageBox.question(self, "清除微信读书登录", "清除苇读中的微信读书登录和网站数据？\n系统浏览器、手机账号与本地图书不会受影响。")
        if answer == QMessageBox.StandardButton.Yes:
            self.clear_session()

    def clear_session(self):
        """Rotate the private profile after closing Chromium; avoid async cookie-clear races."""
        import uuid
        from pathlib import Path

        old_paths = [Path(self.profile.persistentStoragePath()), Path(self.profile.cachePath())]
        previous = self.settings.local.get("weread_profile_id", "")
        self.settings.local["weread_profile_id"] = uuid.uuid4().hex
        try:
            self.settings.save()
        except OSError as exc:
            self.settings.local["weread_profile_id"] = previous
            self.show_message(f"清除登录未执行，设置无法保存：{exc}")
            return
        self.view.stop()
        self._destroy_page()
        # A new directory prevents late writes from the old Chromium profile
        # from resurrecting a supposedly cleared login session.
        self._create_page()
        failure = None
        try:
            for directory in old_paths:
                remove_browser_data(directory)
        except OSError as exc:
            failure = exc
        if failure is not None:
            self.show_message(f"登录已重置，但旧缓存未能完全清除，请检查文件权限：{failure}")
            return
        self.settings.local.pop("weread_url", None)
        try:
            self.settings.save()
        except OSError as exc:
            self.show_message(f"登录数据已清除，但设置保存失败：{exc}")
            return
        self.navigate(SHELF_URL)

    def _destroy_page(self):
        self.view.blockSignals(True)
        delete(self.page)
        delete(self.profile)
        self.view.blockSignals(False)

    def shutdown(self):
        if self._shutdown:
            return
        self.save_geometry()
        self.view.stop()
        self._shutdown = True
        # Destroy the owning view as well: a surviving view can lazily recreate a
        # default page during later paint events, outliving the profile at exit.
        self.view.blockSignals(True)
        delete(self.view)
        delete(self.profile)

    def hideEvent(self, event):
        if not self._shutdown:
            self.save_geometry()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.hide()
        event.ignore()
