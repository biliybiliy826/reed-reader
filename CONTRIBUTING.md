# 参与开发

1. 安装 Python 3.11+ 与 uv，运行 `uv sync --locked`。
2. 使用临时目录开发：`uv run reed-reader --data-dir /tmp/reed-dev --demo`。
3. 提交前运行 `QT_QPA_PLATFORM=offscreen uv run pytest` 和 `uv run ruff check .`。
4. 需要桌面功能时，在 X11 上运行 `QT_QPA_PLATFORM=xcb uv run python scripts/verify_x11.py`。
   该脚本只修改自己创建的窗口，临时注册 Ctrl+Alt+Y，并生成截图和验证 JSON。
5. 新增依赖时解释必要性、检查许可证并更新 `uv.lock`。

保持 UI、文件格式解析、平台集成和持久化的边界。不要引入未经授权的书籍、第三方站点爬虫或原产品素材。提交的贡献以 GPL-3.0-only 发布。

报告问题时附上发行版、桌面环境、X11/Wayland、Python 和 Qt 版本、复现步骤；使用自行生成或允许分享的最小书籍样例。
