"""Invented complete tasks and trial artifacts; never authentic assets or Docker."""
from pathlib import Path
from unittest.mock import patch
import copy
import hashlib
import json
import os
import resource
import signal
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import paired_materialize as M
import pair_sessions as S


def pin(p):
    b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def write(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(b if isinstance(b,bytes) else json.dumps(b,sort_keys=True).encode())


class Fixture:
    def __enter__(self):
        self.temp=tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()))
        self.root=Path(self.temp.name)
        self.h=M.load_helpers();self.source=self.root/'source';self.assets=self.root/'assets'
        self.assets.mkdir();self.source.mkdir()
        donor=json.loads((M.DONOR/'SOURCE_MANIFEST.json').read_bytes())
        self.common={r['path']:('invented source '+r['path']+'\n').encode() for r in donor['files']}
        self.common['instruction.md']=b'Compute exact69cases. /official/category_matching.py is available with its license.\n'
        self.common['task.toml']=b'''schema_version = "1.4"
artifacts = ["/app/output/submission.jsonl"]
[task]
name = "terminal-bench-science/pfc-conditional-reconstruction"
[verifier]
timeout_sec = 900.0
environment_mode = "separate"
[verifier.environment]
network_mode = "no-network"
cpus = 1
memory_mb = 4096
[agent]
timeout_sec = 28800.0
[environment]
cpus = 1
memory_mb = 4096
gpus = 0
network_mode = "public"
'''
        self.common['environment/Dockerfile.template']=b'''FROM __REVIEWED_PFC_RUNTIME_REFERENCE__
WORKDIR /app
COPY assets/participant-packet.json /input/participant-packet.json
COPY assets/paper.xml /instructions/paper.xml
COPY assets/category_matching.py /official/category_matching.py
COPY assets/LICENSE /official/LICENSE
COPY assets/notices/ /instructions/notices/
COPY PACKET_SCHEMA.json /instructions/PACKET_SCHEMA.json
RUN mkdir -p /app/output
'''
        self.common['tests/Dockerfile.template']=b'FROM __REVIEWED_PFC_VERIFIER_RUNTIME_REFERENCE__\nCOPY . /tests\nCOPY assets/participant-packet.json /input/participant-packet.json\n'
        rows=[]
        for n,b in self.common.items():
            write(self.source/'task'/n,b);rows.append({'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
        write(self.source/'SOURCE_MANIFEST.json',{'schema':'PFC_SCIENCE2_SOURCE_MANIFEST_V1','files':rows})
        self.asset_bodies={n:('invented public '+n+'\n').encode() for n in self.h.ASSETS}
        self.notices={n:('invented notice '+n+'\n').encode() for n in M.NOTICE_PINS}
        for n,b in {**self.asset_bodies,**self.notices}.items():write(self.assets/n,b)
        self.patches=[patch.object(M,'MANIFEST_SHA',pin(self.source/'SOURCE_MANIFEST.json')['sha256']),
            patch.object(self.h,'ASSETS',{n:(len(b),hashlib.sha256(b).hexdigest()) for n,b in self.asset_bodies.items()}),
            patch.object(M,'NOTICE_PINS',{n:(len(b),hashlib.sha256(b).hexdigest()) for n,b in self.notices.items()})]
        for p in self.patches:p.start()
        self.request={'schema':'PFC_MATCHED_PAIR_MATERIALIZE_V1','execution_selected':True,
            'source_root':str(self.source),'asset_root':str(self.assets),'output_root':str(self.root/'pair'),
            'base_image':M.BASE}
        return self

    def __exit__(self,*args):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def materialize(self):return M.construct(self.request)

    def plan(self):
        self.materialize()
        request={'schema':'PFC_MATCHED_PAIR_SESSIONS_V1','execution_selected':True,
            'pair_manifest':pin(self.root/'pair/PAIR_MANIFEST.json'),'output_root':str(self.root/'sessions'),
            'nonce':'a'*64,'images':{'A':'sha256:'+'1'*64,'B':'sha256:'+'2'*64,'verifier':'sha256:'+'3'*64},
            'agent':{'name':'oracle','model_name':None}}
        self.session_request=request;self.plan_pin=S.prepare(request)
        self.plan_value=json.loads(Path(self.plan_pin['path']).read_bytes())
        return self.plan_value

    def trials(self):
        plan=self.plan()
        for arm,selected in plan['arms'].items():
            root=Path(selected['trial_dir']);root.mkdir()
            write(root/'config.json',selected['config'])
            write(root/'result.json',{'task_name':S.TASK_NAME,'trial_name':selected['trial_name'],
                'trial_uri':root.as_uri(),'task_id':{'path':selected['task']},'task_checksum':'4'*64,
                'config':selected['config'],'agent_info':{'name':'oracle'},'exception_info':None,
                'started_at':'2026-11-15T00:00:00+00:00','finished_at':'2026-11-15T00:00:01+00:00',
                'verifier_result':None,'verifier':None})
            write(root/'agent/transcript.txt',b'invented independent session '+arm.encode()+b'\n')
            write(root/S.SUBMISSION,b'{"invented":"'+arm.encode()+b'"}\n')
            (root/S.CONVENTIONAL).mkdir(parents=True)
            write(root/'artifacts/manifest.json',[
                {'source':'/app/output/submission.jsonl','destination':S.SUBMISSION,'type':'file','status':'ok','service':'main'},
                {'source':'/logs/artifacts','destination':S.CONVENTIONAL,'type':'directory','status':'empty','service':None}])
        self.freeze_request={'schema':'PFC_MATCHED_PAIR_FREEZE_V1','execution_selected':True,
            'plan':self.plan_pin,'output_root':str(self.root/'frozen'),'closed_arms':['A','B']}
        return plan


class PairedDeliveryControls(unittest.TestCase):
    def test_complete_contexts_and_only_B_official_delta(self):
        with Fixture() as f:
            report=f.materialize();self.assertEqual(len(report['files']),54)
            a=Path(report['task_roots']['A']);b=Path(report['task_roots']['B'])
            for name in f.common:
                target=name.replace('Dockerfile.template','Dockerfile')
                if target!='environment/Dockerfile':self.assertEqual((a/target).read_bytes(),(b/target).read_bytes())
            for n in M.OFFICIAL:
                self.assertFalse((a/'environment/assets'/n).exists())
                self.assertEqual((b/'environment/assets'/n).read_bytes(),f.asset_bodies[n])
            for root in (a,b):
                self.assertIn(b'network_mode = "no-network"',(root/'task.toml').read_bytes())
                self.assertEqual((root/'tests/grade.py').read_bytes(),f.common['tests/grade.py'])
                self.assertEqual((root/'tests/science/conditional_kernel.py').read_bytes(),f.common['tests/science/conditional_kernel.py'])
            self.assertEqual(report['new_benchmark_ids'],0)

    def test_source_or_asset_changes_refuse_before_output(self):
        for rel in ('source/task/tests/grade.py','assets/paper.xml'):
            with self.subTest(rel=rel),Fixture() as f:
                (f.root/rel).write_bytes(b'changed')
                with self.assertRaises(ValueError):f.materialize()
                self.assertFalse((f.root/'pair').exists())

    def test_extra_answer_or_symlink_asset_refused(self):
        with Fixture() as f:
            write(f.source/'task/environment/answers.json',b'invented forbidden payload')
            with self.assertRaises(ValueError):f.materialize()
        with Fixture() as f:
            p=f.assets/'paper.xml';p.unlink();p.symlink_to(f.assets/'participant-packet.json')
            with self.assertRaises(ValueError):f.materialize()

    def test_false_selection_missing_member_and_reused_output_refused(self):
        with Fixture() as f:
            with self.assertRaises(ValueError):M.construct({**f.request,'execution_selected':False})
            (f.assets/'paper.xml').unlink()
            with self.assertRaises(ValueError):f.materialize()
        with Fixture() as f:
            f.materialize()
            with self.assertRaises(ValueError):f.materialize()

    def test_unrelated_arm_change_and_A_official_leak_refused(self):
        with Fixture() as f:
            pair=M.derive(f.common,f.asset_bodies,f.notices,M.BASE)
            pair['A']['tests/grade.py']=b'changed scorer'
            with self.assertRaises(ValueError):M.validate_pair(pair['A'],pair['B'])
            pair=M.derive(f.common,f.asset_bodies,f.notices,M.BASE)
            pair['A']['environment/assets/category_matching.py']=f.asset_bodies['category_matching.py']
            with self.assertRaises(ValueError):M.validate_pair(pair['A'],pair['B'])

    def test_fresh_sessions_identical_agent_and_disabled_verifier(self):
        with Fixture() as f:
            plan=f.plan();a,b=plan['arms']['A'],plan['arms']['B']
            self.assertEqual(a['config']['agent'],b['config']['agent'])
            self.assertNotEqual(a['trial_dir'],b['trial_dir'])
            self.assertNotEqual(a['host_environment_overrides']['HOME'],b['host_environment_overrides']['HOME'])
            for arm in (a,b):
                self.assertTrue(arm['config']['verifier']['disable'])
                self.assertIsNone(arm['config']['source_trial'])
                self.assertFalse(Path(arm['trial_dir']).exists())
                self.assertNotIn('docker_image',arm['config']['environment']['kwargs'])
            with self.assertRaises(ValueError):S.prepare(f.session_request)

    def test_common_base_cannot_masquerade_as_complete_task_image(self):
        with Fixture() as f:
            f.plan();request=copy.deepcopy(f.session_request);request['output_root']=str(f.root/'other')
            request['images']['A']=M.BASE
            with self.assertRaises(ValueError):S.prepare(request)
            self.assertFalse((f.root/'other').exists())

    def test_complete_snapshot_then_both_regrade_configs(self):
        with Fixture() as f:
            f.trials();receipt_pin=S.freeze_pair(f.freeze_request)
            result=json.loads(Path(receipt_pin['path']).read_bytes())
            self.assertTrue(result['both_submissions_frozen_before_grade_configs'])
            for arm in ('A','B'):
                frozen=Path(result['arms'][arm]['root'])
                self.assertTrue((frozen/S.CONVENTIONAL).is_dir())
                self.assertEqual((frozen/'agent/transcript.txt').read_bytes(),b'invented independent session '+arm.encode()+b'\n')
                cfg=json.loads(Path(result['regrade_configs'][arm]['path']).read_bytes())
                self.assertFalse(cfg['verifier']['disable'])
                self.assertEqual(cfg['source_trial'],{'action':'regrade','type':'local','path':str(frozen)})
            original=Path(f.plan_value['arms']['A']['trial_dir'])/S.SUBMISSION
            original.write_bytes(b'later change must not enter the regrade')
            self.assertEqual((Path(result['arms']['A']['root'])/S.SUBMISSION).read_bytes(),b'{"invented":"A"}\n')

    def test_failed_artifact_or_missing_implicit_coverage_refused(self):
        for mutation in ('failed','wrong_destination','duplicate','missing_conventional'):
            with self.subTest(mutation=mutation),Fixture() as f:
                plan=f.trials();root=Path(plan['arms']['B']['trial_dir']);p=root/'artifacts/manifest.json';m=json.loads(p.read_bytes())
                if mutation=='failed':m[0]['status']='failed'
                elif mutation=='wrong_destination':m[0]['destination']='artifacts/wrong.jsonl'
                elif mutation=='duplicate':m.append(m[0])
                else:m.pop()
                write(p,m)
                with self.assertRaises(ValueError):S.freeze_pair(f.freeze_request)
                self.assertFalse((f.root/'frozen').exists())

    def test_preexisting_feedback_resume_or_collect_hook_refused(self):
        for mutation in ('feedback','timing','stock_timing','resume'):
            with self.subTest(mutation=mutation),Fixture() as f:
                plan=f.trials();p=Path(plan['arms']['A']['trial_dir'])/'result.json';r=json.loads(p.read_bytes())
                if mutation=='feedback':r['verifier_result']={'rewards':{'reward':1}}
                elif mutation=='timing':r['verifier_timing']={'started_at':'invented'}
                elif mutation=='stock_timing':r['verifier']={'started_at':'invented'}
                else:r['config']['agent']['kwargs']={'resume':'previous-session'}
                write(p,r)
                with self.assertRaises(ValueError):S.freeze_pair(f.freeze_request)
        with Fixture() as f:
            body=f.common['task.toml'].replace(b'timeout_sec = 900.0',b'timeout_sec = 900.0\ncollect = ["unselected hook"]')
            body=body.replace(b'network_mode = "public"',b'network_mode = "no-network"')
            with self.assertRaises(ValueError):S.bind_images(body,'sha256:'+'1'*64,'sha256:'+'3'*64)

    def test_consumed_namespace_alias_and_unclosed_pair_refused(self):
        with Fixture() as f:
            plan=f.trials();root=Path(plan['arms']['B']['trial_dir'])
            (root/'agent/alias').symlink_to(root/S.SUBMISSION)
            with self.assertRaises(ValueError):S.freeze_pair(f.freeze_request)
        with Fixture() as f:
            f.trials()
            with self.assertRaises(ValueError):S.freeze_pair({**f.freeze_request,'closed_arms':['A']})

    def test_stored_access_state_and_budget_overrides_refused(self):
        mutations=(('agent','load_trajectory','previous.json'),('agent','resume_trajectory',True),
            ('agent','skills',['hidden-skill']),('agent','extra_allowed_hosts',['example.org']),
            ('agent','override_timeout_sec',999999.0),('agent','include_logs',['/protected']),
            ('environment','mounts',[{'source':'/host','target':'/shared'}]),
            ('environment','extra_allowed_hosts',['example.org']),('environment','override_cpus',99),
            ('environment','override_memory_mb',99999),('verifier','exclude_logs',['*']),
            ('task','git_url','https://example.org/other.git'),
            (None,'agent_timeout_multiplier',99.0))
        for role,key,value in mutations:
            with self.subTest(role=role,key=key),Fixture() as f:
                plan=f.trials();p=Path(plan['arms']['A']['trial_dir'])/'config.json';c=json.loads(p.read_bytes())
                (c if role is None else c[role])[key]=value;write(p,c)
                with self.assertRaises(ValueError):S.freeze_pair(f.freeze_request)
                self.assertFalse((f.root/'frozen').exists())

    def test_mid_freeze_mutation_preserves_partial_without_grade_configs(self):
        with Fixture() as f:
            plan=f.trials();original=S.copy_trial_file;changed=[False]
            def changing(*args):
                answer=original(*args)
                if not changed[0]:
                    changed[0]=True
                    (Path(plan['arms']['A']['trial_dir'])/'agent/transcript.txt').write_bytes(b'injected late mutation')
                return answer
            with patch.object(S,'copy_trial_file',side_effect=changing):
                with self.assertRaises(ValueError):S.freeze_pair(f.freeze_request)
            self.assertTrue((f.root/'frozen').exists())
            self.assertFalse((f.root/'frozen/regrade-configs').exists())


if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_CPU,(15,20))
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('generated paired-control30s')))
    signal.alarm(30)
    unittest.main(verbosity=2)
