"""Exercise the public ledger command against a fictional, isolated TSV file."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LEDGER_SCRIPT = Path(__file__).resolve().parents[1] / "pipelines" / "ledger.py"

class LedgerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="migrate-ledger-")
        self.addCleanup(self.temp.cleanup)
        self.ledger = Path(self.temp.name) / "fictional.tsv"
        self.ledger.write_text("42\tunicode-label-cafe\tnew\n43\tother\timplemented\n44\thandoff\tacknowledged\n")

    def command(self, *args):
        return subprocess.run([sys.executable, str(LEDGER_SCRIPT), *args],
            env={**os.environ, "LEDGER_FILE": str(self.ledger)},
            text=True, capture_output=True, timeout=5)

    def test_queue_returns_key_not_label(self):
        result = self.command("earliest")
        self.assertEqual((result.returncode, result.stdout), (0, "42 unicode-label-cafe\n"))
        self.assertEqual(self.command("earliest-implemented").stdout, "43 other\n")

    def test_duplicate_add_preserves_existing_key_and_state(self):
        before = self.ledger.read_bytes()
        result = self.command("add", "43", "replacement")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_valid_update_changes_one_key_and_keeps_handoff_distinct(self):
        result = self.command("update", "42", "implemented")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ledger.read_text(), "42\tunicode-label-cafe\timplemented\n43\tother\timplemented\n44\thandoff\tacknowledged\n")
        self.assertEqual(self.command("stats").stdout, "acknowledged=1 implemented=2\n")
        self.assertNotIn("verified=", self.command("stats").stdout)

    def test_unknown_state_is_failure_and_preserves_ledger(self):
        before = self.ledger.read_bytes()
        result = self.command("update", "42", "done")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertIn("state", result.stderr.lower())

    def test_missing_key_is_failure_and_preserves_ledger(self):
        before = self.ledger.read_bytes()
        result = self.command("update", "404", "verified")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertIn("404", result.stderr)

    def test_add_rejects_tsv_corruption_without_writing(self):
        for issue, label in [("", "title"), ("#42", "title"), (" 99", "title"),
                             ("99", ""), ("99", "trailing "), ("99\tx", "title"),
                             ("99", "a\nb"), ("99", "a\rb"), ("99", "a\u2028b"),
                             ("99\u0085x", "title")]:
            with self.subTest(issue=issue, label=label):
                before = self.ledger.read_bytes()
                result = self.command("add", issue, label)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.ledger.read_bytes(), before)

    def test_corrupt_existing_ledger_is_refused_before_rewrite(self):
        for data in ["42\ttitle\tnew\textra\n", "42\ttitle\tdone\n",
                     "42\ttitle\tnew\n42\tother\timplemented\n", "42\t\tnew\n"]:
            with self.subTest(data=data):
                self.ledger.write_text(data)
                result = self.command("update", "42", "implemented")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.ledger.read_text(), data)

    def test_verified_is_terminal_but_idempotent_confirmation_is_valid(self):
        self.ledger.write_text("42\ttitle\tverified\n")
        for state in ["new", "implemented", "acknowledged"]:
            with self.subTest(state=state):
                before = self.ledger.read_bytes()
                self.assertNotEqual(self.command("update", "42", state).returncode, 0)
                self.assertEqual(self.ledger.read_bytes(), before)
        self.assertEqual(self.command("update", "42", "verified").returncode, 0)

    def test_unreadable_ledger_returns_nonzero_without_traceback(self):
        self.ledger.unlink()
        self.ledger.mkdir()
        result = self.command("stats")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)

    def test_new_unicode_label_round_trips(self):
        self.assertEqual(self.command("add", "99", "café-河").returncode, 0)
        self.assertIn("99\tcafé-河\tnew\n", self.ledger.read_text())

    def test_add_refuses_keys_that_cannot_identify_a_pipeline_story(self):
        for key in ["42 A", "42/child", ".", "..", "clé", "42;echo"]:
            with self.subTest(key=key):
                before = self.ledger.read_bytes()
                self.assertNotEqual(self.command("add", key, "valid-title").returncode, 0)
                self.assertEqual(self.ledger.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
