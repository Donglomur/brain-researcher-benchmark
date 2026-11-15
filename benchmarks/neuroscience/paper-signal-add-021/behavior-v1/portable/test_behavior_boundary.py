"""Invented-only construction controls. No authentic CSV/reference, Docker or model.
Run with the canonical Python under an outer resource bound; exit nonzero on any
failure. The zero-difference fixture is constructed from arithmetic separately
from the accepted reference algorithm. Transport is explicitly mocked.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PROFILE = Path(__file__).resolve().parent.parent
ROOT = PROFILE / 'portable' / 'owner-template'
sys.path.insert(0, str(PROFILE))
sys.path.insert(0, str(ROOT / 'owner'))
sys.path.insert(0, str(ROOT))
import common
import delivery
import docker_owner
import scorer
import runtime_compatibility
import runtime_conventions_probe


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def zero_summary(n):
    return dict(n=n, df=n-1, mean=0.0, sample_sd=0.0, standard_error=0.0,
                t=None, cohens_dz=None, degenerate='all_zero')


def independent_fixture():
    metrics = {}
    for metric in scorer.METRICS:
        cells = [dict(person=p, condition=c, valid_trials=2, missing_trials=0,
                      figure_mean_abs=1.0, source_helper_mean_signed=1.0)
                 for p in scorer.ROSTER for c in scorer.CONDITIONS]
        contrasts = {}
        for name, (a, b) in scorer.CONTRASTS.items():
            contrasts[name] = dict(a=a, b=b, figure_paired=zero_summary(15),
                source_helper_signed_paired=zero_summary(15),
                corrected_participant_sign_flip=dict(p_two_sided=1.0, extreme=32768,
                    enumerated=32768, tie_tolerance=32*__import__('math').ulp(0.0),
                    unit='participant', assumption='joint sign exchangeability of paired differences'),
                corrected_participant_bootstrap=dict(lower=0.0, upper=0.0, confidence=.95,
                    draws=2000, seed=20261114,
                    method='participant-paired percentile bootstrap; type7 quantiles'),
                corrected_sign_flip_holm_six_contrasts=1.0,
                leave_one_person_out=[dict(excluded_person=p, summary=zero_summary(14)) for p in scorer.ROSTER])
        metrics[metric] = dict(participant_cells=cells, contrasts=contrasts)
    return dict(schema=scorer.SCHEMA, roster=list(scorer.ROSTER), metrics=metrics)


def reference(candidate):
    return dict(copy.deepcopy(candidate), helper_reproduction_scope='invented all-one trial fixture',
                complete_task_qualified=False, intake={'invented': True})


def fixture_rows(changed=False):
    return [dict(person=p, condition=c,
                 values={m: 3.0 if changed and p==1 and c=='mid inPF' else 1.0 for m in scorer.METRICS})
            for p in scorer.ROSTER for c in scorer.CONDITIONS for _ in range(2)]


def reference_namespace():
    ns = {'__name__': '_invented_control_reference'}
    exec(compile(runtime_conventions_probe.REFERENCE_SOURCE, '<accepted-source-invented-only>', 'exec'), ns)
    return ns


class StrictScorer(unittest.TestCase):
    def setUp(self):
        self.candidate = independent_fixture()
        self.gold = encode(reference(self.candidate))
        self.gold_hash = hashlib.sha256(self.gold).hexdigest()

    def grade(self, value):
        return scorer.score_submission(value if type(value) is bytes else encode(value), self.gold, self.gold_hash)

    def test_complete_independently_constructed_zero_fixture(self):
        actual = self.grade(self.candidate)
        self.assertEqual(actual['score'], 1.0)
        self.assertEqual(actual['coverage'], dict(participants=15,cells=315,contrasts=18,omissions=270))
        self.assertFalse(actual['whole_task_qualified'])
        self.assertEqual(set(actual['component_assessment']['components']), set(scorer.COMPONENTS))

    def test_reference_builder_agrees_with_independent_zero_arithmetic(self):
        actual = reference_namespace()['build_reference'](fixture_rows())
        self.assertEqual({k:actual[k] for k in ('schema','roster','metrics')}, self.candidate)

    def test_missing_duplicate_reordered_cells(self):
        for mutation in ('missing','duplicate','reordered'):
            c=copy.deepcopy(self.candidate); cells=c['metrics']['ierr']['participant_cells']
            if mutation=='missing': cells.pop()
            elif mutation=='duplicate': cells[1]=copy.deepcopy(cells[0])
            else: cells[0],cells[1]=cells[1],cells[0]
            with self.subTest(mutation=mutation): self.assertEqual(self.grade(c)['status'],'invalid_submission')

    def test_omitted_outcome_contrast_omission_and_null_field(self):
        for mutation in ('outcome','contrast','omission','null_field'):
            c=copy.deepcopy(self.candidate); m=c['metrics']['ierr']; contrast=m['contrasts']['exp1_in_minus_no']
            if mutation=='outcome': del c['metrics']['isacc_rt']
            elif mutation=='contrast': del m['contrasts']['exp1_in_minus_no']
            elif mutation=='omission': contrast['leave_one_person_out'].pop()
            else: del contrast['figure_paired']['t']
            with self.subTest(mutation=mutation): self.assertEqual(self.grade(c)['status'],'invalid_submission')

    def test_duplicate_omitted_participant_and_reversed_direction(self):
        for mutation in ('roster','omission','direction'):
            c=copy.deepcopy(self.candidate); v=c['metrics']['ierr']['contrasts']['exp1_in_minus_no']
            if mutation=='roster': c['roster'][1]=c['roster'][0]
            elif mutation=='omission': v['leave_one_person_out'][1]=copy.deepcopy(v['leave_one_person_out'][0])
            else: v['a'],v['b']=v['b'],v['a']
            with self.subTest(mutation=mutation): self.assertEqual(self.grade(c)['status'],'invalid_submission')

    def test_strict_json_and_number_boundaries(self):
        for raw in (b'{"a":1,"a":2}',b'NaN',b'Infinity',b'-Infinity',b'{',b'\xff',b'[]',b'0',b'',b' '* (scorer.CAP+1)):
            with self.subTest(raw_prefix=repr(raw[:20])): self.assertEqual(self.grade(raw)['status'],'invalid_submission')
        for value in (True,float('inf'),-1.0):
            c=copy.deepcopy(self.candidate);c['metrics']['ierr']['participant_cells'][0]['figure_mean_abs']=value
            raw=json.dumps(c,sort_keys=True,separators=(',',':')).encode()
            self.assertEqual(self.grade(raw)['status'],'invalid_submission')
        raw=encode(self.candidate).replace(b'"figure_mean_abs":1.0',b'"figure_mean_abs":1e999',1)
        self.assertEqual(self.grade(raw)['status'],'invalid_submission')
        raw=encode(self.candidate).replace(b'"figure_mean_abs":1.0',b'"figure_mean_abs":'+b'9'*4000,1)
        self.assertEqual(self.grade(raw)['status'],'invalid_submission')

    def test_duplicate_key_in_otherwise_complete_valid_submission(self):
        valid=encode(self.candidate)
        self.assertEqual(self.grade(valid)['score'],1.0)
        duplicate=b'{"schema":'+json.dumps(scorer.SCHEMA).encode()+b','+valid[1:]
        self.assertEqual(self.grade(duplicate)['status'],'invalid_submission')
        self.assertEqual(self.grade(duplicate)['reason'],'duplicate JSON key')

    def test_exact_fields_and_integer_types(self):
        for mutation in ('extra','boolean_count','boolean_person','boolean_probability','extra_contrast'):
            c=copy.deepcopy(self.candidate);cell=c['metrics']['ierr']['participant_cells'][0]
            if mutation=='extra': c['private_gold']='unrequested'
            elif mutation=='boolean_count': cell['valid_trials']=True
            elif mutation=='boolean_person': cell['person']=True
            elif mutation=='boolean_probability': c['metrics']['ierr']['contrasts']['exp1_in_minus_no']['corrected_sign_flip_holm_six_contrasts']=True
            else: c['metrics']['ierr']['contrasts']['extra']=copy.deepcopy(c['metrics']['ierr']['contrasts']['exp1_in_minus_no'])
            with self.subTest(mutation=mutation): self.assertEqual(self.grade(c)['status'],'invalid_submission')

    def test_reference_faults_are_infrastructure_errors(self):
        for raw, identity in ((self.gold,'0'*64),(b'{}',hashlib.sha256(b'{}').hexdigest()),(b'NaN',hashlib.sha256(b'NaN').hexdigest())):
            with self.assertRaises(scorer.InvalidReference): scorer.score_submission(encode(self.candidate),raw,identity)

    def test_changed_input_rejects_copied_answer(self):
        changed=reference_namespace()['build_reference'](fixture_rows(changed=True));changed['intake']={'invented':True}
        changed_raw=encode(changed); correct={k:changed[k] for k in ('schema','roster','metrics')}
        good=scorer.score_submission(encode(correct),changed_raw,hashlib.sha256(changed_raw).hexdigest())
        copied=scorer.score_submission(encode(self.candidate),changed_raw,hashlib.sha256(changed_raw).hexdigest())
        self.assertEqual(good['score'],1.0);self.assertEqual(copied['score'],0.0)
        self.assertEqual(copied['status'],'scored')
        self.assertFalse(copied['component_assessment']['components']['deterministic_figure_reproduction']['passed'])

    def test_lower_p_is_not_an_improvement_reward(self):
        c=copy.deepcopy(self.candidate);v=c['metrics']['ierr']['contrasts']['exp1_in_minus_no']
        v['corrected_participant_sign_flip']['p_two_sided']=0.0;v['corrected_participant_sign_flip']['extreme']=0
        v['corrected_sign_flip_holm_six_contrasts']=0.0
        score=self.grade(c)
        self.assertEqual(score['score'],0.0)
        self.assertTrue(score['component_assessment']['components']['deterministic_figure_reproduction']['passed'])
        self.assertFalse(score['component_assessment']['components']['corrected_scientific_inference']['passed'])

    def test_valid_nulls_are_required_but_not_inferred(self):
        c=copy.deepcopy(self.candidate);summary=c['metrics']['ierr']['contrasts']['exp1_in_minus_no']['figure_paired']
        summary['degenerate']=None
        self.assertEqual(self.grade(c)['status'],'invalid_submission')
        c=copy.deepcopy(self.candidate);c['metrics']['ierr']['contrasts']['exp1_in_minus_no']['figure_paired']['sample_sd']=1.0
        self.assertEqual(self.grade(c)['status'],'invalid_submission')


class DeliveryBoundary(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='tms-invented-controls-');self.root=Path(self.temp.name).resolve()
        self.events=[];self.outputs={'A':encode(independent_fixture()),'B':encode(independent_fixture())}
        self.gold=self.file('private-invented.json',encode(reference(independent_fixture())))
        self.inputs={'behavioralData_allsubs.csv': self.file('invented.csv',b'INVENTED; no original scientific data\n')}
        self.paper=self.file('invented.pdf',b'%PDF-INVENTED-NOT-A-PAPER\n')
        self.programs={a:self.file(a+'.py',b'print("invented transport fixture")\n') for a in ('A','B')}
        self.code=[{'relative':name,'file':self.file('code'+str(i)+'.py',b'# invented official transport fixture\n')} for i,name in enumerate(delivery.OFFICIAL_CODE)]
        self.docs={n:(PROFILE/n).read_bytes() for n in delivery.DOCS}
        p=common.pin(b'invented review')
        self.selection=dict(schema='tms_behavior_delivery_selection_v1',task_id=delivery.TASK_ID,
            root_execution_selected=True,input_files=self.inputs,paper=self.paper,official_code=self.code,
            official_code_review=p,programs=self.programs,selected_budget={'model_calls':0,'invented':True},
            runtime_admission={'image':docker_owner.IMAGE,'image_content_review':p,'daemon_guard_review':p},behavior_review=p)
        self.budget=common.Budget(time.monotonic()+480,128*1024*1024,64*1024*1024)
        self.patches=[patch.object(delivery,'INPUTS',{n:{k:v[k] for k in ('bytes','sha256')} for n,v in self.inputs.items()}),
            patch.object(delivery,'PAPER',{k:self.paper[k] for k in ('bytes','sha256')}),
            patch.object(delivery,'OFFICIAL_CODE',{v['relative']:{k:v['file'][k] for k in ('bytes','sha256')} for v in self.code}),
            patch.object(delivery,'PROTECTED_REFERENCE',{k:self.gold[k] for k in ('bytes','sha256')}),
            patch.object(docker_owner,'require_configured_cli',lambda *a: self.events.append('cli_mock')),
            patch.object(docker_owner,'run_candidate',self.transport)]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        for path in self.root.rglob('*'):
            if path.is_dir(): os.chmod(path,0o700)
            else: os.chmod(path,0o600)
        self.temp.cleanup()

    def file(self,name,body):
        p=self.root/name;p.write_bytes(body);os.chmod(p,0o400);return dict(path=str(p),**common.pin(body))

    def transport(self,*,root,input_dir,task_dir,program,budget,active_deadline):
        arm=program.stem
        self.assertEqual(set(p.name for p in input_dir.iterdir()),{'behavioralData_allsubs.csv'})
        self.assertEqual((task_dir/'TASK.md').read_bytes(),self.docs['TASK.md'])
        self.assertFalse((task_dir/'private-invented.json').exists())
        self.assertEqual((task_dir/'code').exists(),arm=='B')
        if arm=='B': self.assertEqual(set(str(p.relative_to(task_dir/'code')) for p in (task_dir/'code').rglob('*') if p.is_file()),set(delivery.OFFICIAL_CODE))
        self.assertNotIn('reference_read',self.events)
        root.mkdir(mode=0o700);submission=common.write(root/'stdout',self.outputs[arm],budget)
        lifecycle=dict(episode_closed=True,remaining_owned_cid=None,candidate_closed=True,failure=None,submission=submission)
        life=common.write(root/'lifecycle',common.encode(lifecycle),budget)
        self.events.append('closed_'+arm)
        return docker_owner.ClosedRun(submission,life,docker_owner._CLOSED_TOKEN)

    def execute(self):
        original=delivery.read
        def guarded(path,*args,**kwargs):
            if str(path)==self.gold['path']:
                self.assertEqual([e for e in self.events if e.startswith('closed_')],['closed_A','closed_B'])
                self.assertTrue((self.root/'pair'/'assessment'/'BOTH_CLOSED.private.json').is_file())
                self.events.append('reference_read')
            return original(path,*args,**kwargs)
        with patch.object(delivery,'read',guarded):
            return delivery.execute_pair(self.selection,self.docs,root=self.root/'pair',scorer=scorer,
                reference_selection=self.gold,budget=self.budget,active_deadline=time.monotonic()+420,cli_configuration={'mock':True})

    def test_full_matched_delivery_and_protected_read_order(self):
        result=self.execute()
        self.assertEqual([result['arms'][a]['result']['score'] for a in ('A','B')],[1.0,1.0])
        self.assertEqual(self.events,['cli_mock','closed_A','closed_B','reference_read'])
        self.assertFalse(result['feedback_to_candidates'])
        self.assertEqual((self.root/'pair'/'task-A'/'METHOD.json').read_bytes(),(self.root/'pair'/'task-B'/'METHOD.json').read_bytes())

    def test_malformed_first_arm_does_not_discard_valid_second(self):
        self.outputs['A']=b'not JSON'; result=self.execute()
        self.assertEqual(result['arms']['A']['status'],'invalid_submission')
        self.assertEqual(result['arms']['A']['score'],0.0)
        self.assertEqual(result['arms']['B']['result']['score'],1.0)

    def test_wrong_code_identity_rejected_before_staging(self):
        self.selection['official_code'][0]['file']['sha256']='0'*64
        with self.assertRaisesRegex(common.Refusal,'exact_two_official_behavior_files'): self.execute()
        self.assertFalse((self.root/'pair').exists());self.assertEqual(self.events,[])

    def test_staged_input_mutation_prevents_second_arm_and_reference(self):
        transport=self.transport
        def mutate(**kwargs):
            result=transport(**kwargs)
            if kwargs['program'].stem=='A':
                target=kwargs['input_dir']/'behavioralData_allsubs.csv';os.chmod(target,0o600);target.write_bytes(b'MUTATED')
            return result
        with patch.object(docker_owner,'run_candidate',mutate):
            with self.assertRaises(common.Refusal): self.execute()
        self.assertEqual(self.events,['cli_mock','closed_A'])

    def test_forged_closure_token_never_opens_reference(self):
        binding=delivery.shared_binding(self.selection,self.docs)
        forged=delivery.ClosedSubmission('A',self.outputs['A'],b'{}',b'{}','completed',None,object())
        with patch.object(delivery,'read',side_effect=AssertionError('reference opened before token admission')):
            with self.assertRaises(common.Refusal): delivery.closed_pair_score((forged,forged),binding,self.gold,scorer=scorer,root=self.root/'bad',budget=self.budget)

    def test_frozen_outputs_survive_source_file_change(self):
        binding=delivery.shared_binding(self.selection,self.docs)
        body_entry=self.file('freeze-output.json',self.outputs['A'])
        life=self.file('freeze-life.json',common.encode(dict(episode_closed=True,remaining_owned_cid=None,candidate_closed=True,failure=None,submission=body_entry)))
        token=delivery._freeze(docker_owner.ClosedRun(body_entry,life,docker_owner._CLOSED_TOKEN),'A',binding,self.budget)
        path=Path(body_entry['path']);os.chmod(path,0o600);path.write_bytes(b'changed after closure')
        self.assertEqual(token.body,self.outputs['A'])
        self.assertEqual(common.decode(token.binding_bytes)['submission'],common.pin(self.outputs['A']))


class RuntimeBoundary(unittest.TestCase):
    def test_complete_normative_fingerprint_and_rejections(self):
        config=json.loads((ROOT/'CONFIG.json').read_bytes())
        # Construct the complete invented fixture on this interpreter; never candidate-image admission.
        report=runtime_conventions_probe.collect()
        expected=copy.deepcopy(config['runtime_compatibility']);expected['candidate_python']=report['runtime']['version']
        selection=dict(compatibility=expected,image=config['image'],config=common.pin((ROOT/'CONFIG.json').read_bytes()),probe_source=common.pin((ROOT/'runtime_conventions_probe.py').read_bytes()))
        result=runtime_compatibility.verify(encode(report),selection)
        self.assertTrue(result['same_invented_primitives_and_complete_fixture'])
        self.assertFalse(result['authentic_scientific_or_native_FieldTrip_parity'])
        for field,value in [('complete_artifact_sha256','0'*64),('omissions',269),('complete_artifact_is_invented',1)]:
            changed=copy.deepcopy(report);changed['method_fixture'][field]=value
            with self.subTest(field=field):
                with self.assertRaises(common.Refusal): runtime_compatibility.verify(encode(changed),selection)
        changed=copy.deepcopy(report);changed['runtime']['version']='0.0.0'
        with self.assertRaises(common.Refusal): runtime_compatibility.verify(encode(changed),selection)

if __name__=='__main__':
    unittest.main(verbosity=2)
