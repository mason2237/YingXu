"""The desktop wire is UTF-8 even when the host starts with Windows legacy pipes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows inherited-stream regression')
class UTF8StreamContracts(unittest.TestCase):
    def test_existing_legacy_text_stream_is_reconfigured(self):
        source = """import sys,json
sys.stdout.reconfigure(encoding='gb18030')
from yingxu.desktop.host import inherited_streams
inherited_streams()
print(json.dumps({'name':'中文字幕','state':'需确认'},ensure_ascii=False))
"""
        result = subprocess.run([sys.executable, '-X', 'utf8=0', '-c', source],
                                cwd=Path(__file__).resolve().parents[2], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.decode('utf8')), {'name':'中文字幕','state':'需确认'})


if __name__ == '__main__':
    unittest.main()
