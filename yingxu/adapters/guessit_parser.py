"""Optional GuessIt 4.4.0 metadata, isolated behind a standard-library model.

Disabled by default. The application uses it for shadow evidence only; a missing
or incompatible library never changes filename matching or starts a download.
"""
from dataclasses import replace
from functools import lru_cache
import importlib
from importlib.metadata import version

from ..domain.releases import MAX_NAME, ParsedRelease, parse_release

REQUIRED_VERSION='4.4.0'


class GuessItParser:
    def __init__(self, *, enabled=False):
        self.enabled=enabled

    @lru_cache(maxsize=4096)
    def parse(self, name: str) -> ParsedRelease:
        fallback=parse_release(name)
        if not self.enabled:return fallback
        if not isinstance(name,str) or len(name)>MAX_NAME or not fallback.complete:
            return fallback
        try:
            installed=version('guessit')
            if installed!=REQUIRED_VERSION:raise ValueError('version')
            parser=importlib.import_module('guessit').guessit
            data=parser(name, {'name_only':True, 'no_user_config':True})
            if not isinstance(data,dict):raise ValueError('shape')
            def text(key, limit):
                value=data.get(key)
                if value is None:return None
                if not isinstance(value,str) or not 0<len(value)<=limit or any(ord(c)<32 for c in value):
                    raise ValueError(key)
                return value
            def integer(key):
                value=data.get(key)
                if value is not None and (type(value) is not int or not 0<=value<=9999):raise ValueError(key)
                return value
            episodes=data.get('episode',())
            if type(episodes) is int:episodes=(episodes,)
            if not isinstance(episodes,(list,tuple)) or len(episodes)>100 or any(type(n) is not int or not 0<=n<=9999 for n in episodes):
                raise ValueError('episode')
            kind=text('type',20)
            if kind not in {None,'movie','episode'}:raise ValueError('type')
            # Preserve all coverage. GuessIt must not reduce the YX-01 set.
            guessed=tuple(sorted(set(episodes)))
            warnings=fallback.warnings
            if fallback.episodes and guessed and fallback.episodes!=guessed:
                warnings+=('对照解析的季集集合不同，未用于自动匹配',)
            return replace(fallback,title=text('title',256) or fallback.title,
                year=integer('year') or fallback.year, season=integer('season') if data.get('season') is not None else fallback.season,
                episodes=guessed or fallback.episodes,kind=kind or fallback.kind,
                source=text('source',64) or fallback.source,release_group=text('release_group',64) or fallback.release_group,
                parser='guessit',parser_version=installed,warnings=warnings)
        except Exception:
            return replace(fallback,warnings=fallback.warnings+('可选解析器不可用或结果无效，已使用本地规则',))
