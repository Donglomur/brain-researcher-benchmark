"""Bounded generated engineering controls; no authentic/model execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluator import (ContractError, ARMS, digest, evaluate, score_features, validate_protocol)


def fixture():
    h='a'*64
    images=['nsd:10','nsd:20','nsd:30']
    provenance={m:{'extractor_receipt_sha256':h,'representation':'generated mathematical control; not real CLIP/pixels'}
                for m in ['clip','effnet_b']}
    p={'schema_version':1,'task_id':'PAPER-paper-method-033',
       'status':'prospective_unqualified','target_subject':'generated_target',
       'test_image_ids':images,'metrics':['clip','effnet_b'],'primary_metric':'clip',
       'test_measurements':[{'subject_id':'generated_target','session_id':'test_session',
                             'image_id':im,'measurement_id':'test:'+im} for im in images],
       'selection':{'mode':'fixed_candidate_index','candidate_count':2,'candidate_index':0,
                    'freeze_receipt':'generated prospective selection only'},
       'access_manifest_sha256':h,'image_prior_sha256':h,'feature_provenance':provenance,
       'noncalibration_exposures':[
           {'stage':'shared_training','subject_id':'generated_source','source':'generated',
            'image_ids':['nsd:100'],'membership_receipt_sha256':h},
           {'stage':'image_prior_training','subject_id':'not_applicable','source':'generated',
            'image_ids':[],'membership_receipt_sha256':h}],
       'budgets':[]}
    rows=[{'image_id':'nsd:1','subject_id':'generated_target','measurement_ids':['train:1','train:1b']},
          {'image_id':'nsd:2','subject_id':'generated_target','measurement_ids':['train:2']}]
    p['budgets']=[{'budget':1,'calibration':copy.deepcopy(rows[:1])},{'budget':2,'calibration':copy.deepcopy(rows)}]
    features=np.array([[1,2,4,8],[2,-1,3,0],[0,3,1,-2]],float)
    ref={'protocol_sha256':digest(p),'target_subject':p['target_subject'],
         'image_ids':images,'feature_provenance':provenance,
         'features':{m:features.tolist() for m in provenance}}
    runs=[]
    for b in p['budgets']:
        for arm in ARMS:
            pred=features if arm=='bridge' else np.roll(features,1,axis=0)
            # Candidate 1 is deliberately unrelated, proving fixed candidate selection.
            pred=np.stack([pred,-features],axis=1)
            r={'budget':b['budget'],'arm':arm,'target_subject':p['target_subject'],
               'test_measurements_sha256':digest(p['test_measurements']),
               'access_manifest_sha256':h,'image_prior_sha256':h,
               'calibration_sha256':digest(b['calibration']),
               'noncalibration_exposures_sha256':digest(p['noncalibration_exposures']),
               'selection':p['selection'],'execution_receipt_sha256':h,
               'intervention':{'single':'exposure_matched_single_subject_decoder','bridge':'bridge_neural',
                 'neural_free':'no_neural_input','shuffled_neural':'within_target_image_derangement'}[arm],
               'image_ids':images,'feature_provenance':provenance,
               'features':{m:pred.tolist() for m in provenance}}
            if arm=='shuffled_neural':r['neural_donor_image_ids']=[images[-1]]+images[:-1]
            runs.append(r)
    return p,ref,{'protocol_sha256':digest(p),'runs':runs}


class NumericalTests(unittest.TestCase):
    def test_independent_asymmetric_oracle(self):
        r=[[1,2,4,8],[2,-1,3,0],[0,3,1,-2]]
        p=[[1,2,3,4],[3,0,4,1],[4,1,0,3]]
        np.testing.assert_array_equal(score_features(r,p,'clip'),[1,1,0])
        np.testing.assert_array_equal(score_features(r,p,'clip'),[1,1,0])
    def test_source_np_corrcoef_reference(self):
        rng=np.random.default_rng(93)
        r,p=rng.normal(size=(7,23)),rng.normal(size=(7,23))
        c=np.corrcoef(r,p)[:7,7:]
        expected=(c < np.diag(c)).sum(axis=0)/6
        np.testing.assert_array_equal(score_features(r,p,'clip'),expected)
    def test_strict_ties_not_half_credit(self):
        self.assertEqual(score_features([[1,2,3]]*3,[[1,2,3]]*3,'clip').tolist(),[0,0,0])
    def test_affine_strict_ties_match_source(self):
        for r in [[[1,2,3],[3,4,5],[5,6,7]],[[1,2,4],[3,5,9],[3,4,6]]]:
            np.testing.assert_array_equal(score_features(r,r,'clip'),[0,0,0])
    def test_affine_and_distance(self):
        r=np.array([[1,2,4,8],[2,-1,3,0],[0,3,1,-2]],float)
        shifted=r*np.array([3,5,2])[:,None]+np.array([100,-20,2])[:,None]
        np.testing.assert_allclose(score_features(r,shifted,'pixcorr'),1,atol=1e-14)
        np.testing.assert_allclose(score_features(r,-r,'effnet_b'),2,atol=1e-14)
    def test_undefined_rejected(self):
        for r,p in [([[1,1],[1,2]],[[1,2],[1,2]]),([[1,2]],[[1,2]]),
                    ([[1,2],[3,4]],[[1,2],[float('nan'),3]])]:
            with self.assertRaises(ContractError):score_features(r,p,'clip')


class PipelineTests(unittest.TestCase):
    def test_complete_curve_and_repeat_count(self):
        p,r,s=fixture();o=evaluate(p,r,s,100,12)
        self.assertEqual(o['scientific_qualification'],'unknown')
        self.assertFalse(o['full_contract_complete'])
        self.assertEqual([b['measurement_count'] for b in o['budgets']],[2,3])
        self.assertEqual(o['budgets'][0]['arms']['bridge']['clip']['mean'],1)
        self.assertGreater(o['calibration_efficiency']['benefit_auc'],0)
        self.assertEqual(o,evaluate(p,r,s,100,12))
    def test_row_order_is_identity_aligned(self):
        p,r,s=fixture();a=evaluate(p,r,s,100)
        for run in s['runs']:
            run['image_ids']=list(reversed(run['image_ids']))
            for m in run['features']:run['features'][m]=list(reversed(run['features'][m]))
            if 'neural_donor_image_ids' in run:
                run['neural_donor_image_ids']=list(reversed(run['neural_donor_image_ids']))
        b=evaluate(p,r,s,100)
        self.assertEqual(a['budgets'],b['budgets'])
    def test_missing_duplicate_and_unmatched_rows(self):
        for change in ['missing_run','duplicate_run','missing_image','duplicate_image']:
            p,r,s=fixture()
            if change=='missing_run':s['runs'].pop()
            elif change=='duplicate_run':s['runs'].append(s['runs'][0])
            elif change=='missing_image':s['runs'][0]['image_ids']=s['runs'][0]['image_ids'][:-1]
            else:s['runs'][0]['image_ids']=['nsd:10']*3
            with self.assertRaises(ContractError,msg=change):evaluate(p,r,s,100)
    def test_comparability_and_selection_reject(self):
        for field,value in [('target_subject','other'),('access_manifest_sha256','b'*64),
             ('image_prior_sha256','b'*64),('calibration_sha256','b'*64),
             ('test_measurements_sha256','b'*64),('noncalibration_exposures_sha256','b'*64),
             ('selection',{'mode':'best_true_stimulus_clip'})]:
            p,r,s=fixture();s['runs'][0][field]=value
            with self.assertRaises(ContractError,msg=field):evaluate(p,r,s,100)
    def test_global_image_leakage(self):
        p,_,_=fixture();p['noncalibration_exposures'][0]['image_ids'].append('nsd:10')
        with self.assertRaises(ContractError):validate_protocol(p)
    def test_budgets_not_repeat_counts(self):
        p,_,_=fixture();p['budgets'][0]['budget']=2
        with self.assertRaises(ContractError):validate_protocol(p)
    def test_nested_and_measurement_identity(self):
        for change in ['not_nested','reassign','test_reuse']:
            p,_,_=fixture()
            if change=='not_nested':p['budgets'][1]['calibration'][0]['image_id']='new'
            elif change=='reassign':
                p['budgets'][1]['calibration'][0]['measurement_ids']=['train:2']
                p['budgets'][1]['calibration'][1]['measurement_ids']=['train:1','train:1b']
            else:p['budgets'][0]['calibration'][0]['measurement_ids']=['test:nsd:10']
            with self.assertRaises(ContractError,msg=change):validate_protocol(p)
    def test_neural_shuffle_not_prediction_shuffle_attestation(self):
        p,r,s=fixture();run=next(x for x in s['runs'] if x['arm']=='shuffled_neural')
        run['neural_donor_image_ids']=run['image_ids']
        with self.assertRaises(ContractError):evaluate(p,r,s,100)
    def test_protocol_binding(self):
        p,r,s=fixture();p['primary_metric']='effnet_b'
        with self.assertRaises(ContractError):evaluate(p,r,s,100)
    def test_unused_candidate_still_validated(self):
        p,r,s=fixture();s['runs'][0]['features']['clip'][0][1][0]=float('inf')
        with self.assertRaises(ContractError):evaluate(p,r,s,100)
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[]
            for name,obj in zip(['protocol','reference','submission'],fixture()):
                path=Path(d)/(name+'.json');path.write_text(json.dumps(obj));paths.append(str(path))
            out=Path(d)/'out.json'
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'evaluator.py'),
                                   *paths,str(out),'--bootstrap-samples','100'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(out.read_text())['endpoint_status'],'prospective_feature_endpoint_evaluated')

if __name__=='__main__':unittest.main()
