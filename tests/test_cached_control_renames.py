"""Actual cached-index renames must expose removed control paths to both guards."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_main_graph_guards as fixtures

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rename_guard_subject", ROOT / "pipelines/git_controls.py")
SUBJECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUBJECT)


class CachedControlRenameTests(unittest.TestCase):
    def fixture(self):
        host = fixtures.MainGraphGuardTests()
        host.setUp()
        self.addCleanup(host.doCleanups)
        target = host.target
        control = target / "control"
        control.mkdir()
        for name in ["ledger.py", "git_controls.py", "validation_record.py"]:
            shutil.copyfile(ROOT / "pipelines" / name, control / name)
        queue = target / "queue/[backlog].tsv"
        queue.parent.mkdir()
        queue.write_text("story-1\tfictional-title\tnew\n")
        (target / ".ai/tracked-control.env").write_text("fictional-control-data\n" * 5)
        story = target / "inventory/stories/card.md"
        story.parent.mkdir(parents=True)
        story.write_text("fictional acceptance criterion\n" * 5)
        host.env.update({"BACKLOG": str(queue), "LEDGER_TOOL": str(control / "ledger.py"), "GIT_OPTIONAL_LOCKS": "0"})
        host.host.git(target, "config", "diff.renames", "true")
        host.host.git(target, "add", "--", "f", "ci", "control", "queue", "inventory")
        host.host.git(target, "add", "-f", "--", ".ai/tracked-control.env")
        host.host.git(target, "commit", "-qm", "fictional rename baseline")
        host.host.git(target, "checkout", "-qb", "gm/story-1")
        (host.ai / "gm_logs/story-1").mkdir(parents=True)
        return host, queue

    def git(self, host, *args):
        return subprocess.run([fixtures.setup_fixture.REAL_GIT, "-c", "core.fsmonitor=false", "-C", str(host.target), *args],
            env=host.env, capture_output=True, check=True)

    def snapshot(self, host, queue):
        files = {}
        directories = []
        for path in sorted(host.target.rglob("*")):
            relative = path.relative_to(host.target)
            if ".git" in relative.parts:
                continue
            name = relative.as_posix()
            if path.is_symlink():
                files[name] = {"link": os.readlink(path)}
            elif path.is_file():
                files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            elif path.is_dir():
                directories.append(name)
        return {"head": self.git(host, "rev-parse", "HEAD").stdout.decode().strip(),
            "index_sha256": hashlib.sha256((host.target / ".git/index").read_bytes()).hexdigest(),
            "index_entries_sha256": hashlib.sha256(self.git(host, "ls-files", "--stage", "-z").stdout).hexdigest(),
            "worktree": files, "directories": directories,
            "queue_sha256": hashlib.sha256(queue.read_bytes()).hexdigest()}

    def rename_control(self, host, relative, destination):
        original = (host.target / relative).read_bytes()
        self.git(host, "mv", "--", relative, destination)
        (host.target / relative).write_bytes(original)  # runtime helper/control restored, untracked
        raw = self.git(host, "diff", "--cached", "--name-status", "-M", "-z").stdout
        self.assertTrue(raw.startswith(b"R100\0"), raw)
        default_names = SUBJECT.names(self.git(host, "diff", "--cached", "--name-only", "-z").stdout)
        both_names = SUBJECT.names(self.git(host, "diff", "--cached", "--no-renames", "--name-only", "-z").stdout)
        self.assertNotIn(relative, default_names)
        self.assertIn(relative, both_names)
        return {"old_control": relative, "destination": destination,
                "default_cached_names": default_names, "rename_disabled_names": both_names}

    def test_pre_guard_refuses_all_control_rename_endpoints_without_mutation(self):
        for relative in ["control/ledger.py", "control/git_controls.py", "control/validation_record.py",
                         "queue/[backlog].tsv", ".ai/tracked-control.env", "inventory/stories/card.md"]:
            with self.subTest(control=relative):
                host, queue = self.fixture()
                evidence = self.rename_control(host, relative, "ordinary application.py")
                (host.target / "ordinary actor output.txt").write_text("must stay untracked on refusal\n")
                before = self.snapshot(host, queue)
                result = subprocess.run([sys.executable, str(host.target / "control/git_controls.py"), "stage", str(queue), str(host.target / "control/ledger.py")],
                    cwd=host.target, env=host.env, text=True, capture_output=True)
                after = self.snapshot(host, queue)
                evidence.update({"guard": "pre", "exit_code": result.returncode, "stderr": result.stderr,
                                 "state_unchanged": before == after, "before": before, "after": after})
                print("RENAME_TRACE " + json.dumps(evidence, sort_keys=True))
                self.assertNotEqual(result.returncode, 0, evidence)
                self.assertIn("already staged", result.stderr)
                self.assertEqual(after, before)

    def test_commit_node_blocks_before_head_queue_or_worktree_changes(self):
        host, queue = self.fixture()
        evidence = self.rename_control(host, "control/ledger.py", "actor.py")
        before = self.snapshot(host, queue)
        result = host.run_node("Commit")
        after = self.snapshot(host, queue)
        evidence.update({"guard": "Commit", "domain_token": result.stdout, "exit_code": result.returncode,
                         "stderr": result.stderr, "state_unchanged": before == after, "before": before, "after": after})
        print("RENAME_TRACE " + json.dumps(evidence, sort_keys=True))
        self.assertEqual((result.returncode, result.stdout), (0, "blocked"), evidence)
        self.assertEqual(after, before)

    def test_post_guard_refuses_actual_index_rename_without_rollback(self):
        host, queue = self.fixture()
        original = (host.target / "control/ledger.py").read_bytes()
        (host.target / "application.py").write_bytes(original)
        before = self.snapshot(host, queue)
        real_git = SUBJECT.git
        injected = {}
        calls = []

        def actual_git(*args, **kwargs):
            calls.append(list(args))
            result = real_git(*args, **kwargs)
            if args[:2] == ("add", "-A") and result.returncode == 0:
                # Simulate an index change at the mutation boundary using real
                # Git. The worktree copy stays in place and the queue is untouched.
                removed = real_git("rm", "--cached", "--", "control/ledger.py")
                self.assertEqual(removed.returncode, 0, removed.stderr)
                injected["state"] = self.snapshot(host, queue)
                injected["names"] = SUBJECT.names(self.git(host, "diff", "--cached", "--name-only", "-z").stdout)
            return result

        previous = Path.cwd()
        stderr = io.StringIO()
        try:
            os.chdir(host.target)
            with patch.dict(os.environ, host.env, clear=True), patch.object(SUBJECT, "git", side_effect=actual_git), contextlib.redirect_stderr(stderr):
                result = SUBJECT.main(["stage", str(queue), str(host.target / "control/ledger.py")])
        finally:
            os.chdir(previous)
        after = self.snapshot(host, queue)
        evidence = {"guard": "post", "exit_code": result, "stderr": stderr.getvalue(), "calls": calls,
                    "before": before, "after_native_stage_injection": injected.get("state"), "after_refusal": after,
                    "no_additional_mutation_after_refusal": after == injected.get("state"),
                    "default_names_after_injection": injected.get("names")}
        print("RENAME_TRACE " + json.dumps(evidence, sort_keys=True))
        self.assertIn("state", injected)
        self.assertNotEqual(result, 0, evidence)
        self.assertIn("staged unexpectedly", stderr.getvalue())
        self.assertEqual(after, injected["state"])
        self.assertEqual(after["head"], before["head"])
        self.assertEqual(after["worktree"], before["worktree"])
        self.assertEqual(after["queue_sha256"], before["queue_sha256"])
        # No index reset/rollback: changes already made at the mutation boundary
        # remain visible for review, matching the helper's documented contract.

    def test_ordinary_application_rename_is_not_blocked(self):
        host, queue = self.fixture()
        self.git(host, "mv", "--", "f", "renamed application.txt")
        before_queue = queue.read_bytes()
        before_worktree = self.snapshot(host, queue)["worktree"]
        result = subprocess.run([sys.executable, str(host.target / "control/git_controls.py"), "stage", str(queue), str(host.target / "control/ledger.py")],
            cwd=host.target, env=host.env, text=True, capture_output=True)
        after_names = SUBJECT.names(self.git(host, "diff", "--cached", "--no-renames", "--name-only", "-z").stdout)
        print("RENAME_TRACE " + json.dumps({"guard": "ordinary-positive", "exit_code": result.returncode,
            "cached_endpoints": after_names, "worktree_unchanged": self.snapshot(host, queue)["worktree"] == before_worktree,
            "queue_unchanged": queue.read_bytes() == before_queue}, sort_keys=True))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(after_names), {"f", "renamed application.txt"})
        self.assertEqual(queue.read_bytes(), before_queue)
        self.assertEqual(self.snapshot(host, queue)["worktree"], before_worktree)

    def test_control_rename_with_nul_framed_special_destination_is_blocked(self):
        host, queue = self.fixture()
        destination = "ordinary\n[record] :(glob).py"
        evidence = self.rename_control(host, "control/ledger.py", destination)
        before = self.snapshot(host, queue)
        result = subprocess.run([sys.executable, str(host.target / "control/git_controls.py"), "stage", str(queue), str(host.target / "control/ledger.py")],
            cwd=host.target, env=host.env, text=True, capture_output=True)
        after = self.snapshot(host, queue)
        evidence.update({"guard": "pre-special-name", "exit_code": result.returncode, "state_unchanged": before == after,
                         "before": before, "after": after})
        print("RENAME_TRACE " + json.dumps(evidence, sort_keys=True))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(after, before)

if __name__ == "__main__": unittest.main()
