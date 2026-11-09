"""Filename language/script and purpose, independent of GUI and third parties."""
from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata

VERSION = 'variants-1'
# A script is not a region. Aliases carry only information they actually encode.
LANGUAGES = {
    'chs': ('zh','Hans',''), 'sc': ('zh','Hans',''), 'cn': ('zh','Hans','CN'),
    'zh-cn': ('zh','Hans','CN'), 'zh-hans': ('zh','Hans',''),
    'cht': ('zh','Hant',''), 'tc': ('zh','Hant',''), 'tw': ('zh','Hant','TW'),
    'zh-tw': ('zh','Hant','TW'), 'zh-hant': ('zh','Hant',''),
    'zh-hk': ('zh','Hant','HK'), 'zh': ('zh','',''), 'zho': ('zh','',''),
    'en': ('en','',''), 'eng': ('en','',''), 'en-us': ('en','','US'), 'en-gb': ('en','','GB'),
    'jp': ('ja','',''), 'ja': ('ja','',''), 'jpn': ('ja','',''),
    'kr': ('ko','',''), 'ko': ('ko','',''), 'kor': ('ko','',''),
    'fr': ('fr','',''), 'fre': ('fr','',''), 'fra': ('fr','',''),
    'es': ('es','',''), 'de': ('de','',''), 'ger': ('de','',''),
}
PURPOSES = {'forced':'forced','sdh':'sdh','hi':'sdh','commentary':'commentary'}
COMBINED = {'bilingual','chsen','chteng','双语','中英双语'}
TOKENS = sorted((*LANGUAGES, *PURPOSES, *COMBINED), key=len, reverse=True)
TRAILING = re.compile(r'(?:^|[. _\-\[])(?P<tag>'+ '|'.join(map(re.escape,TOKENS)) +r')\]?$')


@dataclass(frozen=True)
class SubtitleVariant:
    languages: tuple[str,...] = ()
    script: str = ''
    region: str = ''
    forced: bool = False
    sdh: bool = False
    commentary: bool = False
    ambiguous: bool = False
    source: str = 'filename'
    parser_version: str = VERSION

    @property
    def key(self):
        # zh-CN/chs/zh-Hans share a script variant; retain region for display.
        # Regional English variants can remain separate when explicitly tagged.
        region = '' if 'zh' in self.languages and self.script else self.region
        return '|'.join(('+'.join(self.languages) or 'und', self.script, region,
                         str(int(self.forced)),str(int(self.sdh)),str(int(self.commentary)),
                         str(int(self.ambiguous))))

    @property
    def language_label(self):
        if self.languages == ('en','zh'):
            return '繁中英双语' if self.script == 'Hant' else '中英双语'
        if self.languages == ('zh',):
            return {'Hans':'简体中文','Hant':'繁体中文'}.get(self.script,'中文')
        return {'en':'英语','ja':'日语','ko':'韩语','fr':'法语','es':'西班牙语','de':'德语'}.get(
            self.languages[0] if len(self.languages)==1 else '', '未标记')

    @property
    def label(self):
        label=self.language_label+(f' ({self.region})' if self.region and 'zh' not in self.languages else '')
        return ' · '.join([label,
            *(['强制/片段'] if self.forced else []), *(['SDH'] if self.sdh else []),
            *(['评论'] if self.commentary else []), *(['标注冲突'] if self.ambiguous else [])])


@lru_cache(maxsize=4096)
def split_variant(stem: str) -> tuple[str, SubtitleVariant, str]:
    """Only consume known trailing tags; never infer language from the title."""
    if len(stem)>2048:
        return stem, SubtitleVariant(ambiguous=True), ''
    normalized = unicodedata.normalize('NFKC',stem).casefold()
    # NFKC can change offsets; consume the same number of suffix characters on
    # the original only when lengths agree. Otherwise use a normalized suffix.
    remaining, tags = normalized, []
    while match := TRAILING.search(remaining):
        tags.append(match['tag']); remaining=remaining[:match.start()].rstrip('. _-[')
    if not tags:
        return stem, SubtitleVariant(), ''
    tags.reverse()
    languages, scripts, regions, flags = set(),set(),set(),set()
    for tag in tags:
        if tag in LANGUAGES:
            lang,script,region=LANGUAGES[tag];languages.add(lang)
            if script: scripts.add(script)
            if region: regions.add(region)
        elif tag in PURPOSES: flags.add(PURPOSES[tag])
        else:
            languages.update(('zh','en'))
            if tag in {'chsen','chteng'}: scripts.add('Hant' if tag=='chteng' else 'Hans')
    variant=SubtitleVariant(tuple(sorted(languages)), next(iter(scripts)) if len(scripts)==1 else '',
        next(iter(regions)) if len(regions)==1 else '', 'forced' in flags, 'sdh' in flags,
        'commentary' in flags, len(scripts)>1 or len(regions)>1)
    suffix='.'+'.'.join(tags)
    base=stem[:len(remaining)] if len(normalized)==len(stem) else remaining
    return base, variant, suffix


def variant_of(path):
    return split_variant(path.stem)[1]
