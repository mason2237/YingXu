from pathlib import Path
import tempfile
import unittest
from tests.integration.test_noqt_host import ROOT,Client
from tests.unit.test_content_matching import document
from yingxu.domain.sync_models import stamp


class ContentOptInTests(unittest.TestCase):
    def test_only_explicit_compare_returns_evidence_and_keeps_review_and_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            root=Path(directory);media=root/'media';media.mkdir();(media/'Film.2024.mkv').write_bytes(b'generated untouched video')
            doc=document();text='\n\n'.join(f'{i+1}\n{stamp(c.start,"srt","00:00:00,000")} --> {stamp(c.end,"srt","00:00:00,000")}\n{c.text}' for i,c in enumerate(doc.cues))
            (media/'Film.2024.en.srt').write_text(text,encoding='utf8');(media/'Reference.en.srt').write_text(text,encoding='utf8')
            before={p:p.read_bytes() for p in media.iterdir()};client=Client(root/'profile')
            try:
                client.choose(media);client.call('embedded.configure',{'enabled':False,'language':'chinese'});folder=client.call('app.state')['summary']['folderId']
                client.job('scan.start',{'folderId':folder,'recursive':True,'move':False});summary=client.call('app.state')['summary'];ctx={'scanId':summary['scanId'],'revision':summary['revision'],'rowId':'video-1'}
                refs=client.call('sync.references',ctx)['rows'];ref=next(r['subtitleId'] for r in refs if r['name']=='Reference.en.srt')
                old=client.details(ctx);result=client.job('content.compare',{**ctx,'referenceId':ref})
                self.assertEqual(result['meta']['videoBytesRead'] if 'meta' in result else result['videoBytesRead'],0)
                self.assertEqual(client.details(ctx)['subtitles'],old['subtitles']);self.assertEqual(before,{p:p.read_bytes() for p in before})
            finally:client.close()
