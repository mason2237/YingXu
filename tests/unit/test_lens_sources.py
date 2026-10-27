"""Audited upstream provenance/import closure; no third-party build scripts."""
import hashlib
import json
from pathlib import Path
import re
import unittest

from yingxu.desktop.assets import ASSETS

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'frontend/vendor/design-systems/lens'


class LensSourceContracts(unittest.TestCase):
    def test_original_files_match_fixed_upstream_git_blobs(self):
        manifest = json.loads((VENDOR / 'ORIGIN.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['commit'], '7a424c93b9be13cf835b91ea67495fec2ec0584e')
        self.assertEqual(len(manifest['files']), 19)
        for item in manifest['files']:
            with self.subTest(path=item['local']):
                data = (VENDOR / item['local']).read_bytes()
                blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                self.assertEqual(blob, item['gitBlob'])
                self.assertEqual(item['mode'], 'unchanged')

    def test_module_imports_and_styles_are_local_and_allowlisted(self):
        for source in VENDOR.rglob('*.js'):
            body = source.read_text(encoding='utf-8')
            # Match actual module declarations, not usage snippets in strings.
            for target in re.findall(r"^(?:import\s+[^;\n]*?\s+from\s+|export\s+[^;\n]*?\s+from\s+)['\"]([^'\"]+)['\"]", body, re.MULTILINE):
                with self.subTest(source=source.name, target=target):
                    self.assertTrue(target.startswith('.'))
                    dependency = (source.parent / target).resolve()
                    self.assertTrue(dependency.is_relative_to(VENDOR.resolve()))
                    self.assertTrue(dependency.is_file())
                    key = '/' + dependency.relative_to(ROOT / 'frontend').as_posix()
                    self.assertIn(key, ASSETS)
        for css in VENDOR.glob('*.css'):
            self.assertNotRegex(css.read_text(encoding='utf-8'), r'url\s*\(|@import')

    def test_runtime_has_no_network_or_arbitrary_code_execution(self):
        pattern = r'\b(?:fetch|eval|XMLHttpRequest|WebSocket)\s*\(|new\s+Function\b|document\.write\s*\('
        for source in VENDOR.rglob('*.js'):
            self.assertNotRegex(source.read_text(encoding='utf-8'), pattern)
        adapter = (ROOT / 'frontend/js/components/lens-runtime.js').read_text(encoding='utf-8')
        self.assertIn('storage: null', adapter)
        self.assertIn('audio = false', adapter)
        self.assertTrue((VENDOR.parent / 'LICENSE').is_file())
