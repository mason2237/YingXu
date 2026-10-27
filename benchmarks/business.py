"""Independent business benchmark. Uses disposable files, never a timing test."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measure(operation, repeats):
    times, checks = [], []
    original = Path.stat
    for _ in range(repeats):
        count = 0
        def stat(path, *args, **kwargs):
            nonlocal count
            count += 1
            return original(path, *args, **kwargs)
        with patch.object(Path, 'stat', stat):
            start = perf_counter()
            operation()
            times.append(round((perf_counter() - start) * 1000, 3))
        checks.append(count)
    return {'milliseconds': times, 'medianMs': statistics.median(times), 'pathChecks': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation', choices=('layered',), default='layered')
    parser.add_argument('--size', type=int, default=120)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.size <= 1000 or not 1 <= args.repeats <= 10:
        parser.error('size must be 1..1000; repeats 1..10')
    from yingxu.core import build_plan
    from yingxu.review import ReviewPlan
    from yingxu.application.reviewing import ReviewData

    output = ROOT / 'work/test-results/business-benchmarks'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sample-', dir=output) as directory:
        directory = Path(directory)
        videos, subtitles = [], []
        for index in range(args.size):
            video = directory / f'Atlas.S01E{index+1:03}.1080p.mkv'
            subtitle = directory / f'Atlas.S01E{index+1:03}.chs.srt'
            video.write_bytes(b'benchmark placeholder; not a real media container')
            subtitle.write_text('1\n00:00:00,000 --> 00:00:01,000\nSample\n', encoding='utf8')
            videos.append(video); subtitles.append(subtitle)
        registry = {}
        def register(path):
            return registry.setdefault(str(path), f'file-{len(registry)+1}')
        review = ReviewPlan(videos, subtitles)
        data = ReviewData(review, register)
        result = {
            'schema': 1, 'implementation': args.implementation,
            'python': platform.python_version(), 'os': platform.system(),
            'size': args.size, 'repeats': args.repeats,
            'matching': measure(lambda: build_plan(videos, subtitles), args.repeats),
            'reviewBuild': measure(lambda: ReviewData(review, register), args.repeats),
            'singleRowUpdate': measure(lambda: data.updated('review.skip', {'rowId': 'video-1', 'skipped': True}), args.repeats),
        }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
