"""Keep QtQuick's native dependency; no QML debug/profiling plugins are used."""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries
            if "/qmltooling/" not in source.replace("\\", "/")]
