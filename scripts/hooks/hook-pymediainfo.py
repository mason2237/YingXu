"""Ship the reviewed Windows MediaInfo DLL beside its Python wrapper."""
from PyInstaller.utils.hooks import collect_dynamic_libs, get_package_paths
from pathlib import Path

binaries = collect_dynamic_libs("pymediainfo")
_, package = get_package_paths("pymediainfo")
datas = [(str(Path(package) / "License.html"), "pymediainfo")]
