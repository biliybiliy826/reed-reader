# 第三方依赖与原创部分

本项目自身代码、图标和演示文本以 GPL-3.0-only 发布。Fish-book 仅作为公开功能参考，无代码或素材复用。

运行时由包管理器独立安装以下开源依赖，具体版本及完整传递依赖见 `uv.lock`；许可证文本随各依赖包分发：

| 依赖 | 用途 | 上游许可证 |
| --- | --- | --- |
| PySide6-Essentials / Addons / WebEngine / Shiboken6 | Qt 原生桌面界面与官方网页浏览器 | LGPL-3.0 / GPL-2.0 / GPL-3.0 或商业许可（按上游文件） |
| mobi 0.4.1 / KindleUnpack | 无 DRM MOBI 解码 | GPL-3.0-only |
| charset-normalizer | 文本编码识别 | MIT |
| defusedxml | XML 实体防护 | PSF |
| python-xlib | X11 快捷键和窗口属性 | LGPL-2.1-or-later |
| loguru（mobi 依赖） | 解码器日志 | MIT |
| six（python-xlib 依赖） | 兼容层 | MIT |
| standard-imghdr（mobi 依赖） | Python 3.13+ 图像格式兼容 | PSF |

源码包和应用 wheel 不捆绑 Qt 或 Python 运行时。自 v0.2.1 起，`.deb` 和 Linux 便携包包含独立的 CPython（PSF 及其第三方许可）、PySide6/Qt/WebEngine 以及上述依赖；系统图形、音频、NSS 等共享库仍由发行版提供。

二进制包内保留上游 wheel 的 `*.dist-info` 许可证文件，另在 `licenses/` 附带 Python、Qt/PySide 许可证及 Qt 源码中的第三方许可/归属声明，包括 Chromium。Qt/PySide 动态链接，用户可替换 `runtime/lib/python3.13/site-packages` 中的组件；没有修改上游库二进制。

每次发布生成 `build-manifest.json`（确切版本、锁文件哈希和对应源码地址）与 `THIRD_PARTY_SOURCES.md`。Release 同时提供本项目源码、PySide 对应源码和 Qt 完整对应源码包；第三方源码下载入口与应用安装包位于同一个 Release，安装用户无需下载源码包。

微信读书页面、标识和书籍由其官方服务器在运行时提供，不随本项目源代码或 wheel 分发。浏览器内核含 Chromium 等上游第三方组件，相关许可证与声明由 PySide6-WebEngine 包提供。
