"""Actual Git index outcomes and current-attempt validation evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import test_main_graph_guards as main_fixture

ROOT = Path(__file__).resolve().parents[1]

class StagingAndProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.host = main_fixture.MainGraphGuardTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.target, self.ai, self.env = self.host.target, self.host.ai, self.host.env

    def git(self, *args):
        return self.host.host.git(self.target, *args)

    def prepare_commit(self, ignored, tracked_metadata):
        meta = [".ai/private.env","nested/.ai/private.env","__pycache__/cache", "nested/__pycache__/cache","root.pyc","nested/code.pyc"]
        (self.target / "delete-me").write_text("base\n")
        if ignored:(self.target / ".gitignore").write_text(".ai/\n__pycache__/\n*.pyc\n")
        for name in meta:
            path = self.target / name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("before\n")
        self.git("add","--","f","ci","delete-me")
        if ignored:self.git("add","--",".gitignore")
        if tracked_metadata:self.git("add","-f","--",*meta)
        self.git("commit","-qm","fixture prerequisites")
        self.host.token("BranchSetup","ready")
        (self.target / "delete-me").unlink()
        (self.target / "f").write_text("changed\n")
        (self.target / "new file.txt").write_text("new\n")
        for name in meta:
            path = self.target / name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("after\n")
        return meta

    def assert_committed_project_only(self):
        self.host.token("Commit","next")
        changed = self.git("diff","--name-only","HEAD^","HEAD").splitlines()
        self.assertTrue({"f","delete-me","new file.txt"}.issubset(changed),changed)
        self.assertFalse([p for p in changed if any(x in {".ai","__pycache__"} for x in p.split("/")) or p.endswith(".pyc")],changed)
        self.assertIn("\timplemented\n",self.host.backlog.read_text())

    def test_actual_git_commit_ignored_root_and_nested_metadata(self):
        self.prepare_commit(True,False)
        self.assert_committed_project_only()

    def test_actual_git_commit_unignored_root_and_nested_metadata(self):
        self.prepare_commit(False,False)
        self.assert_committed_project_only()

    def test_actual_git_commit_excludes_tracked_metadata_modifications(self):
        self.prepare_commit(False,True)
        self.assert_committed_project_only()
        self.assertIn(".ai/private.env",self.git("diff","--name-only"))

    def test_actual_git_commit_excludes_ignored_tracked_metadata_modifications(self):
        self.prepare_commit(True,True)
        self.assert_committed_project_only()

    def test_pre_staged_metadata_blocks_without_unstaging_or_commit(self):
        self.prepare_commit(False,False)
        special = self.ai / "staged\nmetadata.env"
        special.write_text("fictional private data\n")
        self.git("add","-f","--",str(special))
        before = self.git("rev-parse","HEAD")
        self.host.token("Commit","blocked")
        self.assertEqual(self.git("rev-parse","HEAD"),before)
        staged = subprocess.check_output([main_fixture.setup_fixture.REAL_GIT,"-c","core.fsmonitor=false","-C",str(self.target),"diff","--cached","--name-only","-z"])
        self.assertIn(b".ai/staged\nmetadata.env\0",staged)
        self.assertIn("\tnew\n",self.host.backlog.read_text())

    def test_metadata_directory_symlink_is_not_staged(self):
        self.prepare_commit(False,False)
        import shutil
        shutil.rmtree(self.target / "nested/.ai")
        outside = self.host.base / "outside-metadata"
        outside.mkdir()
        (self.target / "nested/.ai").symlink_to(outside,target_is_directory=True)
        self.assert_committed_project_only()

    def test_later_unit_failure_replaces_old_forge_evidence(self):
        self.host.token("UnitValidate","pass")
        self.env["PROBE_EXIT"] = "7"
        self.host.token("ForgeValidate","fail")
        self.host.token("RetryGate","retry")
        self.env["GATE_EXIT"] = "9"
        self.host.token("UnitValidate","fail")
        logs = self.ai / "gm_logs/story-1"
        observed = {name:(logs / name).read_text() for name in ["unit.log","forge.log","forge-doctor.log"]}
        print("fictional retry evidence:",json.dumps(observed))
        self.assertTrue(observed["forge.log"].startswith("UNRUN attempt 2:"),observed)
        record = json.loads((self.ai / "gm_validation.json").read_text())
        self.assertEqual((record["story"],record["attempt"],record["stage"],record["result"]),("story-1",2,"unit","fail"))
        self.assertEqual(record["logs"],[".ai/gm_logs/story-1/unit.log"])

    def test_failing_doctor_excludes_old_probe_from_current_record(self):
        self.host.token("UnitValidate","pass")
        self.host.token("ForgeValidate","pass")
        self.env["DOCTOR_EXIT"] = "19"
        self.host.token("ForgeValidate","blocked")
        record = json.loads((self.ai / "gm_validation.json").read_text())
        self.assertEqual((record["attempt"],record["stage"],record["result"]),(1,"forge_doctor","blocked"))
        self.assertEqual(record["logs"],[".ai/gm_logs/story-1/forge-doctor.log"])
        self.assertTrue((self.ai / "gm_logs/story-1/forge.log").read_text().startswith("UNRUN attempt 1:"))

    def test_three_total_failed_attempts_give_up_without_fourth(self):
        self.env["GATE_EXIT"] = "9"
        for expected in ["retry","retry","giveup"]:
            self.host.token("UnitValidate","fail")
            self.host.token("RetryGate",expected)
        self.assertEqual((self.ai / "gm_retries").read_text(),"3\n")
        self.host.token("UnitValidate","blocked")

    def test_record_failure_blocks_before_unit_program_runs(self):
        helper_dir = self.host.base / "failed-record-helper"
        helper_dir.mkdir()
        (helper_dir / "ledger.py").write_text("raise SystemExit(19)\n")
        (helper_dir / "validation_record.py").write_text("raise SystemExit(19)\n")
        self.env["LEDGER_TOOL"] = str(helper_dir / "ledger.py")
        (self.target / "ci/gate.sh").write_text("#!/bin/sh\ntouch gate-ran\n")
        self.host.token("UnitValidate","blocked")
        self.assertFalse((self.target / "gate-ran").exists())

    def prepare_stash(self, ignored, staged_metadata=False):
        meta = [".ai/private.env","nested/.ai/private.env","__pycache__/cache","nested/__pycache__/cache","root.pyc","nested/code.pyc"]
        (self.target / "f").write_text("older user change\n")
        self.git("stash","push","-qm","preexisting user stash")
        old_stash = self.git("rev-parse","refs/stash")
        if ignored:(self.target / ".gitignore").write_text(".ai/\n__pycache__/\n*.pyc\n")
        for name in meta:
            path = self.target / name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("baseline metadata\n")
        self.git("add","--","f","ci")
        if ignored:self.git("add","--",".gitignore")
        if staged_metadata:self.git("add","-f","--",*meta)
        self.git("commit","-qm","fixture stash prerequisites")
        for name in meta:(self.target / name).write_text("retained metadata\n")
        if staged_metadata:self.git("add","-f","--",*meta)
        (self.target / "f").write_text("staged user change\n")
        self.git("add","--","f")
        (self.target / "untracked project.txt").write_text("untracked user change\n")
        self.host.token("BranchSetup","ready")
        for name in meta:self.assertEqual((self.target / name).read_text(),"retained metadata\n")
        self.assertEqual((self.target / "f").read_text(),"base\n")
        self.assertFalse((self.target / "untracked project.txt").exists())
        stashes = self.git("stash","list","--format=%H").splitlines()
        self.assertEqual(len(stashes),2)
        self.assertEqual(stashes[1],old_stash)
        self.assertEqual(self.git("show","refs/stash^2:f"),"staged user change")
        self.assertEqual(self.git("show","refs/stash^3:untracked project.txt"),"untracked user change")
        if staged_metadata:
            staged = self.git("diff","--cached","--name-only").splitlines()
            self.assertTrue(set(meta).issubset(staged),staged)
            self.assertNotIn("f",staged)

    def test_native_stash_preserves_ignored_metadata_and_prior_user_stash(self):
        self.prepare_stash(True)

    def test_native_stash_preserves_unignored_metadata_and_prior_user_stash(self):
        self.prepare_stash(False)

    def test_native_stash_preserves_staged_metadata_and_user_index_snapshot(self):
        self.prepare_stash(True,True)

    def test_native_stash_preserves_nested_metadata_symlink(self):
        self.git("add","--","ci")
        self.git("commit","-qm","fixture prerequisites")
        nested = self.target / "nested"
        nested.mkdir()
        outside = self.host.base / "outside-stash-metadata"
        outside.mkdir()
        (nested / ".ai").symlink_to(outside,target_is_directory=True)
        (self.target / "f").write_text("dirty user change\n")
        self.host.token("BranchSetup","ready")
        self.assertTrue((nested / ".ai").is_symlink())
        self.assertEqual((nested / ".ai").resolve(),outside.resolve())

    def test_control_queue_and_helper_survive_stash_commit_and_next_checkout(self):
        import shutil
        queue = self.target / "queue data/[backlog].tsv"
        queue.parent.mkdir()
        queue.write_text("story-1\tfirst\tnew\nstory-2\tsecond\tnew\n")
        helper = self.target / "control/ledger.py"
        helper.parent.mkdir()
        shutil.copyfile(ROOT / "pipelines/ledger.py",helper)
        shutil.copyfile(ROOT / "pipelines/git_controls.py",helper.with_name("git_controls.py"))
        inventory = self.target / "inventory/stories"
        inventory.mkdir(parents=True)
        card = inventory / "story-2.md"
        card.write_text("original acceptance\n")
        (self.target / "delete-me").write_text("delete later\n")
        self.git("add","--","f","ci","delete-me","queue data/[backlog].tsv","control/ledger.py","inventory")
        self.git("commit","-qm","fixture control inputs")
        queue.write_text("story-1\tfirst\timplemented\nstory-2\tsecond\tnew\n")
        card.write_text("retained acceptance\n")
        helper.write_text(helper.read_text()+"\n# retained helper change\n")
        self.env.update({"BACKLOG":str(queue),"LEDGER_TOOL":str(helper)})
        (self.ai / "gm_current.env").write_text("STORY=story-2\n")
        before = queue.read_bytes()
        self.host.token("BranchSetup","ready")
        self.assertEqual(queue.read_bytes(),before)
        self.assertEqual(card.read_text(),"retained acceptance\n")
        self.assertTrue(helper.read_text().endswith("# retained helper change\n"))
        (self.target / "f").write_text("implemented second story\n")
        (self.target / "delete-me").unlink()
        self.host.token("Commit","next")
        changed = self.git("diff","--name-only","HEAD^","HEAD").splitlines()
        self.assertEqual(set(changed),{"f","delete-me"})
        self.assertEqual(queue.read_text(),"story-1\tfirst\timplemented\nstory-2\tsecond\timplemented\n")
        self.git("checkout","-q","main")
        self.assertEqual(queue.read_text(),"story-1\tfirst\timplemented\nstory-2\tsecond\timplemented\n")
        self.assertEqual(card.read_text(),"retained acceptance\n")

    def test_record_rejects_wrong_stage_logs_without_overwrite(self):
        self.host.token("UnitValidate","pass")
        record = self.ai / "gm_validation.json"
        before = record.read_bytes()
        result = subprocess.run([sys.executable,str(ROOT / "pipelines/validation_record.py"),"write","story-1","1","unit","fail",".ai/gm_logs/story-1/forge.log"],cwd=self.target,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(record.read_bytes(),before)
        self.assertEqual(list(self.ai.glob(".gm-validation-*.tmp")),[])

    def test_record_refuses_symlinked_destination_without_writing_outside(self):
        self.host.token("UnitValidate","pass")
        record = self.ai / "gm_validation.json"
        record.unlink()
        outside = self.host.base / "outside-validation.json"
        outside.write_text("preserve\n")
        record.symlink_to(outside)
        result = subprocess.run([sys.executable,str(ROOT / "pipelines/validation_record.py"),"write","story-1","1","unit","fail",".ai/gm_logs/story-1/unit.log"],cwd=self.target,text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(outside.read_text(),"preserve\n")

    def test_reopened_story_keeps_existing_branch_as_manual_ownership_gate(self):
        self.prepare_commit(False,False)
        self.host.token("Commit","next")
        head = self.git("rev-parse","HEAD")
        (self.ai / "verify_current.env").write_text("STORY=story-1\nTITLE=fictional-title\n")
        findings = self.ai / "verify_findings"
        findings.mkdir()
        (findings / "story-1.md").write_text("DEFECT\nfictional independent finding\n")
        self.host.token("ReopenGate","next","verify")
        self.assertIn("story-1\tfictional-title\tnew\n",self.host.backlog.read_text())
        dirty = self.target / "owned worker draft.txt"
        dirty.write_text("preserve concurrent worker draft\n")
        self.host.token("BranchSetup","blocked")
        self.assertEqual(self.git("rev-parse","HEAD"),head)
        self.assertEqual(self.git("rev-parse","refs/heads/gm/story-1"),head)
        self.assertEqual(self.git("branch","--show-current"),"gm/story-1")
        self.assertEqual(dirty.read_text(),"preserve concurrent worker draft\n")
        print("fictional manual recovery gate:",json.dumps({"branch":"gm/story-1","commit":head,"ledger":"new","pr":"authored gh stub only; no actual PR queried","dirty_preserved":True}))

    def test_configured_helper_symlink_node_is_never_committed(self):
        self.prepare_commit(False,False)
        folder = self.target / "control"
        folder.mkdir()
        (folder / "ledger.py").symlink_to(ROOT / "pipelines/ledger.py")
        self.env["LEDGER_TOOL"] = str(folder / "ledger.py")
        self.assert_committed_project_only()
        self.assertTrue((folder / "ledger.py").is_symlink())
        self.assertNotIn("control/ledger.py",self.git("diff","--name-only","HEAD^","HEAD").splitlines())

    def test_configured_helper_symlink_ancestor_is_never_committed(self):
        self.prepare_commit(False,False)
        folder = self.target / "control"
        folder.symlink_to(ROOT / "pipelines",target_is_directory=True)
        self.env["LEDGER_TOOL"] = str(folder / "ledger.py")
        self.assert_committed_project_only()
        self.assertTrue(folder.is_symlink())
        self.assertNotIn("control",self.git("diff","--name-only","HEAD^","HEAD").splitlines())

    def test_ignored_configured_controls_remain_valid_and_unstaged(self):
        import shutil
        queue = self.target / "queue data/[backlog].tsv"
        queue.parent.mkdir()
        queue.write_text("story-1\tfictional-title\tnew\n")
        folder = self.target / "controller"
        folder.mkdir()
        for name in ["ledger.py","git_controls.py","validation_record.py"]:
            shutil.copyfile(ROOT / "pipelines" / name,folder / name)
        (self.target / ".gitignore").write_text(".ai/\nqueue data/\ncontroller/\ninventory/\n")
        inventory = self.target / "inventory/stories"
        inventory.mkdir(parents=True)
        (inventory / "story-1.md").write_text("retained acceptance\n")
        self.git("add","--","ci",".gitignore")
        self.git("commit","-qm","fixture ignored control configuration")
        self.env.update({"BACKLOG":str(queue),"LEDGER_TOOL":str(folder / "ledger.py")})
        (self.target / "f").write_text("stashed user change\n")
        self.host.token("BranchSetup","ready")
        self.assertTrue(queue.is_file())
        self.assertTrue((folder / "git_controls.py").is_file())
        self.assertTrue((inventory / "story-1.md").is_file())
        (self.target / "f").write_text("actor change\n")
        self.host.token("Commit","next")
        self.assertEqual(self.git("diff","--name-only","HEAD^","HEAD"),"f")
        self.assertIn("\timplemented\n",queue.read_text())

    def test_ignored_tracked_queue_is_preserved_without_git_ignore_error(self):
        queue = self.target / "queue data/[backlog].tsv"
        queue.parent.mkdir()
        queue.write_text("story-1\tfictional-title\tnew\n")
        self.git("add","--","ci","queue data/[backlog].tsv")
        self.git("commit","-qm","fixture tracked queue")
        (self.target / ".gitignore").write_text("queue data/\n.ai/\n")
        self.git("add",".gitignore")
        self.git("commit","-qm","fixture ignore tracked queue parent")
        self.env["BACKLOG"] = str(queue)
        self.host.token("BranchSetup","ready")
        (self.target / "f").write_text("actor change\n")
        self.host.token("Commit","next")
        self.assertEqual(self.git("diff","--name-only","HEAD^","HEAD"),"f")
        self.assertIn("\timplemented\n",queue.read_text())

    def test_literal_nul_filename_selection_preserves_special_project_paths(self):
        self.prepare_commit(False,False)
        special = [":(glob)ordinary*.txt","ordinary\nname.txt","café [notes].txt"]
        for name in special:(self.target / name).write_text("ordinary actor output\n")
        self.host.token("Commit","next")
        raw = subprocess.check_output([main_fixture.setup_fixture.REAL_GIT,"-c","core.fsmonitor=false","-C",str(self.target),"diff","--name-only","-z","HEAD^","HEAD"])
        names = raw.split(b"\0")
        for name in special:self.assertIn(os.fsencode(name),names)

if __name__ == "__main__":unittest.main()
