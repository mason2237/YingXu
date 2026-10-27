"""Generated subtitle archives through the real v2 host; no public site needed."""
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
import zipfile

from tests.integration.test_noqt_host import Client, ROOT

SRT='1\n00:00:01,000 --> 00:00:02,000\n你好 Hello\n'


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='inbox-',dir=ROOT/'work/test-results')
        self.root=Path(self.temp.name);self.media=self.root/'中文视频';self.media.mkdir()
        (self.media/'Atlas.S01E001.mkv').write_bytes(b'video unchanged')
        self.profile=self.root/'profile';self.client=Client(self.profile)
        self.addCleanup(self.temp.cleanup);self.addCleanup(lambda:self.client.close())
        self.scan()
    def scan(self):
        self.client.choose(self.media)
        self.client.call('embedded.configure',{'enabled':False,'language':'chinese'})
        folder=self.client.call('app.state')['summary']['folderId']
        self.client.job('scan.start',{'folderId':folder,'recursive':True,'move':False})
        summary=self.client.call('app.state')['summary'];self.context={'scanId':summary['scanId'],'revision':summary['revision']}
    def arm(self, manual=False):
        self.client.call('subtitle.open',self.context)
        task=self.client.call('online.query')['tasks'][0]['taskId']
        provider='zimuku' if manual else 'subhd'
        self.client.call('online.start',{'taskId':task,'query':'Atlas','provider':provider})
        search=next(frame for frame in reversed(self.client.events) if frame.get('type')=='browser.search')
        self.client.feed({'type':'browser.result','taskId':task,'effectId':search['effectId'],'generation':search['generation'],
                          **({'status':'manual','message':'需要人工核对'} if manual else {'status':'results','final':True,'raw':json.dumps({'status':'ready','rows':[
                              {'url':'https://subhd.me/a/TEST123','title':'Atlas','release':'Atlas S01E001','metadata':'中英双语'}]})})})
        if manual:
            self.client.call('online.usePage',{'taskId':task})
            capture=next(frame for frame in reversed(self.client.events) if frame.get('type')=='browser.capture')
            self.client.feed({**capture,'type':'browser.page','url':'https://zimuku.org/detail/1.html','title':'Atlas 字幕'})
            self.client.call('online.query')
        else:
            candidate=self.client.call('online.candidates',{'taskId':task})['rows'][0]
            self.client.call('online.select',{'taskId':task,'candidateId':candidate['candidateId']})
        with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_REQUIRED'):
            self.client.call('online.download',{'taskIds':[task],'acknowledged':False})
        self.client.call('online.download',{'taskIds':[task],'acknowledged':True})
        arm=next(frame for frame in reversed(self.client.events) if frame.get('type')=='browser.arm')
        return arm
    def offer(self,arm,malicious=False):
        offer=uuid4().hex;origin='https://zimuku.org' if 'zimuku' in arm['url'] else 'https://subhd.me'
        frame={'type':'download.offer','taskId':arm['taskId'],'effectId':arm['effectId'],'generation':arm['generation'],
               'offerId':offer,'url':origin+'/file.zip','page':arm['url'],'name':'中英字幕.zip','mime':'application/zip','total':1000}
        frame['url']='blob:'+origin+'/'+str(uuid4())
        self.client.feed(frame)
        accept=self.client.wait(lambda value:value.get('type')=='browser.accept')
        incoming=self.profile/'subtitles/.incoming';incoming.mkdir(exist_ok=True)
        with zipfile.ZipFile(incoming/(offer+'.part'),'w') as archive:
            archive.writestr('../escape.srt' if malicious else 'Atlas.chs.srt',SRT)
        self.client.feed({'type':'download.result','artifactId':accept['artifactId'],'status':'completed'})
        for _ in range(1000):
            state=self.client.call('app.state')
            if not state['busy']:break
        return accept['artifactId'],frame
    def test_download_extract_restart_import_confirm_execute_undo(self):
        identifier,frame=self.offer(self.arm(manual=True))
        records=self.client.call('online.downloads')['rows'];self.assertEqual(records[0]['status'],'ready')
        self.assertEqual(list(self.media.iterdir()),[self.media/'Atlas.S01E001.mkv'])
        self.client.feed({'type':'download.result','artifactId':identifier,'status':'completed'})
        self.assertEqual(self.client.call('online.downloads')['total'],1)
        self.client.close();self.client=Client(self.profile);self.scan()
        imported=self.client.job('online.import',{'artifactIds':[identifier],'acknowledged':True})
        self.assertEqual(imported['assigned'],1)
        summary=self.client.call('app.state')['summary'];context={'scanId':summary['scanId'],'revision':summary['revision']}
        details=self.client.details({**context,'rowId':'video-1'})
        self.assertEqual(details['state'],'需确认')
        self.assertTrue(details['subtitles'][0]['imported'])
        self.client.job('review.confirm',{**context,'rowId':'video-1'})
        context['revision']=self.client.call('app.state')['summary']['revision']
        preview=self.client.job('preview.create',context)
        result=self.client.job('organize.confirmAndStart',{'scanId':context['scanId'],'reviewRevision':context['revision'],
            'snapshotId':preview['snapshotId'],'confirmationToken':preview['confirmationToken'],'acknowledged':True})
        self.assertEqual(len(list(self.media.glob('*.srt'))),1)
        exported=self.root/'operation.json'
        request=self.client.send('result.export',{'recordId':result['batchId']})
        self.client.wait(lambda value:value.get('type')=='native' and value['requestId']==request)
        self.client.feed({'type':'native.result','requestId':request,'sessionId':self.client.sid,
                          'action':'result.export','path':str(exported)})
        self.client.response(request)
        for _ in range(1000):
            if not self.client.call('app.state')['busy']:break
        record=json.loads(exported.read_text(encoding='utf8'))
        self.assertEqual(record['format'],'yingxu.operations.v1')
        self.assertNotIn('ticket',record['run'])
        with self.assertRaisesRegex(RuntimeError,'CACHE_IN_USE'):
            self.client.call('online.discardDownload',{'artifactId':identifier,'acknowledged':True})
        compact=self.client.job('online.compactDownload',{'artifactId':identifier,'acknowledged':True})
        self.assertGreater(compact['releasedBytes'],0)
        self.assertEqual(self.client.call('online.downloads')['rows'][0]['status'],'compacted')
        undo=self.client.job('operation.undoPreview',{'runId':result['batchId']})
        self.client.job('operation.confirm',{'runId':undo['runId'],'snapshotId':undo['snapshotId'],
            'confirmationToken':undo['confirmationToken'],'acknowledged':True})
        self.assertEqual(len(list(self.media.glob('*.srt'))),0)
        self.assertEqual((self.media/'Atlas.S01E001.mkv').read_bytes(),b'video unchanged')
        self.assertLessEqual(self.client.max_bytes,8192)
    def test_archive_traversal_rejected_and_cache_discard_is_scoped(self):
        identifier,_frame=self.offer(self.arm(),malicious=True)
        self.assertEqual(self.client.call('online.downloads')['rows'][0]['status'],'interrupted')
        self.assertFalse((self.profile/'escape.srt').exists())
        self.client.call('online.discardDownload',{'artifactId':identifier,'acknowledged':True})
        self.assertEqual(self.client.call('online.downloads')['total'],0)
        self.assertTrue((self.media/'Atlas.S01E001.mkv').exists())
    def test_cancelled_grant_cannot_accept_late_download(self):
        arm=self.arm();self.client.call('online.cancel',{'taskId':arm['taskId']})
        self.client.feed({'type':'download.offer','taskId':arm['taskId'],'effectId':arm['effectId'],'generation':arm['generation'],
            'offerId':uuid4().hex,'url':'https://subhd.me/file.srt','page':arm['url'],'name':'test.srt','mime':'text/plain','total':10})
        self.client.wait(lambda value:value.get('type')=='browser.reject')
        self.assertEqual(self.client.call('online.downloads')['total'],0)


if __name__=='__main__':unittest.main()
