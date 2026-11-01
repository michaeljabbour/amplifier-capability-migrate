"""The run monitor must reject corrupted histories instead of reporting green."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))
import hillclimb
import fitness


class MonitorIntegrityTests(unittest.TestCase):
    def test_compensated_deletion_is_not_progress(self):
        before = [("42", "extract", "new"), ("43", "render", "new")]
        after = [("43", "render", "implemented")]
        ok, _ = hillclimb.check([before, after])
        self.assertFalse(ok)

    def test_duplicate_story_key_is_invalid(self):
        ok, _ = hillclimb.check([[("42", "extract", "new"), ("42", "render", "implemented")]])
        self.assertFalse(ok)

    def test_unknown_state_is_invalid(self):
        ok, _ = hillclimb.check([[("42", "extract", "done")]])
        self.assertFalse(ok)

    def test_reassigning_a_story_label_does_not_verify_the_old_story(self):
        before = [("42", "extract", "implemented")]
        after = [("42", "different-behavior", "verified")]
        ok, _ = hillclimb.check([before, after], verifier=True)
        self.assertFalse(ok)

    def test_verifier_may_reopen_implemented_story(self):
        before = [("42", "extract", "implemented")]
        after = [("42", "extract", "new")]
        self.assertTrue(hillclimb.check([before, after], verifier=True)[0])
        self.assertFalse(hillclimb.check([before, after])[0])

    def test_no_history_is_not_evidence_of_progress(self):
        self.assertFalse(hillclimb.check([])[0])

    def test_empty_backlog_snapshot_is_valid(self):
        self.assertTrue(hillclimb.check([[]])[0])
        self.assertEqual(fitness.fitness([])["total"], 0)

    def test_acknowledged_never_earns_verified_credit(self):
        result = fitness.fitness([("42", "extract", "acknowledged")])
        self.assertEqual((result["acknowledged"], result["verified_frac"], result["landed_frac"]), (1, 0, 0))

    def test_parser_preserves_identity_by_rejecting_edge_whitespace(self):
        with tempfile.TemporaryDirectory(prefix="gm-monitor-identity-") as temp:
            path = Path(temp) / "fictional.tsv"
            for text in ["42 \ttitle\timplemented\n", "42\t title\timplemented\n", "42\ttitle\timplemented \n"]:
                with self.subTest(text=text):
                    path.write_text(text)
                    with self.assertRaises(ValueError):
                        fitness.read_rows(str(path))

    def test_snapshot_keys_must_address_a_pipeline_story(self):
        for key in ["42 A", "42/child", ".", "..", "clé", "42;echo"]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                fitness.fitness([(key, "valid-title", "implemented")])

if __name__ == "__main__":
    unittest.main()
