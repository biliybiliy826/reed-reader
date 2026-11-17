# 苇读 · Linux 便携版

解压整个目录，运行 `./reed-reader`，或 `./reed-reader --weread` 打开微信读书。
无需安装 Python、uv 或 pip；请保留 runtime 与 reed-reader 在同一目录。
目录可以整体移动。配置、书籍和登录仍位于用户的 XDG 目录，不写入安装目录。

本包面向 x86_64 Linux，最低 glibc 2.34。Ubuntu 用户优先下载 .deb，apt 会处理系统依赖。
便携版仍需要系统的 OpenGL/EGL、NSS、ALSA、X11/Wayland 等桌面库，列表见源码 packaging/debian-depends.txt。
不支持 musl/Alpine。真实 Wayland 行为仍取决于桌面合成器。

F8 / Ctrl+Alt+H / 鼠标中键隐藏全部，Alt+V 恢复；Ctrl+M 切换小窗。
X11 支持全局快捷键；Wayland 需桌面自定义快捷键，中键仅在本应用内有效。

本项目 GPL-3.0-only，详见 LICENSE；第三方版本和来源见 build-manifest.json、licenses/SOURCES.md。
反馈与更新：https://github.com/biliybiliy826/reed-reader
