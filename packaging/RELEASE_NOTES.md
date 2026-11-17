专为 Linux 打造的摸鱼阅读器：透明文字悬浮、一键隐藏，支持微信读书。

## 推荐安装：Ubuntu / Debian 的 `.deb`

下载 `reed-reader_0.2.1_amd64.deb`，在下载目录运行：

```bash
sudo apt install ./reed-reader_0.2.1_amd64.deb
```

然后在应用菜单搜索“苇读”，或运行 `reed-reader`。软件自带 Python、Qt 和 WebEngine，无需 uv/pip 或开发环境。首次安装时 apt 可能需要联网补齐系统桌面库。

已通过 Ubuntu 22.04 / 24.04 x86_64 安装、启动、TXT/EPUB/MOBI 导入、WebEngine 本地渲染及卸载测试。其他 Debian 系发行版未逐一验证；本次没有 ARM 包。

## 免安装压缩包

下载 `reed-reader-0.2.1-linux-x86_64.tar.gz`，完整解压后运行其中的 `./reed-reader`。可整体移动目录；仍需要系统桌面库，最低 glibc 2.34，不支持 Alpine/musl。

## 使用与更新

- `reed-reader --weread`：打开微信读书官方网页，自行扫码登录。
- 鼠标中键 / F8 / Ctrl+Alt+H：立即隐藏全部；Alt+V 恢复。
- Ctrl+M：切换透明小窗；进入小说后点击“摸鱼模式”。
- X11 支持全局快捷键；Wayland 需桌面绑定，窗口效果取决于合成器。
- 更新前退出正在运行的苇读，再用同一条 apt 命令安装新版。
- 卸载：`sudo apt remove reed-reader`。用户书籍、设置与登录数据保留。
- 源码安装过的用户：`~/.local/bin/reed-reader` 或同名用户 desktop 可能优先于系统安装包；请先用 `/usr/bin/reed-reader` 确认新版，再自行移除旧的源码启动入口。

`SHA256SUMS` 提供下载校验；`build-manifest.json` 与 `THIRD_PARTY_SOURCES.md` 提供运行时版本和源码来源。另附应用源码包与 wheel。GPL-3.0-only；第三方组件保留各自许可证。
