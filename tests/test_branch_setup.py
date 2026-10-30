import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GRAPH = next((ROOT / 'pipelines').glob('migrate.dot'), ROOT / 'pipelines/hgt.dot')
MIGRATE = GRAPH.name == 'migrate.dot'
REAL_GIT = shutil.which('git')

class BranchSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cap-guard-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.a = self.repo('host a')
        self.b = self.repo('host b')
        self.log = self.base / 'git.jsonl'
        bindir = self.base / 'bin'
        bindir.mkdir()
        wrapper = bindir / 'git'
        wrapper.write_text('#!' + shutil.which('python3') + '\n' + '''import json,os,sys,subprocess
args=sys.argv[1:]
with open(os.environ['GIT_TEST_LOG'],'a') as f:f.write(json.dumps({'cwd':os.getcwd(),'args':args})+'\\n')
local=args[2:] if len(args)>2 and args[0]=='-C' else args
op='checkout-main' if local[:3]==['checkout','-q','main'] else ('checkout-branch' if local[:3]==['checkout','-q','-b'] else (local[0] if local else ''))
if op==os.environ.get('FAIL_GIT'):sys.exit(17)
if op in {'pull','push'}:sys.exit(0)
sys.exit(subprocess.call([os.environ['REAL_GIT'],*args]))
''')
        wrapper.chmod(0o755)
        self.env = {**os.environ, 'PATH':str(bindir)+os.pathsep+os.environ['PATH'],
                    'REAL_GIT':REAL_GIT,'GIT_TEST_LOG':str(self.log),'GIT_CONFIG_NOSYSTEM':'1'}
        self.env.update({'TARGET_PATH':str(self.a),'HOST_A_PATH':str(self.a),'HOST_B_PATH':str(self.b)})
        self.state = self.a / ('.ai/gm_current.env' if MIGRATE else '.ai/hgt_current.env')
        self.state.write_text('STORY=story-1\n' if MIGRATE else 'SLUG=feature-1\nTARGET=a\n')
        raw = re.search(r'BranchSetup \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")',GRAPH.read_text()).group(1)
        self.command = json.loads(raw)

    def git(self,path,*args):
        return subprocess.check_output([REAL_GIT,'-c','core.fsmonitor=false','-C',str(path),*args],text=True).strip()

    def repo(self,name):
        p=self.base/name;p.mkdir()
        self.git(p,'init','-q','-b','main');self.git(p,'config','user.email','fixture@example.invalid');self.git(p,'config','user.name','Fixture')
        (p/'f').write_text('base\n');self.git(p,'add','f');self.git(p,'commit','-qm','baseline');(p/'.ai').mkdir();return p

    def run_setup(self):
        return subprocess.run(['bash','-c',self.command],cwd=self.base,env=self.env,text=True,capture_output=True)

    def mutations(self):
        records=[json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []
        return [x for x in records if x['args'][0] in {'stash','checkout','pull','reset'}]

    def blocked(self):
        result=self.run_setup()
        # Pipeline adapters intentionally exit0 with a domain failure token: the
        # engine leaves last_line stale on nonzero; blocked has an explicit exit edge.
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'blocked')
        self.assertIn('condition="context.tool.last_line=blocked"',GRAPH.read_text())
        return result

    def test_missing_target_never_mutates_callers_cwd(self):
        self.env['TARGET_PATH' if MIGRATE else 'HOST_A_PATH']=str(self.base/'missing')
        self.blocked();self.assertEqual(self.mutations(),[])

    def test_non_repository_subdirectory_is_refused(self):
        p=self.a/'sub';p.mkdir();self.env['TARGET_PATH' if MIGRATE else 'HOST_A_PATH']=str(p)
        self.blocked();self.assertEqual(self.mutations(),[])

    def test_missing_state_is_refused_before_stash(self):
        self.state.unlink();self.blocked();self.assertEqual(self.mutations(),[])

    def test_state_is_data_never_shell(self):
        marker=self.base/'executed'
        self.state.write_text(('STORY=' if MIGRATE else 'SLUG=')+'$(touch '+str(marker)+')\n'+('' if MIGRATE else 'TARGET=a\n'))
        self.blocked();self.assertFalse(marker.exists());self.assertEqual(self.mutations(),[])

    def test_duplicate_or_extra_state_is_refused(self):
        with self.state.open('a') as f:f.write('UNEXPECTED=value\n')
        self.blocked();self.assertEqual(self.mutations(),[])

    def test_stash_failure_stops_before_checkout(self):
        self.env['FAIL_GIT']='stash';self.blocked()
        self.assertEqual([x['args'][0] for x in self.mutations()],['stash'])
        self.assertEqual(self.git(self.a,'branch','--show-current'),'main')

    def test_checkout_failure_stops_before_pull(self):
        self.env['FAIL_GIT']='checkout-main';self.blocked()
        self.assertEqual([x['args'][0] for x in self.mutations()],['stash','checkout'])

    def test_pull_failure_stops_before_new_branch(self):
        self.env['FAIL_GIT']='pull';self.blocked()
        self.assertEqual(self.git(self.a,'branch','--show-current'),'main')
        self.assertEqual([x['args'][0] for x in self.mutations()],['stash','checkout','pull'])

    def test_existing_run_branch_is_not_reset(self):
        name='gm/story-1' if MIGRATE else 'hgt/feature-1'
        self.git(self.a,'branch',name);head=self.git(self.a,'rev-parse',name)
        self.blocked();self.assertEqual(self.mutations(),[]);self.assertEqual(self.git(self.a,'rev-parse',name),head)

    def test_success_creates_branch_and_preserves_ai_state(self):
        result=self.run_setup();self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'ready')
        self.assertEqual(self.git(self.a,'branch','--show-current'),'gm/story-1' if MIGRATE else 'hgt/feature-1')
        self.assertTrue(self.state.exists())

    @unittest.skipIf(MIGRATE,'transfer-only second host')
    def test_missing_second_host_refuses_before_primary_mutation(self):
        self.state.write_text('SLUG=feature-1\nTARGET=ab\n');self.env['HOST_B_PATH']=str(self.base/'missing')
        self.blocked();self.assertEqual(self.mutations(),[])

    @unittest.skipIf(MIGRATE,'transfer-only second host')
    def test_two_host_success(self):
        self.state.write_text('SLUG=feature-1\nTARGET=ab\n')
        result=self.run_setup();self.assertEqual(result.stdout,'ready',result.stderr)
        self.assertEqual(self.git(self.b,'branch','--show-current'),'hgt/feature-1')

    def node_command(self,node):
        raw=re.search(node+r' \[shape=parallelogram,\s*tool_command=("(?:\\.|[^"\\])*")',GRAPH.read_text()).group(1)
        return json.loads(raw)

    def test_all_guarded_nodes_refuse_wrong_cwd(self):
        self.env['TARGET_PATH' if MIGRATE else 'HOST_A_PATH']=str(self.base/'missing')
        check='CheckBacklog' if MIGRATE else 'CheckLedger'
        for node,token in [(check,'blocked'),('UnitValidate','fail'),('ForgeValidate','fail'),('RetryGate','blocked'),('Commit','blocked'),('MarkBlocked','blocked')]:
            with self.subTest(node=node):
                result=subprocess.run(['bash','-c',self.node_command(node)],cwd=self.base,env=self.env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,token)
        self.assertEqual(self.mutations(),[])

    def test_ledger_error_is_not_reported_as_work_available(self):
        ledger=self.base/'ledger.py';ledger.write_text('raise SystemExit(19)\n')
        self.env.update({'SOURCE_PATH':'fictional','TARGET_KIND':'new:test','FORGE_TOOL':'fictional','BACKLOG':'fictional','LEDGER_TOOL':str(ledger),'DONOR_PATH':'fictional','HOST_A_KIND':'new:test','LEDGER_FILE':'fictional'})
        if not MIGRATE:
            (self.a/'pipelines').mkdir();(self.a/'pipelines/ledger.py').write_text(ledger.read_text())
        result=subprocess.run(['bash','-c',self.node_command('CheckBacklog' if MIGRATE else 'CheckLedger')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'blocked');self.assertEqual(self.mutations(),[])

    def test_commit_refuses_protected_or_changed_branch(self):
        result=subprocess.run(['bash','-c',self.node_command('Commit')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'blocked');self.assertEqual(self.mutations(),[])

    def test_failed_push_does_not_mark_implemented_or_print_next(self):
        self.assertEqual(self.run_setup().stdout,'ready')
        marker=self.base/'ledger-called'
        ledger=self.base/'ledger.py';ledger.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("called")\n')
        self.env.update({'LEDGER_TOOL':str(ledger),'BACKLOG':'fictional','FAIL_GIT':'push'})
        if not MIGRATE:
            (self.a/'pipelines').mkdir();(self.a/'pipelines/ledger.py').write_text(ledger.read_text())
        (self.a/'f').write_text('new feature')
        result=subprocess.run(['bash','-c',self.node_command('Commit')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'blocked',result.stderr);self.assertFalse(marker.exists())

    def test_missing_blocked_plan_does_not_advance_ledger(self):
        result=subprocess.run(['bash','-c',self.node_command('MarkBlocked')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'blocked');self.assertEqual(self.mutations(),[])

    def test_successful_commit_advances_ledger_only_after_pr(self):
        self.assertEqual(self.run_setup().stdout,'ready')
        marker=self.base/'ledger-called';ledger=self.base/'ledger.py'
        ledger.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("called")\n')
        self.env.update({'LEDGER_TOOL':str(ledger),'BACKLOG':'fictional'})
        if not MIGRATE:
            (self.a/'pipelines').mkdir();(self.a/'pipelines/ledger.py').write_text(ledger.read_text())
        gh=self.base/'bin/gh';gh.write_text('#!/bin/sh\nexit 0\n');gh.chmod(0o755)
        (self.a/'f').write_text('feature')
        result=subprocess.run(['bash','-c',self.node_command('Commit')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'next',result.stderr);self.assertTrue(marker.exists())

    def test_invalid_retry_counter_is_blocked(self):
        (self.a/('.ai/gm_retries' if MIGRATE else '.ai/hgt_retries')).write_text('$(touch unexpected)')
        result=subprocess.run(['bash','-c',self.node_command('RetryGate')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'blocked');self.assertFalse((self.a/'unexpected').exists())

    def test_unit_gate_receives_validated_state_as_environment_data(self):
        ci=self.a/'ci';ci.mkdir();gate=ci/'gate.sh'
        gate.write_text('#!/bin/sh\n'+('test "$STORY" = story-1\n' if MIGRATE else 'test "$SLUG" = feature-1 && test "$TARGET" = a\n'));gate.chmod(0o755)
        self.env.update({'TARGET_KIND':'new:fixture','HOST_A_KIND':'new:fixture'})
        result=subprocess.run(['bash','-c',self.node_command('UnitValidate')],cwd=self.base,env=self.env,text=True,capture_output=True)
        self.assertEqual(result.stdout,'pass',result.stderr)

if __name__=='__main__':unittest.main()
