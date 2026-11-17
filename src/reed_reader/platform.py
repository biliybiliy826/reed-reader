"""Optional X11 integration. Never pretends Xwayland grants Wayland-wide access."""

import os

from PySide6.QtCore import QObject, QSocketNotifier, Signal


def is_x11() -> bool:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    return (bool(os.environ.get("DISPLAY"))
            and os.environ.get("XDG_SESSION_TYPE") != "wayland"
            and not os.environ.get("WAYLAND_DISPLAY")
            and (app is None or app.platformName() == "xcb"))


def key_spec(sequence: str):
    from Xlib import XK, X

    tokens = sequence.split("+")
    mask = 0
    modifiers = {"Ctrl": X.ControlMask, "Alt": X.Mod1Mask, "Shift": X.ShiftMask, "Meta": X.Mod4Mask}
    for token in tokens[:-1]:
        if token not in modifiers:
            raise ValueError(f"不支持的快捷键修饰符：{token}")
        mask |= modifiers[token]
    key = tokens[-1]
    names = {"Space": "space", "Esc": "Escape", "PgUp": "Prior", "PgDown": "Next", "Del": "Delete"}
    key = names.get(key, key.lower() if len(key) == 1 else key)
    symbol = XK.string_to_keysym(key)
    if not symbol or not mask:
        raise ValueError("全局快捷键需要 Ctrl / Alt / Shift / Meta 修饰键和一个有效按键。")
    return symbol, mask


class GlobalKeys(QObject):
    triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.display = None
        self.notifier = None
        self.bindings = {}
        self.lock_mask = 0

    def configure(self, bindings: dict[str, str]) -> str:
        self.close()
        if not is_x11():
            return "Wayland：使用桌面自定义快捷键绑定 reed-reader --toggle / --next / --previous / --hide。"
        from Xlib import XK, X, display

        try:
            self.display = display.Display()
            root = self.display.screen().root
            num_lock = self.display.keysym_to_keycode(XK.string_to_keysym("Num_Lock"))
            num_mask = 0
            for i, codes in enumerate(self.display.get_modifier_mapping()):
                if num_lock in codes:
                    num_mask |= 1 << i
            self.lock_mask = X.LockMask | num_mask
            failures = []
            for action, sequence in bindings.items():
                symbol, mask = key_spec(sequence)
                code = self.display.keysym_to_keycode(symbol)
                if not code:
                    raise ValueError(f"键盘不支持：{sequence}")
                self.bindings[(code, mask)] = action
                for extra in {0, X.LockMask, num_mask, X.LockMask | num_mask}:
                    root.grab_key(code, mask | extra, False, X.GrabModeAsync, X.GrabModeAsync,
                                  onerror=lambda error, request, seq=sequence: failures.append(seq))
            self.display.sync()
            if failures:
                raise ValueError("快捷键被其他程序占用：" + ", ".join(sorted(set(failures))))
            self.notifier = QSocketNotifier(self.display.fileno(), QSocketNotifier.Type.Read, self)
            self.notifier.activated.connect(self._drain)
            return "X11 全局快捷键已启用。"
        except Exception as exc:
            self.close()
            return f"全局快捷键未启用，应用内快捷键仍可用：{exc}"

    def _drain(self, *_):
        from Xlib import X

        while self.display and self.display.pending_events():
            event = self.display.next_event()
            if event.type == X.KeyPress:
                action = self.bindings.get((event.detail, event.state & ~self.lock_mask))
                if action:
                    self.triggered.emit(action)

    def close(self):
        if self.notifier:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.display:
            from Xlib import X
            self.display.screen().root.ungrab_key(X.AnyKey, X.AnyModifier)
            self.display.sync()
            self.display.close()
            self.display = None
        self.bindings.clear()


def windows() -> list[tuple[int, str]]:
    if not is_x11():
        raise ValueError("其他窗口透明度仅在支持合成的 X11 桌面可用。")
    from Xlib import X, display
    from Xlib.error import BadWindow

    connection = display.Display()
    try:
        prop = connection.screen().root.get_full_property(connection.intern_atom("_NET_CLIENT_LIST"), X.AnyPropertyType)
        result = []
        if prop:
            for window_id in prop.value:
                window = connection.create_resource_object("window", int(window_id))
                try:
                    name = window.get_full_property(connection.intern_atom("_NET_WM_NAME"), X.AnyPropertyType)
                    title = name.value.decode("utf-8", errors="replace") if name else window.get_wm_name()
                    if title:
                        result.append((int(window_id), title))
                except BadWindow:
                    continue
        return result
    finally:
        connection.close()


def set_opacity(window_id: int, percent: int):
    if not is_x11() or not 15 <= percent <= 100:
        raise ValueError("需要 X11 环境，透明度范围为 15–100%。")
    from Xlib import Xatom, display

    connection = display.Display()
    try:
        window = connection.create_resource_object("window", window_id)
        atom = connection.intern_atom("_NET_WM_WINDOW_OPACITY")
        failures = []
        if percent == 100:
            window.delete_property(atom, onerror=lambda e, r: failures.append(str(e)))
        else:
            window.change_property(atom, Xatom.CARDINAL, 32, [round(0xFFFFFFFF * percent / 100)],
                                   onerror=lambda e, r: failures.append(str(e)))
        connection.sync()
        if failures:
            raise ValueError("窗口已关闭或拒绝修改：" + failures[0])
    finally:
        connection.close()
