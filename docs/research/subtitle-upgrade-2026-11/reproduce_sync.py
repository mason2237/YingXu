"""Optional upstream experiment; requires ffsubsync 0.5.1 at the recorded SHA.

Generates original subtitle text and timestamps. Never opens real media.
Run with the isolated research virtual environment, not YingXu's runtime.
"""
from datetime import timedelta
import json
from pathlib import Path
import random
import tempfile

import srt
from ffsubsync.ffsubsync import make_parser, run

rng = random.Random(20261109)
cues, position = [], 15.0
for index in range(100):
    position += rng.uniform(2.0, 8.0)
    duration = rng.uniform(.6, 2.5)
    cues.append(srt.Subtitle(index + 1, timedelta(seconds=position),
                            timedelta(seconds=position + duration), f"Generated line {index + 1}"))
    position += duration

outcomes = []
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    ref = root / "reference.srt"
    ref.write_text(srt.compose(cues), encoding="utf-8")
    for name, scale, offset in (("offset", 1.0, 2.5), ("drift", 25 / 24, 2.5)):
        inp, out = root / (name + ".srt"), root / (name + ".synced.srt")
        shifted = [srt.Subtitle(c.index, c.start * scale + timedelta(seconds=offset),
                               c.end * scale + timedelta(seconds=offset), c.content) for c in cues]
        inp.write_text(srt.compose(shifted), encoding="utf-8")
        before = inp.read_bytes()
        args = [str(ref), "-i", str(inp), "-o", str(out), "--skip-sync-on-low-quality"]
        if name == "offset":
            args.append("--no-fix-framerate")
        result = run(make_parser().parse_args(args))
        synced = list(srt.parse(out.read_text(encoding="utf-8")))
        expected = list(srt.parse(ref.read_text(encoding="utf-8")))
        max_error = max(abs((a.start - b.start).total_seconds()) for a, b in zip(synced, expected))
        assert result["retval"] == 0 and result["sync_was_successful"]
        assert len(synced) == len(expected) == 100
        assert max_error <= .03
        assert inp.read_bytes() == before
        assert [c.content for c in synced] == [c.content for c in expected]
        outcomes.append({"case": name, "input_scale": scale, "input_offset_seconds": offset,
                         "cue_count": len(synced), "max_start_error_seconds": max_error,
                         "input_unchanged": True, "text_unchanged": True,
                         "retval": result["retval"], "sync_was_successful": result["sync_was_successful"]})
output = Path(__file__).with_name("evidence") / "sync-probe.json"
output.write_text(json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
print(json.dumps(outcomes, indent=2))
