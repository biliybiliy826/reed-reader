"""Build an isolated, relocatable CPython runtime from locked upstream inputs."""

import hashlib
import json
import shutil
import subprocess
import tarfile
import tomllib
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = "3.13.13"
PYTHON_KEY = f"cpython-{PYTHON_VERSION}-linux-x86_64-gnu"


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], cwd=PROJECT, check=True, **kwargs)


def fetch(url: str, destination: Path, sha256: str | None = None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Reed-Reader-build"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    with destination.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if sha256 and digest != sha256:
        raise ValueError(f"Source checksum mismatch: {destination.name}")
    return digest


def source_notices(bundle: Path, python_root: Path, cache: Path, version: str):
    """Keep wheel licenses; add the licenses omitted from official PySide wheels."""
    lock = tomllib.loads((PROJECT / "uv.lock").read_text())
    packages = {p["name"]: p for p in lock["package"]}
    qt_version = packages["pyside6-essentials"]["version"]
    upstream = json.loads((PROJECT / "packaging/upstream-sources.json").read_text())
    if qt_version != upstream["qt_version"]:
        raise ValueError("Update verified Qt source hashes when changing the runtime version")
    pyside_source = (f"https://download.qt.io/official_releases/QtForPython/pyside6/"
                     f"PySide6-{qt_version}-src/pyside-setup-everywhere-src-{qt_version}.tar.xz")
    archive = cache / f"pyside-source-{qt_version}.tar.xz"
    pyside_hash = fetch(pyside_source, archive, upstream["pyside_sha256"])
    licenses = bundle / "licenses"
    licenses.mkdir()
    with tarfile.open(archive) as source:
        for member in source:
            parts = Path(member.name).parts
            if member.isfile() and "LICENSES" in parts:
                target = licenses / "Qt-PySide" / Path(*parts[parts.index("LICENSES") + 1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    if not list((licenses / "Qt-PySide").glob("*")):
        raise RuntimeError("PySide source archive contains no licenses")
    qt_series = ".".join(qt_version.split(".")[:2])
    qt_source = (f"https://download.qt.io/official_releases/qt/{qt_series}/{qt_version}/single/"
                 f"qt-everywhere-src-{qt_version}.tar.xz")
    qt_archive = cache / f"qt-everywhere-src-{qt_version}.tar.xz"
    print("Downloading Qt corresponding source and third-party license notices", flush=True)
    qt_hash = fetch(qt_source, qt_archive, upstream["qt_sha256"])
    with tarfile.open(qt_archive) as source:
        for member in source:
            path = Path(member.name)
            if member.isfile() and (path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
                                    or "LICENSES" in path.parts):
                target = licenses / "Qt-third-party" / Path(*path.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    notices = [p for p in (licenses / "Qt-third-party").rglob("*") if p.is_file()]
    if len(notices) < 100 or not any("chromium" in str(p).lower() for p in notices):
        raise RuntimeError("Qt source archive is missing expected third-party/Chromium notices")
    for filename in ("LICENSE", "THIRD_PARTY.md", "uv.lock"):
        shutil.copy2(PROJECT / filename, bundle / filename)
    shutil.copy2(python_root / "lib/python3.13/LICENSE.txt", licenses / "Python.txt")
    metadata_code = """import importlib.metadata,json
print(json.dumps(sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()], key=lambda d:d['name'])))"""
    installed = json.loads(subprocess.check_output(
        [str(bundle / "runtime/bin/python3"), "-I", "-c", metadata_code], text=True))
    sources = []
    for package in installed:
        name = package["name"].lower().replace("_", "-")
        item = packages.get(name)
        if item and item.get("sdist"):
            sources.append({"name": name, "version": item["version"], **item["sdist"]})
        elif name.startswith(("pyside6", "shiboken6")):
            sources.append({"name": name, "version": package["version"], "url": pyside_source,
                            "hash": "sha256:" + pyside_hash})
        elif name == "reed-reader":
            sources.append({"name": name, "version": version,
                            "url": f"https://github.com/biliybiliy826/reed-reader/tree/v{version}"})
        else:
            sources.append({"name": name, "version": package["version"],
                            "url": f"https://pypi.org/project/{name}/{package['version']}/#files"})
    sources += [
        {"name": "Qt (including WebEngine/Chromium and bundled third-party libraries)", "version": qt_version,
         "url": qt_source, "hash": "sha256:" + qt_hash, "release_asset": qt_archive.name},
        {"name": "CPython", "version": PYTHON_VERSION,
         "url": f"https://www.python.org/ftp/python/{PYTHON_VERSION}/Python-{PYTHON_VERSION}.tar.xz"},
        {"name": "python-build-standalone build recipes and dependency versions",
         "version": (python_root / "BUILD").read_text().strip(),
         "url": "https://github.com/astral-sh/python-build-standalone/tree/" + (python_root / "BUILD").read_text().strip()},
    ]
    manifest = {"application": version, "architecture": "x86_64", "python": PYTHON_VERSION,
                "python_build": (python_root / "BUILD").read_text().strip(),
                "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
                "uv_lock_sha256": hashlib.sha256((PROJECT / "uv.lock").read_bytes()).hexdigest(),
                "packages": installed, "corresponding_sources": sources}
    (bundle / "build-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (licenses / "SOURCES.md").write_text(
        "# Corresponding sources and notices\n\n"
        "Reed Reader is GPL-3.0-only. Bundled libraries retain their upstream licenses. "
        "Qt/PySide are dynamically linked and replaceable in runtime/lib/python3.13/site-packages. "
        "No library binaries are modified. Their source code and build instructions can be downloaded "
        "at the following upstream locations; exact dependency hashes are in uv.lock. "
        "Wheel license files remain in each *.dist-info directory. "
        "Qt license texts are in Qt-PySide; bundled third-party notices (including Chromium) "
        "are in Qt-third-party. The complete Qt source archive is also attached to the Release.\n\n"
        + "\n".join(f"- {p['name']} {p['version']}: {p['url']}" for p in sources) + "\n")


def build_runtime(bundle: Path, work: Path, wheel: Path, version: str):
    if bundle.exists():
        raise ValueError(f"Refusing to overwrite existing runtime: {bundle}")
    download = work / "python-download"
    run("uv", "python", "install", PYTHON_KEY, "--install-dir", download, "--no-bin")
    python_root = download / PYTHON_KEY
    upstream = json.loads((PROJECT / "packaging/upstream-sources.json").read_text())
    if (python_root / "BUILD").read_text().strip() != upstream["python_build"]:
        raise ValueError("Unexpected CPython standalone build; review before updating the pin")
    bundle.mkdir(parents=True)
    runtime = bundle / "runtime"
    shutil.copytree(python_root, runtime, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    requirements = work / "runtime-requirements.txt"
    run("uv", "export", "--locked", "--no-dev", "--no-emit-project", "--output-file", requirements,
        stdout=subprocess.DEVNULL)
    site_packages = runtime / "lib/python3.13/site-packages"
    run("uv", "pip", "install", "--python", runtime / "bin/python3", "--target", site_packages,
        "--require-hashes", "--only-binary", ":all:", "--requirements", requirements)
    run("uv", "pip", "install", "--python", runtime / "bin/python3", "--target", site_packages,
        "--no-deps", wheel)
    # Local wheel provenance contains the build machine path; the release manifest
    # identifies the package without publishing machine-specific metadata.
    (site_packages / f"reed_reader-{version}.dist-info/direct_url.json").unlink(missing_ok=True)
    # Console entry-point shebangs contain the build path. Only our relative launcher is supported.
    for entry in (runtime / "bin").iterdir():
        if entry.name not in {"python", "python3", "python3.13"}:
            if entry.is_file() or entry.is_symlink():
                entry.unlink()
    target_bin = site_packages / "bin"
    if target_bin.exists():
        shutil.rmtree(target_bin)
    for path in runtime.rglob("*"):
        if path.is_symlink():
            resolved = path.resolve()
            if not resolved.is_relative_to(runtime):
                raise ValueError(f"Non-relocatable symlink: {path.relative_to(runtime)}")
    shutil.copy2(PROJECT / "packaging/launcher.sh", bundle / "reed-reader")
    (bundle / "reed-reader").chmod(0o755)
    shutil.copy2(PROJECT / "packaging/reed-reader.svg", bundle / "reed-reader.svg")
    shutil.copy2(PROJECT / "packaging/reed-reader.desktop", bundle / "reed-reader.desktop")
    source_notices(bundle, python_root, work / "upstream-sources", version)
