from pathlib import Path
import tempfile
import unittest
from tests.integration.test_noqt_host import Client,ROOT


class SyncStagingTests(unittest.TestCase):
    def test_generated_candidate_restart_stage_confirm_and_undo(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            root=Path(directory);media=root/'media';media.mkdir();(media/'Film.2024.mkv').write_bytes(b'generated')
            original=media/'Film.2024.en.srt';raw=b'1\n00:00:01,000 --> 00:00:03,000\nGenerated text\n';original.write_bytes(raw)
            client=Client(root/'profile')
            def context():
                value=client.call('app.state')['summary'];return {'scanId':value['scanId'],'revision':value['revision'],'rowId':'video-1'}
            try:
                client.choose(media);client.call('embedded.configure',{'enabled':False,'language':'chinese'})
                folder=client.call('app.state')['summary']['folderId'];client.job('scan.start',{'folderId':folder,'recursive':True,'move':False})
                ctx=context();sub=client.details(ctx)['subtitles'][0]['subtitleId']
                result=client.job('sync.create',{**ctx,'subtitleId':sub,'syncMode':'manual','offsetMs':2000})
                self.assertEqual(result['status'],'succeeded');self.assertEqual(original.read_bytes(),raw)
                client.close();client=Client(root/'profile');ctx=context()
                self.assertEqual(client.call('sync.results',ctx)['total'],1)
                with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_REQUIRED'):client.call('sync.stage',{**ctx,'artifactId':result['artifactId'],'acknowledged':False})
                client.job('sync.stage',{**ctx,'artifactId':result['artifactId'],'acknowledged':True});ctx=context()
                self.assertEqual(client.details(ctx)['state'],'需确认');self.assertEqual(original.read_bytes(),raw)
                with self.assertRaisesRegex(RuntimeError,'CACHE_IN_USE'):client.call('sync.discard',{**ctx,'artifactId':result['artifactId'],'acknowledged':True})
                client.job('review.confirm',ctx);ctx=context();preview=client.job('preview.create',{'scanId':ctx['scanId'],'revision':ctx['revision']})
                done=client.job('organize.confirmAndStart',{'scanId':ctx['scanId'],'reviewRevision':ctx['revision'],'snapshotId':preview['snapshotId'],'confirmationToken':preview['confirmationToken'],'acknowledged':True})
                self.assertEqual(original.read_bytes(),raw)
                undo=client.job('operation.undoPreview',{'runId':done['batchId']});client.job('operation.confirm',{'runId':undo['runId'],'snapshotId':undo['snapshotId'],'confirmationToken':undo['confirmationToken'],'acknowledged':True})
                self.assertEqual(original.read_bytes(),raw)
            finally:client.close()
