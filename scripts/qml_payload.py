"""Explicit Basic-style QML runtime, without collecting the installed QML tree."""
from pathlib import Path
import hashlib
import shutil

NATIVE_ASSETS = ('native/desktop.qml', 'native/hdr.frag', 'native/hdr.frag.qsb')
QML_MODULES = frozenset({
    'QtQml', 'QtQml/Models', 'QtQml/WorkerScript', 'QtQuick', 'QtQuick/Window',
    'QtQuick/Controls', 'QtQuick/Controls/impl', 'QtQuick/Controls/Basic',
    'QtQuick/Controls/Basic/impl', 'QtQuick/Templates', 'QtQuick/Layouts',
    'QtQuick/Dialogs', 'QtQuick/Dialogs/quickimpl', 'QtQuick/Shapes', 'Qt/labs/folderlistmodel',
    'QtWebChannel', 'QtWebEngine', 'QtWebEngine/ControlsDelegates',
})


def stage_qml(qt_root, destination):
    source = Path(qt_root) / 'qml'
    manifest = {}
    for module in sorted(QML_MODULES):
        directory = source / module
        if not (directory / 'qmldir').is_file():
            raise RuntimeError('Missing required QML module: ' + module)
        for path in directory.rglob('*'):
            if not path.is_file() or path.suffix in {'.pdb', '.debug'} or 'designer' in path.relative_to(source).parts: continue
            # A nested module is collected only when it is independently allowed.
            parent = path.parent
            while parent != source and not (parent / 'qmldir').is_file(): parent = parent.parent
            if parent.relative_to(source).as_posix() not in QML_MODULES: continue
            relative = path.relative_to(source).as_posix()
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest
