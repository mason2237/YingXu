"""Generated local and downloaded content through the real protocol and reader."""
import codecs
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.integration import test_subtitle_inbox as inbox
from yingxu.adapters.subtitle_reader import LocalSubtitleReader
from yingxu.domain.subtitle_document import MAX_BYTES
from yingxu.domain.subtitle_quality import analyze
from yingxu.domain.errors import ProtocolError


class SubtitleReaderIntegration(unittest.TestCase):
    def test_boms_legacy_choices_and_size_limit_do_not_change_original_bytes(self):
        text='1\n00:00:01,000 --> 00:00:02,000\n中文字幕\n'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'generated.srt';reader=LocalSubtitleReader()
            for encoding in ('utf-8-sig','utf-16','utf-32'):
                original=text.encode(encoding);path.write_bytes(original)
                read=reader.read(path);self.assertEqual(read.text,text);self.assertEqual(path.read_bytes(),original)
            raw=text.encode('gb18030');path.write_bytes(raw)
            read=reader.read(path)
            self.assertIsNone(read.text);self.assertIn('gb18030',[c[0] for c in read.candidates])
            self.assertEqual(analyze(read).status,'encoding_required')
            self.assertEqual(reader.read(path,encoding='gb18030').text,text)
            self.assertEqual(path.read_bytes(),raw)
            path.write_bytes(b'x'*(MAX_BYTES+1));read=reader.read(path)
            self.assertIsNone(read.text);self.assertIn('8 MiB',read.issue)

    def test_wide_text_without_bom_and_truncation_require_attention(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'text.srt';reader=LocalSubtitleReader()
            path.write_bytes('1\n00:00:01,000 --> 00:00:02,000\nText\n'.encode('utf-16-le'))
            self.assertIsNone(reader.read(path).text)
            self.assertEqual(analyze(reader.read(path,encoding='utf-16-le')).status,'clean')
            path.write_bytes(codecs.BOM_UTF16_LE+b'\x41')
            self.assertIsNone(reader.read(path).text)
            with patch.object(Path,'is_symlink',return_value=True):
                with self.assertRaises(ProtocolError):reader.read(path)


class SubtitleQualityHostTests(unittest.TestCase):
    setUp=inbox.InboxTests.setUp
    scan=inbox.InboxTests.scan
    arm=inbox.InboxTests.arm
    offer=inbox.InboxTests.offer

    def test_errors_page_and_stale_context_preserve_list_and_preview(self):
        path=self.media/'Atlas.S01E001.chs.srt'
        path.write_text('1\n00:00:03,000 --> 00:00:01,000\n<script>window.bad=true</script>\n',encoding='utf-8')
        self.scan();before=path.read_bytes()
        details=self.client.details({**self.context,'rowId':'video-1'})
        params={**self.context,'rowId':'video-1','subtitleId':details['subtitles'][0]['subtitleId']}
        preview=self.client.job('preview.create',self.context)
        result=self.client.job('review.quality',params)
        self.assertGreater(result['errors'],0)
        page=self.client.call('review.qualityPage',{**params,'reportId':result['reportId']})
        self.assertTrue(any(i['code']=='REVERSED_TIME' for i in page['entries']))
        self.assertTrue(any('<script>' in i['excerpt'] for i in page['entries']))
        self.assertEqual(self.client.call('review.query',self.context)['total'],1)
        self.client.call('preview.query',{'snapshotId':preview['snapshotId']})
        with self.assertRaisesRegex(RuntimeError,'INVALID_REQUEST'):
            self.client.call('review.quality',{**params,'path':str(path)})
        self.client.job('review.skip',{**self.context,'rowId':'video-1','skipped':True})
        with self.assertRaisesRegex(RuntimeError,'STALE_REVIEW'):
            self.client.call('review.qualityPage',{**params,'reportId':result['reportId']})
        self.assertEqual(path.read_bytes(),before);self.assertLessEqual(self.client.max_bytes,8192)

    def test_downloaded_invalid_srt_is_not_presented_as_quality_clean(self):
        with patch.object(inbox,'SRT','1\n00:00:02,000 --> 00:00:01,000\nGenerated text\n'):
            identifier,_frame=self.offer(self.arm())
        files=self.client.call('online.qualityFiles',{'artifactId':identifier})
        self.assertGreater(files['entries'][0]['quality']['errors'],0)
        params={'artifactId':identifier,'fileIndex':0}
        job=self.client.call('online.quality',params)
        for _ in range(500):
            status=self.client.call('online.qualityResult',{'artifactId':identifier,'jobId':job['jobId']})
            if status['status']!='running':break
            time.sleep(.01)
        self.assertEqual(status['status'],'completed')
        report=status['report'];self.assertGreater(report['errors'],0)
        page=self.client.call('online.qualityPage',{**params,'reportId':report['reportId']})
        self.assertTrue(any(i['code']=='REVERSED_TIME' for i in page['entries']))
        self.assertEqual(list(self.media.iterdir()),[self.media/'Atlas.S01E001.mkv'])
        self.assertLessEqual(self.client.max_bytes,8192)

    def test_many_unicode_issues_round_trip_in_variable_size_pages(self):
        path=self.media/'Atlas.S01E001.chs.srt'
        text='\n'.join(f'{index}\n00:00:03,000 --> 00:00:01,000\n'+('中🙂'*100)+'\n' for index in range(200))
        path.write_text(text,encoding='utf-8');self.scan();before=path.read_bytes()
        details=self.client.details({**self.context,'rowId':'video-1'})
        params={**self.context,'rowId':'video-1','subtitleId':details['subtitles'][0]['subtitleId']}
        report=self.client.job('review.quality',params);actual=[];small_page=False
        while len(actual)<report['issueCount']:
            page=self.client.call('review.qualityPage',{**params,'reportId':report['reportId'],'offset':len(actual),'limit':200})
            self.assertTrue(page['entries']);actual.extend(page['entries'])
            small_page|=len(page['entries'])<min(200,page['total']-page['offset'])
            self.assertEqual(page['nextOffset'],len(actual) if len(actual)<page['total'] else None)
        self.assertTrue(small_page);self.assertEqual(len(actual),report['issueCount'])
        self.assertEqual(sum(i['code']=='REVERSED_TIME' for i in actual),200)
        self.assertLessEqual(self.client.max_bytes,8192);self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
