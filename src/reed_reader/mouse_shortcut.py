"""X11 middle-button observation without grabbing or recording keyboard input."""

import threading

from PySide6.QtCore import QObject, Signal

from .platform import is_x11


class MiddleButtonShortcut(QObject):
    pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.control = None
        self.stream = None
        self.context = None
        self.thread = None
        self.ready = threading.Event()
        self.stopping = threading.Event()

    def start(self) -> str:
        self.close()
        if not is_x11():
            return "鼠标中键：当前环境仅支持苇读窗口内触发。"
        from Xlib import X, display
        from Xlib.ext import record
        from Xlib.protocol import rq

        try:
            self.control = display.Display()
            self.stream = display.Display()
            if not self.stream.has_extension("RECORD"):
                raise RuntimeError("X11 RECORD 扩展不可用")
            self.context = self.stream.record_create_context(0, [record.AllClients], [{
                "core_requests": (0, 0), "core_replies": (0, 0),
                "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
                "delivered_events": (0, 0), "device_events": (X.ButtonPress, X.ButtonPress),
                "errors": (0, 0), "client_started": False, "client_died": False,
            }])
            self.stream.sync()
            self.ready.clear()
            self.stopping.clear()

            def receive(reply):
                if reply.category == record.StartOfData:
                    self.ready.set()
                if reply.category != record.FromServer or reply.client_swapped or self.stopping.is_set():
                    return
                data = reply.data
                while data:
                    event, data = rq.EventField(None).parse_binary_value(data, self.stream.display, None, None)
                    if event.type == X.ButtonPress and event.detail == 2:
                        self.pressed.emit()

            def listen():
                try:
                    self.stream.record_enable_context(self.context, receive)
                finally:
                    self.ready.set()

            self.thread = threading.Thread(target=listen, name="reed-middle-button", daemon=True)
            self.thread.start()
            if not self.ready.wait(1.0) or not self.thread.is_alive():
                raise RuntimeError("中键监听未能启动")
            return "鼠标中键：X11 全局隐藏已启用（其他应用的中键行为不受拦截）。"
        except Exception as exc:
            self.close()
            return f"全局中键未启用；苇读窗口内中键仍可隐藏：{exc}"

    def close(self):
        self.stopping.set()
        if self.control and self.context is not None:
            self.control.record_disable_context(self.context)
            self.control.sync()
        if self.thread:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                raise RuntimeError("中键监听线程未能停止，请退出应用后重试。")
        if self.stream:
            if self.context is not None:
                self.stream.record_free_context(self.context)
                self.stream.sync()
            self.stream.close()
        if self.control:
            self.control.close()
        self.control = self.stream = self.thread = self.context = None
