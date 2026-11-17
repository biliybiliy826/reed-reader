"""Emergency hiding must be idempotent and work from independent child windows."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QVBoxLayout

from reed_reader.app import Application
from reed_reader.platform import key_spec
from reed_reader.settings import Preferences


def test_bare_function_key_and_backward_compatible_preferences():
    assert key_spec("F8")[1] == 0
    assert Preferences.parse({"panic_key": "Ctrl+Alt+H"}).panic_alt_key == "F8"
    with pytest.raises(ValueError):
        key_spec("H")
    with pytest.raises(ValueError):
        Preferences.parse({"panic_alt_key": "Alt+V"})


@pytest.mark.parametrize("trigger", ["middle", "F8", "Ctrl+Alt+H"])
def test_hide_all_from_child_and_restore_last_reader(qtbot, qapp, tmp_path, trigger):
    instance = Application(qapp, tmp_path, tmp_path / "config")
    qtbot.addWidget(instance.window)
    qtbot.addWidget(instance.reader)
    dialog = QDialog(instance.reader)
    qtbot.addWidget(dialog)
    child = QLineEdit(dialog)
    QVBoxLayout(dialog).addWidget(child)
    try:
        instance.window.open_demo()
        instance.window.show()
        dialog.show()
        qapp.processEvents()
        if trigger == "middle":
            qtbot.mouseClick(child, Qt.MouseButton.MiddleButton)
        else:
            key = Qt.Key.Key_F8 if trigger == "F8" else Qt.Key.Key_H
            modifiers = Qt.KeyboardModifier.NoModifier if trigger == "F8" else (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            qtbot.keyClick(child, key, modifiers)
        assert not any(w.isVisible() for w in (instance.window, instance.reader, dialog))
        instance.action("hide_alt")
        instance.action("hide")
        assert not instance.reader.isVisible()
        instance.action("toggle")
        assert instance.reader.isVisible()
        assert not dialog.isVisible() and not instance.window.isVisible()
    finally:
        instance.cleanup()
