"""Invented complete34-movie controls; no authentic arrays or reference access."""
import copy
from fractions import Fraction as F
from itertools import combinations
import json
import math
from pathlib import Path
import types
import unittest

P=Path(__file__).absolute().with_name('event_score.py')
S=types.ModuleType('voltron_native_generated_source');S.__file__=str(P)
exec(compile(P.read_bytes(),str(P),'exec'),S.__dict__)


def fixture():
    cells=['c'+str(i) for i in range(12)];mapping={c:'s'+str(i//2) for i,c in enumerate(cells)}
    public={'schema':'voltron-native-frame-public/v1','task_id':S.TASK,'profile':S.PROFILE,
        'release_manifest_sha256':'0'*64,'cells':cells,'expected_subjects':6,'movies':{}}
    ref={'schema':'voltron-native-frame-reference/v1','task_id':S.TASK,'public_sha256':'',
        'census_evidence_sha256':'1'*64,'mapping_evidence_sha256':'2'*64,'cell_to_subject':mapping,
        'outer_folds':{'f'+str(i):{'query_subject':'s'+str(i),'train_cells':[c for c in cells if mapping[c]!='s'+str(i)]} for i in range(6)},'movies':{}}
    for i in range(34):
        mid='m'+str(i);c=cells[i%12]
        public['movies'][mid]={'cell_id':c,'fold_id':'f'+str((i%12)//2),'nominal_optical_rate_hz':400 if i%2 else 1000,
            'start_time':0,'end_time':[1,50],'frame_times':[[j,401] for j in range(6)],'input_disposition':'ready',
            'optical_valid_intervals':[[0,[1,50]]],'cores':[{'core_id':mid+'a','start_frame':0,'end_frame':3},{'core_id':mid+'b','start_frame':3,'end_frame':6}]}
        ref['movies'][mid]={'valid_intervals':[[0,[1,50]]],'spikes':[[1,401],[4,401]]}
    predictions={'schema':'voltron-native-frame-predictions/v1','task_id':S.TASK,'public_sha256':'','roles':{}}
    for role in S.ROLES:
        predictions['roles'][role]={'program_sha256':'3'*64,'calibration_sha256':'4'*64,'cores':{}}
        for mid in public['movies']:
            predictions['roles'][role]['cores'].update({mid+'a':[1] if role!='metadata_rate' else [],mid+'b':[4] if role=='candidate' else []})
    rebind(public,predictions,ref)
    return public,predictions,ref


def rebind(public,predictions,ref):
    sha=S.identity(public);predictions['public_sha256']=sha;ref['public_sha256']=sha


class Matching(unittest.TestCase):
    def test_exhaustive_dynamic_programming_cardinality(self):
        grid=[F(i,200) for i in range(5)]
        panels=[tuple(c) for n in range(6) for c in combinations(grid,n)]
        pairs=0
        for p in panels:
            for t in panels:
                dp=[[0]*(len(t)+1) for _ in range(len(p)+1)]
                for i in range(1,len(p)+1):
                    for j in range(1,len(t)+1):
                        dp[i][j]=max(dp[i-1][j],dp[i][j-1],dp[i-1][j-1]+int(abs(p[i-1]-t[j-1])<=F(1,200)))
                self.assertEqual(S.match_events(p,t)[0],dp[-1][-1]);pairs+=1
        self.assertEqual(pairs,1024)
    def test_inclusive_exact_boundary_and_binary_float(self):
        self.assertEqual(S.match_events([F(1,200)],[0])[0],1)
        self.assertEqual(S.match_events([-F(1,200)],[0])[0],1)
        self.assertEqual(S.match_events([.005],[0])[0],0) # represented binary float is just above1/200
        self.assertEqual(S.match_events([math.nextafter(.005,0.)],[0])[0],1)
    def test_earliest_compatible_beats_nearest_greedy(self):
        self.assertEqual(S.match_events([F(4,1000),F(8,1000)],[0,F(5,1000)]),
                         (2,0,0,(F(4,1000),F(3,1000))))
        # Earliest-compatible is deliberately not minimum latency.
        self.assertEqual(S.match_events([F(4,1000)],[0,F(5,1000)])[3],(F(4,1000),))
    def test_empty_and_rejected_scalars(self):
        self.assertEqual(S.match_events([],[]),(0,0,0,()))
        for v in (True,float('nan'),float('inf'),[1,0],[1,-2],['1',2]):
            with self.subTest(value=v),self.assertRaises(S.ContractError):S.match_events([v],[])
        for v in ([0,0],[1,0]):
            with self.assertRaises(S.ContractError):S.match_events(v,[])
    def test_no_gap_crossing_and_adjacent_coalescence(self):
        p=(F(4,1000),);t=(F(6,1000),)
        self.assertEqual(S._match_intervals(p,t,((F(0),F(5,1000)),(F(55,10000),F(1,100))))[:3],(0,1,1))
        spans=S._intervals([[0,[5,1000]],[[5,1000],[1,100]]],F(0),F(1,100),S.ReferenceError)
        self.assertEqual(S._match_intervals(p,t,spans)[:3],(1,0,0))
    def test_representation_ceiling_uses_neighbors_and_selected_subset(self):
        public={'movies':{'m':{'cell_id':'c','frame_times':(F(0),F(3,1000),F(6,1000),F(9,1000))}},'cells':('c',)}
        ref={'m':{'spikes':(F(4,1000),F(5,1000)),'valid_intervals':((F(0),F(1,100)),)}}
        row=S.representation_ceiling(ref,public)['movies']['m']
        self.assertEqual((row['maximum_matches'],row['representation_only_f1']),(2,1.))
        self.assertEqual(row['eligible_frame_centers'],4)
        ref['m']['spikes']=();row=S.representation_ceiling(ref,public)['movies']['m']
        self.assertIsNone(row['attainable_recall']);self.assertIsNone(row['representation_only_f1'])


class CompleteGrade(unittest.TestCase):
    def test_complete_profile_and_private_barrier_snapshot(self):
        p,s,r=fixture();loads=[]
        def load():
            loads.append(1)
            s['roles']['candidate']['cores']['m0a'][:]=[]
            p['movies']['m0']['frame_times'][1][:]=[100,1]
            return r
        result=S.grade(p,s,load)
        self.assertEqual(loads,[1]);self.assertEqual(len(result['roles']['candidate']['movies']),34)
        self.assertEqual(len(result['roles']['candidate']['cells']),12)
        self.assertEqual(len(result['roles']['candidate']['subjects']),6)
        self.assertTrue(all(x['equal_cell_f1']==1 for x in result['roles']['candidate']['subjects'].values()))
        self.assertFalse(result['scientific_qualified']);self.assertNotIn('score',result)
        self.assertNotIn('oracle_frame_indices',json.dumps(result))
    def test_missing_duplicate_wrong_core_and_nonfinite_rejected_before_reference(self):
        mutations=[lambda s:s['roles']['candidate']['cores'].pop('m33b'),
                   lambda s:s['roles'].pop('metadata_rate'),
                   lambda s:s['roles']['candidate']['cores'].__setitem__('m0a',[1,1]),
                   lambda s:s['roles']['candidate']['cores'].__setitem__('m0a',[4]),
                   lambda s:s['roles']['candidate']['cores'].__setitem__('m0a',[True]),
                   lambda s:s['roles']['candidate']['cores'].__setitem__('m0a',[float('nan')])]
        for mutation in mutations:
            p,s,r=fixture();mutation(s);loads=[]
            result=S.grade(p,s,lambda:loads.append(1))
            self.assertEqual(result['status'],'invalid_submission');self.assertEqual(loads,[])
    def test_reference_missing_movie_leakage_and_invalid_truth_raise(self):
        mutations=[lambda r:r['movies'].pop('m33'),lambda r:r['outer_folds']['f0']['train_cells'].append('c0'),
            lambda r:r['movies']['m0'].__setitem__('spikes',[[1,401],[1,401]]),
            lambda r:r['movies']['m0'].__setitem__('valid_intervals',[[0,[1,1000]]]),
            lambda r:r['movies']['m0'].__setitem__('spikes',[float('nan')])]
        for mutation in mutations:
            p,s,r=fixture();mutation(r)
            with self.assertRaises(S.ReferenceError):S.grade(p,s,lambda:r)
    def test_public_missing_scope_clock_and_core_tail_raise(self):
        mutations=[lambda p:p['movies'].pop('m33'),lambda p:p.__setitem__('expected_subjects',7),
            lambda p:p['movies']['m0']['cores'][-1].__setitem__('end_frame',5),
            lambda p:p['movies']['m0']['frame_times'].__setitem__(1,[0,1]),
            lambda p:p['movies']['m0']['frame_times'].__setitem__(1,float('inf'))]
        for mutation in mutations:
            p,s,r=fixture();mutation(p)
            with self.assertRaises(S.ContractError):S.grade(p,s,lambda:r)
    def test_failed_extraction_stays_visible_and_undefined_cell_propagates(self):
        p,s,r=fixture()
        for mid,m in p['movies'].items():
            if m['cell_id']=='c0':
                m['input_disposition']='optical_extraction_failed';m['optical_valid_intervals']=[]
                r['movies'][mid]={'spikes':[],'valid_intervals':[]}
        rebind(p,s,r);result=S.grade(p,s,lambda:r)['roles']['candidate']
        self.assertEqual(result['cells']['c0']['movie_count'],3)
        self.assertEqual(result['cells']['c0']['optical_extraction_failed_movies'],3)
        self.assertIsNone(result['subjects']['s0']['equal_cell_f1'])
        self.assertEqual(result['subjects']['s0']['observed_only_equal_cell_f1'],1.)
        self.assertFalse(result['subjects']['s0']['complete_validity'])
        self.assertEqual(result['cells']['c0']['predictions_outside_valid_support'],6)
    def test_counts_pool_before_cell_and_cells_are_equally_weighted(self):
        p,s,r=fixture()
        # c0:6 true events, one TP =>cellF1=2/7; c1:6 TP=>cellF1=1.
        for mid,m in p['movies'].items():
            if m['cell_id']=='c0':
                s['roles']['candidate']['cores'][mid+'a']=[1] if mid=='m0' else []
                s['roles']['candidate']['cores'][mid+'b']=[]
        result=S.grade(p,s,lambda:r)['roles']['candidate']
        self.assertEqual(result['cells']['c0']['f1'],2/7)
        self.assertEqual(result['subjects']['s0']['equal_cell_f1_ratio'],[9,14])
    def test_no_truth_false_positive_and_empty_empty_conventions(self):
        p,s,r=fixture()
        for row in r['movies'].values():row['spikes']=[]
        result=S.grade(p,s,lambda:r)
        a=result['roles']['candidate']['cells']['c0'];b=result['roles']['metadata_rate']['cells']['c0']
        self.assertEqual(a['f1'],0.);self.assertEqual(a['precision'],0.);self.assertIsNone(a['recall'])
        self.assertGreater(a['false_events_per_minute'],0);self.assertIsNone(b['f1'])
        self.assertIsNone(result['private_representation_ceiling']['cells']['c0']['representation_only_f1'])
    def test_private_loader_failure_is_operational(self):
        p,s,r=fixture()
        def fail():raise OSError('invented unavailable private reference')
        with self.assertRaises(OSError):S.grade(p,s,fail)


if __name__=='__main__':unittest.main(verbosity=2)
