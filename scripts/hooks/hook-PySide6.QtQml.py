"""This Widgets/HTML application does not import any QML documents.

Retain the native QtQml dependency discovered by the standard Qt helper, but
do not collect every installed QML plugin (including unrelated GPL modules).
No installed PyInstaller or third-party source file is modified.
"""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries
            if "/qmltooling/" not in source.replace("\\", "/")]
