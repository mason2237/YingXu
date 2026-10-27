"""Qt-free teaching prototype. No network, media access or real validation.

Only the workflow database is written. A fake provider supplies synthetic DTOs;
--simulate-download drives trusted completion events with a fake artifact ID.
It does not test a website, download bytes, inspect a subtitle or import a file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yingxu.adapters.sqlite_workflow_store import SQLiteWorkflowStore
from yingxu.application.subtitles import SubtitleWorkflow
from yingxu.desktop.protocol import decode_command, encode_receipt
from yingxu.domain.models import WorkflowCommand, WorkflowError, canonical_json
from yingxu.ports.subtitle_provider import (
    DownloadSourceResult, InteractionMode, ProviderCapabilities, ProviderStatus,
    SearchRequest, SearchResult, SubtitleCandidate,
)


class FakeSubtitleProvider:
    """Replace this adapter, not the workflow, when teaching a real provider."""
    provider_id = 'fake'
    capabilities = ProviderCapabilities(
        search=InteractionMode.AUTOMATIC, download=InteractionMode.AUTOMATIC,
        resumable_download=False,
    )

    def search(self, request: SearchRequest) -> SearchResult:
        candidate = SubtitleCandidate('demo-candidate', self.provider_id,
                                      request.title + ' / synthetic example', request.language)
        return SearchResult(ProviderStatus.READY, (candidate,))

    def resolve_download(self, candidate_id: str) -> DownloadSourceResult:
        if candidate_id != 'demo-candidate':
            return DownloadSourceResult(ProviderStatus.FAILED, message='Unknown fake candidate')
        return DownloadSourceResult(ProviderStatus.READY, source_ref='demo-artifact')


def snapshot(task):
    value = task.to_dict()
    value.pop('data_json')
    value['data'] = task.data
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path,
                        default=ROOT / 'work/test-results/workflow-prototype/tasks.sqlite3')
    parser.add_argument('--show-task', help='Read a saved task without advancing it')
    parser.add_argument('--simulate-download', action='store_true',
                        help='Simulate consent, transfer, validation and preparation; no files involved')
    args = parser.parse_args()
    store = SQLiteWorkflowStore(args.database)
    try:
        workflow = SubtitleWorkflow(store)
        if args.show_task:
            print(json.dumps(snapshot(workflow.get_task(args.show_task)), ensure_ascii=False))
            return 0

        provider = FakeSubtitleProvider()
        task = workflow.create_task('demo-workspace', 1)
        print(json.dumps({'mode': 'SIMULATED_ONLY', 'taskId': task.task_id,
                          'database': str(args.database), 'phase': task.phase.value}))

        def send(action, params=None, *, internal=False):
            nonlocal task
            params = params or {}
            if internal:
                # Only trusted application adapters create these callbacks.
                command = WorkflowCommand(
                    uuid4().hex, task.task_id, action, task.revision,
                    task.workspace_id, task.review_revision,
                    canonical_json(params), task.active_effect_id,
                )
            else:
                command = decode_command(json.dumps({
                    'v': 2, 'id': uuid4().hex, 'taskId': task.task_id,
                    'action': action, 'expectedRevision': task.revision,
                    'workspaceId': task.workspace_id, 'reviewRevision': task.review_revision,
                    'params': params,
                }))
            receipt = workflow.dispatch(command)
            task = receipt.task
            print(encode_receipt(command.command_id, receipt))

        request = SearchRequest('Example film')
        send('search', {'query': request.title, 'provider_id': provider.provider_id})
        result = provider.search(request)
        send('results', {'candidates': [item.to_dict() for item in result.candidates]}, internal=True)
        send('select', {'candidate_id': result.candidates[0].candidate_id})

        if args.simulate_download:
            send('confirm_download', {'acknowledged': True})
            source = provider.resolve_download(result.candidates[0].candidate_id)
            artifact = {'artifact_id': source.source_ref}
            for action in ('downloaded', 'verified', 'prepared'):
                send(action, artifact, internal=True)

        qt_loaded = any(name.startswith(('PySide6', 'PyQt')) for name in sys.modules)
        print(json.dumps({'final': snapshot(task), 'qtImported': qt_loaded}, ensure_ascii=False))
        return 0
    except WorkflowError as error:
        print(json.dumps({'error': {'code': error.code, 'message': error.message}},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
