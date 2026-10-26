"""Correlate displayed PresentMon frames with bounded architecture-probe phases.

Uses CPUStartQPCTime + DisplayLatency, never CPU FrameTime or rAF as scanout.
An overlay-only stream cannot qualify: one stream must cover every input phase.
"""
import argparse
import csv
import json
import math
from pathlib import Path


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def phase_metrics(times, start, end, trim_ms):
    start, end = start + trim_ms, end - trim_ms
    if end <= start:
        return {"conclusive": False, "reason": "Phase shorter than edge exclusion"}
    selected = sorted({t for t in times if start <= t <= end})
    if len(selected) < 2:
        return {"conclusive": False, "displayedFrames": len(selected), "coverage": 0}
    gaps = [b - a for a, b in zip(selected, selected[1:])]
    span = selected[-1] - selected[0]
    coverage = span / (end - start)
    ordered = sorted(gaps)
    fps = 1000 * len(gaps) / span
    p95 = ordered[min(len(ordered) - 1, math.floor(len(ordered) * .95))]
    over25 = sum(gap > 25 for gap in gaps) * 100 / len(gaps)
    conclusive = coverage >= .95
    return {"conclusive": conclusive, "displayedFrames": len(selected),
            "coverage": round(coverage, 5), "fps": round(fps, 3),
            "p95Ms": round(p95, 4), "over25Percent": round(over25, 4),
            "maxMs": round(max(gaps), 4),
            "passed": conclusive and fps >= 120 and p95 <= 11.2 and over25 < 1}


def analyze(rows, record):
    clock = record.get("clock", {})
    if not record.get("completed") or not record.get("nativeWindowVisible"):
        return {"conclusive": False, "passed": False, "reason": "Incomplete or hidden-window run"}
    uncertainty = number(clock.get("uncertaintyMs"))
    if uncertainty is None or uncertainty >= 250:
        return {"conclusive": False, "passed": False, "reason": "Missing or imprecise QPC anchor"}
    trim_ms = max(250, uncertainty * 4)
    ids = {str(item["id"]) for item in record["processes"]}
    streams = {}
    for row in rows:
        if row["ProcessID"] not in ids:
            continue
        cpu, latency, displayed = (number(row[key]) for key in
                                   ("CPUStartQPCTime", "DisplayLatency", "DisplayedTime"))
        if cpu is None or latency is None or displayed is None or displayed <= 0:
            continue
        key = (row["ProcessID"], row["SwapChainAddress"], row["VidPnSourceId"], row["LayerIndex"])
        streams.setdefault(key, []).append(cpu + latency)
    candidates = []
    for key, times in streams.items():
        phases = []
        for run in record["passes"]:
            for name, phase in run["phases"].items():
                if not phase.get("completed") or not all(field in phase for field in ("startQpcMs", "endQpcMs")):
                    return {"conclusive": False, "passed": False, "reason": "Missing completed phase boundaries"}
                metrics = phase_metrics(times, phase["startQpcMs"], phase["endQpcMs"], trim_ms)
                phases.append({"iteration": run["iteration"], "phase": name, **metrics})
        candidates.append({"processId": int(key[0]), "swapChain": key[1], "display": key[2], "layer": key[3],
                           "displayedSamples": len(times), "phases": phases,
                           "continuous": bool(phases) and all(p.get("conclusive") for p in phases)})
    eligible = [candidate for candidate in candidates if candidate["continuous"]]
    if len(eligible) != 1:
        return {"conclusive": False, "passed": False, "trimMs": trim_ms, "streams": candidates,
                "reason": "No unique continuous UI stream; do not substitute a partial HDR overlay stream"}
    main = eligible[0]
    passed = all(phase["passed"] for phase in main["phases"])
    return {"conclusive": True, "passed": passed, "trimMs": trim_ms, "streams": candidates,
            "primaryStream": {key: main[key] for key in ("processId", "swapChain", "display", "layer")},
            "reason": "All displayed-frame gates passed" if passed else "At least one displayed-frame phase misses the gate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True, action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    results = []
    for run in args.run:
        record = json.loads(run.read_text(encoding="utf-8-sig"))
        results.append({"host": record["host"], "effects": record["effects"], **analyze(rows, record)})
    report = {"method": "PresentMon 2.6.0 ETW: CPUStartQPCTime + DisplayLatency; displayed rows only",
              "gate": {"fpsMin": 120, "p95MsMax": 11.2, "over25PercentBelow": 1,
                       "coverageMin": .95}, "results": results,
              "passed": bool(results) and all(item["passed"] for item in results)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "results": [
        {key: result[key] for key in ("host", "effects", "conclusive", "passed", "reason")}
        for result in results]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
