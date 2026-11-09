"""Freeze the reviewed optional worker, merging identical Python runtime files."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bundle=Path(sys.argv[1]).resolve();version=Path(sys.argv[2]).resolve()
    if not bundle.is_relative_to((ROOT/'outputs/releases').resolve()):raise ValueError('Invalid bundle destination')
    build=ROOT/'work/build/sync';build.mkdir(parents=True,exist_ok=True)
    requirements=[]
    for line in (ROOT/'requirements-sync.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            name,pinned=line.split('==');actual=importlib.metadata.version(name)
            if actual!=pinned:raise RuntimeError('Optional worker version mismatch: '+name)
            requirements.append((name,pinned))
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed','--noupx',
        '--name','YingXuSync','--paths',str(ROOT),'--distpath',str(build/'dist'),'--workpath',str(build/'build'),
        '--specpath',str(build),'--version-file',str(version),'--icon',str(ROOT/'assets/subtitle_organizer.ico'),
        '--copy-metadata','webrtcvad-wheels','--additional-hooks-dir',str(ROOT/'scripts/hooks')]
    for module in ('auditok','cchardet','chardet','imageio_ffmpeg','PySide6','PyQt5','PyQt6','shiboken6','tkinter','torch','whisper','onnxruntime'):
        command+=['--exclude-module',module]
    command.append(str(ROOT/'scripts/sync_worker_entry.py'))
    subprocess.run(command,cwd=ROOT,check=True)
    source=build/'dist/YingXuSync';target=bundle/'python'
    for path in source.rglob('*'):
        if not path.is_file():continue
        # pip's local-wheel installation provenance exposes build-machine paths.
        # Reviewed upstream wheel hashes are supplied separately in SYNC_RUNTIME.
        if path.name=='direct_url.json' and path.parent.name.endswith('.dist-info'):continue
        relative=path.relative_to(source);destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists() and destination.name=='base_library.zip':
            values={}
            for archive in (destination,path):
                with zipfile.ZipFile(archive) as z:
                    for name in z.namelist():
                        data=z.read(name)
                        if name in values and values[name]!=data:raise RuntimeError('Shared standard library conflict: '+name)
                        values[name]=data
            with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for name,data in values.items():z.writestr(name,data)
        elif destination.exists():
            if digest(destination)!=digest(path):raise RuntimeError('Shared runtime conflict: '+str(relative))
        else:shutil.copy2(path,destination)
    legal=bundle/'licenses/sync-runtime';legal.mkdir(parents=True,exist_ok=True);inventory=[]
    origins=json.loads((ROOT/'work/tools/sync-install-review.json').read_text());selected_origins=[]
    for name,pinned in requirements:
        prefix=name.casefold().replace('-','_')+'-'+pinned+'-'
        origin=next((o for o in origins if o['wheel'].casefold().startswith(prefix)),None)
        if origin is None:raise RuntimeError('Missing reviewed wheel origin: '+name)
        selected_origins.append(origin)
        distribution=importlib.metadata.distribution(name);files=[]
        for relative in distribution.files or []:
            if relative.name.lower().startswith(('license','licence','copying','notice','authors')) and relative.suffix.lower() not in {'.py','.pyc'}:
                destination=legal/name/relative
                if not destination.resolve().is_relative_to((legal/name).resolve()):raise ValueError('Invalid license destination')
                destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(distribution.locate_file(relative),destination);files.append(destination.relative_to(bundle).as_posix())
        if not files:raise RuntimeError('Missing optional runtime license: '+name)
        if name.casefold()=='tqdm':
            mpl=ROOT/'licenses/MPL-2.0.txt'
            if digest(mpl)!='3f3d9e0024b1921b067d6f7f88deb4a60cbe7a78e76c64e3f1d7fc3b779b9d04':raise RuntimeError('Official MPL text differs from reviewed source')
            destination=legal/name/'MPL-2.0.txt';shutil.copy2(mpl,destination);files.append(destination.relative_to(bundle).as_posix())
            source_dir=legal/name/'source'
            for relative in distribution.files or []:
                if relative.suffix=='.py' and relative.parts[0]=='tqdm':
                    destination=source_dir/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(distribution.locate_file(relative),destination)
            (source_dir/'SOURCE_NOTICE.txt').write_text('Unmodified tqdm 4.67.1 Python source, supplied under its original MPL-2.0/MIT terms.\nUpstream: https://github.com/tqdm/tqdm/tree/v4.67.1\nThese independent source files are not subject to YingXu noncommercial restrictions.\n',encoding='utf8')
        inventory.append({'name':name,'version':pinned,'licenseFiles':files})
    from PyInstaller.archive.readers import CArchiveReader
    archive=CArchiveReader(str(target/'YingXuSync.exe'));modules=sorted(archive.open_embedded_archive('PYZ.pyz').toc)
    forbidden=[n for n in modules if n.lower().startswith(('auditok','pyside','pyqt','shiboken','tkinter','torch','whisper','imageio_ffmpeg','cchardet','chardet'))]
    if forbidden:raise RuntimeError('Forbidden optional modules: '+str(forbidden))
    manifest={'engine':'ffsubsync-0.5.1','vad':'webrtc','dependencies':inventory,'reviewedWheelOrigins':selected_origins,
        'excluded':['auditok','chardet','faust-cchardet','imageio-ffmpeg','FFmpeg binary'],'ffmpegRedistributed':False,
        'moduleCount':len(modules),'qtModules':[],'sharedPythonRuntime':True,'localInstallMetadataOmitted':True,'workerSha256':digest(target/'YingXuSync.exe')}
    (bundle/'SYNC_RUNTIME.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    print('Optional worker ready; shares Python/_internal, no FFmpeg binary or GPL auditok.',flush=True)


if __name__=='__main__':main()
