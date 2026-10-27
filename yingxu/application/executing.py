"""Confirmed file workflow, recovery assessment and compensating undo. No GUI/IPC."""
from datetime import datetime, timezone
from pathlib import Path

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled
from ..domain.operations import status_for
from ..ports.operation_journal import OperationJournal
from ..ports.transaction_files import TransactionFiles


LABELS = {'success': '成功', 'blocked': '已阻止', 'error': '失败', 'cancelled': '未执行',
          'skipped': '跳过', 'unmatched': '未匹配', 'unchanged': '无需变更', 'pending': '待处理'}
COMMIT_STEPS = {'committing', 'committed', 'deleting', 'applied'}


def now():
    return datetime.now(timezone.utc).isoformat()


class Execution:
    def __init__(self, journal: OperationJournal, files: TransactionFiles, *, checkpoint=None):
        self.journal, self.files = journal, files
        self.checkpoint = checkpoint or (lambda point, run_id, index: None)
        self.interrupted = journal.interrupt_running()
        journal.expire_tickets()

    def invalidate(self):
        self.journal.expire_tickets()

    def freeze(self, snapshot, context, stop, report):
        specs, sources, targets = [], set(), set()
        for index, item in enumerate(snapshot.items):
            check_cancelled(stop)
            report(index, len(snapshot.items), '核对文件身份与内容…', 'preview')
            spec = self.files.freeze(item, stop)
            if spec['action'] == 'rename':
                source, target = str(Path(spec['source'])).casefold(), str(Path(spec['target'])).casefold()
                if source in sources or target in targets:
                    raise ProtocolError('STALE_PLAN', '计划存在重复的源或目标，未提交执行。')
                sources.add(source)
                targets.add(target)
            specs.append(spec)
        identifier = self.journal.create(specs, context)
        for item in self.journal.bundle(identifier)[1]:
            observed = {'state': 'source', 'message': '原字幕已核对；确认后整理。'} if item['spec']['action'] == 'rename' else {'state': 'unchanged', 'message': ''}
            self.journal.update_item(identifier, item['n'], observed=observed)
        return identifier

    def _managed(self, item, run_id):
        if item['buffer'] and (Path(item['buffer']).parent != self.files.buffer_root or
                               not Path(item['buffer']).name.startswith(f'{run_id}-{item["n"]}-')):
            raise ProtocolError('CORRUPT_JOURNAL', '备份路径与日志归属不符，未自动继续。')
        if item['temp'] and (Path(item['temp']).parent != Path(item['spec']['target']).parent or
                             not Path(item['temp']).name.startswith(f'.yingxu-{run_id}-{item["n"]}-')):
            raise ProtocolError('CORRUPT_JOURNAL', '临时路径与日志归属不符，未自动继续。')

    def _owned_version(self, path, owned, complete, expected):
        if not path or not owned:
            return None
        version = self.files.inspect(path)
        if (version and version['identity'] == owned['identity'] and version['size'] == expected['size']
                and version['digest'] == expected['digest'] and (complete is None or version == complete)):
            return version
        return None

    def assess(self, run, item):
        spec = item['spec']
        if spec['action'] != 'rename':
            return {'state': 'unchanged', 'message': ''}
        try:
            self._managed(item, run['id'])
            if self.files.parent(spec['target']) != spec['target_parent']:
                raise ProtocolError('DIRECTORY_CHANGED', '目标目录已被替换。')
            if spec['video_version'] is not None and self.files.inspect(spec['video'], digest=False) != spec['video_version']:
                raise ProtocolError('FILE_CHANGED', '视频已变化或不可用，请保留缓存并人工核对。')
            source = self.files.inspect(spec['source'])
            target = self.files.inspect(spec['target'])
            expected = item['post_version']
            if expected is None and item['step'] in COMMIT_STEPS:
                expected = spec['source_version'] if item['mode'] == 'rename' else item['temp_version']
            if target is not None:
                if expected is None or target != expected:
                    raise ProtocolError('TARGET_EXISTS', '目标已存在或已被修改，未覆盖它。')
                if source is None:
                    return {'state': 'done', 'message': '目标完整且原位置已空，不会重复整理。', 'target_version': target}
                if item['mode'] not in {'copy', 'restore'} or source != spec['source_version']:
                    raise ProtocolError('FILE_CHANGED', '目标已提交，但原位置出现不同文件，未自动删除。')
                if self.files.parent(spec['source']) != spec['source_parent']:
                    raise ProtocolError('DIRECTORY_CHANGED', '原目录身份已变化。')
                return {'state': 'cleanup', 'message': '目标已完成、原字幕仍保留；确认后完成此项。', 'target_version': target}
            if item['step'] == 'applied':
                raise ProtocolError('FILE_CHANGED', '整理后的文件已不在原目标位置，未重复操作。')
            buffer = self._owned_version(item['buffer'], item['buffer_owned'], item['buffer_version'], spec['source_version'])
            if source is None:
                if buffer:
                    return {'state': 'restore', 'message': '原字幕与目标均不在；确认后从已校验备份恢复到目标。', 'buffer_version': buffer}
                raise ProtocolError('FILE_CHANGED', '原字幕和目标均不可用，备份未通过校验，请人工核对。')
            if source != spec['source_version']:
                raise ProtocolError('FILE_CHANGED', '原字幕已被修改或替换，未自动继续。')
            if self.files.parent(spec['source']) != spec['source_parent']:
                raise ProtocolError('DIRECTORY_CHANGED', '原目录已被替换。')
            staged = self._owned_version(item['temp'], item['temp_owned'], item['temp_version'], spec['source_version'])
            return {'state': 'source', 'message': '原字幕保留，确认后继续未完成的步骤。',
                    'buffer_version': buffer, 'temp_version': staged}
        except (ProtocolError, OSError) as error:
            return {'state': 'blocked', 'code': getattr(error, 'code', 'PATH_UNREADABLE'), 'message': str(error)[:300]}

    def prepare_resume(self, run_id, stop, report):
        run, items = self.journal.bundle(run_id)
        if run['phase'] not in {'interrupted', 'partial', 'cancelled', 'archived'} or run['undo_child']:
            raise ProtocolError('STALE_PLAN', '任务已结束或已提交撤销，请刷新记录。')
        observations = []
        for index, item in enumerate(items):
            check_cancelled(stop)
            report(index, len(items), '核对中断任务，尚未改动文件…', 'recovery')
            observations.append(self._observe(run, item))
        changes = {'checked': now()}
        if all(value['state'] in {'done', 'unchanged'} for value in observations):
            changes.update(phase='completed', finished=now(), message='所有文件已核对完成，无需重复整理。')
        self.journal.update_run(run_id, **changes)
        return run_id

    def prepare_undo(self, parent_id, stop, report):
        parent, items = self.journal.bundle(parent_id)
        if parent['kind'] != 'apply' or parent['undo_child'] or parent['phase'] in {'running', 'preview', 'invalidated'}:
            raise ProtocolError('UNDO_UNAVAILABLE', '此任务已提交撤销，或尚未结束。')
        specs = []
        for index, item in enumerate(reversed(items)):
            check_cancelled(stop)
            report(index, len(items), '核对撤销条件，尚未改动文件…', 'undo_preview')
            if item['spec']['action'] != 'rename':
                continue
            observed = self.assess(parent, item)
            if item['step'] != 'applied':
                # A refused same-volume rename leaves the original object at the
                # source. That proves this item was never committed, even when
                # an unrelated target appeared. Other ambiguous commits need audit.
                uncommitted = False
                if item['step'] == 'committing' and item['mode'] == 'rename':
                    try:
                        uncommitted = self.files.inspect(item['spec']['source']) == item['spec']['source_version']
                    except (OSError, ProtocolError):
                        pass
                if observed['state'] in {'cleanup', 'done'} or (item['step'] in COMMIT_STEPS and observed['state'] != 'source' and not uncommitted):
                    raise ProtocolError('RECOVERY_REQUIRED', '仍有已经提交的目标待核对，请先恢复该任务，再撤销。')
                continue
            spec = item['spec']
            reverse = {'video': spec['video'], 'source': spec['target'], 'target': spec['source'], 'action': 'rename',
                       'source_version': item['post_version'], 'video_version': None,
                       'source_parent': spec['target_parent'], 'target_parent': spec['source_parent']}
            specs.append(reverse)
        if not specs:
            raise ProtocolError('UNDO_UNAVAILABLE', '没有已完成且可撤销的文件变更。')
        identifier = self.journal.create(specs, {'parentRunId': parent_id}, kind='undo', parent_id=parent_id)
        run, reverse_items = self.journal.bundle(identifier)
        for item in reverse_items:
            self.journal.update_item(identifier, item['n'], observed=self.assess(run, item))
        return identifier

    def info(self, run_id):
        run, items = self.journal.bundle(run_id)
        changes = [item for item in items if item['spec']['action'] == 'rename']
        blocked = sum(item.get('observed', {}).get('state') == 'blocked' for item in changes)
        completed = sum(item.get('observed', {}).get('state') == 'done' for item in changes)
        pending = sum(item['spec']['action'] == 'pending' for item in items)
        mode = 'undo' if run['kind'] == 'undo' else 'apply' if run['phase'] == 'preview' else 'resume'
        return {'runId': run_id, 'snapshotId': run['snapshot_id'], 'scanId': run['context'].get('scanId'),
                'revision': run['context'].get('revision'), 'operation': mode,
                'changeCount': len(changes), 'completedCount': completed, 'remainingCount': len(changes) - completed,
                'pendingCount': pending, 'conflictCount': blocked,
                'itemCount': len(items), 'unmatchedCount': sum(item['spec']['action'] == 'unmatched' for item in items),
                'canExecute': len(changes) > completed and not blocked and not pending and not run['undo_child'] and run['phase'] not in {'running', 'completed', 'invalidated'},
                'executionReason': '从备份恢复或撤销同样需要核对；已有文件不会被覆盖。' if mode != 'apply' else ''}

    def issue(self, run_id, session, purpose):
        info = self.info(run_id)
        if info['canExecute']:
            _, items = self.journal.bundle(run_id)
            approved = {str(item['n']): item['observed'].get('state') for item in items}
            info['confirmationToken'] = self.journal.issue_ticket(run_id, session, purpose, approved)
        else:
            info['confirmationToken'] = None
        return info

    def claim(self, run_id, snapshot_id, session, token, acknowledged, *, purposes):
        run, _ = self.journal.bundle(run_id)
        if snapshot_id != run['snapshot_id']:
            raise ProtocolError('STALE_PLAN', '固定计划已失效。')
        claimed = self.journal.claim(run_id, session, token, acknowledged=acknowledged, purposes=purposes)
        self.checkpoint('confirmed', run_id, -1)
        return claimed

    def _retain(self, item, key):
        retained = list(item['retained'])
        if item[key]:
            retained.append({'path': item[key], 'identity': item[key + '_owned']})
        if len(retained) > 100:
            raise ProtocolError('RETRY_LIMIT', '已保留多次中断缓存，请先打开缓存与日志人工核对。')
        return retained

    def _apply_item(self, run, item, observed):
        identifier, index, spec = run['id'], item['n'], item['spec']
        restore = observed['state'] == 'restore'
        if restore and run['approved'].get(str(index)) != 'restore':
            raise ProtocolError('FILE_CHANGED', '原字幕在确认后消失，请重新预览备份恢复。')
        with self.files.session(spec, missing_source=restore) as session:
            if observed['state'] == 'cleanup':
                session.guard_target(observed['target_version'])
            buffer_version = observed.get('buffer_version')
            if buffer_version:
                item = self.journal.update_item(identifier, index, buffer_version=buffer_version)
            elif observed['state'] != 'restore':
                path = self.files.allocate_buffer(identifier, index)
                item = self.journal.update_item(identifier, index, step='buffering', retained=self._retain(item, 'buffer'),
                                                buffer=path, buffer_owned=None, buffer_version=None)
                version = session.write_buffer(path,
                    lambda value: (self.journal.update_item(identifier, index, buffer_owned=value), self.checkpoint('buffer_created', identifier, index)),
                    lambda point: self.checkpoint('buffer_' + point, identifier, index))
                self.checkpoint('buffer_written', identifier, index)
                item = self.journal.update_item(identifier, index, buffer_version=version, step='buffered')
                self.checkpoint('buffered', identifier, index)
            if observed['state'] == 'cleanup':
                item = self.journal.update_item(identifier, index, step='committed', mode='copy', post_version=observed['target_version'])
            elif not restore and spec['source_version']['volume'] == spec['target_parent']['volume']:
                self.journal.update_item(identifier, index, step='committing', mode='rename')
                self.checkpoint('before_commit', identifier, index)
                try:
                    post = session.rename_source()
                except OSError as error:
                    if getattr(error, 'winerror', None) != 17:
                        raise
                else:
                    self.checkpoint('target_committed', identifier, index)
                    self.journal.update_item(identifier, index, step='applied', post_version=post, error='', error_code='',
                        observed={'state': 'done', 'message': '已完成撤销。' if run['kind'] == 'undo' else '已完成整理。'})
                    self.checkpoint('applied', identifier, index)
                    return
            if observed['state'] != 'cleanup':
                item = self.journal.item(identifier, index)
                staged = observed.get('temp_version')
                if staged:
                    item = self.journal.update_item(identifier, index, temp_version=staged, step='staged')
                else:
                    path = self.files.allocate_stage(spec, identifier, index)
                    item = self.journal.update_item(identifier, index, step='staging', retained=self._retain(item, 'temp'),
                                                    temp=path, temp_owned=None, temp_version=None)
                    staged = session.stage(item['buffer'], item['buffer_version'], path,
                        lambda value: (self.journal.update_item(identifier, index, temp_owned=value), self.checkpoint('temp_created', identifier, index)),
                        lambda point: self.checkpoint('temp_' + point, identifier, index))
                    self.checkpoint('temp_written', identifier, index)
                    item = self.journal.update_item(identifier, index, step='staged', temp_version=staged)
                    self.checkpoint('staged', identifier, index)
                self.journal.update_item(identifier, index, step='committing', mode='restore' if restore else 'copy')
                self.checkpoint('before_commit', identifier, index)
                post = session.commit_stage(item['temp'], staged)
                self.checkpoint('target_committed', identifier, index)
                item = self.journal.update_item(identifier, index, step='committed', post_version=post)
                self.checkpoint('committed', identifier, index)
            if not restore:
                self.journal.update_item(identifier, index, step='deleting')
                session.remove_source()
                self.checkpoint('source_removed', identifier, index)
            self.journal.update_item(identifier, index, step='applied', error='', error_code='',
                observed={'state': 'done', 'message': '已完成撤销。' if run['kind'] == 'undo' else '已完成整理。'})
            self.checkpoint('applied', identifier, index)

    def execute(self, run_id, stop, report):
        run, items = self.journal.bundle(run_id)
        if run['phase'] != 'running' or not run['ticket'] or not run['ticket']['used']:
            raise ProtocolError('CONFIRMATION_REQUIRED', '文件任务未获得一次性确认。')
        observations = [self.assess(run, item) for item in items]
        blocked = False
        for item, observed in zip(items, observations):
            self.journal.update_item(run_id, item['n'], observed=observed)
            if observed['state'] == 'blocked' or (observed['state'] == 'restore' and run['approved'].get(str(item['n'])) != 'restore'):
                blocked = True
                self.journal.update_item(run_id, item['n'], error=observed['message'] or '确认后文件状态已变化。',
                                         error_code=observed.get('code', 'FILE_CHANGED'))
        if blocked:
            self.journal.update_run(run_id, phase='partial', finished=now(), message='文件状态已变化，未开始新的变更。')
            return {'batchId': run_id}
        phase, message = 'completed', ''
        for item, observed in zip(items, observations):
            if item['spec']['action'] != 'rename':
                continue
            if stop():
                phase, message = 'cancelled', '已在文件之间停止，已完成的变更和缓存保留。'
                break
            try:
                report(item['n'], len(items), '正在整理 · ' + Path(item['spec']['source']).name, 'applying')
                if observed['state'] == 'done':
                    self.journal.update_item(run_id, item['n'], step='applied', post_version=observed['target_version'], error='', error_code='')
                else:
                    self._apply_item(run, self.journal.item(run_id, item['n']), observed)
            except (OSError, ProtocolError) as error:
                self.journal.update_item(run_id, item['n'], error=str(error)[:300], error_code=getattr(error, 'code', 'FILE_OPERATION_FAILED'))
                phase, message = 'partial', '已停止后续文件；已完成的变更、原文件及备份按日志保留。'
                break
        self.journal.update_run(run_id, phase=phase, finished=now(), message=message)
        report(len(items), len(items), '本次任务已结束', 'applying')
        return {'batchId': run_id}

    def _observe(self, run, item):
        observed = self.assess(run, item)
        changes = {'observed': observed}
        if observed['state'] == 'done':
            changes.update(step='applied', post_version=observed['target_version'], error='', error_code='')
        elif observed['state'] == 'blocked':
            changes.update(error=observed['message'], error_code=observed.get('code', 'FILE_CHANGED'))
        self.journal.update_item(run['id'], item['n'], **changes)
        return observed

    def audit(self, stop, report):
        identifiers = self.journal.pending_ids()
        complete = 0
        for position, run_id in enumerate(identifiers):
            check_cancelled(stop)
            report(position, len(identifiers), '正在只读核对上次文件任务…', 'reconcile')
            run, items = self.journal.bundle(run_id)
            for item in items:
                check_cancelled(stop)
                self._observe(run, item)
            _, current = self.journal.bundle(run_id)
            if all(item['spec']['action'] != 'rename' or item['observed'].get('state') == 'done' for item in current):
                self.journal.update_run(run_id, phase='completed', finished=now(), checked=now(),
                                        message='已核对上次完整完成的变更，没有重复操作文件。')
                complete += 1
            else:
                self.journal.update_run(run_id, checked=now())
        return {'checked': len(identifiers), 'completed': complete, 'pending': len(self.journal.pending_ids())}

    def page(self, run_id, offset=0, limit=20):
        run = self.journal.run(run_id)
        values = []
        for item in self.journal.page(run_id, offset, limit):
            spec, observed = item['spec'], item['observed']
            values.append({'videoName': Path(spec['video']).name, 'sourceName': Path(spec['source']).name if spec['source'] else '未关联字幕',
                           'sourcePath': spec['source'] or spec['video'], 'targetName': Path(spec['target']).name if spec['target'] else '—',
                           'targetPath': spec['target'] or '—', 'action': 'blocked' if observed.get('state') == 'blocked' else
                           'unchanged' if observed.get('state') == 'done' else spec['action'], 'message': observed.get('message', '')})
        return {'items': values, 'itemCount': sum(self.journal.counts(run_id).values()), 'offset': offset}

    def record_meta(self, run_id):
        run = self.journal.run(run_id)
        counts = self.journal.counts(run_id)
        first = self.journal.page(run_id, 0, 1)
        folder = Path(first[0]['spec']['video']).parent.name if first else '文件任务'
        undone = bool(run['undo_child'] and self.journal.run(run['undo_child'])['phase'] == 'completed')
        return {'recordId': run_id, 'title': ('撤销 · ' if run['kind'] == 'undo' else '') + folder[:100],
                'time': run['finished'] or run['started'] or run['created'], 'success': counts.get('success', 0),
                'skipped': counts.get('skipped', 0), 'errors': counts.get('blocked', 0) + counts.get('error', 0),
                'unchanged': counts.get('unchanged', 0), 'unmatched': counts.get('unmatched', 0),
                'cancelled': counts.get('cancelled', 0) + counts.get('pending', 0), 'itemCount': sum(counts.values()),
                'issue': ('本任务已完成的变更已撤销。' if undone else run['message']), 'historyError': '',
                'kind': run['kind'], 'phase': run['phase'], 'undone': undone,
                'canUndo': run['kind'] == 'apply' and counts.get('success', 0) > 0 and not run['undo_child'] and run['phase'] != 'running',
                'canResume': run['phase'] in {'interrupted', 'partial', 'cancelled', 'archived'} and not run['undo_child'],
                'needsRecovery': run_id in self.journal.pending_ids()}

    def record_page(self, run_id, offset=0, limit=20):
        run = self.journal.run(run_id)
        rows = []
        for item in self.journal.page(run_id, offset, limit):
            spec, status = item['spec'], status_for(item, run['phase'])
            rows.append({'source': Path(spec['source'] or spec['video']).name, 'target': Path(spec['target']).name if spec['target'] else '—',
                         'sourcePath': spec['source'] or spec['video'], 'targetPath': spec['target'] or '',
                         'state': LABELS[status], 'status': status,
                         'error': item['error'] or (item['observed'].get('message', '') if status != 'success' else '')})
        return {**self.record_meta(run_id), 'items': rows, 'offset': offset}

    def history(self, limit=30):
        return [self.record_meta(run['id']) for run in self.journal.history(limit)]

    def archive(self, run_id, acknowledged):
        if acknowledged is not True:
            raise ProtocolError('CONFIRMATION_REQUIRED', '请确认稍后再处理此任务。')
        run = self.journal.run(run_id)
        if run['phase'] not in {'interrupted', 'partial', 'cancelled', 'archived'}:
            raise ProtocolError('STALE_PLAN', '当前任务不能转为稍后处理。')
        self.journal.update_run(run_id, phase='archived', message='已保留文件和缓存，稍后可在记录中重新核对。')
        return {'archived': True}

    def contains(self, run_id):
        try:
            self.journal.run(run_id)
            return True
        except ProtocolError as error:
            if error.code != 'NOT_FOUND':
                raise
            return False

    def discard(self, run_id):
        if run_id and self.journal.run(run_id)['phase'] == 'preview':
            self.journal.update_run(run_id, phase='invalidated', message='此预览已失效，文件未改动。')
