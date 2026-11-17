# Linux 发行包

## 构建

在 Linux x86_64、Python 3.11+、uv、dpkg-deb、tar 可用的环境中：

```bash
uv sync --locked
uv run python scripts/package_linux.py
```

构建默认使用全新的 `build/linux-package` 和空的 `dist/linux`；为避免误覆盖，重复构建需指定新的 `--work-dir` 与 `--output-dir`。下载仅发生在构建阶段。构建目录与包均不读取本地应用数据。

`build_runtime.py` 用固定 CPython 3.13.13 standalone、锁定依赖和新构建的 wheel 组装运行时；相对 shell 启动器以隔离模式启动 Python。`package_linux.py` 先搬移到含空格的路径验证，随后产生 deb/便携归档、源码/wheel、第三方对应源码、版本清单和 SHA256SUMS。Qt/WebEngine 二进制保持原样且可替换；第三方许可证从确切版本源码提取，wheel 自带许可证保留。

## 安装所有权

- `/opt/reed-reader`：私有、可整体替换的运行时。
- `/usr/bin/reed-reader`：指向运行时相对启动器的链接。
- `/usr/share/applications/reed-reader.desktop` 和 hicolor 图标：系统桌面入口。
- 用户数据：原 XDG 路径，不属于 deb，卸载不删除。

包的 Depends 明确列出所需发行版库；安装维护脚本不调用 pip、不联网、不写用户目录。已有源码安装的用户入口优先级由用户自行处理。

## 发布流水线

main 推送先构建并验证安装包，保留短期 CI 产物，不自动发布。更新应用版本及 release notes、uv.lock，验证通过后创建相同版本的 `v*` 标签。流水线校验标签与项目版本，运行单元测试、构建安装包，在 Ubuntu 22.04 和 24.04 安装 deb、验证真实 X11（Xvfb）控件和 WebEngine、搬移便携目录，并检查卸载保留用户文件。只有标签的全部检查通过才创建草稿 Release、上传所有资产并公开；仅此 job 有 contents:write。

`verify_package.py` 使用包内 Python 及包内应用源码，核对导入位置；TXT/EPUB/MOBI 为原创生成样例，WebEngine 使用本地 HTML/Canvas，不访问微信读书、不使用任何用户账号。官网授权与跨设备同步不属于安装包验证范围。

校验文件覆盖全部发行资产；源码归档与 manifest 随二进制一同发布。没有对所有 Linux 发行版作兼容承诺，ARM 构建暂未提供。

## 上游

- [uv 管理的 Python](https://docs.astral.sh/uv/concepts/python-versions/)
- [Python standalone distributions](https://docs.astral.sh/python-build-standalone/)
- [Qt 第三方许可](https://doc.qt.io/qt-6/licenses-used-in-qt.html)
- [Debian 二进制包依赖](https://www.debian.org/doc/debian-policy/ch-binary.html)
