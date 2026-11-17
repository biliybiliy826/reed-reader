# Linux 安装包与 Release · 2026-11-17

## 目标与边界

发布 v0.2.1：amd64 `.deb` 和带独立 Python/Qt/WebEngine 的便携 tar.gz，普通用户无需 Python/uv。保留源码和 wheel；本轮不承诺 ARM、RPM、AppImage 或所有发行版兼容。用户已明确授权上传 GitHub Release。

## 设计

- 从固定 CPython standalone 版本及 uv.lock 构建全新运行目录，不复制开发虚拟环境或用户数据。
- `.deb` 安装到 `/opt/reed-reader`，通过 `/usr/bin/reed-reader` 和 desktop/icon 集成；系统库由 apt 解决，不在维护脚本中联网装 pip。
- 同一运行目录生成便携 tar.gz；支持移动目录，不依赖构建机器绝对路径。
- 优先 Ubuntu 22.04/24.04 x86_64；Qt wheel 的 glibc 基线为 2.34，实际支持由干净 runner 安装测试证明。
- 保留许可证与第三方声明，生成版本/来源清单、SHA256 校验文件。
- 标签触发 CI：构建、安装/网页渲染/IPC 验证成功后创建 Release 并上传资产；仅发布 job 具有写权限。

## 进度

- [x] 检查原有安装入口、Qt/WebEngine 分包与 MOBI 子进程需求。
- [x] 构建可搬迁运行目录、deb 与便携包。
- [x] 完成运行目录搬迁、独立数据、Qt/WebEngine 和打包内容验证。
- [x] 增加 CI 构建与安装验证、Release 发布流程。
- [x] 更新安装/卸载说明与依赖声明，发布并核对下载资产。

## 基线与回滚

起点 bbe7544 / v0.2.0；现有 75 项测试通过。仅修改项目构建和必要启动逻辑，保留用户运行实例及数据。失败的 CI 不发布安装包；已发布旧版本不覆写、不移动 v0.2.0 标签。回滚可下载旧标签源码，安装包卸载不删除 XDG 用户数据。

## 验证与修正

- v0.2.1 本地运行目录和解包后的 deb 均通过：TXT/EPUB/MOBI、WebEngine 原创 Canvas、透明条、保持隐藏、CLI 单实例退出；未使用用户账号。
- 75 项原有测试与 ruff 通过；运行时搬到含空格路径后验证通过。
- 首次 Ubuntu 22.04 构建暴露旧 dpkg 不支持 --threads-max，改为可兼容的环境变量限流。
- 下载产物验证发现 uv 自动生成的隐藏 .gitignore 被误列入 SHA256SUMS；已从发行产物移除。
- 第三方来源使用固定 SHA256 校验，Qt 完整源码与 Python standalone 构建配方随 Release 提供；Python/Qt/Chromium 通知保留在安装包中。
- 最终发布仍以两版 Ubuntu 的安装/卸载验证和 Release 实际资产核对为准。

Ubuntu 22.04 / 24.04 的干净 runner 安装、桌面文件验证、Xvfb 下 GUI/WebEngine、搬移便携目录、卸载保留数据已全部通过：[main 验证运行](https://github.com/biliybiliy826/reed-reader/actions/runs/44072382695)。v0.2.1 标签指向同一源码提交 84b73ed，[正式发布运行 44073238308](https://github.com/biliybiliy826/reed-reader/actions/runs/44073238308) 已全部成功。

## 发布完成

[v0.2.1 Release](https://github.com/biliybiliy826/reed-reader/releases/tag/v0.2.1) 已公开，共 10 个附件。下载 SHA256SUMS 后逐项核对 GitHub 资产 digest，9 个被校验附件全部匹配，并实际下载核对 manifest 与第三方源码索引。deb 为 209,343,384 字节（约 200 MiB），便携包为 298,069,080 字节（约 284 MiB）。具体证据见 [package-verification.json](package-verification.json)。

本机未安装或卸载系统包，只做解包后 offscreen/X11 运行验证；apt 安装、桌面入口验证和卸载保留数据在两版 Ubuntu 的干净 GitHub runner 完成。未验证 ARM、其他发行版实际桌面或手机端微信读书同步。
