# 苇读 · Reed Reader

**专为 Linux 打造的摸鱼阅读器：透明文字悬浮、一键隐藏，支持微信读书。**

A stealth reader for Linux — read novels discreetly at work, with transparent overlays, instant hide shortcuts, and WeRead integration.

让小说以几行文字浮在工作窗口上，按鼠标中键或 F8 立即隐藏，Alt+V 恢复阅读。支持本地电子书和微信读书官方网页版。

独立实现 Fish-book 官网公开介绍的主要功能。不是 Fish-book 官方版本；没有使用其代码、品牌图案或素材。

项目以 **GPL-3.0-only** 开源，完整许可证见 [LICENSE](LICENSE)。

![微信读书透明文字条效果（原创演示文本）](docs/screenshots/weread-fish-demo.png)

![苇读书架](docs/screenshots/bookshelf.png)

## 开始使用

### 下载安装包（推荐）

前往 [GitHub Releases](https://github.com/biliybiliy826/reed-reader/releases/latest)，下载 `reed-reader_0.2.1_amd64.deb`：

```bash
sudo apt install ./reed-reader_0.2.1_amd64.deb
```

安装后从应用菜单打开“苇读”。自带 Python、Qt 和微信读书浏览器组件，不需要 uv/pip。
面向 Ubuntu 22.04 / 24.04 x86_64；其他 Debian 系发行版尚未逐一验证。也提供免安装的 `linux-x86_64.tar.gz`，解压后运行 `./reed-reader`。安装包较大，因为包含完整浏览器运行时。

鼠标中键 / **F8** 隐藏，**Alt+V** 恢复。卸载使用 `sudo apt remove reed-reader`，保留个人书籍和设置。详细安装、更新及源码安装入口冲突处理见 [Linux 使用说明](docs/linux.md)。

### 从源码运行

```bash
# 需要 Python 3.11+ 和 uv
git clone https://github.com/biliybiliy826/reed-reader.git
cd reed-reader
uv sync
uv run reed-reader
# 体验随附原创示例
uv run reed-reader --demo
# 微信读书官方网页版，打开后微信扫码
uv run reed-reader --weread
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
- 微信读书官方网页版：微信扫码、官方书架与小说阅读、持久登录、透明文字条、缩放、独立文字/背景透明度及快捷隐藏。
- X11 全局快捷键与其他窗口透明度；Wayland 可使用桌面快捷键调用单实例命令。

## 快捷键

| 按键 | 操作 |
| --- | --- |
| Alt+Z / Alt+C | 上一页 / 下一页（X11 全局） |
| Alt+V | 显示 / 隐藏阅读器（X11 全局） |
| F8 / Ctrl+Alt+H | 立即隐藏全部窗口，重复按仍保持隐藏（X11 全局） |
| 鼠标中键 | 立即隐藏全部窗口（X11 默认全局；其他环境在苇读窗口内） |
| Ctrl+O | 导入书籍 |
| Ctrl+M / F11 | mini 小窗 / 全屏沉浸 |
| Ctrl+F / Ctrl+B | 目录与搜索 / 添加书签 |
| ← / → / PgUp / PgDown / Space | 阅读窗口翻页 |
| Esc | 退出全屏，否则隐藏阅读窗口 |

全局快捷键可在设置中更改；也可关闭全局中键。其他应用的中键行为不被拦截。Alt+V 或托盘恢复阅读。隐藏会暂停自动翻页。拖拽小窗标题区域移动，右下角调整大小；点击“书架”可恢复主界面。无系统托盘时关闭书架会退出应用。

## 微信读书

点击左侧 **微信读书** 或运行 `reed-reader --weread`，在官网点击登录并用微信扫码，即可从官方书架选择小说。登录与内容权限由官网管理；点击“摸鱼模式”可将已打开的小说变为透明文字条，移除网页和应用工具栏；Ctrl+M 返回完整窗口。支持独立文字/背景透明度、缩放和全局隐藏。Alt+V 操作最后激活的阅读窗口。详见[微信读书说明](docs/weread.md)。

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
