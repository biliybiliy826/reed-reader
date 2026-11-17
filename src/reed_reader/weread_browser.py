"""Qt web boundary: official navigation, per-app profile, no credential extraction."""

import errno
import re
import shutil
import time
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

from .weread_policy import allowed_navigation


class OfficialPage(QWebEnginePage):
    navigation_blocked = Signal(str)

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if not is_main_frame or allowed_navigation(url.toString()):
            return True
        # Initial empty document used by Qt is not an external navigation.
        if url.toString() == "about:blank":
            return True
        self.navigation_blocked.emit("该链接不属于微信读书/微信登录页面。请使用系统浏览器访问其他网站。")
        return False

    def javaScriptConsoleMessage(self, level, message, line, source):
        # Console messages may include authenticated URLs or account information.
        # Loading failures have a dedicated user-facing error path instead.
        return


def make_profile(root: Path, parent=None, generation="") -> QWebEngineProfile:
    if not isinstance(generation, str) or (generation and not re.fullmatch(r"[a-f0-9]{32}", generation)):
        raise ValueError("微信读书配置目录标识无效。")
    suffix = "-" + generation if generation else ""
    storage = root / "weread" / ("profile" + suffix)
    cache = root / "weread" / ("cache" + suffix)
    for directory in (storage.parent, storage, cache):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    profile = QWebEngineProfile("reed-weread", parent)
    profile.setPersistentStoragePath(str(storage))
    profile.setCachePath(str(cache))
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setHttpCacheMaximumSize(128 * 1024 * 1024)
    profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.5")
    # Keep Chromium's real user agent and normal TLS/sandbox behavior.
    profile.downloadRequested.connect(lambda download: download.cancel())
    return profile


def remove_browser_data(path: Path):
    """Allow Chromium's final asynchronous file writes to finish; surface real failures."""
    for attempt in range(10):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if exc.errno != errno.ENOTEMPTY or attempt == 9:
                raise
            time.sleep(0.05)


def configure_page(page: OfficialPage):
    settings = page.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    # Reader login needs no camera/mic, location or notification grants.
    page.permissionRequested.connect(lambda permission: permission.deny())
    page.fileSystemAccessRequested.connect(lambda request: request.reject())
