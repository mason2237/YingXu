"""Run from the repository root with python -S; no third-party dependencies."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from yingxu.domain.matching import similarity
from yingxu.adapters.subtitle_downloads import inspect_download

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline-ref', default='c7b8056b35d02e335723366e9916512032133a13')
parser.add_argument('--output', type=Path, default=Path(__file__).with_name('evidence') / 'matching-probe.json')
args = parser.parse_args()
BASE = args.baseline_ref
source = subprocess.check_output(
    ["git", "show", BASE + ":yingxu/domain/matching.py"], cwd=ROOT, text=True, encoding='utf-8'
)
original = types.ModuleType("original_matching")
sys.modules[original.__name__] = original
try:
    exec(compile(source, "original_matching", "exec"), original.__dict__)
finally:
    sys.modules.pop(original.__name__, None)

cases = [
    ("Show.S01E01E02.mkv", "Show.S01E01.chs.srt", True),
    ("Show.S01E01-E03.mkv", "Show.S01E01.chs.srt", True),
    ("Show.S01E01E03.mkv", "Show.S01E01E02.chs.srt", True),
    ("Show.Ｓ０１Ｅ０１.mkv", "Show.S01E02.chs.srt", True),
    ("Show.S01E01.mkv", "Show.S01E01.chs.srt", False),
]
comparison = [{"video": v, "subtitle": s, "conflict": conflict,
               "before": original.similarity(Path(v), Path(s)),
               "after": similarity(Path(v), Path(s))} for v, s, conflict in cases]
assert all(row["after"] == 0 for row in comparison if row["conflict"])
assert comparison[-1]["after"] == comparison[-1]["before"] == 1

names = [f"{title}.S{season:02d}E{number:02d}"
         for title in ("Show", "剧集", "Different.Title")
         for season in (1, 2) for number in range(1, 16)]
pairs = [(Path(v + ".mkv"), Path(s + ".chs.srt")) for v in names for s in names]
start = time.perf_counter()
before = [original.similarity(v, s) for v, s in pairs]
before_seconds = time.perf_counter() - start
start = time.perf_counter()
after = [similarity(v, s) for v, s in pairs]
after_seconds = time.perf_counter() - start
assert before == after

# Recognition is not a quality check; these probes document the next-stage gap.
recognition = []
with tempfile.TemporaryDirectory() as directory:
    for name, content in (
        ("empty.ass", "[Script Info]\n[Events]\n"),
        ("reversed.srt", "1\n00:00:02,000 --> 00:00:01,000\nGenerated text\n"),
    ):
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        recognition.append({"file": name, "result": inspect_download(path)})

result = {"baseline": BASE, "cases": comparison,
          "unchanged_single_episode_scores": len(pairs),
          "one_run_seconds_not_a_performance_claim": {"before": before_seconds, "after": after_seconds},
          "format_recognition_is_not_quality": recognition}
output = args.output
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
