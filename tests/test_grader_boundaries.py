import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('apply_patch_grader',ROOT/'benchmarks/codex-apply-patch/grade.py')
GRADE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(GRADE)

class GraderBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='grader-guard-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.marker=self.root/'executed';self.candidate=self.root/'candidate'
        self.case={'name':'fictional','files_before':{},'files_after':{},'patch':'fictional input','expect_exit_zero':True}

    def program(self,body):
        self.candidate.write_text('#!'+sys.executable+'\n'+body+'\n');self.candidate.chmod(0o755);return str(self.candidate)

    def test_known_frozen_cases_still_validate(self):self.assertEqual(len(GRADE.load_cases(GRADE.default_cases_path())),21)

    def test_real_child_receives_no_host_credentials_or_config(self):
        code='''import os
from pathlib import Path
assert all(name not in os.environ for name in ['OPENAI_API_KEY','AWS_SECRET_ACCESS_KEY','PORTFOLIO_TEST_TOKEN','PYTHONPATH','LD_PRELOAD','HTTPS_PROXY'])
assert 'fictional-never-forward' not in repr(dict(os.environ))
assert Path.home().resolve() == (Path.cwd().parent/'home').resolve()
assert list(Path.home().iterdir()) == []
assert os.environ['PATH'] == os.defpath
'''
        binary=self.program(code)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fictional-never-forward','AWS_SECRET_ACCESS_KEY':'fictional-never-forward','PORTFOLIO_TEST_TOKEN':'fictional-never-forward','PYTHONPATH':'/fictional/loader','LD_PRELOAD':'/fictional/loader','HTTPS_PROXY':'https://fictional.invalid','HOME':str(self.root)}):
            result=GRADE.run_case(binary,self.case)
        self.assertTrue(result['passed'],result)

    def test_absolute_or_traversing_seed_never_launches_or_writes(self):
        outside=self.root/'outside';binary=self.program('from pathlib import Path\nPath('+repr(str(self.marker))+').write_text("executed")')
        for path in [str(outside),'../outside','a/../outside','/absolute','C:/escape','..\\escape','nested//file','./file']:
            with self.subTest(path=path):
                result=GRADE.run_case(binary,{**self.case,'files_before':{path:'fictional'}})
                self.assertFalse(result['passed']);self.assertIsNone(result['exit_code']);self.assertFalse(outside.exists());self.assertFalse(self.marker.exists())

    def test_invalid_expected_paths_rejected_even_when_tree_check_skipped(self):
        binary=self.program('raise AssertionError("candidate must not run")')
        for path in ['/absolute','../outside','x/../../outside']:
            result=GRADE.run_case(binary,{**self.case,'files_after':{path:None},'skip_tree_check':True})
            self.assertFalse(result['passed']);self.assertIsNone(result['exit_code'])

    def test_all_seed_names_validated_before_any_write(self):
        work=self.root/'work';work.mkdir()
        with self.assertRaises(ValueError):GRADE.write_files_before(work,{'valid':'one','../outside':'two'})
        self.assertEqual(list(work.iterdir()),[])

    def test_seed_refuses_parent_and_leaf_symlinks_and_hardlinks(self):
        work=self.root/'work';work.mkdir();outside=self.root/'outside';outside.mkdir();sentinel=outside/'file';sentinel.write_text('preserve')
        (work/'parent').symlink_to(outside,target_is_directory=True)
        (work/'leaf').symlink_to(sentinel)
        os.link(sentinel,work/'hard')
        for path in ['parent/file','leaf','hard']:
            with self.subTest(path=path),self.assertRaises(OSError):GRADE.write_files_before(work,{path:'overwrite'})
        self.assertEqual(sentinel.read_text(),'preserve')

    def test_snapshot_never_follows_file_or_directory_symlinks(self):
        outside=self.root/'outside';outside.mkdir();(outside/'secret').write_text('fictional-private-sentinel')
        binary=self.program('from pathlib import Path\nPath("file-link").symlink_to('+repr(str(outside/'secret'))+')\nPath("directory-link").symlink_to('+repr(str(outside))+',target_is_directory=True)')
        result=GRADE.run_case(binary,self.case)
        self.assertFalse(result['passed']);self.assertNotIn('fictional-private-sentinel',repr(result))
        self.assertIn('unsafe',repr(result))

    def test_snapshot_rejects_hardlinks_and_special_files_without_reading(self):
        sentinel=self.root/'private';sentinel.write_text('fictional-private-sentinel')
        binary=self.program('import os\nos.link('+repr(str(sentinel))+',"hard")\nos.mkfifo("fifo")')
        result=GRADE.run_case(binary,self.case)
        self.assertFalse(result['passed']);self.assertNotIn('fictional-private-sentinel',repr(result));self.assertIn('unsafe',repr(result))

    def test_relative_nested_regular_fixture_and_child_update_pass(self):
        binary=self.program('from pathlib import Path\np=Path("nested/a.txt")\nassert p.read_text()=="before"\np.write_text("after")')
        result=GRADE.run_case(binary,{**self.case,'files_before':{'nested/a.txt':'before'},'files_after':{'nested/a.txt':'after'}})
        self.assertTrue(result['passed'],result)

    def test_malformed_later_case_is_rejected_before_cli_execution(self):
        binary=self.program('from pathlib import Path\nPath('+repr(str(self.marker))+').write_text("executed")')
        cases=self.root/'cases.json';cases.write_text(json.dumps([self.case,{**self.case,'files_before':{'../outside':'x'}}]))
        self.assertEqual(GRADE.main(['--bin',binary,'--cases',str(cases)]),2);self.assertFalse(self.marker.exists())

    def test_root_symlink_is_never_followed(self):
        outside=self.root/'outside';outside.mkdir();(outside/'private').write_text('fictional-private-sentinel')
        link=self.root/'root-link';link.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(OSError):GRADE.write_files_before(link,{'private':'overwrite'})
        snapshot=GRADE.snapshot_tree(link);self.assertNotIn('fictional-private-sentinel',repr(snapshot));self.assertIn(None,snapshot.values())

    def test_unsafe_entry_cannot_match_literal_marker_content(self):
        outside=self.root/'private';outside.write_text('fictional-private-sentinel')
        binary=self.program('from pathlib import Path\nPath("link").symlink_to('+repr(str(outside))+')')
        result=GRADE.run_case(binary,{**self.case,'files_after':{'link':'<<unsafe symlink, hardlink or special file>>'}})
        self.assertFalse(result['passed']);self.assertIn('unsafe',repr(result))

if __name__=='__main__':unittest.main()
