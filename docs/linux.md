# Linux 使用、安装与发布

## 环境

Python 3.11+，Linux 桌面，优先使用 X11。依赖通过 `uv sync --locked` 安装。当前机器实际验证环境为 x86_64 Linux、X11、Python 3.13.13、Qt/PySide Essentials 6.12.0。

若 Qt 提示 xcb 插件依赖缺失，Debian/Ubuntu 可安装 `libxcb-cursor0 libegl1 libopengl0 libnss3 libxss1 libasound2t64`（较旧 Ubuntu 使用 `libasound2`）；中文缺字可安装 `fonts-noto-cjk`。不同发行版软件包名可能不同。

## 安装到当前用户

在项目目录运行：

```bash
./scripts/install.sh
```

脚本安装虚拟环境依赖，创建 `~/.local/bin/reed-reader` 命令链接、用户级 `.desktop` 文件和原创 SVG 图标，不需要 sudo。之后在应用菜单搜索“苇读”，或运行 `reed-reader`。

启动器指向项目的 `.venv/bin/reed-reader`；移动项目目录后需要重新安装启动器。若同名命令或启动器不属于本项目，安装脚本会停止而不是覆盖。

仅安装 wheel（不要用 sudo pip）：

```bash
python3 -m venv ~/.local/share/reed-reader-venv
~/.local/share/reed-reader-venv/bin/pip install dist/reed_reader-0.2.0-py3-none-any.whl
~/.local/share/reed-reader-venv/bin/reed-reader
```

## X11 与 Wayland

| 能力 | X11 | Wayland |
| --- | --- | --- |
| 阅读、文件格式、书架、搜索、配置 | 支持 | Qt 原生窗口支持，未在真实会话验证 |
| 全局快捷键 | 内置 python-xlib 抓键；冲突显示错误 | 在桌面系统设置中绑定下列命令 |
| 小窗拖动 | 系统移动，必要时坐标拖动 | Qt startSystemMove，效果由合成器决定 |
| 置顶、半透明、窗口位置恢复 | 取决于窗口管理器/合成器；当前环境已检查 | 由合成器控制；不能保证所有桌面一致 |
| 改变其他窗口透明度 | 支持 `_NET_WM_WINDOW_OPACITY` | 不支持 |

Wayland 自定义快捷键命令（若命令不在 PATH，使用完整路径）：

```text
/home/你的用户名/.local/bin/reed-reader --toggle
/home/你的用户名/.local/bin/reed-reader --next
/home/你的用户名/.local/bin/reed-reader --previous
/home/你的用户名/.local/bin/reed-reader --hide
```

这些命令通过当前用户可访问的本地 Qt socket 控制已有实例，不会启动第二份书架。`--show` 恢复书架；`--demo` 打开原创示例；`--mini` 切换小窗。`--data-dir /path` 使用独立数据和配置，测试或便携使用时很方便。

## 数据与排错

- 正文、进度、书签：`${XDG_DATA_HOME:-~/.local/share}/reed-reader/library.sqlite3`。
- 本机配置：`${XDG_CONFIG_HOME:-~/.config}/reed-reader/settings.json`。
- 标准错误输出保留后台任务的 traceback；UI 显示可理解的失败原因。
- 导入限制：64 MiB 文件；EPUB 展开合计 128 MiB；MOBI 解码子进程 45 秒墙钟 / 30 秒 CPU / 512 MiB 地址空间，失败自动清理临时文件。
- 未缓存的网络章节需要手机服务在线；读取失败可下一页重试，或在目录选择已缓存章节。
- 网络进度是显式操作。手机新增章节时先“刷新所选书籍的章节目录”，再拉取进度；已有章节发生重排时会拒绝自动覆盖本机数据。
- 在阅读器关闭、软件重启或窗口调整后继续阅读时，位置仍以规范化纯文本的字符索引保存；不会修改导入的原始文件。
- 备份时先退出苇读，再复制整个数据目录和配置目录。

## 源码发布

`uv build` 生成带 LICENSE 的源码 tar.gz 和应用 wheel。源码包包含测试、锁文件、文档、安装脚本和 GitHub Actions 工作流。源码按 GPL-3.0-only 许可；依赖说明见 `THIRD_PARTY.md`。

本地交付不等于已经公开托管。发布到 GitHub/Gitee 时，先检查源码及本文件的功能边界，然后在用户指定的仓库推送并创建 release。不要将用户数据目录、书籍、密钥或 `.venv` 加入仓库。

卸载桌面入口只需删除本项目创建的 `~/.local/bin/reed-reader`、`~/.local/share/applications/reed-reader.desktop` 和 `~/.local/share/icons/hicolor/scalable/apps/reed-reader.svg`（若设置 XDG_DATA_HOME 则使用对应位置）。保留数据即可保留书架；不会自动删除用户数据。

## 微信读书（0.2.0）

`reed-reader --weread` 打开独立官方网页窗口；扫码与可读范围由官网管理。Qt WebEngine 增加 Chromium 运行时依赖，首次安装体积较 0.1.0 增大。`reed-reader --quit` 正常退出并保存网页会话。更新正在运行的旧版本后，需要退出旧进程再启动新版；不会改变本地图书数据库格式。详见 [微信读书说明](weread.md)。
