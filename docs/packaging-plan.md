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
- [ ] 构建可搬迁运行目录、deb 与便携包。
- [ ] 完成运行目录搬迁、独立数据、Qt/WebEngine 和打包内容验证。
- [ ] 增加 CI 构建与安装验证、Release 发布。
- [ ] 更新安装/卸载说明与依赖声明，发布并核对下载资产。

## 基线与回滚

起点 bbe7544 / v0.2.0；现有 75 项测试通过。仅修改项目构建和必要启动逻辑，保留用户运行实例及数据。失败的 CI 不发布安装包；已发布旧版本不覆写、不移动 v0.2.0 标签。回滚可下载旧标签源码，安装包卸载不删除 XDG 用户数据。
