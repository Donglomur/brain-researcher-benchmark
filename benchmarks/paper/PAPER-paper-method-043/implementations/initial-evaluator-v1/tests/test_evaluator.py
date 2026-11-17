"""Generated engineering controls; not authentic NeuroPictor/NSD evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neuropictor_evaluator', ROOT / 'evaluator.py')
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

R = np.array([[1,-1,0,0],[0,1,-1,0],[0,0,1,-1]], dtype=float)
P = np.array([[1,-1,0,0],[1,0,-1,0],[0,-1,0,1]], dtype=float)
H = 'a'*64


def fixtures(folder):
    samples = [{'sample_id':f's1-{i}', 'subject_id':'1', 'stimulus_id':str(i), 'session_ids':['generated']} for i in range(3)]
    extraction = {'pixel_policy':'source256_then425_rgb_chw_01','ssim_policy':'explicit_2d_gaussian_v1',
                  'preprocessing_sha256':H, **{f'{f}_extractor_sha256':H for f in ev.FEATURES}}
    protocol = {'task_id':ev.TASK_ID,'policy':'prospective-prepared-panel-v1','scope':'declared_subjects',
                'protected_pool_receipt_sha256':H,'exposure_ledger_sha256':H,'rights_review_sha256':H,
                'generation_policy':'one_sample_per_subject_stimulus','samples':samples,'extraction':extraction}
    ramp = np.tile(np.linspace(.1,.9,425),(425,1))
    pixels = np.stack([np.stack([ramp, ramp.T, ramp]) for _ in range(3)])
    def bundle(name, features):
        path = folder / f'{name}.npz'
        np.savez(path,pixels425=pixels,**{k:features for k in ev.FEATURES})
        return {'path':path.name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'samples':copy.deepcopy(samples),'extraction':copy.deepcopy(extraction)}
    ref = bundle('reference',R)
    conditions = []
    for role, features in [('pretrained',R),('target_only',P),('neural_free',P)]:
        conditions.append({'role':role,'name':role,'bundle':bundle(role,features),
            'target_training_membership_sha256':H,'diffusion_prior_sha256':H,'tuning_budget_sha256':H,
            'generation_budget_sha256':H,'encoder_initialization_sha256':H,'checkpoint_sha256':H,
            'initialization_exposure_sha256':H,'encoder_route':'released_encoder',
            'image_pretraining_route':'released_multi_subject_checkpoint' if role=='pretrained' else 'none',
            'neural_input':role!='neural_free'})
    return {'protocol':protocol,'reference':ref,'conditions':conditions}


class ArithmeticControls(unittest.TestCase):
    def test_independent_asymmetric_axis_oracle(self):
        # Independently derived matrix: [[1,.5,.5],[-.5,.5,-.5],[0,-.5,-.5]].
        np.testing.assert_allclose(ev.two_way_identification(R,P),[1,.5,0])
        self.assertAlmostEqual(ev.two_way_identification(R,P).mean(),.5)
        np.testing.assert_allclose(ev.paired_correlation(R,P),[1,.5,-.5])
        self.assertAlmostEqual((1-ev.paired_correlation(R,P)).mean(),2/3)
        np.testing.assert_allclose(ev.two_way_identification(R,P,block_size=1),[1,.5,0])

    def test_ties_fail_instead_of_half_or_full_credit(self):
        tied = np.array([[1,-1,0],[1,-1,0],[-1,0,1]])
        np.testing.assert_allclose(ev.two_way_identification(tied,tied),[.5,.5,1])

    def test_invalid_features(self):
        for a in (np.ones((3,4)), np.array([[1,np.nan],[2,3]]), np.array([[1,np.inf],[2,3]])):
            with self.assertRaises(ev.ValidationError): ev.two_way_identification(a,a)
        with self.assertRaises(ev.ValidationError): ev.two_way_identification(R[:1],P[:1])
        with self.assertRaises(ev.ValidationError): ev.two_way_identification(R,P,0)

    def test_ssim_independent_constant_offset(self):
        x = np.full((20,20),.25)
        y = np.full((20,20),.5)
        self.assertAlmostEqual(ev.ssim_2d(x,y),.8000639795265515,12)
        self.assertAlmostEqual(ev.ssim_2d(x,x),1,12)
        with self.assertRaises(ev.ValidationError): ev.ssim_2d(x-1,y)

    def test_correlation_not_cosine(self):
        x = np.array([[0,1,2],[3,4,2]])
        np.testing.assert_allclose(ev.paired_correlation(x, x+1000),[1,1])


class ProtocolControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.manifest = fixtures(cls.folder)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_complete_panel_and_directions(self):
        result = ev.evaluate(self.manifest,self.folder)
        self.assertFalse(result['research_qualified'])
        self.assertFalse(result['full_contract_complete'])
        means = result['conditions']['target_only']['macro_subject_mean']
        self.assertEqual(set(means),set(ev.METRICS))
        self.assertAlmostEqual(means['clip'],.5)
        self.assertAlmostEqual(means['effnet'],2/3)
        self.assertAlmostEqual(result['pretrained_minus_comparator']['target_only']['clip'],.5)
        self.assertAlmostEqual(result['pretrained_minus_comparator']['target_only']['effnet'],-2/3)

    def test_population_rejection(self):
        for kind in ('missing','duplicate','identity','sessions'):
            m = copy.deepcopy(self.manifest)
            rows=m['conditions'][0]['bundle']['samples']
            if kind=='missing': rows.pop()
            if kind=='duplicate': rows[1]=rows[0]
            if kind=='identity': rows[0]['stimulus_id']='extra'
            if kind=='sessions': rows[0]['session_ids']=['other']
            with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)

    def test_reordered_npz_identity_alignment(self):
        m = copy.deepcopy(self.manifest)
        b = m['conditions'][1]['bundle']
        with np.load(self.folder/b['path']) as src:
            arrays={k:src[k][[2,0,1]] for k in ev.ARRAYS}
        path=self.folder/'reordered.npz'
        np.savez(path,**arrays)
        b.update(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),samples=[b['samples'][i] for i in [2,0,1]])
        a=ev.evaluate(self.manifest,self.folder)
        z=ev.evaluate(m,self.folder)
        self.assertEqual(a['conditions'],z['conditions'])

    def test_all_matching_receipts_enforced(self):
        for key in ('target_training_membership_sha256','diffusion_prior_sha256','tuning_budget_sha256',
                    'generation_budget_sha256','encoder_initialization_sha256','encoder_route'):
            m=copy.deepcopy(self.manifest)
            m['conditions'][1][key]='random_init' if key=='encoder_route' else 'b'*64
            with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)

    def test_control_and_extraction_required(self):
        m=copy.deepcopy(self.manifest)
        m['conditions'].pop()
        with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)
        m=copy.deepcopy(self.manifest)
        m['conditions'][0]['bundle']['extraction']['preprocessing_sha256']='b'*64
        with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)
        m=copy.deepcopy(self.manifest)
        m['conditions'][1]['image_pretraining_route']='released_multi_subject_checkpoint'
        with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)

    def test_hash_and_paper_population_fail_closed(self):
        m=copy.deepcopy(self.manifest)
        m['conditions'][0]['bundle']['sha256']='0'*64
        with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)
        m=copy.deepcopy(self.manifest)
        m['protocol']['scope']='paper_four_subjects'
        with self.assertRaises(ev.ValidationError): ev.evaluate(m,self.folder)

    def test_shared_stimuli_across_subjects_allowed(self):
        p=copy.deepcopy(self.manifest['protocol'])
        p['samples'] += [{**r,'sample_id':'s2-'+r['stimulus_id'],'subject_id':'2'} for r in p['samples']]
        self.assertEqual(set(ev.validate_protocol(p)),{'1','2'})

    def test_macro_averages_subjects_not_images(self):
        # Test aggregation with unequal subject sizes via a controlled panel oracle,
        # leaving tensor math to independent numeric tests above.
        from unittest.mock import patch
        m=copy.deepcopy(self.manifest)
        m['protocol']['samples'] += [{**r,'sample_id':'s2-'+r['stimulus_id'],'subject_id':'2'} for r in m['protocol']['samples'][:2]]
        bundle={k:np.zeros((5,2)) for k in ev.ARRAYS}
        def panel(real,pred):
            n=len(real['pixels425'])
            return {k:np.full(n,1 if n==3 else 0) for k in ev.METRICS}
        with patch.object(ev,'_load_bundle',return_value=bundle), patch.object(ev,'metric_panel',side_effect=panel):
            result=ev.evaluate(m,self.folder)
        self.assertEqual(result['conditions']['pretrained']['macro_subject_mean']['clip'],.5)

    def test_cli_end_to_end(self):
        manifest=self.folder/'manifest.json'; output=self.folder/'report.json'
        manifest.write_text(json.dumps(self.manifest))
        result=subprocess.run([sys.executable,str(ROOT/'evaluator.py'),str(manifest),'--output',str(output)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        r=json.loads(output.read_text())
        self.assertEqual(r['input_manifest_sha256'],hashlib.sha256(manifest.read_bytes()).hexdigest())
        self.assertEqual(r['status'],'engineering_panel_only')


if __name__=='__main__': unittest.main()
