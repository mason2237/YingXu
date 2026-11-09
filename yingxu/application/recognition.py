"""Advisory filename recognition, with an optional replaceable shadow parser."""
from ..domain.releases import ParsedRelease, parse_release, release_lines
from ..ports.release_parser import ReleaseParser


class Recognition:
    def __init__(self, shadow: ReleaseParser | None = None):
        self.shadow=shadow

    def lines(self, name):
        baseline=parse_release(name)
        lines=release_lines(baseline)
        if self.shadow is not None:
            try:
                compared=self.shadow.parse(name)
                if not isinstance(compared,ParsedRelease):raise ValueError('parser result')
                # Optional results cannot affect allocation or create unbounded DTOs.
                if compared.parser=='guessit':
                    fields=[label for label in ('title','year','season','episodes','source','release_group')
                            if getattr(baseline,label)!=getattr(compared,label)]
                    lines.append('GuessIt 对照 · '+('差异字段：'+ '、'.join(fields) if fields else '主要字段一致')+'；未改变自动匹配')
                lines.extend(str(warning)[:200] for warning in compared.warnings[:3] if warning not in baseline.warnings)
            except Exception:
                lines.append('可选解析器未完成，保留本地识别结果')
        return lines
