"""Validated, portable appearance settings; endpoint/geometry stay local."""

import json
import os
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Preferences:
    font: str = "Noto Sans CJK SC"
    font_size: int = 16
    foreground: str = "#33443d"
    background: str = "#f5f2e9"
    text_opacity: int = 100
    background_opacity: int = 96
    window_opacity: int = 100
    line_spacing: float = 1.35
    auto_seconds: int = 12
    wheel_pages: bool = True
    preserve_paragraphs: bool = True
    always_on_top: bool = True
    hide_on_leave: bool = False
    progress_position: str = "bottom"
    previous_key: str = "Alt+Z"
    next_key: str = "Alt+C"
    toggle_key: str = "Alt+V"
    panic_key: str = "Ctrl+Alt+H"
    panic_alt_key: str = "F8"
    global_middle_hide: bool = True

    @classmethod
    def parse(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("设置必须是 JSON 对象。")
        default = cls()
        allowed = {f.name for f in fields(cls)}
        if set(data) - allowed:
            raise ValueError("配置含未知字段：" + ", ".join(sorted(set(data) - allowed)))
        for name, value in data.items():
            expected = getattr(default, name)
            if isinstance(expected, bool):
                valid = type(value) is bool
            elif isinstance(expected, float):
                valid = type(value) in {int, float}
            else:
                valid = type(value) is type(expected)
            if not valid:
                raise ValueError(f"{name} 的类型不正确。")
        result = cls(**data)
        ranges = {"font_size": (10, 60), "text_opacity": (10, 100), "background_opacity": (0, 100),
                  "window_opacity": (15, 100), "line_spacing": (1.0, 2.5), "auto_seconds": (1, 600)}
        for name, (low, high) in ranges.items():
            if not low <= getattr(result, name) <= high:
                raise ValueError(f"{name} 必须在 {low} 到 {high} 之间。")
        for name in ("foreground", "background"):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", getattr(result, name)):
                raise ValueError(f"{name} 必须是 #RRGGBB 颜色。")
        if result.progress_position not in {"top", "bottom", "hidden"}:
            raise ValueError("无效的进度位置。")
        keys = [result.previous_key, result.next_key, result.toggle_key, result.panic_key, result.panic_alt_key]
        if len(set(keys)) != len(keys) or any(not k or len(k) > 60 for k in keys):
            raise ValueError("快捷键不能为空或重复。")
        return result


def data_directory() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "reed-reader"


def config_directory() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "reed-reader"


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self.preferences = Preferences()
        self.local = {}
        self.warning = ""
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.preferences = Preferences.parse(data["preferences"])
                self.local = data.get("local", {})
                if not isinstance(self.local, dict):
                    raise ValueError("本机设置格式错误。")
            except (ValueError, KeyError, TypeError) as exc:
                self.local = {}
                self.warning = f"设置无法读取，已使用默认值；原文件保留：{exc}"

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"preferences": asdict(self.preferences), "local": self.local},
                                        ensure_ascii=False, indent=2))
        temporary.replace(self.path)

    def export(self) -> str:
        return json.dumps({"reed_reader": 1, "preferences": asdict(self.preferences)}, ensure_ascii=False, indent=2)

    def import_code(self, code: str):
        if len(code) > 32_000:
            raise ValueError("配置代码过长。")
        data = json.loads(code)
        if not isinstance(data, dict) or data.get("reed_reader") != 1:
            raise ValueError("这不是苇读 v1 配置。")
        self.preferences = Preferences.parse(data.get("preferences"))
