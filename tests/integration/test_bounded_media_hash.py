from pathlib import Path
from threading import Event
import os
import tempfile
import unittest
from unittest.mock import patch
from yingxu.adapters.media_identity import LocalMediaIdentity
from yingxu.domain.matching import ScanCancelled
from tests.integration.test_noqt_host import Client,ROOT


class BoundedMediaHashTests(unittest.TestCase):
    def test_opt_in_boundary_cache_and_same_size_time_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Film.mkv';path.write_bytes(b'A'*(128*1024));reader=LocalMediaIdentity()
            self.assertEqual(reader.read(path,include_hash=False)['bytesRead'],0)
            first=reader.read(path,include_hash=True);self.assertEqual(first['bytesRead'],128*1024)
            self.assertTrue(reader.read(path,include_hash=True)['cacheHit'])
            stamp=path.stat();path.write_bytes(b'B'*(128*1024));os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            changed=reader.read(path,include_hash=True);self.assertNotEqual(first['hash'],changed['hash']);self.assertFalse(changed['cacheHit'])
            stop=Event();stop.set()
            with self.assertRaises(ScanCancelled):reader.read(path,include_hash=True,should_stop=stop.is_set)
            path.write_bytes(b'x');self.assertEqual(reader.read(path,include_hash=True)['hashStatus'],'unsupported')

    def test_neighbour_nfo_never_inherited_and_read_change_rejected(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'Film.mkv';path.write_bytes(b'\0'*(128*1024))
            (root/'Other.nfo').write_text('<movie><id>tt1234567</id></movie>')
            reader=LocalMediaIdentity();self.assertEqual(reader.read(path,include_hash=False)['ids'],[])
            (root/'Film.nfo').write_text('<movie><id>tt1234567</id></movie>')
            self.assertEqual(reader.read(path,include_hash=False)['ids'][0]['id'],'tt1234567')
            (root/'Film.nfo').unlink();real=os.fstat;calls=[]
            def changed(fd):
                value=real(fd);calls.append(1)
                return SimpleNamespace(st_dev=value.st_dev,st_ino=value.st_ino,st_size=value.st_size,
                    st_mtime_ns=value.st_mtime_ns+int(len(calls)>1),st_ctime_ns=value.st_ctime_ns)
            with patch('yingxu.adapters.media_identity.os.fstat',side_effect=changed),self.assertRaisesRegex(Exception,'变化'):
                reader.read(path,include_hash=True)

    def test_manual_id_is_scoped_and_survives_restart(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/test-results') as directory:
            root=Path(directory);media=root/'media';media.mkdir();(media/'Film.mkv').write_bytes(b'generated');(media/'Other.mkv').write_bytes(b'generated')
            client=Client(root/'profile')
            try:
                client.choose(media);client.call('embedded.configure',{'enabled':False,'language':'chinese'})
                folder=client.call('app.state')['summary']['folderId'];client.job('scan.start',{'folderId':folder,'recursive':True,'move':False})
                state=client.call('app.state')['summary'];context={'scanId':state['scanId'],'revision':state['revision']}
                client.job('identity.set',{**context,'rowId':'video-1','imdbId':'tt1234567'});client.close();client=Client(root/'profile')
                state=client.call('app.state')['summary'];context={'scanId':state['scanId'],'revision':state['revision']}
                self.assertIn('tt1234567',' '.join(client.details({**context,'rowId':'video-1'})['basis']))
                self.assertNotIn('tt1234567',' '.join(client.details({**context,'rowId':'video-2'})['basis']))
            finally:client.close()
