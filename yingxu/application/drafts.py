"""Serialize and restore business review choices through explicit storage/FS ports."""
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled
from ..domain.review import ReviewPlan, ReviewRow, ReviewMatch, path_key
from ..ports.checkpoint import CheckpointStore
from .reviewing import ReviewData


class Drafts:
    def __init__(self, store: CheckpointStore, filesystem):
        self.store, self.fs = store, filesystem
        self.fingerprints = OrderedDict()

    def fingerprint(self, path):
        key = str(path)
        if key not in self.fingerprints:
            self.fingerprints[key] = self.fs.fingerprint(path)
            while len(self.fingerprints)>20000: self.fingerprints.popitem(last=False)
        return self.fingerprints[key]

    def capture(self, workspace, data, stop=lambda:False, *, fresh=False):
        if not workspace.folder: return None
        if fresh: self.fingerprints.clear()
        review = data.review
        files = []
        for path in (*review.videos,*review.subtitles):
            check_cancelled(stop)
            files.append({'path':str(path),'mark':self.fingerprint(path)})
        return {'v':1,'folder':str(workspace.folder),'folderMark':asdict(workspace.folder_mark),
                'scanId':data.scan_id,'revision':data.revision,'options':dict(workspace.options),
                'embeddedOptions':dict(workspace.embedded),'files':files,
                'subtitles':[str(path) for path in review.subtitles],
                'imported':[{'path':key,'metadata':metadata} for key,metadata in review.imported.items()],
                'warnings':data.scan_warnings[:50],
                'rows':[{'video':str(row.video),'skipped':row.skipped,'embedded':row.embedded,
                         'embeddedIgnored':row.embedded_ignored,
                         'matches':[{'source':str(match.source),'score':match.score,'manual':match.manual,
                                     'confirmed':match.confirmed} for match in row.matches]} for row in review.rows]}

    def restore(self, value, register, stop=lambda:False):
        folder = Path(value['folder'])
        if not folder.is_absolute() or asdict(self.fs.directory_mark(folder)) != value['folderMark']:
            raise ProtocolError('DRAFT_CHANGED','草稿目录身份已变化；保留草稿，请重新选择并扫描。')
        if len(value['files'])>20000 or len(value['rows'])>10000:
            raise ProtocolError('CORRUPT_CHECKPOINT','草稿文件数量超出限制。')
        paths = set()
        for file in value['files']:
            check_cancelled(stop)
            path = Path(file['path'])
            if not path.is_absolute() or self.fs.fingerprint(path) != file['mark']:
                raise ProtocolError('DRAFT_CHANGED',f'文件已变化，未恢复旧匹配：{path.name}。请重新扫描。')
            self.fingerprints[str(path)] = file['mark']
            paths.add(str(path))
        videos = [Path(row['video']) for row in value['rows']]
        subtitles = tuple(Path(path) for path in value['subtitles'])
        if any(str(path) not in paths for path in (*videos,*subtitles)) or len(set(videos))!=len(videos):
            raise ProtocolError('CORRUPT_CHECKPOINT','草稿引用的文件不完整。')
        review = ReviewPlan([],[],value['options']['move'],exists=self.fs.exists)
        review.videos, review.subtitles = tuple(videos), subtitles
        review.imported = {item['path']:item['metadata'] for item in value['imported']}
        review.rows = []
        for row in value['rows']:
            matches=[]
            for match in row['matches']:
                if Path(match['source']) not in subtitles:
                    raise ProtocolError('CORRUPT_CHECKPOINT','草稿匹配不属于字幕清单。')
                matches.append(ReviewMatch(Path(match['source']),score=match['score'],manual=match['manual'],confirmed=match['confirmed']))
            review.rows.append(ReviewRow(Path(row['video']),matches,row['skipped'],row['embedded'],row['embeddedIgnored']))
        assigned=[path_key(match.source) for row in review.rows for match in row.matches]
        if len(set(assigned))!=len(assigned):
            raise ProtocolError('CORRUPT_CHECKPOINT','草稿存在重复分配的字幕。')
        review._replan(stop)
        data = ReviewData(review,register,scan_id=value['scanId'],revision=value['revision'],warnings=value['warnings'])
        return folder, self.fs.directory_mark(folder), data, value['options'], value['embeddedOptions']
