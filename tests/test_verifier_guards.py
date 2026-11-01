"""Execute the verifier graph's actual shell commands in fictional repositories."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "pipelines/verify.dot"

class VerifierGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gm-verify-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.target = self.base / "target repo"
        self.target.mkdir()
        subprocess.run(["git", "-c", "core.fsmonitor=false", "init", "-q", str(self.target)], check=True, capture_output=True)
        self.ai = self.target / ".ai"
        self.ai.mkdir()
        self.backlog = self.base / "fictional.tsv"
        self.backlog.write_text("42\tfictional-title\timplemented\n")
        self.forge = self.base / "forge.py"
        self.forge.write_text("raise SystemExit(0)\n")
        self.env = {**os.environ, "SOURCE_PATH":str(self.base), "TARGET_PATH":str(self.target),
                    "FORGE_TOOL":str(self.forge), "LEDGER_TOOL":str(ROOT / "pipelines/ledger.py"),
                    "BACKLOG":str(self.backlog)}
        self.state("42", "fictional-title")

    def state(self, story, title):
        (self.ai / "verify_current.env").write_text(f"STORY={story}\nTITLE={title}\n")

    def command(self, node):
        text = re.search(node + r' \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")', GRAPH.read_text()).group(1)
        return json.loads(text)

    def run_node(self, node):
        return subprocess.run(["bash", "-c", self.command(node)], cwd=self.base,
            env=self.env, text=True, capture_output=True, timeout=5)

    def assert_token(self, node, token):
        result = self.run_node(node)
        self.assertEqual((result.returncode, result.stdout), (0, token), result.stderr)
        return result

    def test_failed_ledger_read_blocks_queue_and_selection(self):
        fake = self.base / "failed_ledger.py"
        fake.write_text("raise SystemExit(19)\n")
        self.env["LEDGER_TOOL"] = str(fake)
        (self.ai / "verify_current.env").unlink()
        for node in ["CheckQueue", "SelectRow"]:
            with self.subTest(node=node):
                self.assert_token(node, "blocked")
                self.assertFalse((self.ai / "verify_current.env").exists())

    def test_valid_queue_selection_preserves_label_data(self):
        self.backlog.write_text("42\tfictional label café\timplemented\n")
        self.assert_token("CheckQueue", "process")
        self.assert_token("SelectRow", "ready")
        self.assertEqual((self.ai / "verify_current.env").read_text(), "STORY=42\nTITLE=fictional label café\n")

    def test_empty_queue_is_done_and_does_not_select_empty_story(self):
        self.backlog.write_text("42\tfictional-title\tverified\n")
        self.assert_token("CheckQueue", "done")
        self.assert_token("SelectRow", "blocked")

    def test_all_nodes_refuse_wrong_target_without_writing_in_callers_cwd(self):
        self.env["TARGET_PATH"] = str(self.base / "missing")
        for node in ["CheckQueue", "SelectRow", "RunChecks", "MarkVerified", "ReopenGate"]:
            with self.subTest(node=node):
                self.assert_token(node, "blocked")
        self.assertFalse((self.base / ".ai").exists())

    def test_state_is_data_and_never_shell_evaluation(self):
        marker = self.base / "evaluated"
        self.state("42", "$(touch '" + str(marker) + "')")
        self.assert_token("MarkVerified", "next")
        self.assertFalse(marker.exists())

    def test_invalid_story_never_reaches_forge_or_ledger(self):
        marker = self.base / "evaluated"
        self.state("$(touch '" + str(marker) + "')", "title")
        before = self.backlog.read_bytes()
        for node in ["RunChecks", "MarkVerified", "ReopenGate"]:
            with self.subTest(node=node):
                self.assert_token(node, "blocked")
                self.assertFalse(marker.exists())
                self.assertEqual(self.backlog.read_bytes(), before)

    def test_failed_state_update_cannot_print_next_or_create_reopen_marker(self):
        self.state("404", "missing-title")
        findings = self.ai / "verify_findings"
        findings.mkdir()
        (findings / "404.md").write_text("DEFECT\nfictional\n")
        self.assert_token("MarkVerified", "blocked")
        self.assert_token("ReopenGate", "blocked")
        self.assertFalse((self.ai / "verify_reopened_404").exists())

    def test_run_checks_uses_real_script_exit_status(self):
        checks = self.ai / "verify_checks"
        checks.mkdir()
        script = checks / "42.sh"
        script.write_text("exit 0\n")
        self.assert_token("RunChecks", "pass")
        script.write_text("exit 7\n")
        self.assert_token("RunChecks", "fail")

    def test_first_defect_reopens_and_second_defect_acknowledges(self):
        findings = self.ai / "verify_findings"
        findings.mkdir()
        (findings / "42.md").write_text("DEFECT\nfictional\n")
        self.assert_token("ReopenGate", "next")
        self.assertIn("\tnew\n", self.backlog.read_text())
        self.backlog.write_text("42\tfictional-title\timplemented\n")
        self.assert_token("ReopenGate", "next")
        self.assertIn("\tacknowledged\n", self.backlog.read_text())

    def test_flake_rechecks_only_once(self):
        findings = self.ai / "verify_findings"
        findings.mkdir()
        (findings / "42.md").write_text("FLAKE\nfictional\n")
        self.assert_token("ReopenGate", "recheck")
        self.assert_token("ReopenGate", "next")
        self.assertIn("\tnew\n", self.backlog.read_text())

    def test_selection_refuses_symlinked_state_directory(self):
        self.ai.rename(self.target / ".ai-original")
        outside = self.base / "outside"
        outside.mkdir()
        self.ai.symlink_to(outside, target_is_directory=True)
        self.assert_token("SelectRow", "blocked")
        self.assertEqual(list(outside.iterdir()), [])

    def test_selection_refuses_symlinked_state_file(self):
        state = self.ai / "verify_current.env"
        state.unlink()
        outside = self.base / "outside.env"
        outside.write_text("preserve\n")
        state.symlink_to(outside)
        self.assert_token("SelectRow", "blocked")
        self.assertEqual(outside.read_text(), "preserve\n")

    def test_checks_write_target_scoped_logs(self):
        checks = self.ai / "verify_checks"
        checks.mkdir()
        (checks / "42.sh").write_text("printf fictional-output\n")
        self.assert_token("RunChecks", "pass")
        self.assertEqual((self.ai / "verify_logs/42.log").read_text(), "fictional-output")
        self.assertTrue((self.ai / "verify_logs/42-doctor.log").is_file())

    def test_checks_refuse_symlinked_log_directory(self):
        outside = self.base / "outside-logs"
        outside.mkdir()
        (self.ai / "verify_logs").symlink_to(outside, target_is_directory=True)
        self.assert_token("RunChecks", "blocked")
        self.assertEqual(list(outside.iterdir()), [])

    def test_empty_first_duplicate_assignments_are_not_state(self):
        for text in ["STORY=\nSTORY=42\nTITLE=title\n", "STORY=42\nTITLE=\nTITLE=title\n"]:
            with self.subTest(text=text):
                (self.ai / "verify_current.env").write_text(text)
                before = self.backlog.read_bytes()
                self.assert_token("MarkVerified", "blocked")
                self.assertEqual(self.backlog.read_bytes(), before)

    def test_missing_check_script_is_blocked_not_a_behavior_defect(self):
        self.assert_token("RunChecks", "blocked")
        self.assertFalse((self.ai / "verify_logs").exists())

    def test_forge_doctor_failure_blocks_before_behavior_check(self):
        checks = self.ai / "verify_checks"
        checks.mkdir()
        marker = self.base / "ran-behavior-check"
        (checks / "42.sh").write_text("touch '" + str(marker) + "'\n")
        self.forge.write_text("raise SystemExit(19)\n")
        self.assert_token("RunChecks", "blocked")
        self.assertFalse(marker.exists())

    def test_marker_write_failure_does_not_advance_ledger(self):
        findings = self.ai / "verify_findings"
        findings.mkdir()
        (findings / "42.md").write_text("DEFECT\nfictional\n")
        bindir = self.base / "bin"
        bindir.mkdir()
        touch = bindir / "touch"
        touch.write_text("#!/bin/sh\nexit 19\n")
        touch.chmod(0o755)
        self.env["PATH"] = str(bindir) + os.pathsep + self.env["PATH"]
        before = self.backlog.read_bytes()
        self.assert_token("ReopenGate","blocked")
        self.assertEqual(self.backlog.read_bytes(),before)
        self.assertFalse((self.ai / "verify_reopened_42").exists())

    def test_missing_backlog_is_blocked_not_empty_queue(self):
        self.backlog.unlink()
        self.assert_token("CheckQueue","blocked")
        self.backlog.write_text("")
        self.assert_token("CheckQueue","done")

    def test_selection_refuses_symlinked_future_check_or_finding(self):
        for folder, name in [("verify_checks","42.sh"),("verify_findings","42.md")]:
            with self.subTest(folder=folder):
                directory = self.ai / folder
                directory.mkdir(exist_ok=True)
                outside = self.base / ("outside-"+folder)
                outside.write_text("preserve\n")
                link = directory / name
                link.symlink_to(outside)
                self.assert_token("SelectRow","blocked")
                self.assertEqual(outside.read_text(),"preserve\n")
                link.unlink()

    def test_failed_update_and_failed_marker_cleanup_remain_blocked(self):
        self.state("404","missing-title")
        findings = self.ai / "verify_findings"
        findings.mkdir()
        (findings / "404.md").write_text("DEFECT\nfictional\n")
        bindir = self.base / "bin"
        bindir.mkdir()
        rm = bindir / "rm"
        rm.write_text("#!/bin/sh\nexit 19\n")
        rm.chmod(0o755)
        self.env["PATH"] = str(bindir) + os.pathsep + self.env["PATH"]
        before = self.backlog.read_bytes()
        self.assert_token("ReopenGate","blocked")
        self.assertEqual(self.backlog.read_bytes(),before)
        self.assertTrue((self.ai / "verify_reopened_404").is_file())

if __name__ == "__main__":
    unittest.main()
