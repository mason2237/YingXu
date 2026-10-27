"""A real CLI process composes the codec, use case, provider double and SQLite."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WorkflowPrototypeIntegration(unittest.TestCase):
    def setUp(self):
        output = ROOT / 'work/test-results'
        output.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='workflow-cli-', dir=output)
        self.database = Path(self.temp.name) / '中文任务' / 'tasks.sqlite3'

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *options):
        completed = subprocess.run(
            [sys.executable, '-S', str(ROOT / 'scripts/run_workflow_prototype.py'),
             '--database', str(self.database), *options],
            cwd=ROOT, capture_output=True, text=True, encoding='utf8',
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=15,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, '')
        return [json.loads(line) for line in completed.stdout.splitlines()]

    def test_default_demo_stops_before_consent_and_imports_no_qt(self):
        frames = self.run_cli()
        self.assertEqual(frames[0]['mode'], 'SIMULATED_ONLY')
        self.assertFalse(frames[-1]['qtImported'])
        self.assertEqual(frames[-1]['final']['phase'], 'selected')
        phases = [item['data']['task']['phase'] for item in frames if item.get('ok')]
        self.assertNotIn('downloading', phases)

    def test_simulated_completion_can_be_read_by_another_process_without_reset(self):
        frames = self.run_cli('--simulate-download')
        saved = frames[-1]['final']
        self.assertFalse(frames[-1]['qtImported'])
        self.assertEqual(saved['phase'], 'review_ready')
        self.assertEqual(self.run_cli('--show-task', saved['task_id']), [saved])
        second = self.run_cli()[-1]['final']
        self.assertNotEqual(second['task_id'], saved['task_id'])
        self.assertEqual(self.run_cli('--show-task', saved['task_id']), [saved])


if __name__ == '__main__':
    unittest.main()
