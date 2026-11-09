"""Serialize and restore business review choices through explicit storage/FS ports."""
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled
from ..domain.review import REVIEW_MODEL, ReviewPlan, ReviewRow, ReviewMatch, path_key
from ..domain.match_assessment import POLICY_VERSION, AssessmentIndex
from ..domain.subtitle_policy import DEFAULT_POLICY, VERSION as NEEDS_VERSION, SubtitlePolicy
from ..domain.media_identity import imdb
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
                'reviewModel':REVIEW_MODEL,
                'matchPolicy':POLICY_VERSION,
                'subtitlePolicy':{'version':NEEDS_VERSION,**getattr(data,'subtitle_policy',
                    workspace.needs.policy.dto() if hasattr(workspace,'needs') else DEFAULT_POLICY)},
                'scanId':data.scan_id,'revision':data.revision,'options':dict(workspace.options),
                'embeddedOptions':dict(workspace.embedded),'files':files,
                'subtitles':[str(path) for path in review.subtitles],
                'imported':[{'path':key,'metadata':metadata} for key,metadata in review.imported.items()],
                'upgrades':dict(review.upgrades),
                'identities':dict(review.identities),
                'warnings':data.scan_warnings[:50],
                'rows':[{'video':str(row.video),'skipped':row.skipped,'embedded':row.embedded,
                         'embeddedIgnored':row.embedded_ignored,
                         'matches':[{'source':str(match.source),'score':match.score,'manual':match.manual,
                                     'confirmed':match.confirmed,'needsReview':match.needs_review} for match in row.matches]} for row in review.rows]}

    def restore(self, value, register, stop=lambda:False, *, recognition=None, subtitle_policy=None):
        model = value.get('reviewModel')
        if model not in (None, REVIEW_MODEL):
            raise ProtocolError('UNSUPPORTED_CHECKPOINT','草稿识别模型版本不受支持，已保留原数据。')
        policy=value.get('matchPolicy')
        if policy not in (None,POLICY_VERSION):
            raise ProtocolError('UNSUPPORTED_CHECKPOINT','草稿匹配策略版本不受支持，已保留原数据。')
        saved_policy=value.get('subtitlePolicy')
        if saved_policy is not None:
            if not isinstance(saved_policy,dict) or saved_policy.get('version')!=NEEDS_VERSION:
                raise ProtocolError('UNSUPPORTED_CHECKPOINT','草稿字幕需求版本不受支持，已保留原数据。')
            SubtitlePolicy.read({k:v for k,v in saved_policy.items() if k!='version'})
        migrated = (model != REVIEW_MODEL or policy != POLICY_VERSION or subtitle_policy is not None
                    and saved_policy!={'version':NEEDS_VERSION,**subtitle_policy})
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
        upgrades=value.get('upgrades',{})
        if not isinstance(upgrades,dict) or len(upgrades)>len(subtitles):
            raise ProtocolError('CORRUPT_CHECKPOINT','升级来源记录无效。')
        subtitle_keys={path_key(p) for p in subtitles}
        for candidate,metadata in upgrades.items():
            if (candidate not in subtitle_keys or not isinstance(metadata,dict)
                    or set(metadata)!={'original','originalDigest','candidateDigest','originalOrigin','candidateOrigin','policy'}
                    or metadata.get('original') not in paths or metadata.get('policy')!=NEEDS_VERSION
                    or any(not isinstance(metadata.get(key),str) or len(metadata[key])!=64
                           or any(c not in '0123456789abcdef' for c in metadata[key]) for key in ('originalDigest','candidateDigest'))
                    or any(not isinstance(metadata[key],str) or len(metadata[key])>128 for key in ('originalOrigin','candidateOrigin'))):
                raise ProtocolError('CORRUPT_CHECKPOINT','升级来源不完整，保留原草稿。')
        review.upgrades=dict(upgrades)
        identities=value.get('identities',{})
        video_keys={path_key(p) for p in videos}
        if not isinstance(identities,dict) or len(identities)>len(videos):raise ProtocolError('CORRUPT_CHECKPOINT','人工标识清单无效。')
        for key,item in identities.items():
            if key not in video_keys or not isinstance(item,dict) or set(item)!={'id','kind','source'} or item['kind'] not in {'movie','episode'} or item['source']!='manual':
                raise ProtocolError('CORRUPT_CHECKPOINT','人工标识不属于当前作品。')
            imdb(item['id'])
        review.identities=dict(identities)
        review.model_migrated = migrated
        review.rows = []
        for row in value['rows']:
            matches=[]
            for match in row['matches']:
                if Path(match['source']) not in subtitles:
                    raise ProtocolError('CORRUPT_CHECKPOINT','草稿匹配不属于字幕清单。')
                matches.append(ReviewMatch(Path(match['source']),score=match['score'],manual=match['manual'],
                    confirmed=False if migrated else match['confirmed'],needs_review=migrated or match.get('needsReview',False)))
            review.rows.append(ReviewRow(Path(row['video']),matches,row['skipped'],row['embedded'],row['embeddedIgnored']))
        assigned=[path_key(match.source) for row in review.rows for match in row.matches]
        if len(set(assigned))!=len(assigned):
            raise ProtocolError('CORRUPT_CHECKPOINT','草稿存在重复分配的字幕。')
        review._replan(stop)
        review.assessment=AssessmentIndex([row.video for row in review.rows if not row.uses_embedded],subtitles,stop)
        data = ReviewData(review,register,scan_id=value['scanId'],revision=value['revision']+int(migrated),
                          warnings=value['warnings'],recognition=recognition)
        if subtitle_policy is not None:data.subtitle_policy=subtitle_policy
        return folder, self.fs.directory_mark(folder), data, value['options'], value['embeddedOptions']
