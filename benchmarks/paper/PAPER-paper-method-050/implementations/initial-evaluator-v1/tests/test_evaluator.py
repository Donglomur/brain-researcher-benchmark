import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
import h5py
import numpy as np

SPEC = importlib.util.spec_from_file_location('dant_evaluator', Path(__file__).resolve().parents[1] / 'evaluator.py')
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)

def fixture(path, sessions=(1,1,1,2,2,3,3)):
    with h5py.File(path, 'w') as h:
        group = h.create_group('spikeInfo')
        for name in ('RatName','SpikeTimes','SessionIndex','Waveform','Kcoords','Xcoords','Ycoords','PETH'):
            refs = group.create_dataset(name,shape=(len(sessions),1),dtype=h5py.ref_dtype)
            for i,session in enumerate(sessions):
                val = {'RatName':np.array([78,97]), 'SpikeTimes':np.array([[i+1.,i+2.]]),
                       'SessionIndex':np.array([[session]]), 'Waveform':np.arange(6).reshape(3,2)+i,
                       'Kcoords':np.array([[1,1]]), 'Xcoords':np.array([[10,20]]),
                       'Ycoords':np.array([[30,40]]), 'PETH':np.array([[1,1,3,3]])}[name]
                refs[i,0] = h.create_dataset(name+str(i),data=val).ref

def packet():
    sessions=[1,1,1,2,2,3,3]
    vectors=[[1,1,3,3],[.6,2.2,1.8,3.4],[1,2,3,1],[.6,2.2,1.8,3.4],[1,1,3,3],[.6,2.2,1.8,3.4],[2,1,2,4]]
    units=[{'dataset':'Nasha','unit_id':i,'session':s,'shank':1,'peth':vectors[i]} for i,s in enumerate(sessions)]
    labels=[1,2,-1,1,2,1,-1]
    assignments=[{'dataset':'Nasha','unit_id':i,'track_id':label} for i,label in enumerate(labels)]
    common={'validation_feature':'PETH','validation_used_for_selection':False,'all_matching_settings_supplied':True,
            'settings':{'motionEstimation':{'features':['Waveform','AutoCorr']}},'settings_provenance':'generated-control',
            'quality_filter_provenance':'same generated complete population','assignments':assignments}
    candidate={**copy.deepcopy(common),'role':'candidate','algorithm':'DANT'}
    reference={**copy.deepcopy(common),'role':'reference','algorithm':'UnitMatch','half_waveforms_verified':True}
    receipt={'dataset':'Nasha','contract_sha256':e.CONTRACT_SHA256,'source_code_revision':e.REVISION,
             'source_kind':'generated_engineering_control','unit_count':7,'units':[{'unit_id':i,'session':s} for i,s in enumerate(sessions)]}
    return {'task_id':e.TASK_ID,'contract_sha256':e.CONTRACT_SHA256,'source_kind':'generated_engineering_control',
            'units':units,'conversion_receipts':[receipt],'feature_lineage_frozen_before_matching':True,
            'dataset_to_animal':{'Nasha':'rat-Nasha'},'animal_grouping_provenance':'generated-control',
            'animal_splits':{'train':[],'validation':[],'test':['rat-Nasha']},'methods':[candidate,reference]}

class ConversionTests(unittest.TestCase):
    def test_exact_transpose_order_and_receipt(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); fixture(root/'in.mat')
            r=e.convert_spikeinfo(root/'in.mat',root/'out','Nasha',source_kind='generated_engineering_control')
            self.assertEqual(r['unit_count'],7)
            np.testing.assert_array_equal(np.load(root/'out/waveform_all.npy',allow_pickle=False)[0],[[0,2,4],[1,3,5]])
            np.testing.assert_array_equal(np.load(root/'out/channel_locations.npy',allow_pickle=False),[[10,30],[20,40]])
            np.testing.assert_array_equal(np.load(root/'out/spike_times/Unit3.npy',allow_pickle=False),[4,5])
            self.assertFalse(r['scientific_qualified'])
            self.assertEqual(len(r['files']),12)
            for row in r['files']: self.assertEqual(row['sha256'], e.digest(root/'out'/row['path']))
            with self.assertRaises(e.ContractError): e.convert_spikeinfo(root/'in.mat',root/'out','Nasha')
    def test_real_asset_gate_rejects_generated(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); fixture(root/'in.mat')
            with self.assertRaisesRegex(e.ContractError,'byte size'):
                e.convert_spikeinfo(root/'in.mat',root/'out','Nasha')
            self.assertFalse((root/'out').exists())
    def test_gap_rejected_and_no_partial_output(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); fixture(root/'in.mat',[1,3])
            with self.assertRaisesRegex(e.ContractError,'contiguous'):
                e.convert_spikeinfo(root/'in.mat',root/'out','Nasha',source_kind='generated_engineering_control')
            self.assertFalse((root/'out').exists())
            self.assertEqual(list(root.glob('.spikeinfo-*')),[])

class ScoringTests(unittest.TestCase):
    def test_independent_hand_count_directional_yield(self):
        result=e.evaluate(packet()); a=result['methods']['candidate']['datasets']['Nasha']
        self.assertEqual(a['longitudinal_track_count'],2)
        self.assertEqual(a['matched_pair_count'],4)
        self.assertEqual(a['tracked_unit_fraction'],5/7)
        directions={(r['source_session'],r['target_session']):r['fraction'] for r in a['directional_session_yield']}
        self.assertEqual(directions[1,2],2/3)
        self.assertEqual(directions[2,1],1)
        self.assertEqual(a['all_session_track_count'],1)
        self.assertEqual(result['paired_candidate_minus_reference']['Nasha']['directional_yield_difference'],0)
        self.assertIsNone(result['identity_accuracy'])
        json.dumps(result,allow_nan=False)
    def test_independent_fisher_oracle(self):
        # Independent derivation: centered vectors have correlation 3/5;
        # atanh(3/5) = log(2), repeated bins leave the correlation unchanged.
        a=np.tile([1.,1.,3.,3.],750); b=np.tile([.6,2.2,1.8,3.4],750)
        self.assertAlmostEqual(e._fisher_z(a,b),math.log(2),places=12)
        self.assertIsNone(e._fisher_z(np.ones(4),np.arange(4)))
        for vector in [np.array([0.,1.,2.]), np.array([-1.,1.]), np.array([0.,1e300,2e300])]:
            self.assertEqual(e._fisher_z(vector,vector), math.inf)
            self.assertEqual(e._fisher_z(vector,-vector), -math.inf)
        self.assertAlmostEqual(e._fisher_z(a*1e300,b*1e300),math.log(2),places=12)

    def test_permutation_does_not_change_scores(self):
        p=packet(); expected=e.evaluate(p)
        p['units'].reverse()
        for method in p['methods']: method['assignments'].reverse()
        self.assertEqual(e.evaluate(p),expected)
    def test_leakage_in_any_nested_setting(self):
        for key in ['motionEstimation','sharedMotion','features_after_shared','clustering','autoCuration','tuning']:
            p=packet(); p['methods'][0]['settings'][key]={'features':[['PETH']]}
            with self.subTest(key=key), self.assertRaisesRegex(e.ContractError,'independence'):
                e.evaluate(p)
    def test_missing_duplicate_unknown_units_and_population(self):
        for change in ['missing','duplicate','unknown','omitted_population']:
            p=packet(); rows=p['methods'][0]['assignments']
            if change=='missing': rows.pop()
            elif change=='duplicate': rows.append(copy.deepcopy(rows[0]))
            elif change=='unknown': rows[0]['unit_id']=100
            else: p['units'].pop()
            with self.subTest(change=change), self.assertRaises(e.ContractError): e.evaluate(p)
    def test_same_session_track_and_singleton_rejected(self):
        for labels in [[1,1,-1,1,-1,-1,-1],[1,-1,-1,-1,-1,-1,-1]]:
            p=packet()
            for row,label in zip(p['methods'][0]['assignments'],labels): row['track_id']=label
            with self.assertRaises(e.ContractError): e.evaluate(p)
    def test_huge_session_gap_rejected_without_range_allocation(self):
        p=packet(); p['units'][-1]['session']=10**30
        p['conversion_receipts'][0]['units'][-1]['session']=10**30
        with self.assertRaisesRegex(e.ContractError,'contiguous'): e.evaluate(p)
    def test_cross_shank_track_rejected(self):
        p=packet(); p['units'][3]['shank']=2
        with self.assertRaisesRegex(e.ContractError,'shanks'): e.evaluate(p)
    def test_unmatched_and_constant_diagnostics(self):
        p=packet()
        for method in p['methods']:
            for row in method['assignments']: row['track_id']=-1
        a=e.evaluate(p)['methods']['candidate']['datasets']['Nasha']
        self.assertEqual(a['macro_directional_session_yield'],0)
        self.assertIsNone(a['peth_fisher_z']['mean'])
        p=packet()
        for u in p['units']: u['peth']=[1,1,1,1]
        a=e.evaluate(p)['methods']['candidate']['datasets']['Nasha']
        self.assertEqual(a['peth_fisher_z']['constant_feature_pairs'],4)
        self.assertIsNone(a['peth_fisher_z']['mean'])
    def test_split_filter_and_unitmatch_boundaries(self):
        for case in ['split','filter','half','selection','all13','grouping']:
            p=packet()
            if case=='split': p['animal_splits']['train']=['rat-Nasha']
            elif case=='filter': p['methods'][0]['quality_filter_provenance']='different'
            elif case=='half': p['methods'][1]['half_waveforms_verified']=False
            elif case=='selection': p['methods'][0]['validation_used_for_selection']=True
            elif case=='grouping': p['dataset_to_animal']={}
            else: p['source_kind']='source_asset'
            with self.subTest(case=case), self.assertRaises(e.ContractError): e.evaluate(p)

if __name__=='__main__': unittest.main()
