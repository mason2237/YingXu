"""Verify the packaged, windowless reader with no developer runtime on PATH."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.media_fixtures import mkv,mp4
from yingxu.embedded_subtitles import assess


def main():
    exe=Path(sys.argv[1]).resolve(strict=True)
    target=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT/'work/test-results/stage18-packaged-reader.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    result={'passed':False,'checks':[],'physicalFramesVerified':False}
    with tempfile.TemporaryDirectory(prefix='embedded-exe-',dir=target.parent) as folder:
        folder=Path(folder)
        files=[mkv(folder/'中文 & 空格.mkv',[('zho','简体中文',False)]),mp4(folder/'english.mp4','eng'),
               mkv(folder/'未知语言.mkv',[('und','Full',False)]),
               mkv(folder/'独立双轨.mkv',[('zho','中文',False),('eng','English',False)])]
        original={path.name:path.read_bytes() for path in files}
        requests=[{'id':uuid4().hex,'path':str(path)} for path in files]
        payload=b''.join(json.dumps(item,ensure_ascii=True).encode('utf-8')+b'\n' for item in requests)
        environment=os.environ.copy()
        windows=Path(environment.get('SystemRoot','C:/Windows'))
        environment['PATH']=str(windows/'System32')+os.pathsep+str(windows)
        for key in ('PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QML2_IMPORT_PATH','QML_IMPORT_PATH','QTWEBENGINE_REMOTE_DEBUGGING'):
            environment.pop(key,None)
        completed=subprocess.run([str(exe),'--read-embedded-subtitles'],input=payload,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,cwd=folder,env=environment,timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        assert completed.returncode==0, f'Packaged reader exited {completed.returncode}; stderr={completed.stderr[:1000]!r}'
        replies=[json.loads(line) for line in completed.stdout.splitlines()]
        assert [item['id'] for item in replies]==[item['id'] for item in requests], 'Missing/invalid pipe replies'
        assert all(item['result']['status']=='ok' for item in replies), replies
        result['checks'].append('actual_windowed_exe_inherited_pipes_and_bundled_dll_without_developer_PATH')
        decide=lambda index,lang:assess(replies[index]['result'],{'enabled':True,'language':lang})['satisfied']
        assert decide(0,'chinese') and not decide(1,'chinese') and decide(1,'english')
        assert not decide(2,'chinese') and decide(2,'any')
        assert not decide(3,'bilingual')
        result['checks'].append('actual_mkv_mp4_languages_unknown_and_separate_dual_tracks')
        assert original=={path.name:path.read_bytes() for path in files}
        assert {path.name for path in folder.iterdir()}==set(original)
        result['checks'].append('no_extraction_no_video_changes_no_new_media_files')
        result.update(passed=True,replies=len(replies),stderrEmpty=not bool(completed.stderr))
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
