"""Real HTTP responses on a local fixture server; no public website claims."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
from pathlib import Path
from threading import Thread
import unittest
from urllib.request import build_opener

from yingxu.adapters.http_transfer import transfer, digest
from yingxu.domain.matching import ScanCancelled

BODY = b'1\n00:00:01,000 --> 00:00:02,000\nHello / subtitle\n'*4000


class Server(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        self.server.requests.append(dict(self.headers))
        mode = self.path.strip('/')
        offset = int(self.headers.get('Range', 'bytes=0-')[6:-1])
        payload = BODY
        if mode == 'expired':
            self.send_error(403); return
        if mode == '416' and offset:
            self.send_response(416); self.end_headers(); return
        ranged = offset and mode != '200'
        if mode == 'changed': payload = b'X'+BODY[1:]
        self.send_response(206 if ranged else 200)
        self.send_header('Content-Type', 'text/html' if mode == 'html' else 'text/plain')
        if mode != 'novalidator': self.send_header('ETag', '"v2"' if mode == 'changed' else '"v1"')
        if ranged:
            start = offset+1 if mode == 'bad-range' else offset
            self.send_header('Content-Range', f'bytes {start}-{len(payload)-1}/{len(payload)}')
        else: offset = 0
        self.send_header('Content-Length', str(len(payload)-offset))
        self.end_headers()
        if mode == 'drop':
            self.wfile.write(payload[offset:offset+1024]); self.wfile.flush(); self.close_connection=True
        else:
            try: self.wfile.write(payload[offset:])
            except (BrokenPipeError, ConnectionResetError): pass


class TransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Server)
        cls.server.requests = []
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'subtitle.srt'
        self.state = {}; self.server.requests.clear()
    def run_transfer(self, mode='ok', stop=lambda:False):
        record = {'url': f'http://127.0.0.1:{self.server.server_port}/{mode}', 'http': self.state}
        def save(state): self.state = state
        return transfer(record, self.path, save, stop, lambda *args:None, opener=build_opener())
    def partial(self, validator=True):
        self.path.write_bytes(BODY[:1000])
        self.state = {'offset':1000, 'etag':'"v1"' if validator else '', 'modified':'', 'total':len(BODY), 'digest':digest(self.path)}
    def test_verified_206_resumes(self):
        self.partial(); result=self.run_transfer()
        self.assertTrue(result['resumed']);self.assertEqual(self.path.read_bytes(), BODY)
        self.assertEqual(self.server.requests[0]['If-Range'], '"v1"')
    def test_200_and_416_restart_without_joining_objects(self):
        for mode in ('200','416','changed'):
            with self.subTest(mode=mode):
                self.partial(); result=self.run_transfer(mode)
                self.assertFalse(result['resumed'])
                self.assertEqual(self.path.read_bytes(), b'X'+BODY[1:] if mode=='changed' else BODY)
    def test_no_validator_does_not_send_range(self):
        self.partial(False);self.run_transfer('novalidator')
        self.assertNotIn('Range',self.server.requests[-1]);self.assertEqual(self.path.read_bytes(),BODY)
    def test_range_mismatch_is_not_appended(self):
        self.partial()
        with self.assertRaisesRegex(ValueError,'区间'):self.run_transfer('bad-range')
        self.assertEqual(self.path.read_bytes(),BODY[:1000])
    def test_changed_buffer_refuses_network(self):
        self.partial();self.path.write_bytes(b'Z'*1000)
        with self.assertRaisesRegex(ValueError,'内容已变化'):self.run_transfer()
        self.assertEqual(self.server.requests,[])
    def test_drop_preserves_a_hashed_checkpoint_and_retries(self):
        with self.assertRaises(ValueError):self.run_transfer('drop')
        self.assertGreater(self.state['offset'],0)
        self.assertEqual(self.state['digest'],digest(self.path))
        self.run_transfer();self.assertEqual(self.path.read_bytes(),BODY)
    def test_uncommitted_crash_tail_is_not_appended(self):
        self.partial()
        with self.path.open('ab') as stream:stream.write(b'crash tail')
        self.run_transfer();self.assertEqual(self.path.read_bytes(),BODY)
    def test_expired_link_and_html_rejected(self):
        for mode in ('expired','html'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.run_transfer(mode)
        self.assertFalse(self.path.exists())
    def test_cancel_keeps_valid_bytes(self):
        checks=[]
        def stop():checks.append(1);return len(checks)>2
        with self.assertRaises(ScanCancelled):self.run_transfer(stop=stop)
        self.assertGreater(self.state['offset'],0)
        self.assertEqual(self.state['digest'],digest(self.path))


if __name__=='__main__':unittest.main()
