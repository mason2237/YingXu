"""Embedded subtitle language policy over metadata; no media or network access."""
from copy import deepcopy
import re

LANGUAGES = {
    "chinese": "中文（双语优先）", "bilingual": "仅中英双语",
    "simplified": "简体中文", "traditional": "繁体中文",
    "english": "英语", "japanese": "日语", "korean": "韩语", "any": "任意语言（含未标注）",
}
DEFAULT_OPTIONS = {"enabled": True, "language": "chinese"}
MAX_RESPONSE = 256 * 1024
MAX_READ = 16 * 1024 * 1024
_library_checked = False


class EngineUnavailable(RuntimeError):
    pass


def clean(value, limit=256):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _families(value):
    value = value.casefold()
    groups = {
        "zh": r"\b(?:zh(?:-[a-z]+)?|zho|chi|chinese|chs|cht)\b|中文|简体|繁体|簡體|繁體|简中|簡中|繁中",
        "en": r"\b(?:en(?:-[a-z]+)?|eng|english)\b|英语|英語",
        "ja": r"\b(?:ja|jpn|japanese)\b|日语|日語",
        "ko": r"\b(?:ko|kor|korean)\b|韩语|韓語",
    }
    return {key for key, pattern in groups.items() if re.search(pattern, value)}


def track_info(track, number):
    raw, title = clean(track.language, 80), clean(track.title)
    declared, named = _families(raw), _families(title)
    if not declared and raw and raw.casefold() not in {"und", "undefined", "unknown"}:
        declared = {"other"}
    bilingual = bool(re.search(r"中英|简英|繁英|簡英|(?:chs|cht|chinese|中文|简中|繁中)\W{0,8}(?:eng|english|英文|英语)|(?:eng|english|英文|英语)\W{0,8}(?:chs|cht|chinese|中文|简中|繁中)", title, re.I))
    if bilingual: named |= {"zh", "en"}
    ambiguous = bool(declared and named and declared.isdisjoint(named))
    families = set() if ambiguous else declared or named
    if bilingual and not ambiguous:
        families |= {"zh", "en"}
    script = ""
    if "zh" in families:
        simplified = bool(re.search(r"zh-(?:cn|sg|hans)|简体|簡體|简中|簡中|简英|簡英|\bchs\b|\bsc\b|\bsimplified\b", raw+" "+title, re.I))
        traditional = bool(re.search(r"zh-(?:tw|hk|mo|hant)|繁体|繁體|繁中|繁英|\bcht\b|\btc\b|\btraditional\b", raw+" "+title, re.I))
        script = "simplified" if simplified and not traditional else "traditional" if traditional and not simplified else ""
    labels = {"zh": "简体中文" if script == "simplified" else "繁体中文" if script == "traditional" else "中文",
              "en": "英语", "ja": "日语", "ko": "韩语"}
    label = "中英双语" if {"zh", "en"} <= families else " / ".join(labels.get(key, raw) for key in sorted(families))
    if not label:
        label = "语言标注冲突" if ambiguous else raw if raw and raw.casefold() not in {"und", "undefined", "unknown"} else "语言未标注"
    codec = clean(track.format or track.codec_id, 80) or "未知格式"
    yes = lambda value: clean(value).casefold() in {"yes", "true", "1"}
    forced = yes(track.forced) or bool(re.search(r"\bforced\b|强制|強制|(?:仅|僅).{0,3}(?:歌曲|对白|對白)|signs?\s*(?:&|and|/)\s*songs?", title, re.I))
    commentary = bool(re.search(r"\bcommentary\b|导演.{0,2}(?:评论|解说)|導演.{0,2}(?:評論|解說)", title, re.I))
    return {"trackId": f"track-{number}", "title": title, "language": label,
            "declaredLanguage": raw, "families": sorted(families), "script": script,
            "codec": codec, "kind": "bitmap" if re.search(r"pgs|vobsub|dvb|rle", codec, re.I) else "text",
            "default": yes(track.default), "forced": forced, "commentary": commentary,
            "ambiguous": ambiguous, "languageSource": "metadata+title" if declared and bilingual and not {"zh","en"} <= declared else "metadata" if declared else "title" if families else "unknown"}


def assess(info, options):
    """Unknown/contradictory language never silently passes a language rule."""
    result = deepcopy(info)
    tracks = result.get("tracks", [])
    language = options["language"]
    accepted = []
    for track in tracks:
        family = set(track["families"])
        allowed = (language == "any" or
                   language == "chinese" and "zh" in family or
                   language == "bilingual" and {"zh", "en"} <= family or
                   language in {"simplified", "traditional"} and track["script"] == language or
                   language == "english" and "en" in family or
                   language == "japanese" and "ja" in family or
                   language == "korean" and "ko" in family)
        if allowed and not track["forced"] and not track["commentary"] and (not track["ambiguous"] or language == "any"):
            accepted.append(track["trackId"])
    satisfied = result.get("status") == "ok" and bool(accepted)
    if satisfied:
        reason = f"内嵌字幕符合“{LANGUAGES[language]}”，已通过，无需外挂字幕。"
    elif result.get("status") == "disabled":
        reason = "未启用视频内字幕检查。"
    elif result.get("status") != "ok":
        reason = result.get("error") or "未能读取视频内字幕信息，保留外挂匹配结果。"
    elif not tracks:
        reason = "未发现独立字幕轨；烧录在画面中的字幕无法通过轨道信息判断。"
    elif all(track["forced"] or track["commentary"] for track in tracks):
        reason = "仅有强制/片段或评论字幕，不按完整字幕自动通过。"
    elif result.get("truncated"):
        reason = "本次仅检查前 64 条字幕轨，未确认满足语言要求，请人工核对。"
    elif any(track["ambiguous"] or not track["families"] for track in tracks):
        reason = "内嵌字幕语言未标明或标注冲突，保留待处理，请核对语言。"
    else:
        reason = f"内嵌语言不符合“{LANGUAGES[language]}”，继续匹配外挂字幕。"
    result.update(satisfied=satisfied, acceptedTrackIds=accepted if satisfied else [],
                  policy=language, policyLabel=LANGUAGES[language], reason=reason)
    return result
