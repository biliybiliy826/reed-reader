"""Native input checks, focused on an owned X11 window; no user clipboard access."""

import json
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication
from Xlib import XK, X, display
from Xlib.ext import xtest

from reed_reader.mouse_shortcut import MiddleButtonShortcut
from reed_reader.platform import GlobalKeys


def main():
    app = QApplication([])
    connection = display.Display()
    root = connection.screen().root
    pointer = root.query_pointer()
    focus = connection.get_input_focus()
    target = root.create_window(80, 80, 240, 100, 0, connection.screen().root_depth,
                                X.InputOutput, X.CopyFromParent,
                                background_pixel=connection.screen().white_pixel,
                                event_mask=X.ButtonPressMask | X.ButtonReleaseMask)
    keys = GlobalKeys()
    mouse = MiddleButtonShortcut()
    actions, clicks = [], []
    keys.triggered.connect(actions.append)
    mouse.pressed.connect(lambda: clicks.append("middle"))

    def pump():
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)

    def press(names):
        codes = [connection.keysym_to_keycode(XK.string_to_keysym(name)) for name in names]
        for code in codes:
            xtest.fake_input(connection, X.KeyPress, code)
        for code in reversed(codes):
            xtest.fake_input(connection, X.KeyRelease, code)
        connection.sync()
        pump()

    try:
        target.set_wm_name("Reed owned input verification")
        target.map()
        connection.sync()
        pump()
        target.set_input_focus(X.RevertToParent, X.CurrentTime)
        target.warp_pointer(100, 50)
        connection.sync()
        status = keys.configure({"hide_alt": "F8", "hide": "Ctrl+Alt+Y"})
        assert len(keys.bindings) == 2, status
        status = mouse.start()
        assert mouse.thread and mouse.thread.is_alive(), status
        press(["F8"])
        press(["Control_L", "Alt_L", "y"])
        assert actions == ["hide_alt", "hide"], actions
        xtest.fake_input(connection, X.ButtonPress, 2)
        xtest.fake_input(connection, X.ButtonRelease, 2)
        connection.sync()
        pump()
        assert clicks == ["middle"], clicks
        received = []
        while connection.pending_events():
            event = connection.next_event()
            if event.type in (X.ButtonPress, X.ButtonRelease):
                received.append((event.type, event.detail))
        assert received == [(X.ButtonPress, 2), (X.ButtonRelease, 2)], received
        mouse.close()
        assert mouse.thread is None
        assert "已启用" in mouse.start()
        mouse.close()
        evidence = {"global_f8": True, "global_modified_key": True,
                    "global_middle_button": True, "other_client_middle_press_release_preserved": True,
                    "observer_stop_restart": True, "input_target": "owned X11 test window"}
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        output = Path(__file__).resolve().parents[1] / "docs/panic-shortcuts-verification.json"
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    finally:
        mouse.close()
        keys.close()
        root.warp_pointer(pointer.root_x, pointer.root_y)
        connection.set_input_focus(focus.focus, focus.revert_to, X.CurrentTime)
        target.destroy()
        connection.sync()
        connection.close()


if __name__ == "__main__":
    main()
