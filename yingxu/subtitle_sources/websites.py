"""Curated website entries. Mirrors come from the sites' own published lists."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Website:
    key: str
    provider: str
    label: str
    home: str
    hosts: frozenset[str]


ZIMUKU_HOSTS = frozenset({"zimuku.org", "www.zimuku.org", "srtku.com", "www.srtku.com"})
SUBHD_HOSTS = frozenset({"subhd.me", "www.subhd.me", "subhd.one", "www.subhd.one",
                        "subhdtw.com", "www.subhdtw.com", "subhd.top", "www.subhd.top", "subhd.cc", "www.subhd.cc"})

WEBSITES = (
    Website("zimuku", "zimuku", "字幕库 · 首选", "https://zimuku.org/", ZIMUKU_HOSTS),
    Website("srtku", "zimuku", "字幕库 · 官方备用", "https://srtku.com/", ZIMUKU_HOSTS),
    Website("subhd", "subhd", "SubHD · 备用来源", "https://subhd.me/", SUBHD_HOSTS),
    Website("subhd-one", "subhd", "SubHD · 备用线路", "https://subhd.one/", SUBHD_HOSTS),
)


def website_for(key):
    for site in WEBSITES:
        if site.key == key:
            return site
    raise ValueError("未支持的字幕网站。")
