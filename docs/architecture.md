# 架构

`app` 管理进程入口、单实例 IPC、托盘和生命周期。
`window` 管理书架与页面导航；`reader` 管理独立阅读窗口及阅读状态。
`canvas` 负责按 Qt 字形布局分页；进度偏移统一使用 Python Unicode 字符索引。
`formats` 把 TXT/EPUB/MOBI 转为 `Book`/`Chapter`；正文是纯文本，不运行书籍 HTML。
`storage` 是 SQLite 的唯一持久化边界，UI 线程拥有连接。
`settings` 验证可共享设置、原子保存；不导出网络地址或阅读记录。
`legado` 负责有界限、超时的 HTTP 请求和响应验证。
`jobs` 是线程池边界，不从 worker 操作 QWidget 或 SQLite。
`platform` 管理 X11 快捷键和窗口透明度；不在 Wayland 宣称系统级权限。

## 数据
XDG_DATA_HOME/reed-reader/library.sqlite3 保存规范化正文、书架、进度及书签。
XDG_CONFIG_HOME/reed-reader/settings.json 保存外观与快捷键；端点单独保存在本机设置，配置分享不包括端点。
本地导入按文件 SHA-256 去重。导入时读取副本内容；删除条目不删除原始文件。
网络书籍由服务地址和 bookUrl 联合标识；章节按需缓存；离线时已缓存章节仍可阅读。
跨设备同步由用户明确选择拉取或推送，避免覆盖另一个设备的进度。
