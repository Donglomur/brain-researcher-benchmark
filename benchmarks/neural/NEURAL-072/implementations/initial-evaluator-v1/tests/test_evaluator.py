"""Bounded generated controls. These are not observations from Narratives."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

MODULE = Path(__file__).resolve().parents[1] / 'evaluator.py'
spec=importlib.util.spec_from_file_location('neural072_evaluator',MODULE)
e=importlib.util.module_from_spec(spec); spec.loader.exec_module(e)


def fixture():
    rng=np.random.default_rng(734)
    cases={'source_task':'NEURAL-071','source_task_sha256':e.SOURCE_TASK_SHA256,'target_ids':['parcel_a','parcel_b'],'runs':[]}
    features,ys={},{}
    for listener in ['s1','s2']:
        for i,split in enumerate(['train','train','dev','test','test']):
            n=64; rid=listener+'_'+str(i)
            r={'id':rid,'listener':listener,'story_family':'f'+str(i),'story':'story'+str(i),
               'scan_identity':'generated-'+rid,'passage_ids':['passage'+str(i)],'split':split,'n_time':n,'indices':list(range(2,n)),
               'tr':1.5,'scanner_start':0.,'story_start':0.,'story_end':n*1.5}
            cases['runs'].append(r)
            nuisance=rng.normal(size=(n,4)); nuisance[:,-1]=np.arange(n)/n
            lexical=rng.normal(size=(n,4)); contextual=rng.normal(size=(n,4))
            y=np.column_stack([2*contextual[:,0]+.3*nuisance[:,0], contextual[:,1]-.1*nuisance[:,1]])
            ys[rid]=y[r['indices']].tolist()
            times=np.arange(n)*1.5
            features[rid]={'nuisance':nuisance.tolist(),'lexical':lexical.tolist(),'contextual':contextual.tolist(),
                           'support_start':times.tolist(),'support_end':times.tolist()}
    protocol={'task_id':'NEURAL-072','task_sha256':e.TASK_SHA256,'recipe':'prospective-whitened-ridge-v1',
              'cases_sha256':e.digest(cases),'context_direction':'past_and_present','nuisance_columns':e.NUISANCE,
              'metric':'run-centered-pooled-family-r2','constant_target_policy':'reject','case_scope':'within_listener',
              'lags':[0,1],'feature_rank':4,'alphas':[.01,1.,100.],'bootstrap_replicates':31,
              'null_replicates':11,'seed':42,'null_min_shift':2}
    for key in ['atlas_pin','clock_manifest_pin','checkpoint_pin','checkpoint_exposure','feature_lineage_pin','rights_review_pin']:
        protocol[key]='generated-control-only-unresolved-for-real-data'
    train={r['id']:ys[r['id']] for r in cases['runs'] if r['split']!='test'}
    test={r['id']:ys[r['id']] for r in cases['runs'] if r['split']=='test'}
    return protocol,cases,features,train,test


class MetricControls(unittest.TestCase):
    def simple(self,y,n,l,c):
        cases={'runs':[{'id':'r','listener':'s','story_family':'f','split':'test'}]}
        ys={'r':np.asarray(y,dtype=float).reshape(-1,1)}
        ps={'r':{a:np.asarray(v,dtype=float).reshape(-1,1) for a,v in zip(e.ARMS,[n,l,c])}}
        return e.cell_metrics(cases,ys,ps)[0]

    def test_independent_exact_signed_variance(self):
        cell=self.simple([-1,0,1],[0,0,0],[-.5,0,.5],[-1,0,1])
        self.assertEqual(cell['contrasts'],{'lexical_minus_nuisance':.75,'contextual_minus_nuisance':1.,'contextual_minus_lexical':.25})
        bad=self.simple([-1,0,1],[0,0,0],[-.5,0,.5],[1,0,-1])
        self.assertEqual(bad['contrasts']['contextual_minus_lexical'],-3.75)

    def test_correlation_is_not_variance(self):
        cell=self.simple([-1,0,1],[0,0,0],[-1,0,1],[1,2,3])
        self.assertEqual(cell['r2_by_target']['contextual'],[-5.])

    def test_second_independent_reference(self):
        cell=self.simple([1,2,3,4],[2.5]*4,[2,3,4,5],[4,3,2,1])
        self.assertAlmostEqual(cell['contrasts']['contextual_minus_lexical'],-3.2)
        self.assertAlmostEqual(cell['contrasts']['lexical_minus_nuisance'],.2)

    def test_overflow_is_rejected(self):
        with self.assertRaisesRegex(e.ContractError,'nonfinite squared'):
            self.simple([1,2,3],[0]*3,[1,2,3],[1e308]*3)

    def test_constant_target_rejected(self):
        with self.assertRaises(e.ContractError): self.simple([1,1,1],[1]*3,[1]*3,[1]*3)

    def test_listener_macro_not_cell_macro(self):
        cells=[{'listener':l,'story_family':f,'contrasts':{'x':v}} for l,f,v in [('s1','a',1),('s1','b',1),('s2','a',-1)]]
        self.assertEqual(e.summarize(cells)['x'],0.)

    def test_target_scale_macro_and_run_pooling(self):
        cases={'runs':[{'id':r,'listener':'s','story_family':'f','split':'test'} for r in ['a','b']]}
        ys={'a':np.array([[-1,-10],[0,0],[1,10.]]),'b':np.array([[-2,-20],[0,0],[2,20.]])}
        ps={r:{'nuisance':np.zeros_like(y),'lexical':np.column_stack([y[:,0],np.zeros(3)]),'contextual':y.copy()} for r,y in ys.items()}
        cell=e.cell_metrics(cases,ys,ps)[0]
        self.assertEqual(cell['contrasts']['lexical_minus_nuisance'],.5)
        self.assertEqual(cell['contrasts']['contextual_minus_lexical'],.5)


class PipelineControls(unittest.TestCase):
    def setUp(self): self.p,self.c,self.f,self.y,self.t=fixture()
    def predict(self): return e.fit_predict(self.p,self.c,self.f,self.y)
    def mutate_cases(self): self.p['cases_sha256']=e.digest(self.c)

    def test_predict_score_and_matched_effective_capacity(self):
        pred=self.predict(); report=e.score(self.p,self.c,self.t,pred)
        self.assertFalse(report['scientific_qualified']); self.assertFalse(report['submission_ready'])
        self.assertEqual(report['counts']['listeners'],2)
        self.assertGreater(report['listener_macro_contrasts']['contextual_minus_lexical'],.1)
        self.assertEqual(report['uncertainty']['valid'],31)
        for ledger in pred['fit_ledger']:
            df=ledger['effective_df_including_intercept']
            self.assertAlmostEqual(df['lexical'],df['contextual'],places=8)
            self.assertEqual(ledger['selection_fits'],6)

    def test_test_targets_forbidden_at_fit(self):
        self.y.update(self.t)
        with self.assertRaisesRegex(e.ContractError,'hidden targets'): self.predict()

    def test_test_features_do_not_change_fit_or_selection(self):
        before=self.predict()
        for r in self.c['runs']:
            if r['split']=='test':
                for arm in e.ARMS:
                    self.f[r['id']][arm]=(np.asarray(self.f[r['id']][arm])*200+100).tolist()
        after=self.predict()
        self.assertEqual(before['fit_ledger'],after['fit_ledger'])

    def test_family_leakage_and_new_listener_rejected(self):
        self.c['runs'][0]['story_family']='f3'; self.mutate_cases()
        with self.assertRaisesRegex(e.ContractError,'famil'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture()
        self.c['runs'][3]['listener']='unseen'; self.mutate_cases()
        with self.assertRaisesRegex(e.ContractError,'each listener'): self.predict()

    def test_case_digest_duplicate_and_missing_runs(self):
        self.c['runs'][0]['story']='changed'
        with self.assertRaisesRegex(e.ContractError,'cases differ'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture()
        self.c['runs'][1]['id']=self.c['runs'][0]['id']; self.mutate_cases()
        with self.assertRaisesRegex(e.ContractError,'duplicate run'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture(); del self.f['s1_3']
        with self.assertRaisesRegex(e.ContractError,'feature inventory'): self.predict()

    def test_future_context_and_boundary_crossing(self):
        self.f['s1_3']['support_end'][10]+=1
        with self.assertRaisesRegex(e.ContractError,'future'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture();self.f['s1_3']['support_start'][1]=-1
        with self.assertRaisesRegex(e.ContractError,'crosses story'): self.predict()

    def test_rank_constant_and_nonfinite_features(self):
        for f in self.f.values(): f['contextual']=np.ones((64,4)).tolist()
        with self.assertRaisesRegex(e.ContractError,'frozen feature rank'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture();self.f['s1_0']['lexical'][0][0]=float('nan')
        with self.assertRaises(e.ContractError): self.predict()

    def test_missing_arm_and_unbounded_null_rejected(self):
        pred=self.predict(); del pred['predictions']['s1_3']['contextual']
        with self.assertRaisesRegex(e.ContractError,'three prediction arms'):e.score(self.p,self.c,self.t,pred)
        self.p['null_min_shift']=100
        with self.assertRaisesRegex(e.ContractError,'too short'): self.predict()

    def test_null_reproducible_and_declared_diagnostic(self):
        pred=self.predict(); first=e.score(self.p,self.c,self.t,pred); second=e.score(self.p,self.c,self.t,pred)
        self.assertEqual(first,second)
        self.assertIn('not a calibrated significance',first['temporal_null']['limitation'])
        self.assertEqual(len(first['temporal_null']['values']),11)

    def test_whitened_design_is_train_orthogonal(self):
        blocks={a:np.concatenate([e.prepare(self.p,self.c,self.f)[r['id']][a] for r in self.c['runs'] if r['split']=='train']) for a in e.ARMS}
        d=e.Design(blocks,4)
        for arm in ['lexical','contextual']:
            x=d.transform(blocks,arm)
            np.testing.assert_allclose(x.T@x,len(x)*np.eye(x.shape[1]),atol=1e-8)
            np.testing.assert_allclose(x.mean(axis=0),0,atol=1e-12)

    def test_nuisance_only_linguistic_block_rejected(self):
        for f in self.f.values():
            f['lexical']=copy.deepcopy(f['nuisance'])
            f['contextual']=copy.deepcopy(f['nuisance'])
        with self.assertRaisesRegex(e.ContractError,'frozen feature rank'): self.predict()

    def test_scan_and_passage_aliases_rejected(self):
        self.c['runs'][3]['scan_identity']=self.c['runs'][0]['scan_identity']; self.mutate_cases()
        with self.assertRaisesRegex(e.ContractError,'duplicate scan'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture()
        self.c['runs'][3]['passage_ids']=['passage0']; self.mutate_cases()
        with self.assertRaisesRegex(e.ContractError,'repeated passage'): self.predict()

    def test_malformed_objects_rejected(self):
        for bad in [None,[],42]:
            with self.assertRaises(e.ContractError): e.validate(bad,self.c)
            with self.assertRaises(e.ContractError): e.validate(self.p,bad)
            with self.assertRaises(e.ContractError): e.fit_predict(self.p,self.c,bad,self.y)
        self.c['target_ids']=[[]]; self.mutate_cases()
        with self.assertRaises(e.ContractError):self.predict()

    def test_malformed_support_and_prediction_identity(self):
        self.f['s1_0']['support_start']=['bad']
        with self.assertRaisesRegex(e.ContractError,'must be numeric'): self.predict()
        self.p,self.c,self.f,self.y,self.t=fixture(); pred=self.predict(); pred['task_id']='other'
        with self.assertRaisesRegex(e.ContractError,'task ID'): e.score(self.p,self.c,self.t,pred)

    def test_hash_seed_does_not_change_null(self):
        script = "import sys;sys.path.insert(0,"+repr(str(Path(__file__).parent))+ ");from test_evaluator import fixture,e;p,c,f,y,t=fixture();pred=e.fit_predict(p,c,f,y);print(e.score(p,c,t,pred)['temporal_null']['values'])"
        outputs=[subprocess.run([sys.executable,'-c',script],env=dict(os.environ,PYTHONHASHSEED=seed),capture_output=True,text=True,check=True).stdout for seed in ['1','2']]
        self.assertEqual(outputs[0],outputs[1])

    def test_cli_roundtrip_and_duplicate_json_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name,value in [('p',self.p),('c',self.c),('f',self.f),('y',self.y),('t',self.t)]:
                (root/name).write_text(json.dumps(value))
            base=[sys.executable,str(MODULE)]
            subprocess.run(base+['predict','--protocol',str(root/'p'),'--cases',str(root/'c'),'--features',str(root/'f'),'--targets',str(root/'y'),'--output',str(root/'pred')],check=True,capture_output=True)
            subprocess.run(base+['score','--protocol',str(root/'p'),'--cases',str(root/'c'),'--predictions',str(root/'pred'),'--targets',str(root/'t'),'--output',str(root/'report')],check=True,capture_output=True)
            self.assertIn('input_file_sha256',json.loads((root/'report').read_text()))
            (root/'bad').write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(e.ContractError,'duplicate JSON key'): e.load(root/'bad')


if __name__=='__main__':unittest.main()
