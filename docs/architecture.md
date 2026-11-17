# 架构

`app` 管理进程入口、单实例 IPC、托盘和生命周期。它记录最后激活的本地/网页阅读器，将全局命令路由到对应窗口；微信读书组件只在打开入口时惰性创建。
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

## 微信读书边界（0.2.0）

`weread_policy` 负责主导航域名及可保存的书籍 URL 验证；`weread_browser` 管理官方页面与独立 Chromium profile；`weread_window` 管理官网视图及窗口状态。没有连接 SQLite 正文/书架的转换路径，没有私有接口、Cookie 提取或 WebChannel 原生桥。

profile 位于 XDG_DATA_HOME/reed-reader/weread，页面/视图必须先于 profile 释放。关闭时保存网页窗口状态，再停止并销毁视图，最后释放 profile，以便会话持久化。清除登录需要用户在 UI 确认，重建 profile 前停止并销毁旧页面；异常会明确显示。

外部网页是唯一新增依赖边界。Qt 6.12 将 WebEngine 单独分包，所以明确依赖 PySide6-WebEngine（它再依赖 Addons/Essentials），不能只装 Addons。普通本地阅读启动不创建 WebEngine profile，也不访问官网。

`weread_presentation` 提供仅限已显示阅读页的可撤销样式及滚动操作；`weread_chrome` 管理透明条的悬停控件。完整网页与透明条共享同一个 page/profile，不复制正文到另一渲染器。CSS 不覆盖内容节点的 display/visibility，不能把未显示正文变为可见；文字使用透明 Canvas 的显示滤镜，外层背景与文字 alpha 分别处理。

### 紧急隐藏输入

`app.py` 统一路由 F8、Ctrl+Alt+H、中键为幂等的隐藏全部操作，恢复由 Alt+V/托盘负责。`platform.py` 注册独立 X11 键盘快捷键；冲突时只回退对应键到窗口控件过滤器。`mouse_shortcut.py` 通过独立 X11 RECORD 连接观察 ButtonPress，线程仅发送 Qt 信号，不接触 UI；退出/重配先停止并回收监听线程。中键事件不从其他 X11 客户端抢占。非 X11 环境仅应用控件内中键可用。WebEngine 异步样式切换保留窗口可见性，不能撤销隐藏操作。
