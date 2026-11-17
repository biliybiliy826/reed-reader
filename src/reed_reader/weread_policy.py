"""Official navigation and resume URL validation, independent of the web engine."""

import re
from urllib.parse import urlsplit, urlunsplit

HOME_URL = "https://weread.qq.com/"
SHELF_URL = "https://weread.qq.com/web/shelf"
# Login may navigate into WeChat OAuth; CDN/API subresources remain browser-managed.
NAVIGATION_HOSTS = frozenset({"weread.qq.com", "open.weixin.qq.com"})


def allowed_navigation(value: str) -> bool:
    if not isinstance(value, str) or any(c.isspace() for c in value) or "\\" in value:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname in NAVIGATION_HOSTS
                and url.port in {None, 443} and url.username is None and url.password is None)
    except ValueError:
        return False


def input_url(value: str) -> str:
    value = value.strip()
    if value.startswith("weread.qq.com/") or value == "weread.qq.com":
        value = "https://" + value
    if not allowed_navigation(value) or urlsplit(value).hostname != "weread.qq.com":
        raise ValueError("请粘贴 https://weread.qq.com/ 开头的微信读书官方链接。")
    return value


def resume_url(value) -> str:
    """Never persist OAuth codes or query strings in shareable/local JSON settings."""
    if not allowed_navigation(value):
        return SHELF_URL
    url = urlsplit(value)
    if url.hostname == "weread.qq.com" and re.fullmatch(r"/web/reader/[A-Za-z0-9_-]+/?", url.path):
        return urlunsplit(("https", "weread.qq.com", url.path, "", ""))
    return SHELF_URL
