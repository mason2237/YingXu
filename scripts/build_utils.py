"""Pure release helpers, with no GUI runtime or legacy builder dependency."""
from pathlib import Path
import hashlib
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from yingxu.version import VERSION, WINDOWS_VERSION

def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def python_sources():
    result = {path.relative_to(ROOT).as_posix(): digest(path)
              for path in sorted((ROOT / "yingxu").rglob("*.py"))}
    result["run.py"] = digest(ROOT / "run.py")
    return result

def stage_frontend(destination, *, include_native=False, extra=()):
    """Copy only the production allowlist, not the showcase or fixture adapter."""
    from yingxu.desktop.assets import WORKSPACE_ASSETS
    manifest = {}
    native = set()
    for key in sorted(set(WORKSPACE_ASSETS) | native | set(extra)):
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

def hash_bundle(folder):
    entries = [f"{digest(path)}  {path.relative_to(folder).as_posix()}"
               for path in sorted(folder.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt"]
    (folder / "SHA256SUMS.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")
