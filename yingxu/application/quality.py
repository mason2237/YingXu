"""Owns bounded report snapshots; callers supply an already authorized file ID."""
from collections import OrderedDict
from dataclasses import dataclass
from uuid import uuid4

from ..domain.errors import ProtocolError
from ..domain.matching import check_cancelled
from ..domain.subtitle_quality import QualityReport, analyze
from ..ports.subtitle_reader import SubtitleReader


@dataclass(frozen=True)
class ReportSnapshot:
    identifier: str
    scope: tuple
    report: QualityReport
    name: str


class Quality:
    def __init__(self, reader: SubtitleReader):
        self.reader=reader
        self.reports=OrderedDict()

    def inspect(self,path,scope,*,encoding='auto',max_cps=40,should_stop=None):
        check_cancelled(should_stop)
        read=self.reader.read(path,encoding=encoding,should_stop=should_stop)
        report=analyze(read,max_cps=max_cps,should_stop=should_stop)
        check_cancelled(should_stop)
        return ReportSnapshot(uuid4().hex,scope,report,path.name)

    def accept(self,snapshot):
        self.reports[snapshot.identifier]=snapshot
        # Reports are disposable snapshots, not execution permission or drafts.
        # At most two reports and 60000 cues remain resident.
        while len(self.reports)>2 or (len(self.reports)>1 and sum(len(s.report.document.cues) for s in self.reports.values())>60000):
            self.reports.popitem(last=False)
        return {'reportId':snapshot.identifier,'name':snapshot.name,**snapshot.report.summary()}

    def page(self,identifier,scope,section='issues',offset=0,limit=20):
        snapshot=self.reports.get(identifier)
        if snapshot is None or snapshot.scope!=scope:
            raise ProtocolError('STALE_REPORT','检查结果已过期或选择已变化，请重新检查。')
        self.reports.move_to_end(identifier)
        report=snapshot.report
        if section=='issues':
            values=report.document.issues
            entries=[issue.dto() for issue in values[offset:offset+limit]]
        elif section=='cues':
            values=report.document.cues
            entries=[{'cue':cue.identifier,'line':cue.line,'start':cue.start,'end':cue.end,
                'excerpt':cue.text[:320],'style':cue.style[:80],'layer':cue.layer[:40],
                'settings':cue.settings[:160],'kind':cue.kind} for cue in values[offset:offset+limit]]
        else:raise ProtocolError('INVALID_REQUEST','不支持的字幕检查部分。')
        next_offset=offset+len(entries)
        return {'reportId':identifier,'qualitySection':section,'entries':entries,'total':len(values),
                'offset':offset,'nextOffset':next_offset if next_offset<len(values) else None}
