"""Bounded MediaInfo reads and a small identity-keyed metadata cache."""
from collections import OrderedDict
from copy import deepcopy

from ..domain.matching import check_cancelled
from ..domain.media import assess
from ..domain.review import path_key
from .mediainfo import ProbeSession


class LocalMediaInspector:
    def __init__(self):
        self.cache = OrderedDict()

    def inspect(self, videos, options, filesystem, stop, report):
        result = {}
        with ProbeSession(stop.is_set) as reader:
            for index, video in enumerate(videos):
                check_cancelled(stop.is_set)
                info = {'status': 'disabled', 'tracks': []}
                if options['enabled']:
                    report(index, len(videos), f'检查内嵌字幕 · {index+1} / {len(videos)}', 'embedded')
                    try:
                        mark = filesystem.file_mark(video)
                        key = (path_key(video), mark)
                        info = self.cache.get(key)
                        if info is None:
                            info = reader.probe(video)
                            if filesystem.file_mark(video) != mark:
                                raise ValueError('读取时视频发生变化，请重新扫描。')
                            if info['status'] == 'ok':
                                self.cache[key] = deepcopy(info)
                                while len(self.cache) > 512:
                                    self.cache.popitem(last=False)
                    except (OSError, ValueError) as error:
                        info = {'status': 'error', 'tracks': [], 'error': str(error)}
                result[path_key(video)] = assess(info, options)
        return result
