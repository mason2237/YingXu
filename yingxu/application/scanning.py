"""Read inventory and metadata through ports, then build the existing review rules."""
from ..domain.matching import check_cancelled
from ..domain.review import ReviewPlan
from ..ports.workspace import Filesystem, MediaInspector
from .reviewing import ReviewData


def scan(folder, mark, options, embedded_options, revision, register,
         filesystem: Filesystem, inspector: MediaInspector, worker):
    warnings = []
    warning_count = 0

    def warning(error):
        nonlocal warning_count
        warning_count += 1
        if len(warnings) < 50:
            warnings.append(str(error))

    videos, subtitles = filesystem.collect(
        folder, options['recursive'], should_stop=worker.stop.is_set,
        on_error=warning, progress=lambda done, videos, subs: worker.report(
            done, None, f'已读取 {done} 项 · {videos} 个视频 · {subs} 份字幕', 'collect'),
    )

    def inside(paths):
        accepted = []
        for path in paths:
            check_cancelled(worker.stop.is_set)
            try:
                if filesystem.inside(path, folder):
                    accepted.append(path)
                else:
                    warning(f'跳过链接或目录外文件：{path.name}')
            except OSError as error:
                warning(error)
        return accepted

    videos, subtitles = inside(videos), inside(subtitles)
    embedded = inspector.inspect(videos, embedded_options, filesystem, worker.stop, worker.report)
    if filesystem.directory_mark(folder) != mark:
        raise ValueError('扫描时目录已变化，请重新选择。')
    review = ReviewPlan(
        videos, subtitles, options['move'], exists=filesystem.exists,
        should_stop=worker.stop.is_set, embedded=embedded,
        progress=lambda done, total, phase: worker.report(done, total, f'计算匹配 · {done} / {total}', phase),
    )
    check_cancelled(worker.stop.is_set)
    data = ReviewData(review, register, revision=revision, warnings=warnings)
    data.warning_count = warning_count
    return data
