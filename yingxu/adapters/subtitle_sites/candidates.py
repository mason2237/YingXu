"""Bounded, read-only website results and explainable local ranking.

Only SubHD's observed result markup is supported. A website recommendation is
never a verified subtitle match, and this module performs no network/file IO.
"""
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from ...domain.matching import extract_episode
from .zimuku import search_terms, source_url

LANGUAGES = {
    "bilingual": "中英双语优先", "zh-Hans": "简体中文优先",
    "zh-Hant": "繁体中文优先", "en": "英语优先",
}
MAX_CANDIDATES = 60


def candidates_script(site, query):
    payload = json.dumps({"hosts": sorted(site.hosts), "provider": site.provider,
                          "query": query, "limit": MAX_CANDIDATES}, ensure_ascii=True)
    return r"""(() => {
      const c = PAYLOAD, u = new URL(location.href);
      const done = (status, rows=[]) => JSON.stringify({status, rows});
      if (u.protocol !== 'https:' || !c.hosts.includes(u.hostname)
          || (u.port && u.port !== '443') || u.username || u.password) return done('untrusted');
      if (c.provider !== 'subhd') return done('unsupported');
      const norm = s => s.normalize('NFKC').trim().replace(/\s+/g,' ').toLowerCase();
      if (!u.pathname.startsWith('/search/')
          || norm(decodeURIComponent(u.pathname.slice(8))) !== norm(c.query)) return done('not_results');
      const text = n => (n?.textContent || '').replace(/\s+/g,' ').trim().slice(0,1200);
      const rows = [], seen = new Set();
      // Observed 2026-10-23: each result has one .clearfix container with
      // a release .view-text link and a .text-truncate metadata strip.
      for (const a of Array.from(document.querySelectorAll('.view-text a[href^="/a/"]')).slice(0,180)) {
        const box = a.closest('.clearfix');
        if (!box || seen.has(a.href)) continue;
        const detail = new URL(a.href);
        if (detail.origin !== u.origin || !/^\/a\/[A-Za-z0-9]+\/?$/.test(detail.pathname)) continue;
        seen.add(a.href);
        rows.push({url:a.href, title:text(box.querySelector('.float-start a')),
                   release:text(a), metadata:text(box.querySelector('.text-truncate'))});
        if (rows.length >= c.limit) break;
      }
      if (rows.length) return done('ready',rows);
      const body = (document.body?.innerText || '').slice(0,5000);
      return done(/(?:共\s*0\s*条|没有找到|未找到|没有搜索到)/.test(body) ? 'empty' : 'unrecognized');
    })()""".replace("PAYLOAD", payload)


def clean_text(value, limit):
    if not isinstance(value, str):
        return ""
    return " ".join("".join(ch for ch in value[:limit * 2]
                            if not unicodedata.category(ch).startswith("C")).split())[:limit]


def parse_candidates(raw, site):
    if not isinstance(raw, str) or len(raw) > 256_000:
        return "unrecognized", []
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        return "unrecognized", []
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return "unrecognized", []
    rows, seen = [], set()
    for item in data["rows"][:MAX_CANDIDATES]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or len(url) > 2048 or not source_url(url, site.hosts):
            continue
        parts = urlsplit(url)
        if site.provider != "subhd" or not re.fullmatch(r"/a/[A-Za-z0-9]+/?", parts.path):
            continue
        # No signed query, fragment, cookie, markup or download URL retained.
        url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        if url in seen:
            continue
        title, release = clean_text(item.get("title"), 400), clean_text(item.get("release"), 1200)
        if not release:
            continue
        seen.add(url)
        rows.append({"url": url, "title": title, "release": release,
                     "metadata": clean_text(item.get("metadata"), 400), "provider": site.provider,
                     "endpoint": site.key})
    status = data.get("status")
    if status == "ready":
        return ("ready", rows) if rows else ("unrecognized", [])
    return (status if status in {"empty", "unsupported", "not_results", "untrusted"} else "unrecognized"), []


def _words(value):
    return set(re.findall(r"[a-z]+|[\u3400-\u9fff]+", unicodedata.normalize("NFKC", value).casefold()))


def _title(value):
    # search_terms takes a filename; append a neutral suffix for free text.
    value = re.sub(r"(?i)\.(mkv|mp4|avi|mov|wmv|m4v|ts)$", "", value)
    value = search_terms(value + ".mkv")
    value = re.sub(r"(?i)s\d{1,2}e\d{1,3}|第\s*\d+\s*集|\b(?:19|20)\d{2}\b", " ", value)
    return _words(value)


def rank_candidates(rows, video_name, preference="bilingual"):
    preference = preference if preference in LANGUAGES else "bilingual"
    video_title = _title(video_name)
    video_years = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", video_name))
    video_episode = extract_episode(video_name)
    ranked = []
    for order, row in enumerate(rows):
        names = row["title"] + " " + row["release"]
        words = _title(names)
        overlap = len(video_title & words) / max(1, len(video_title))
        reasons, warnings = [], []
        if overlap >= .8:
            reasons.append("片名关键词一致")
        else:
            warnings.append("片名需人工核对（中英文别名不作自动推断）")
        candidate_years = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", names))
        conflict = bool(video_years and candidate_years and not video_years & candidate_years)
        if conflict:
            warnings.append("年份不一致")
        elif video_years & candidate_years:
            reasons.append("年份一致")
        elif video_years:
            warnings.append("候选未标明年份")
        candidate_episode = extract_episode(names)
        if video_episode and candidate_episode:
            mismatch = (video_episode[1] != candidate_episode[1] or
                        (video_episode[0] is not None and candidate_episode[0] is not None
                         and video_episode[0] != candidate_episode[0]))
            conflict |= mismatch
            (warnings if mismatch else reasons).append("集数不一致" if mismatch else "季集一致")
        elif video_episode:
            warnings.append("候选未标明对应集数，可能为合集")
        metadata = row["metadata"]
        chinese = bool(re.search("简体|繁体|中文|简中|繁中", metadata))
        english = bool(re.search(r"英语|英文|(?i:\benglish\b)", metadata))
        bilingual = chinese and english and bool(re.search(r"双语|(?i:\bbilingual\b)", metadata))
        tags = {"bilingual": bilingual, "zh-Hans": bool(re.search("简体|简中", metadata)),
                "zh-Hant": bool(re.search("繁体|繁中", metadata)), "en": english}
        languages = [name for key, name in (("bilingual", "中英双语"), ("zh-Hans", "简体"),
                                           ("zh-Hant", "繁体"), ("en", "英语")) if tags[key]]
        if chinese and english and not bilingual:
            languages.append("含中英文，未注明双语")
        preferred = tags[preference]
        if preferred:
            reasons.append("符合语言偏好（网站标注）")
        else:
            warnings.append("语言未明确符合偏好")
        # Conflicts are always last; numeric rank is internal, never a probability.
        score = overlap * 100 + (25 if preferred else 0) + (12 if video_years & candidate_years else 0)
        ranked.append({**row, "language": " · ".join(languages) or "语言未标明",
                       "reasons": reasons, "warnings": warnings, "needsReview": bool(warnings),
                       "label": "信息冲突" if conflict else "需核对" if warnings else "优先查看",
                       "_rank": (conflict, -score, order)})
    ranked.sort(key=lambda item: item["_rank"])
    for row in ranked:
        row.pop("_rank")
    return ranked
