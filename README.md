# 苇读 · Reed Reader

一个适用于 Linux 的原生轻量阅读器。独立实现 Fish-book 官网公开介绍的主要功能，以透明小窗、离线阅读和快速隐藏为核心。不是 Fish-book 官方版本；没有使用其代码、品牌图案或素材。

项目以 **GPL-3.0-only** 开源，完整许可证见 [LICENSE](LICENSE)。

![苇读书架](docs/screenshots/bookshelf.png)

![透明小窗](docs/screenshots/mini.png)

## 开始使用

```bash
# 需要 Python 3.11+ 和 uv
uv sync
uv run reed-reader
# 体验随附原创示例
uv run reed-reader --demo
```

不使用 uv：`python3 -m venv .venv && .venv/bin/pip install .`，然后运行 `.venv/bin/reed-reader`。

## 功能

- TXT（UTF-8 / UTF-16 / GB18030 等）、EPUB、无 DRM 的 MOBI / AZW / AZW3 导入；拖放、多文件、重复内容识别。
- 本地书架、收藏、书名/作者过滤、封面与列表布局、自动保存阅读位置。
- 独立阅读窗口、可拖动与缩放的 mini 小窗、置顶、全屏沉浸、一键隐藏、托盘恢复。
- 字体、字号、文字/背景颜色、独立文字/背景透明度、窗口透明度、行距、段落显示。
- 键盘/滚轮翻页、自动翻页、进度跳转、章节过滤、全文搜索、书签。
- 外观配置 JSON 分享/导入、窗口位置与大小记忆。
- Legado 网络书架、按需缓存、下一章预加载、显式拉取/推送阅读进度。
- X11 全局快捷键与其他窗口透明度；Wayland 可使用桌面快捷键调用单实例命令。

## 快捷键

| 按键 | 操作 |
| --- | --- |
| Alt+Z / Alt+C | 上一页 / 下一页（X11 全局） |
| Alt+V | 显示 / 隐藏阅读器（X11 全局） |
| Ctrl+Alt+H | 隐藏全部窗口（X11 全局） |
| Ctrl+O | 导入书籍 |
| Ctrl+M / F11 | mini 小窗 / 全屏沉浸 |
| Ctrl+F / Ctrl+B | 目录与搜索 / 添加书签 |
| ← / → / PgUp / PgDown / Space | 阅读窗口翻页 |
| Esc | 退出全屏，否则隐藏阅读窗口 |

全局快捷键可在设置中更改。隐藏会暂停自动翻页。拖拽小窗标题区域移动，右下角调整大小；点击“书架”可恢复主界面。无系统托盘时关闭书架会退出应用。

## 网络书架

在手机阅读 App 中开启 Web 服务，将其地址填入“网络书架”。双击书籍后目录保存在本地，阅读时缓存当前章并预加载下一章。离线可读取已缓存章节。点击“拉取手机进度”或“推送本机进度”显式同步；默认不会自动覆盖手机进度。

本项目不包含小说站点书源、在线搜索聚合或账号云同步。协议依据维护分支的公开 API；真实设备兼容性见[验证记录](docs/implementation-plan.md)。

## 开发与验证

```bash
uv sync --locked
QT_QPA_PLATFORM=offscreen uv run pytest
uv run ruff check .
uv build
```

[功能对照](docs/features.md) · [Linux 安装与兼容性](docs/linux.md) · [架构](docs/architecture.md) · [验证记录](docs/implementation-plan.md)
