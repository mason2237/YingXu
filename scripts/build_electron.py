"""Build the pinned Electron app plus a replaceable, frozen Python helper."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yingxu.version import VERSION
from scripts.build import digest, hash_bundle, python_sources, release_documents, stage_frontend, version_resource
from scripts.setup_electron import ELECTRON_SHA256, VERSION as ELECTRON_VERSION

BUILD = ROOT/'work/build/electron'
DIST = ROOT/'outputs/releases'/VERSION
BUNDLE = DIST/'YingXu'
INPUTS = BUILD/'release-inputs.json'
DESKTOP_FILES = ('desktop/electron/main.cjs', 'desktop/electron/preload.cjs', 'desktop/electron/package.json',
                 'scripts/desktop_backend_entry.py', 'scripts/build_electron.py', 'run_electron.py')


def source_hashes():
    result = python_sources()
    result['scripts/desktop_backend_entry.py'] = digest(ROOT/'scripts/desktop_backend_entry.py')
    return result


def validate_bundle(assets):
    internal = BUNDLE/'python/_internal'
    required = ['YingXu.exe', 'LICENSE', 'LICENSES.chromium.html', 'resources/app/main.cjs',
                'resources/app/preload.cjs', 'resources/app/package.json', 'python/YingXuBackend.exe',
                'python/_internal/PySide6/QtWebEngineProcess.exe',
                'python/_internal/PySide6/Qt6WebEngineCore.dll',
                'python/_internal/PySide6/resources/qtwebengine_resources.pak',
                'python/_internal/PySide6/resources/qtwebengine_resources_100p.pak',
                'python/_internal/PySide6/resources/qtwebengine_resources_200p.pak',
                'python/_internal/PySide6/translations/qtwebengine_locales/en-US.pak',
                'python/_internal/PySide6/plugins/platforms/qwindows.dll',
                'python/_internal/pymediainfo/MediaInfo.dll', 'python/_internal/pymediainfo/License.html']
    for name in required:
        if not (BUNDLE/name).is_file():raise RuntimeError('Missing release resource: '+name)
    actual = {p.relative_to(internal/'frontend').as_posix(): digest(p)
              for p in (internal/'frontend').rglob('*') if p.is_file()}
    if actual != {key.lstrip('/'): value for key, value in assets.items()}:
        raise RuntimeError('Frontend payload differs from the reviewed allowlist')
    forbidden = ('Qt6Charts', 'Qt6DataVisualization', 'Qt6Graphs', 'Qt6Quick3D', 'Qt6VirtualKeyboard',
                 'Qt6QuickTimeline', 'Qt6Pdf', 'Qt6Mqtt', 'Qt6Coap')
    if any(p.name.startswith(forbidden) for p in (internal/'PySide6').glob('Qt6*.dll')):
        raise RuntimeError('Unused optional Qt module in the release')
    if any((internal/'PySide6/qml').rglob('qmldir')):
        raise RuntimeError('The independent Widgets browser must not bundle a QML plugin tree')
    origin = json.loads((ROOT/'licenses/MediaInfo-ORIGIN.json').read_text(encoding='utf8'))
    if digest(internal/'pymediainfo/MediaInfo.dll') != origin['dllSha256']:
        raise RuntimeError('MediaInfo binary differs from the reviewed wheel')
    inputs = json.loads(INPUTS.read_text(encoding='utf8'))
    if inputs['desktopSources'] != {name: digest(ROOT/name) for name in DESKTOP_FILES}:
        raise RuntimeError('Desktop sources changed since compilation; rebuild')
    for name in ('main.cjs', 'preload.cjs', 'package.json'):
        if digest(BUNDLE/'resources/app'/name) != inputs['desktopSources']['desktop/electron/'+name]:
            raise RuntimeError('Packaged desktop source changed: '+name)


def customize_executable(executable, resource):
    # Editing resources invalidates upstream signing. Remove its certificate table,
    # and document that this application is unsigned, instead of implying a valid signature.
    import pefile
    from PyInstaller import config
    from PyInstaller.utils.win32.icon import CopyIcons
    from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file, write_version_info_to_executable
    pe = pefile.PE(str(executable), fast_load=True)
    entry = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_SECURITY']]
    offset, size = entry.VirtualAddress, entry.Size
    entry.VirtualAddress = entry.Size = 0
    data = pe.write();pe.close()
    if offset and offset + size == len(data):data = data[:offset]
    executable.write_bytes(data)
    config.CONF.setdefault('workpath', str(BUILD))
    CopyIcons(str(executable), [str(ROOT/'assets/subtitle_organizer.ico')])
    write_version_info_to_executable(str(executable), load_version_info_from_text_file(str(resource)))


def finalize(assets, archive):
    validate_bundle(assets)
    # The official Electron notice belongs to Electron; the application LICENSE
    # belongs to the original code. Keep both byte-identical in distinct locations.
    electron_license = BUNDLE/'LICENSE'
    if electron_license.read_bytes() != (ROOT/'LICENSE').read_bytes():
        target = BUNDLE/'licenses/electron-LICENSE.txt';target.parent.mkdir(exist_ok=True)
        shutil.copy2(electron_license, target)
    release_documents(BUNDLE, assets, inputs_path=INPUTS, source_hashes=source_hashes(),
                      internal=BUNDLE/'python/_internal', docs=('STAGE20A_ELECTRON.md', 'STAGE20B_ELECTRON.md', 'STAGE20C_RELEASE.md'))
    # Required full Chromium attribution comes directly from the official runtime ZIP.
    if not (BUNDLE/'LICENSES.chromium.html').stat().st_size > 100000:
        raise RuntimeError('Missing complete Electron Chromium notices')
    manifest = json.loads((BUNDLE/'BUILD_MANIFEST.json').read_text(encoding='utf8'))
    manifest.update({'entry': 'YingXu.exe', 'helper': 'python/YingXuBackend.exe',
                     'profile': '%LOCALAPPDATA%/YingXu/Electron', 'electron': ELECTRON_VERSION,
                     'electronArchiveSha256': ELECTRON_SHA256, 'unsigned': True,
                     'onlineContainer': 'Separate Qt Widgets/WebEngine helper; no business bridge in remote pages'})
    (BUNDLE/'BUILD_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    for p in (BUNDLE/'python/_internal/PySide6/resources').glob('*.debug.pak'):p.unlink()
    hash_bundle(BUNDLE)
    if archive:
        package = Path(shutil.make_archive(str(DIST/f'YingXu-{VERSION}-windows-x64'), 'zip', DIST, 'YingXu'))
        package.with_suffix('.zip.sha256').write_text(f'{digest(package)}  {package.name}\n', encoding='utf8')
        print(f'Archive ready: {package.name}, {package.stat().st_size:,} bytes', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', action='store_true')
    parser.add_argument('--finalize-existing', action='store_true')
    parser.add_argument('--rebuild', action='store_true', help='Replace only this version generated candidate')
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    if not BUNDLE.resolve().is_relative_to((ROOT/'outputs/releases').resolve()):
        raise RuntimeError('Release destination escapes workspace')
    staging = BUILD/'payload'
    if staging.exists():
        if not staging.resolve().is_relative_to(BUILD.resolve()):raise RuntimeError('Unsafe staging path')
        shutil.rmtree(staging)
    assets = stage_frontend(staging/'frontend', include_native=False, extra=('/js/hdr-layer.js',))
    if args.finalize_existing:
        finalize(assets, args.zip);return
    if BUNDLE.exists():
        if not args.rebuild:raise RuntimeError('Candidate exists; use --finalize-existing or --rebuild')
        print(f'Replacing generated candidate only: {BUNDLE.resolve()}', flush=True);shutil.rmtree(BUNDLE)
    DIST.mkdir(parents=True, exist_ok=True)
    archive = ROOT/'work/tools'/f'electron-v{ELECTRON_VERSION}-win32-x64.zip'
    if digest(archive) != ELECTRON_SHA256:raise RuntimeError('Official Electron ZIP checksum mismatch')
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            if not (BUNDLE/member.filename).resolve().is_relative_to(BUNDLE.resolve()):raise RuntimeError('Unsafe runtime archive path')
            if member.filename != 'resources/default_app.asar':source.extract(member, BUNDLE)
    (BUNDLE/'electron.exe').rename(BUNDLE/'YingXu.exe')
    app = BUNDLE/'resources/app';app.mkdir(parents=True)
    for name in ('main.cjs', 'preload.cjs', 'package.json'):shutil.copy2(ROOT/'desktop/electron'/name, app/name)
    inputs = {'host': 'electron', 'gitBase': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
              'uncommittedSourcesAtBuild': bool(subprocess.check_output(['git','status','--porcelain'], cwd=ROOT, text=True).strip()),
              'frontend': assets, 'pythonSources': source_hashes(),
              'desktopSources': {name:digest(ROOT/name) for name in DESKTOP_FILES}, 'qml': {}}
    INPUTS.write_text(json.dumps(inputs, indent=2)+'\n', encoding='utf8')
    version = staging/'windows-version.txt';version_resource(version)
    customize_executable(BUNDLE/'YingXu.exe', version)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed', '--noupx',
               '--name', 'YingXuBackend', '--icon', str(ROOT/'assets/subtitle_organizer.ico'), '--version-file', str(version),
               '--paths', str(ROOT), '--distpath', str(BUILD/'python-dist'), '--workpath', str(BUILD/'python-build'),
               '--specpath', str(BUILD), '--additional-hooks-dir', str(ROOT/'scripts/hooks'),
               '--add-data', f'{staging/"frontend"};frontend',
               '--add-data', f'{ROOT/"assets/subtitle_organizer.ico"};.']
    for module in ('PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtQml', 'PySide6.QtQuick',
                   'PySide6.QtQuickWidgets', 'PySide6.QtWebEngineQuick'):
        command += ['--exclude-module', module]
    command.append(str(ROOT/'scripts/desktop_backend_entry.py'))
    environment = os.environ.copy();system = Path(environment.get('SystemRoot', 'C:/Windows'))
    qt = Path(next(iter(importlib.util.find_spec('PySide6').submodule_search_locations)))
    environment['PATH'] = os.pathsep.join(map(str, (Path(sys.executable).parent, qt, system/'System32', system)))
    for name in ('PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QML_IMPORT_PATH'):environment.pop(name, None)
    print('Compiling private Python helper; log: work/build/electron/pyinstaller.log', flush=True)
    with (BUILD/'pyinstaller.log').open('wb') as log:subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
    shutil.copytree(BUILD/'python-dist/YingXuBackend', BUNDLE/'python')
    finalize(assets, args.zip)
    print(f'Portable app ready: {BUNDLE/"YingXu.exe"}', flush=True)


if __name__ == '__main__':main()
