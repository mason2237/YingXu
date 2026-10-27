"""Qt-free release resources, attribution and source identity checks."""
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

from scripts.build_utils import ROOT, digest, hash_bundle, python_sources, stage_frontend, version_resource
from yingxu.version import VERSION


RUNTIME_PACKAGES = ('pymediainfo',)
BUILD_PACKAGES = ('pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'packaging', 'pefile', 'pywin32-ctypes', 'setuptools')
LEGAL_FILES = ('PolyForm-Noncommercial-1.0.0.txt', 'NotoSansSC-OFL.txt',
               'pymediainfo-MIT.txt', 'MediaInfo-License.html', 'MediaInfo-ORIGIN.json', 'electron-LICENSE.txt')


def release_documents(folder, assets, *, inputs_path, source_hashes, **unused):
    inputs = json.loads(inputs_path.read_text(encoding='utf8'))
    if inputs['frontend'] != assets or inputs['pythonSources'] != source_hashes:
        raise RuntimeError('Sources changed after freezing; rebuild the helper')
    for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md'):
        shutil.copy2(ROOT/name, folder/name)
    for name in ('README.zh-CN.md','LICENSE_STATUS.md','RELEASE_NOTES.md'):
        shutil.copy2(ROOT/'release'/name, folder/name)
    licenses = folder/'licenses';licenses.mkdir(exist_ok=True)
    provenance = json.loads((ROOT/'licenses/SOURCES.json').read_text(encoding='utf8'))
    selected = set(LEGAL_FILES)
    records = [value for value in provenance['documents'] if value['file'] in selected]
    for value in records:
        if digest(ROOT/'licenses'/value['file']) != value['sha256']:
            raise RuntimeError('License provenance changed: '+value['file'])
    if (ROOT/'LICENSE').read_bytes() != (ROOT/'licenses/PolyForm-Noncommercial-1.0.0.txt').read_bytes():
        raise RuntimeError('Original license differs from official PolyForm text')
    for name in LEGAL_FILES:
        shutil.copy2(ROOT/'licenses'/name, licenses/name)
    (licenses/'SOURCES.json').write_text(json.dumps({'documents':records},indent=2)+'\n',encoding='utf8')
    upstream = ROOT/'frontend/vendor/design-systems'
    for name in ('LICENSE','UPSTREAM.md','lens/ORIGIN.json'):
        shutil.copy2(upstream/name, licenses/('design-systems-'+Path(name).name))
    shutil.copy2(ROOT/'frontend/assets/fonts/ORIGIN.json', licenses/'NotoSansSC-ORIGIN.json')
    font = json.loads((ROOT/'frontend/assets/fonts/ORIGIN.json').read_text(encoding='utf8'))
    if digest(ROOT/'frontend/assets/fonts/NotoSansSC.ttf') != font['fontSHA256']:
        raise RuntimeError('Font differs from reviewed unmodified upstream asset')
    origin = json.loads((upstream/'lens/ORIGIN.json').read_text(encoding='utf8'))
    import hashlib
    for item in origin['files']:
        data = (upstream/'lens'/item['local']).read_bytes()
        if hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest() != item['gitBlob']:
            raise RuntimeError('Unchanged upstream Lens module changed: '+item['local'])
    inventory = []
    for name in (*RUNTIME_PACKAGES,*BUILD_PACKAGES):
        distribution = importlib.metadata.distribution(name)
        item = {'name':name,'version':distribution.version,
                'declaredLicense':distribution.metadata.get('License-Expression') or distribution.metadata.get('License'),
                'role':'runtime' if name in RUNTIME_PACKAGES else 'build','licenseFiles':[]}
        for relative in distribution.files or []:
            if relative.name.lower().startswith(('license', 'copying', 'notice', 'authors')) and relative.suffix.lower() not in {'.py', '.pyc'}:
                source = Path(distribution.locate_file(relative))
                target = licenses/name/relative
                if not target.resolve().is_relative_to((licenses/name).resolve()):
                    raise RuntimeError('License path escapes distribution')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source,target);item['licenseFiles'].append(target.relative_to(folder).as_posix())
        inventory.append(item)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Missing interpreter license')
    shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
    documentation = folder/'docs';documentation.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'docs/DEPENDENCIES.md',documentation)
    shutil.copy2(ROOT/'architecture.txt',folder)
    manifest = {'version':VERSION,'status':'candidate','builtAt':datetime.now(timezone.utc).isoformat(),
                **inputs,'python':sys.version,'dependencies':inventory,'applicationLicense':'PolyForm-Noncommercial-1.0.0',
                'bundledQtModules':[],'runtime':'Electron + Python','cleanWindowsTested':False,
                'licenseAudit':'Basic compatibility, attribution and required-text review; see LICENSE_STATUS.md.'}
    (folder/'BUILD_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
