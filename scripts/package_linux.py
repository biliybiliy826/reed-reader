"""Build an amd64 Debian package and portable archive, without installing on the host."""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import tomllib
from pathlib import Path

from build_runtime import PROJECT, build_runtime, run


def create_deb(bundle: Path, work: Path, output: Path, version: str):
    staging = work / "deb-root"
    if staging.exists():
        raise ValueError(f"Refusing to overwrite staging directory: {staging}")
    app_root = staging / "opt/reed-reader"
    # Hard links avoid a second 800 MB copy. No staged payload is modified afterward.
    shutil.copytree(bundle, app_root, symlinks=True, copy_function=os.link)
    for directory in ("usr/bin", "usr/share/applications", "usr/share/icons/hicolor/scalable/apps",
                      "usr/share/doc/reed-reader", "DEBIAN"):
        (staging / directory).mkdir(parents=True, exist_ok=True)
    (staging / "usr/bin/reed-reader").symlink_to("/opt/reed-reader/reed-reader")
    shutil.copy2(PROJECT / "packaging/reed-reader.desktop", staging / "usr/share/applications/reed-reader.desktop")
    shutil.copy2(PROJECT / "packaging/reed-reader.svg", staging / "usr/share/icons/hicolor/scalable/apps/reed-reader.svg")
    shutil.copy2(PROJECT / "LICENSE", staging / "usr/share/doc/reed-reader/copyright")
    shutil.copy2(PROJECT / "THIRD_PARTY.md", staging / "usr/share/doc/reed-reader/THIRD_PARTY.md")
    dependencies = ", ".join((PROJECT / "packaging/debian-depends.txt").read_text().splitlines())
    size = sum(p.stat().st_size for p in staging.rglob("*") if p.is_file() and not p.is_symlink()) // 1024
    control = f"""Package: reed-reader
Version: {version}
Section: text
Priority: optional
Architecture: amd64
Maintainer: Reed Reader contributors <biliybiliy826@users.noreply.github.com>
Homepage: https://github.com/biliybiliy826/reed-reader
Installed-Size: {size}
Depends: {dependencies}
Recommends: fonts-noto-cjk
Description: Stealth reader for Linux with WeRead integration
 Transparent reading overlays, instant hide shortcuts, local ebook library,
 and the official WeRead web reader. Includes a private Python and Qt runtime.
"""
    (staging / "DEBIAN/control").write_text(control)
    checksums = []
    for path in sorted(staging.rglob("*")):
        if path.is_file() and not path.is_symlink() and "DEBIAN" not in path.relative_to(staging).parts:
            with path.open("rb") as source:
                checksums.append(f"{hashlib.file_digest(source, 'md5').hexdigest()}  {path.relative_to(staging)}")
    (staging / "DEBIAN/md5sums").write_text("\n".join(checksums) + "\n")
    archive = output / f"reed-reader_{version}_amd64.deb"
    run("dpkg-deb", "--root-owner-group", "-Zxz", "-z6", "--threads-max=2", "--build", staging, archive)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=PROJECT / "build/linux-package")
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "dist/linux")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This release pipeline currently supports Linux x86_64 only.")
    project = tomllib.loads((PROJECT / "pyproject.toml").read_text())["project"]
    version = project["version"]
    work, output = args.work_dir.resolve(), args.output_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    if list(output.iterdir()):
        raise SystemExit("Output directory must be empty; choose a fresh --output-dir.")
    run("uv", "build", "--out-dir", output)
    wheel = output / f"reed_reader-{version}-py3-none-any.whl"
    bundle = work / f"reed-reader-{version}-linux-x86_64"
    build_runtime(bundle, work, wheel, version)
    shutil.copy2(PROJECT / "packaging/PORTABLE.md", bundle / "README.md")
    # Validate from a different directory, exercising space-containing paths and no PYTHONPATH.
    relocated = work / "relocation test" / bundle.name
    relocated.parent.mkdir(exist_ok=True)
    bundle.rename(relocated)
    try:
        run(relocated / "reed-reader", "--version")
        run(relocated / "runtime/bin/python3", "-I", PROJECT / "scripts/verify_package.py", relocated,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=90)
    finally:
        relocated.rename(bundle)
    create_deb(bundle, work, output, version)
    portable = output / f"reed-reader-{version}-linux-x86_64.tar.gz"
    epoch = subprocess.check_output(["git", "show", "-s", "--format=%ct", "HEAD"], cwd=PROJECT, text=True).strip()
    run("tar", "--sort=name", f"--mtime=@{epoch}", "--owner=0", "--group=0", "--numeric-owner",
        "-czf", portable, "-C", work, bundle.name)
    shutil.copy2(bundle / "build-manifest.json", output / "build-manifest.json")
    # An easy-to-find source/notice index accompanies the binary downloads.
    shutil.copy2(bundle / "licenses/SOURCES.md", output / "THIRD_PARTY_SOURCES.md")
    for source in (work / "upstream-sources").glob("*.tar.xz"):
        shutil.copy2(source, output / source.name)
    sums = []
    for path in sorted(output.iterdir()):
        if path.is_file():
            with path.open("rb") as source:
                sums.append(f"{hashlib.file_digest(source, 'sha256').hexdigest()}  {path.name}")
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(f"Release assets: {output}")


if __name__ == "__main__":
    main()
