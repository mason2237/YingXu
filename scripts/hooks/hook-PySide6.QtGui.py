"""Retain QtGui plugins except unused PDF and virtual-keyboard extensions."""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries
            if Path(source).name.lower() not in {"qpdf.dll", "qtvirtualkeyboardplugin.dll"}]
