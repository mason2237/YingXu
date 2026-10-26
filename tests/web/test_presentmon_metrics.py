"""Guard the independent presentation gate against CPU/overlay false positives."""
import unittest

from scripts.analyze_presentmon import analyze, phase_metrics


class PresentationMetricsTests(unittest.TestCase):
    def test_displayed_intervals_enforce_refresh_and_tail_gates(self):
        fast = [i * 1000 / 180 for i in range(1800)]
        slow = [i * 1000 / 60 for i in range(600)]
        self.assertTrue(phase_metrics(fast, 0, 10000, 250)["passed"])
        self.assertFalse(phase_metrics(slow, 0, 10000, 250)["passed"])
        stalls = [t for i, t in enumerate(fast) if i % 90 not in range(8)]
        self.assertFalse(phase_metrics(stalls, 0, 10000, 250)["passed"])

    def test_missing_edge_coverage_is_inconclusive(self):
        times = [i * 1000 / 180 for i in range(180, 1500)]
        self.assertFalse(phase_metrics(times, 0, 10000, 250)["conclusive"])

    def test_cpu_frames_and_hover_only_overlay_do_not_pass(self):
        record = {"completed": True, "nativeWindowVisible": True,
                  "clock": {"uncertaintyMs": 20}, "processes": [{"id": 1}],
                  "passes": [{"iteration": 1, "phases": {
                      name: {"completed": True, "startQpcMs": i * 10000,
                             "endQpcMs": (i + 1) * 10000}
                      for i, name in enumerate(("hover", "drag", "scroll"))}}]}
        def rows(displayed=True, all_phases=True):
            for i in range(5400 if all_phases else 1800):
                yield {"ProcessID": "1", "SwapChainAddress": "ui", "VidPnSourceId": "0",
                       "LayerIndex": "0", "CPUStartQPCTime": str(i * 1000 / 180),
                       "DisplayLatency": "5", "DisplayedTime": "5.555" if displayed else "NA"}
        self.assertTrue(analyze(rows(), record)["passed"])
        self.assertFalse(analyze(rows(displayed=False), record)["conclusive"])
        self.assertFalse(analyze(rows(all_phases=False), record)["conclusive"])
        ambiguous = list(rows())
        ambiguous += [{**row, "SwapChainAddress": "another"} for row in ambiguous]
        self.assertFalse(analyze(ambiguous, record)["conclusive"])


if __name__ == "__main__":
    unittest.main()
