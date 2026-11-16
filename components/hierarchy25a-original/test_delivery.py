"""Invented metadata/bytes only; no Docker, numerical imports or original bodies."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = load('hierarchy_provision', HERE / 'provision.py')
r = load('hierarchy_successor_entry', HERE / 'run_program.py')
f, original = r.bind_legacy()
a = original.admit.__globals__['accounting'].__globals__
accounting = original.admit.__globals__['accounting']
validate = a['validate_values']
expected = a['expected_request']


def fixtures():
    old = dict(candidate_id=p.TASK, runtime_id='hierarchy_bounded_task_v1', status='passed',
        source_freeze_sha256=p.FREEZE_SHA, prior_known_seconds=2520, charged_seconds=780,
        known_after_seconds=3300, all_owned_absent=True, all_activated_groups_absent=True,
        controller_process_reaped=True, controller_launch_attempted=True,
        lifetime_cost_complete=False, automatic_retry=False)
    custody = {'path': '/invented/history/custody.json', 'bytes': 4990,
        'sha256': 'de70e28ea3db7d703d62176487e7fabb4cc67973760443d9a1c962966ce4d12c'}
    ref = dict(schema='hierarchy_retained_reference_owner_outcome_v1', accepted=True,
        dispatched=True, status='constructed_pending_independent_whole_review',
        prior_known_seconds=3300, new_full_charge_seconds=180, known_after_seconds=3480,
        accounting_custody=custody, lifetime_cost_complete=False, automatic_retry=False,
        scientific_qualification=False, transport=dict(schema='nider_gated_capture_bridge_v2',
        exit_code=0, child_reaped=True, process_group_absent=True, pipe_EOF=['stdout','stderr'],
        observer_exception=None, termination_reason=None))
    owner = dict(a['REFERENCE_RECEIPT'], path='/invented/history/owner.json')
    accepted = dict(schema='hierarchy_full_independent_retained_reference_admission_v1',
        accepted=True, owner_outcome=owner, automatic_retry=False, scientific_qualification=False,
        cost=dict(prior_known_producer_family_seconds=3300, producer_full_charge_seconds=180,
        known_producer_family_seconds=3480, independent_review_allocation_seconds=180,
        lifetime_complete=False, independent_review_separate_from_producer_family_charge=True),
        producer=dict(engine_natural_exit_observed=True, outside_natural_exit_code=0,
        worker_exit_code=0, forced_signals=[], fresh_owned_absence=[
            dict(pid=i, pid_state='ESRCH', pgid_state='ESRCH') for i in range(1,11)]))
    return old, ref, accepted


def review():
    return dict(accounting_successor=expected(), prior_known_seconds=3480,
        known_after_seconds=4260, latest_accounting_evidence=copy.deepcopy(a['REFERENCE_RECEIPT']),
        prior_is_latest_known_closed_family_event=True)


class Delivery(unittest.TestCase):
    def test_original_public_graph_exact_and_no_private_reads(self):
        result = p.check(ROOT, True)
        self.assertEqual(result['ancestry_frozen_members_checked'], 40)
        self.assertEqual(result['external_files_checked'], 0)
        ext, _ = p.contract(ROOT)
        self.assertEqual(sum(x['bytes'] for x in ext.values()), 773668517)
        self.assertEqual(len(ext), 11)
        for row in ext.values():
            self.assertFalse((ROOT / row['destination']).exists())

    def test_relocated_direct_cli_discovery_without_private_dependencies(self):
        result = subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE/'run_program.py'), '--help'],
                                capture_output=True, timeout=10, check=True)
        self.assertLess(len(result.stdout), 4096)
        self.assertEqual(result.stderr, b'')
        for name in (b'--program', b'--output', b'--review', b'--other-reserve-bytes'):
            self.assertIn(name, result.stdout)

    def test_actual_original_admission_binds_only_successor_accounting(self):
        self.assertIs(original.admit.__globals__['accounting'], accounting)
        self.assertEqual(Path(original.__file__), r.LEGACY / 'run_program.py')
        self.assertEqual(original.WORK_SECONDS, 720)
        self.assertEqual(original.WHOLE, 780)
        with patch.dict(a, {'descriptor': lambda item, cap: copy.deepcopy(fixtures()[
                [a['LEGACY_RECEIPT'], a['REFERENCE_RECEIPT'], a['REFERENCE_ACCEPTANCE']].index(item)])}):
            self.assertEqual(accounting(review(), 780), 3480)
        self.assertEqual(expected()['known_after_seconds'], 4260)

    def test_stale_request_refused_before_capture(self):
        for field, value in [('prior_known_seconds',3300), ('known_after_seconds',4080),
                             ('prior_is_latest_known_closed_family_event',False)]:
            v = review(); v[field] = value
            with patch.dict(a, {'descriptor': lambda *x: self.fail('Stale request opened evidence')}):
                with self.assertRaises(ValueError): accounting(v,780)
        v=review();v['accounting_successor']['latest_accounting_evidence']['path']='elsewhere.json'
        with patch.dict(a, {'descriptor': lambda *x: self.fail('Alternate evidence opened')}):
            with self.assertRaises(ValueError): accounting(v,780)

    def test_captured_review_binds_admission_and_source_commit_reads(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td).resolve()/'review.json';other=path.with_name('other.json')
            raw=b'{"source_successor":{"captured":true},"prior_known_seconds":3480}\n'
            path.write_bytes(raw);other.write_bytes(b'other')
            old_read=original.read;old_json=original.admit.__globals__['json_read']
            try:
                r.bind_review(original,f,path,raw)
                path.write_text('{}\n')
                self.assertEqual(original.admit.__globals__['json_read'](path),json.loads(raw))
                self.assertEqual(original.read(path),raw)
                self.assertEqual(original.read(other),b'other')
                with self.assertRaises(ValueError):original.read(path,len(raw)-1)
            finally:
                original.read=old_read
                original.admit.__globals__['json_read']=old_json

    def test_complete_receipt_semantics_and_no_invented_reset(self):
        self.assertEqual(validate(expected(),780,*fixtures()),3480)
        mutations=[(0,'charged_seconds',True),(1,'dispatched',False),
                   (1,'new_full_charge_seconds',0),(2,'accepted',False)]
        for index,key,value in mutations:
            rows=list(fixtures());rows[index][key]=value
            with self.assertRaises(ValueError):validate(expected(),780,*rows)
        for change in ('missing','duplicate','live','review_cost'):
            old,ref,accepted=fixtures();rows=accepted['producer']['fresh_owned_absence']
            if change=='missing':rows.pop()
            elif change=='duplicate':rows[-1]['pid']=rows[0]['pid']
            elif change=='live':rows[-1]['pgid_state']='PRESENT'
            else:accepted['cost']['independent_review_separate_from_producer_family_charge']=False
            with self.assertRaises(ValueError):validate(expected(),780,old,ref,accepted)
        with self.assertRaises(ValueError):validate(expected(),3360,*fixtures())

    def test_fixed_evidence_hash_checked_before_interpretation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();path=root/a['LEGACY_RECEIPT']['path'];path.parent.mkdir()
            path.write_bytes(b'X'*a['LEGACY_RECEIPT']['bytes'])
            with patch.object(f,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'Pinned identity'):accounting(review(),780)

    def test_successor_review_and_body_drift(self):
        freeze_path=HERE/'SOURCE_FREEZE.json';body=freeze_path.read_bytes()
        desc={'path':str(freeze_path.relative_to(ROOT)),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
        v={'freeze_sha256':p.FREEZE_SHA,'source_successor':{'freeze':desc,'source_reviews':[
            {'path':'invented-review.json','bytes':1,'sha256':'f'*64}]}}
        old=f.descriptor
        def capture(item,cap=250000,decode=True):
            if item['path']=='invented-review.json':
                return {'status':'passed','findings':[],'source_freeze_sha256':desc['sha256']}
            return old(item,cap,decode)
        with patch.object(f,'descriptor',capture): self.assertEqual(r.admit_successor(v,f),desc)
        bad=copy.deepcopy(v);bad['source_successor']['freeze']['sha256']='0'*64
        with self.assertRaises(ValueError):r.admit_successor(bad,f)
        with patch.object(f,'descriptor',lambda *args,**kwargs: {'status':'passed'}):
            with self.assertRaises(ValueError):r.admit_successor(v,f)

    def make_install(self, root):
        checkout=root/'checkout';checkout.mkdir();src=root/'inputs';src.mkdir()
        actual,_=p.contract(ROOT);rows={};paths={}
        for i,(role,row) in enumerate(sorted(actual.items())):
            body=('invented '+role+'\n').encode();source=src/str(i);source.write_bytes(body)
            rows[role]={'destination':row['destination'],'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
            paths[role]=str(source)
        return checkout,rows,paths

    def test_all_eleven_exclusive_installs_and_modes_under_umask_zero(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();checkout,rows,paths=self.make_install(root);receipt=root/'receipt.json'
            prior=os.umask(0)
            try:
                with patch.object(p,'contract',return_value=(rows,{})):
                    result=p.install(checkout,paths,receipt)
                    self.assertEqual(len(result['completed']),11)
                    with self.assertRaises(ValueError):p.install(checkout,paths,root/'again.json')
            finally:os.umask(prior)
            self.assertEqual(receipt.stat().st_mode&0o777,0o600)
            for role,row in rows.items():
                target=checkout/row['destination']
                self.assertEqual(target.stat().st_nlink,1)
                self.assertEqual(target.stat().st_mode&0o777,0o444 if role in p.PUBLIC_READ else 0o400)
                self.assertEqual(target.read_bytes(),Path(paths[role]).read_bytes())
            self.assertFalse((root/'again.json').exists())

    def test_bad_hash_preserves_partial_and_never_reports_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();checkout,rows,paths=self.make_install(root);receipt=root/'receipt.json'
            bad=sorted(rows)[2];source=Path(paths[bad]);source.write_bytes(b'X'*source.stat().st_size)
            with patch.object(p,'contract',return_value=(rows,{})):
                with self.assertRaises(ValueError):p.install(checkout,paths,receipt)
            result=json.loads(receipt.read_text())
            self.assertEqual(result['status'],'failed_partials_preserved')
            self.assertEqual(result['completed'],sorted(rows)[:2])
            self.assertEqual(result['attempted'],sorted(rows)[:3])
            self.assertEqual((checkout/rows[bad]['destination']).stat().st_mode&0o777,0o600)

    def test_preexisting_exposed_private_parent_refused_before_copies(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();checkout,rows,paths=self.make_install(root)
            parent=(checkout/rows['private_report']['destination']).parent
            parent.mkdir(parents=True);parent.chmod(0o755)
            receipt=root/'receipt.json'
            with patch.object(p,'contract',return_value=(rows,{})):
                with self.assertRaisesRegex(ValueError,'mode0700'):p.install(checkout,paths,receipt)
                self.assertFalse(receipt.exists())
                self.assertTrue(all(not (checkout/v['destination']).exists() for v in rows.values()))
                parent.chmod(0o700)
                self.assertEqual(p.install(checkout,paths,receipt)['status'],'complete_exact_dependencies_installed')
                self.assertEqual((checkout/rows['private_report']['destination']).stat().st_mode&0o777,0o444)
                parent.chmod(0o755)
                with self.assertRaisesRegex(ValueError,'mode0700'):p.check(checkout)

    def test_alias_hardlink_escape_and_incomplete_input_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();checkout,rows,paths=self.make_install(root)
            with patch.object(p,'contract',return_value=(rows,{})):
                with self.assertRaises(ValueError):p.install(checkout,{},root/'r.json')
                relative=dict(paths);relative[next(iter(relative))]='relative/input'
                with self.assertRaises(ValueError):p.install(checkout,relative,root/'r.json')
                role=next(iter(paths));source=Path(paths[role]);alias=root/'alias';alias.symlink_to(source)
                alternate=dict(paths);alternate[role]=str(alias)
                with self.assertRaises(ValueError):p.install(checkout,alternate,root/'r.json')
                alias.unlink();os.link(source,alias)
                with self.assertRaises(ValueError):p.install(checkout,paths,root/'r.json')
            self.assertFalse((root/'r.json').exists())
            for name in ('../escape','/absolute','bad\nname'):
                with self.assertRaises(ValueError):p.member(checkout,name)

    def test_relocated_public_submission_rejected_before_private_loader(self):
        base=ROOT/p.BASE
        core=load('hierarchy_relocated_scorer',base/'scorer_core.py')
        spec=core.strict_json((base/'OUTPUT_SCHEMA.json').read_bytes())
        calls=[]
        def loader():calls.append(1);raise AssertionError('Private reference opened')
        for body in [b'{}',b'{"schema_version":1,"candidate_id":"PAPER-FIND-ADD-006","sessions":[]}',
                     b'{"schema_version":1,"schema_version":1}']:
            result=core.grade(body,spec,loader,None,None)
            self.assertEqual(result['status'],'invalid_submission')
        self.assertEqual(calls,[])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Delivery)
    if suite.countTestCases()!=13:
        raise RuntimeError('All thirteen delivery controls required')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
