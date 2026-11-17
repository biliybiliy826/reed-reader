"""Install per-user launcher; never overwrite unrelated launchers or executables."""

import os
import shutil
import sys
from pathlib import Path


def quote_exec(path: Path) -> str:
    value = str(path).replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"' + value + '"'


def main():
    project = Path(__file__).resolve().parents[1]
    executable = Path(sys.executable).parent / "reed-reader"
    if not executable.is_file():
        raise SystemExit("请使用项目虚拟环境运行安装程序：.venv/bin/python scripts/install_desktop.py")
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    launcher = root / "applications/reed-reader.desktop"
    icon = root / "icons/hicolor/scalable/apps/reed-reader.svg"
    command = Path.home() / ".local/bin/reed-reader"
    if launcher.exists() and "X-Reed-Reader-Managed=true" not in launcher.read_text():
        raise SystemExit(f"已有非本项目创建的启动器，未覆盖：{launcher}")
    if (command.exists() or command.is_symlink()) and command.resolve() != executable.resolve():
        raise SystemExit(f"已有同名命令，未覆盖：{command}")
    launcher.parent.mkdir(parents=True, exist_ok=True)
    icon.parent.mkdir(parents=True, exist_ok=True)
    command.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "packaging/reed-reader.svg", icon)
    launcher.write_text(f'''[Desktop Entry]
Type=Application
Version=1.0
Name=Reed Reader
Name[zh_CN]=苇读
Comment=An offline-first lightweight Linux reader
Comment[zh_CN]=离线优先的 Linux 轻量阅读器
Exec={quote_exec(executable)} %F
Icon=reed-reader
Terminal=false
Categories=Office;Viewer;
MimeType=text/plain;application/epub+zip;application/x-mobipocket-ebook;
StartupNotify=true
StartupWMClass=reed-reader
X-Reed-Reader-Managed=true
''')
    if not command.is_symlink():
        command.symlink_to(executable)
    print(f"桌面入口：{launcher}\n命令入口：{command}\n运行：reed-reader")


if __name__ == "__main__":
    main()
