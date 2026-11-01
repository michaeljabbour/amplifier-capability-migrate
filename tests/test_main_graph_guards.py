"""Main/inventory graph commands in authored temporary repositories only.

Git pull/push, gh and Forge/CI are fixture stubs; no service/provider is called.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
import test_branch_setup as setup_fixture

ROOT = Path(__file__).resolve().parents[1]

class MainGraphGuardTests(unittest.TestCase):
    def setUp(self):
        self.host = setup_fixture.BranchSetupTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.base, self.target, self.env = self.host.base, self.host.a, self.host.env
        self.ai = self.target / ".ai"
        self.backlog = self.base / "backlog.tsv"
        self.backlog.write_text("story-1\tfictional-title\tnew\n")
        self.surfaces = self.base / "surfaces.tsv"
        self.surfaces.write_text("surface-1\tfictional-title\tnew\n")
        self.forge = self.base / "forge.py"
        self.forge.write_text("import os,sys\nprint('fictional-doctor')\nraise SystemExit(int(os.environ.get('DOCTOR_EXIT','0')))\n")
        self.env.update({"SOURCE_PATH":str(self.base),"SOURCE_KIND":"python","TARGET_KIND":"new:fixture",
            "LEDGER_TOOL":str(ROOT / "pipelines/ledger.py"),"BACKLOG":str(self.backlog),
            "SURFACES":str(self.surfaces),"FORGE_TOOL":str(self.forge)})
        (self.ai / "gm_plan.md").write_text("fictional plan\n")
        (self.ai / "gm_forge_check.sh").write_text("printf fictional-probe; exit ${PROBE_EXIT:-0}\n")
        ci = self.target / "ci"
        ci.mkdir()
        gate = ci / "gate.sh"
        gate.write_text("#!/bin/sh\nprintf fictional-unit; exit ${GATE_EXIT:-0}\n")
        gate.chmod(0o755)
        gh = self.base / "bin/gh"
        gh.write_text("#!/bin/sh\nprintf fictional-pr; exit ${GH_EXIT:-0}\n")
        gh.chmod(0o755)

    def command(self, node, graph="migrate"):
        text = (ROOT / "pipelines" / (graph + ".dot")).read_text()
        raw = re.search(node + r' \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")', text).group(1)
        return json.loads(raw)

    def run_node(self, node, graph="migrate"):
        return subprocess.run(["bash","-c",self.command(node,graph)],cwd=self.base,env=self.env,
            text=True,capture_output=True,timeout=5)

    def token(self, node, expected, graph="migrate"):
        result = self.run_node(node,graph)
        self.assertEqual((result.returncode,result.stdout),(0,expected),result.stderr)
        return result

    def test_entry_prepares_metadata_before_first_builder_agent(self):
        shutil.rmtree(self.ai)
        self.token("CheckBacklog","process")
        self.assertTrue(self.ai.is_dir())

    def test_symlinked_ai_is_refused_by_all_main_commands(self):
        self.ai.rename(self.target / ".ai-original")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "gm_current.env").write_text("STORY=story-1\n")
        (outside / "gm_plan.md").write_text("preserve plan\n")
        self.ai.symlink_to(outside,target_is_directory=True)
        for node in ["CheckBacklog","BranchSetup","UnitValidate","ForgeValidate","RetryGate","Commit","MarkBlocked"]:
            with self.subTest(node=node):self.token(node,"blocked")
        self.assertEqual(sorted(p.name for p in outside.iterdir()),["gm_current.env","gm_plan.md"])

    def test_symlinked_retry_file_is_refused_without_write(self):
        outside = self.base / "outside-counter"
        outside.write_text("1\n")
        (self.ai / "gm_retries").symlink_to(outside)
        self.token("RetryGate","blocked")
        self.assertEqual(outside.read_text(),"1\n")

    def test_symlinked_state_file_is_refused_before_git_mutation(self):
        state = self.ai / "gm_current.env"
        state.unlink()
        outside = self.base / "outside-state"
        outside.write_text("STORY=story-1\n")
        state.symlink_to(outside)
        self.token("BranchSetup","blocked")
        self.assertEqual(self.host.mutations(),[])

    def test_empty_first_duplicate_story_is_invalid_data(self):
        (self.ai / "gm_current.env").write_text("STORY=\nSTORY=story-1\n")
        self.token("BranchSetup","blocked")
        self.assertEqual(self.host.mutations(),[])

    def test_inventory_queue_read_error_is_blocked(self):
        fake = self.base / "failed_ledger.py"
        fake.write_text("raise SystemExit(19)\n")
        self.env["LEDGER_TOOL"] = str(fake)
        self.token("CheckSurfaces","blocked","inventory")

    def test_inventory_missing_target_is_blocked(self):
        self.env["TARGET_PATH"] = str(self.base / "missing")
        self.token("CheckSurfaces","blocked","inventory")

    def test_inventory_preflight_allows_new_empty_non_git_target(self):
        empty = self.base / "empty-target"
        empty.mkdir()
        self.env["TARGET_PATH"] = str(empty)
        self.token("Preflight","ready","inventory")
        self.assertTrue((empty / ".ai").is_dir())
        self.assertTrue((empty / "inventory/stories").is_dir())

    def test_inventory_preflight_refuses_symlinked_output_directory(self):
        outside = self.base / "outside-inventory"
        outside.mkdir()
        (self.target / "inventory").symlink_to(outside,target_is_directory=True)
        self.token("Preflight","blocked","inventory")
        self.assertEqual(list(outside.iterdir()),[])

    def test_unit_pass_and_failure_use_scoped_logs(self):
        self.token("UnitValidate","pass")
        log = self.ai / "gm_logs/story-1/unit.log"
        self.assertEqual(log.read_text(),"fictional-unit")
        self.env["GATE_EXIT"] = "7"
        self.token("UnitValidate","fail")

    def test_forge_gate_uses_scoped_logs_and_actual_probe_status(self):
        self.token("ForgeValidate","pass")
        self.assertEqual((self.ai / "gm_logs/story-1/forge.log").read_text(),"fictional-probe")
        self.assertEqual((self.ai / "gm_logs/story-1/forge-doctor.log").read_text(),"fictional-doctor\n")
        self.env["PROBE_EXIT"] = "7"
        self.token("ForgeValidate","fail")

    def test_forge_missing_probe_and_failed_doctor_are_blocked(self):
        (self.ai / "gm_forge_check.sh").unlink()
        self.token("ForgeValidate","blocked")
        (self.ai / "gm_forge_check.sh").write_text("touch should-not-run\n")
        self.env["DOCTOR_EXIT"] = "19"
        self.token("ForgeValidate","blocked")
        self.assertFalse((self.target / "should-not-run").exists())

    def test_symlinked_per_story_log_directory_is_refused(self):
        logs = self.ai / "gm_logs"
        logs.mkdir()
        outside = self.base / "outside-logs"
        outside.mkdir()
        (logs / "story-1").symlink_to(outside,target_is_directory=True)
        self.token("UnitValidate","blocked")
        self.assertEqual(list(outside.iterdir()),[])

    def test_symlinked_log_file_is_refused(self):
        logs = self.ai / "gm_logs/story-1"
        logs.mkdir(parents=True)
        outside = self.base / "outside-log"
        outside.write_text("preserve\n")
        (logs / "unit.log").symlink_to(outside)
        self.token("UnitValidate","blocked")
        self.assertEqual(outside.read_text(),"preserve\n")

    def test_retry_limit_keeps_three_total_attempts(self):
        for expected in ["retry","retry","giveup"]:self.token("RetryGate",expected)
        self.assertEqual((self.ai / "gm_retries").read_text(),"3\n")
        self.token("RetryGate","blocked")

    def test_mark_blocked_refuses_symlinked_destination(self):
        folder = self.ai / "gm_blocked"
        folder.mkdir()
        outside = self.base / "outside-plan"
        outside.write_text("preserve\n")
        (folder / "story-1.md").symlink_to(outside)
        self.token("MarkBlocked","blocked")
        self.assertEqual(outside.read_text(),"preserve\n")
        self.assertIn("\tnew\n",self.backlog.read_text())

    def test_mark_blocked_refuses_missing_plan(self):
        (self.ai / "gm_plan.md").unlink()
        self.token("MarkBlocked","blocked")
        self.assertIn("\tnew\n",self.backlog.read_text())

    def test_commit_records_pr_log_before_advancing_ledger(self):
        self.token("BranchSetup","ready")
        (self.target / "f").write_text("fictional change\n")
        self.token("Commit","next")
        self.assertEqual((self.ai / "gm_logs/story-1/pr.log").read_text(),"fictional-pr")
        self.assertIn("\timplemented\n",self.backlog.read_text())

    def test_failed_pr_does_not_advance_ledger(self):
        self.token("BranchSetup","ready")
        (self.target / "f").write_text("fictional change\n")
        self.env["GH_EXIT"] = "19"
        self.token("Commit","blocked")
        self.assertIn("\tnew\n",self.backlog.read_text())

    def test_missing_backlog_blocks_but_empty_backlog_is_done(self):
        self.backlog.unlink()
        self.token("CheckBacklog","blocked")
        self.backlog.write_text("")
        self.token("CheckBacklog","done")

    def test_missing_surfaces_blocks_after_enumeration_but_empty_is_done(self):
        self.surfaces.unlink()
        self.token("CheckSurfaces","blocked","inventory")
        self.surfaces.write_text("")
        self.token("CheckSurfaces","done","inventory")

    def test_surface_state_is_validated_as_data_before_derivation(self):
        (self.ai / "gm_surface.env").write_text("SURFACE=surface-1\n")
        self.token("ValidateSurface","ready","inventory")
        for state in ["SURFACE=\nSURFACE=surface-1\n", "SURFACE=../outside\n", "SURFACE=$(touch marker)\n"]:
            with self.subTest(state=state):
                (self.ai / "gm_surface.env").write_text(state)
                self.token("ValidateSurface","blocked","inventory")
        self.assertFalse((self.target / "marker").exists())

if __name__ == "__main__":unittest.main()
