"""Run the declared portable subset or the full Windows suite, with evidence.

No websites, desktop windows, downloads, or publishing are started by this runner.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PORTABLE_CONTRACTS = ("test_core.py", "test_subtitle_sources.py", "test_desktop_protocol.py")


class CountingResult(unittest.TextTestResult):
    """Count successful methods directly; failed subtests are not test methods."""
    passed = 0

    def addSuccess(self, test):
        self.passed += 1
        super().addSuccess(test)


def preflight():
    # The suite deliberately runs with -S. Inspect the same interpreter's installed
    # media dependency in a separate, isolated process without changing sys.path.
    command = (
        "import json, pathlib; import pymediainfo; from pymediainfo import MediaInfo; "
        "p=pathlib.Path(pymediainfo.__file__).with_name('MediaInfo.dll'); "
        "print(json.dumps({'version':pymediainfo.__version__, 'dll_present':p.is_file(), "
        "'can_parse':bool(p.is_file() and MediaInfo.can_parse(library_file=str(p)))}))"
    )
    try:
        probe = subprocess.run([sys.executable, "-I", "-c", command], capture_output=True,
                               text=True, timeout=20)
        media = json.loads(probe.stdout) if probe.returncode == 0 else {
            "error": "pymediainfo/MediaInfo.dll 不可用，请按 requirements-runtime.txt 安装依赖。"}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        media = {"error": "MediaInfo 预检失败；未将内嵌字幕测试标为通过。"}
    return {"python": platform.python_version(), "os": platform.platform(),
            "windows": os.name == "nt", "media": media}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("portable", "windows"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "work/test-results/platform-tests.json")
    args = parser.parse_args()
    (ROOT / "work/test-results").mkdir(parents=True, exist_ok=True)
    environment = preflight()
    report = {"schema": 1, "suite": args.suite, "environment": environment,
              "scope": "all tests" if args.suite == "windows" else
                  {"unit": "all", "contract": PORTABLE_CONTRACTS,
                   "excluded": "other contracts, integration and recovery; run on Windows"}}
    if args.suite == "windows" and (os.name != "nt" or
            not environment["media"].get("can_parse")):
        report.update(status="environment_error", success=False,
                      reason="Windows 全量检查要求 Windows 和可加载的 MediaInfo.dll。")
        code = 2
    else:
        loader = unittest.TestLoader()
        if args.suite == "windows":
            suite = loader.discover(str(ROOT / "tests"))
        else:
            suite = unittest.TestSuite([unittest.TestLoader().discover(str(ROOT / "tests/unit"))])
            for pattern in PORTABLE_CONTRACTS:
                suite.addTests(unittest.TestLoader().discover(str(ROOT / "tests/contract"), pattern))
        start = time.monotonic()
        result = unittest.TextTestRunner(verbosity=2, resultclass=CountingResult).run(suite)
        report.update(status="completed", success=result.wasSuccessful(),
            seconds=round(time.monotonic()-start, 3), total=result.testsRun,
            passed=result.passed,
            failures=[{"test": t.id(), "traceback": trace} for t, trace in result.failures],
            errors=[{"test": t.id(), "traceback": trace} for t, trace in result.errors],
            skipped=[{"test": t.id(), "reason": reason} for t, reason in result.skipped])
        code = 0 if result.wasSuccessful() else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"failures", "errors"}},
                     ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
