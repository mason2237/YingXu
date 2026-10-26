"""Build the current offline PySide6 application. Run with --zip for a full package."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.version import VERSION, WINDOWS_VERSION
from scripts.qml_payload import NATIVE_ASSETS, QML_MODULES, stage_qml


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def python_sources():
    result = {path.relative_to(ROOT).as_posix(): digest(path)
              for path in sorted((ROOT / "yingxu").rglob("*.py"))}
    result["run.py"] = digest(ROOT / "run.py")
    return result


def stage_frontend(destination, *, include_native=True, extra=()):
    """Copy only the production allowlist, not the showcase or fixture adapter."""
    from yingxu.web_ui.resources import WORKSPACE_ASSETS
    manifest = {}
    native = {'/' + name for name in NATIVE_ASSETS} if include_native else set()
    for key in sorted(set(WORKSPACE_ASSETS) | native | set(extra)):
        if key == "/qt/qwebchannel.js":  # Provided by Qt's compiled resources.
            continue
        source = ROOT / "frontend" / key.lstrip("/")
        target = destination / key.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest[key] = digest(source)
    return manifest


def version_resource(path):
    # Text accepted by PyInstaller's version-file loader, with zh-CN strings.
    path.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={WINDOWS_VERSION!r}, prodvers={WINDOWS_VERSION!r},
    mask=0x3f, flags=0x2, OS=0x40004, fileType=0x1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('080404b0', [
    StringStruct('FileDescription', '映序 · 字幕整理器'),
    StringStruct('FileVersion', '{VERSION}'),
    StringStruct('InternalName', 'YingXu'),
    StringStruct('OriginalFilename', 'YingXu.exe'),
    StringStruct('ProductName', '映序'),
    StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])])
''', encoding="utf-8")


def release_documents(folder, assets, *, inputs_path=None, source_hashes=None, internal=None, docs=()):
    inputs = json.loads((inputs_path or ROOT / "work/build/release-inputs.json").read_text(encoding="utf-8"))
    if inputs["frontend"] != assets or inputs["pythonSources"] != (source_hashes or python_sources()):
        raise RuntimeError("Sources changed since compilation; rebuild instead of relabeling the old executable")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", folder)
    for name in ("LICENSE", "NOTICE"):
        shutil.copy2(ROOT / name, folder)
    for source in (ROOT / "release").glob("*.md"):
        shutil.copy2(source, folder)
    licenses = folder / "licenses"
    licenses.mkdir(exist_ok=True)
    upstream = ROOT / "frontend" / "vendor" / "design-systems"
    for name in ("LICENSE", "UPSTREAM.md", "lens/ORIGIN.json"):
        shutil.copy2(upstream / name, licenses / ("design-systems-" + Path(name).name))
    inventory = []
    names = ("PySide6", "PySide6_Essentials", "PySide6_Addons", "PySide6_WebEngine",
             "PySide6_Pdf", "shiboken6", "PyInstaller", "pyinstaller-hooks-contrib", "pymediainfo")
    for name in names:
        distribution = importlib.metadata.distribution(name)
        item = {"name": name, "version": distribution.version,
                "declaredLicense": distribution.metadata.get("License-Expression") or distribution.metadata.get("License"),
                "role": "build" if name in {"PyInstaller", "pyinstaller-hooks-contrib"} else "runtime",
                "licenseFiles": []}
        for relative in distribution.files or []:
            if "licenses/" in relative.as_posix().lower():
                source = Path(distribution.locate_file(relative))
                target = licenses / name / source.name
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(source, target)
                item["licenseFiles"].append(target.relative_to(folder).as_posix())
        inventory.append(item)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    legal_sources = ROOT / "licenses"
    provenance = json.loads((legal_sources / "SOURCES.json").read_text(encoding="utf-8"))
    canonical = legal_sources / "PolyForm-Noncommercial-1.0.0.txt"
    if (ROOT / "LICENSE").read_bytes() != canonical.read_bytes():
        raise RuntimeError("Project LICENSE differs from the official unmodified PolyForm text")
    for document in provenance["documents"]:
        if digest(legal_sources / document["file"]) != document["sha256"]:
            raise RuntimeError("License text changed: " + document["file"])
    if not any(item["file"].startswith("qtwebengine-3rdparty-") for item in provenance["documents"]):
        raise RuntimeError("Qt WebEngine third-party notices have not been collected")
    for source in legal_sources.glob("*"):
        if source.is_file():
            shutil.copy2(source, licenses / source.name)
    documentation = folder / "docs"
    documentation.mkdir(exist_ok=True)
    for name in ("DEPENDENCIES.md", "STAGE18_EMBEDDED_SUBTITLES.md", "STAGE19_RENDERING.md", *docs):
        shutil.copy2(ROOT / "docs" / name, documentation)
    qt_modules = sorted(path.name for path in ((internal or folder / "_internal")/"PySide6").glob("Qt6*.dll"))
    manifest = {"version": VERSION, "status": "prerelease", "builtAt": datetime.now(timezone.utc).isoformat(),
                **inputs, "python": sys.version, "dependencies": inventory,
                "applicationLicense": "PolyForm-Noncommercial-1.0.0", "bundledQtModules": qt_modules,
                "licenseAudit": "Basic attribution and compatibility review; see LICENSE_STATUS.md and docs/DEPENDENCIES.md.",
                "cleanWindowsTested": False}
    (folder / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_bundle(folder, assets):
    internal = folder / "_internal"
    required = ("PySide6/QtWebEngineProcess.exe", "PySide6/Qt6WebEngineCore.dll",
                "PySide6/resources/qtwebengine_resources.pak",
                "PySide6/resources/qtwebengine_resources_100p.pak",
                "PySide6/resources/qtwebengine_resources_200p.pak",
                "PySide6/translations/qtwebengine_locales/en-US.pak",
                "PySide6/plugins/platforms/qwindows.dll", "subtitle_organizer.ico",
                "pymediainfo/MediaInfo.dll", "pymediainfo/License.html")
    for relative in required:
        if not (internal / relative).is_file():
            raise RuntimeError(f"Missing release runtime: {relative}")
    media_package = Path(importlib.util.find_spec("pymediainfo").origin).parent
    media_origin = json.loads((ROOT / "licenses/MediaInfo-ORIGIN.json").read_text(encoding="utf-8"))
    if importlib.metadata.version("pymediainfo") != media_origin["version"] or digest(media_package / "MediaInfo.dll") != media_origin["dllSha256"]:
        raise RuntimeError("MediaInfo installation changed; review its wheel and license before release")
    if digest(internal / "pymediainfo/MediaInfo.dll") != digest(media_package / "MediaInfo.dll"):
        raise RuntimeError("Bundled MediaInfo differs from the reviewed installed wheel")
    qt = internal / "PySide6"
    forbidden = ("Qt6Charts", "Qt6DataVisualization", "Qt6Graphs", "Qt6Quick3D",
                 "Qt6VirtualKeyboard", "Qt6QuickTimeline", "Qt6Pdf", "Qt6Mqtt", "Qt6Coap")
    unexpected = [path.name for path in qt.glob("Qt6*.dll") if path.name.startswith(forbidden)]
    if unexpected:
        raise RuntimeError(f"Unused QML/GPL-only modules in the release: {unexpected}")
    expected_qml = json.loads((ROOT / 'work/build/release-inputs.json').read_text(encoding='utf-8'))['qml']
    actual_qml = {path.relative_to(qt/'qml').as_posix(): digest(path)
                  for path in (qt/'qml').rglob('*') if path.is_file()}
    if actual_qml != expected_qml:
        raise RuntimeError('QML runtime differs from the explicit Basic-style payload')
    modules = {path.parent.relative_to(qt/'qml').as_posix() for path in (qt/'qml').rglob('qmldir')}
    if modules != QML_MODULES:
        raise RuntimeError('Unexpected QML modules: ' + str(modules ^ QML_MODULES))
    expected = {key.lstrip("/") for key in assets}
    actual = {path.relative_to(internal / "frontend").as_posix()
              for path in (internal / "frontend").rglob("*") if path.is_file()}
    if actual != expected:
        raise RuntimeError(f"Unexpected frontend payload: {actual ^ expected}")
    for key, value in assets.items():
        if digest(internal / "frontend" / key.lstrip("/")) != value:
            raise RuntimeError(f"Asset changed while building: {key}")
    # The Qt hook also copies debug-only resource packs from developer wheels.
    # Remove only these exact generated files, keeping production packs/locales.
    for path in (internal / "PySide6" / "resources").glob("*.debug.pak"):
        path.unlink()


def hash_bundle(folder):
    entries = [f"{digest(path)}  {path.relative_to(folder).as_posix()}"
               for path in sorted(folder.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt"]
    (folder / "SHA256SUMS.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")


def finalize_release(dist, assets, *, archive=False):
    folder = dist / "YingXu"
    validate_bundle(folder, assets)
    release_documents(folder, assets)
    hash_bundle(folder)
    print(f"Release candidate: {folder / 'YingXu.exe'}", flush=True)
    if archive:
        package = Path(shutil.make_archive(str(dist / f"YingXu-{VERSION}-windows-x64"), "zip", dist, "YingXu"))
        package.with_suffix(".zip.sha256").write_text(f"{digest(package)}  {package.name}\n", encoding="utf-8")
        print(f"Archive: {package} ({package.stat().st_size:,} bytes)", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", action="store_true", help="Also archive the entire release directory")
    parser.add_argument("--finalize-existing", action="store_true", help="Validate/archive the current candidate without rebuilding")
    args = parser.parse_args()
    root = ROOT
    build = root / "work" / "build"
    build.mkdir(parents=True, exist_ok=True)
    name = "YingXu"
    dist = root / "outputs" / "releases" / VERSION
    # Only our explicit, repository-contained candidate directory is replaced.
    if not dist.resolve().is_relative_to((root / "outputs").resolve()):
        raise RuntimeError("Release output escapes the project")
    staging = Path(tempfile.mkdtemp(prefix="payload-", dir=build))
    assets = stage_frontend(staging / "frontend")
    if args.finalize_existing:
        finalize_release(dist, assets, archive=args.zip)
        return
    qt_root = Path(next(iter(importlib.util.find_spec('PySide6').submodule_search_locations)))
    qml_assets = stage_qml(qt_root, staging / 'qml')
    inputs = {"gitBase": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
              "uncommittedSourcesAtBuild": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
              "frontend": assets, "pythonSources": python_sources(), 'qml': qml_assets}
    (build / "release-inputs.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")
    version = staging / "windows-version.txt"
    version_resource(version)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--noupx", "--name", name,
        "--icon", str(root / "assets" / "subtitle_organizer.ico"),
        "--version-file", str(version),
        "--add-data", f"{staging / 'frontend'};frontend",
        "--add-data", f"{root / 'assets' / 'subtitle_organizer.ico'};.",
        "--paths", str(root), "--distpath", str(dist),
        "--workpath", str(build), "--specpath", str(build),
    ]
    command.extend(("--additional-hooks-dir", str(root / "scripts" / "hooks")))
    command.extend(('--add-data', f"{staging / 'qml'};PySide6/qml"))
    for relative in sorted(qml_assets):
        if relative.endswith('.dll'):
            command.extend(('--add-binary', f"{staging / 'qml' / relative};PySide6/qml/{Path(relative).parent.as_posix()}"))
    for module in ("PySide6.QtPdf",):
        command.extend(("--exclude-module", module))
    command.append(str(root / "run.py"))
    # A host PATH can contain an unrelated ICU (e.g. Poppler's versioned build).
    # Qt uses the Windows ICU API; mixing those DLLs produces a broken QtCore.
    # Restrict only the child build environment, never the user's system PATH.
    qt_root = Path(next(iter(importlib.util.find_spec("PySide6").submodule_search_locations)))
    system = Path(os.environ.get("SystemRoot", "C:/Windows"))
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join(map(str, (
        Path(sys.executable).parent, qt_root, system / "System32", system,
    )))
    for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH"):
        environment.pop(name, None)
    subprocess.run(command, cwd=root, env=environment, check=True)
    # Keep the verifier independent of the build process's loaded Qt state;
    # it is also resumable after an interrupted build without recompilation.
    finalize = [sys.executable, str(Path(__file__).resolve()), "--finalize-existing"]
    if args.zip:
        finalize.append("--zip")
    subprocess.run(finalize, cwd=root, env=environment, check=True)


if __name__ == "__main__":
    main()
