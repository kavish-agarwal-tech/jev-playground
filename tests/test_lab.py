import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from support_lab.core import MockFrontier, MockJev, evaluate, load_data, run


class LabTests(unittest.TestCase):
    def test_blocked_ticket_preserves_escalation(self):
        result = run("Our entire team cannot export reports.")
        self.assertEqual(result["routing"]["action"], "human_review")
        self.assertGreater(result["triage"]["multiple_users"]["noul"], .8)
        self.assertFalse(result["routing"]["sent"])

    def test_unknown_and_conflicting_categories(self):
        for text in ("Something is wrong", "My invoice and login have errors"):
            self.assertEqual(run(text)["routing"]["action"], "human_review")

    def test_threshold_changes_routing(self):
        self.assertEqual(run("Where is my invoice?", threshold=.75)["routing"]["action"], "draft_ready")
        self.assertEqual(run("Where is my invoice?", threshold=.95)["routing"]["action"], "human_review")

    def test_distributions_and_retrieval(self):
        for ticket in load_data("tickets"):
            result = run(ticket["text"])
            self.assertAlmostEqual(sum(result["triage"]["category"]["probabilities"].values()), 1)
            self.assertAlmostEqual(sum(result["triage"]["impact"]["probabilities"]), 1)
            for doc in result["evidence"]:
                self.assertIn(f"[{doc['id']}]", result["draft"])
        self.assertEqual(run("export csv")["evidence"][0]["category"], "exports")
        result = run("Since yesterday our entire team cannot export reports for a presentation.")
        self.assertTrue(all(doc["category"] in ("exports", "other") for doc in result["evidence"]))

    def test_unsafe_draft_escalates(self):
        class PromiseFrontier(MockFrontier):
            def draft(self, text, category, evidence):
                return "This will be fixed today."
        result = run("Where is my invoice?", frontier_provider=PromiseFrontier())
        self.assertEqual(result["routing"]["action"], "human_review")
        self.assertGreater(result["review"]["unverified_fix_promise"]["noul"], .8)

    def test_frontier_only_never_calls_jev(self):
        class ExplodingJev(MockJev):
            def triage(self, text):
                raise AssertionError("Jev must not be called")
            def review(self, text, draft):
                raise AssertionError("Jev must not be called")
        result = run("invoice", mode="frontier-only", decision_provider=ExplodingJev())
        self.assertEqual(result["usage"]["jev_calls"], 0)
        self.assertEqual(result["usage"]["frontier_calls"], 3)
        self.assertNotIn("mock-jev", [s["provider"] for s in result["stages"]])

    def test_invalid_inputs(self):
        for text in ("", "  ", "x" * 10001):
            with self.assertRaises(ValueError):
                run(text)
        for threshold in (-1, 2, float("nan")):
            with self.assertRaises(ValueError):
                run("invoice", threshold=threshold)

    def test_evaluation_metrics_and_split(self):
        report = evaluate("test")
        for metrics in report["modes"].values():
            rows = metrics["tickets"]
            self.assertEqual({r["id"] for r in rows}, {t["id"] for t in load_data("tickets") if t["split"] == "test"})
            self.assertEqual(metrics["category_accuracy"], sum(r["expected_category"] == r["predicted_category"] for r in rows) / len(rows))
            urgent = [r for r in rows if r["urgent"]]
            self.assertEqual(metrics["urgent_recall"], sum(r["human_review"] for r in urgent) / len(urgent))
            self.assertEqual(metrics["api_cost_usd"], 0)

    def test_cli_json_errors_and_no_overwrite(self):
        base = [sys.executable, "-m", "support_lab", "run"]
        result = subprocess.run(base + ["--ticket", "T01", "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "hybrid")
        self.assertNotEqual(subprocess.run(base + ["--ticket", "missing"], capture_output=True).returncode, 0)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trace.json"
            args = base + ["--ticket", "T02", "--output", str(output)]
            self.assertEqual(subprocess.run(args, capture_output=True).returncode, 0)
            original = output.read_bytes()
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
