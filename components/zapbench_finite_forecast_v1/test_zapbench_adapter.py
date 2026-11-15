"""Invented controls; do not read authentic arrays or execute upstream code."""
import copy
import math
import unittest
from unittest.mock import patch
import zapbench_adapter as z

class ContractControls(unittest.TestCase):
    def test_independent_full_geometry_table(self):
        # Independently calculated from padded split lengths, not output snapshots.
        rows = [(0,519,616,98),(1,2067,2389,323),(2,2947,3045,99),
                (4,4784,5014,231),(5,5520,5605,86),(6,6426,6590,165),
                (7,7148,7246,99),(8,7759,7846,88),(3,3335,3702,368)]
        for context in (1,4,256):
            plan=z.validate_manifest(z.expected_manifest(context))
            self.assertEqual([(e['condition'],e['first_target_start'],e['last_target_start'],e['num_windows']) for e in plan['endpoints']],rows)
            self.assertEqual(sum(e['num_windows'] for e in plan['endpoints']),1557)
            for e in plan['endpoints']:
                for t in (e['first_target_start'],e['last_target_start']):
                    z.validate_window(e['condition'],e['split'],context,t-context,t,t+32)
        self.assertEqual(1557*32*z.NEURONS,3573427104)

    def test_training_validation_geometry(self):
        self.assertEqual(sum(z.window_geometry(c,'train',256)['num_windows'] for c in z.TRAIN_CONDITIONS),2756)
        self.assertEqual(sum(z.window_geometry(c,'val',256)['num_windows'] for c in z.TRAIN_CONDITIONS),469)
        z.validate_window(0,'val',256,199,455,487)  # legal train context
        z.validate_window(0,'test',256,264,520,552)  # includes preceding test observation

    def test_forbidden_condition_split_membership(self):
        for split in ('train','val','test'):
            with self.assertRaises(z.AdmissionError):z.window_geometry(3,split,256)
        with self.assertRaises(z.AdmissionError):z.window_geometry(0,'test_holdout',256)

    def test_invalid_boundaries(self):
        for values in [(0,'test',256,262,518,550),(0,'test',256,361,617,649),
                       (3,'test_holdout',256,3078,3334,3366),
                       (0,'test',256,263,519,550),(0,'test',256,264,519,551)]:
            with self.assertRaises(z.AdmissionError):z.validate_window(*values)

    def test_context_type_and_range(self):
        for context in (0,257,-1,True,4.0,'4',None):
            with self.assertRaises(z.AdmissionError):z.expected_manifest(context)
        for condition in (True,0.0,-1,9):
            with self.assertRaises(z.AdmissionError):z.condition_bounds(condition)

    def test_full_manifest_rejects_omission_extra_permutation_and_shape(self):
        mutations = [lambda p:p['endpoints'].pop(),
                     lambda p:p['endpoints'].reverse(),
                     lambda p:p['endpoints'].append(p['endpoints'][0]),
                     lambda p:p['endpoints'][0].update(num_windows=97),
                     lambda p:p['endpoints'][0]['shape'].__setitem__(2,71720),
                     lambda p:p.update(extra='unreviewed'),
                     lambda p:p.update(output_offset=1),
                     lambda p:p.update(warmup_steps=1),
                     lambda p:p.update(sequential=1),
                     lambda p:p.update(horizon=32.0),
                     lambda p:p['training_intervals'].append({'condition':3,'interval':[3079,3538]}),
                     lambda p:p['neuron_axis'].update(start=1),
                     lambda p:p.update(upstream_commit='0'*40)]
        for mutate in mutations:
            p=z.expected_manifest();mutate(p)
            with self.assertRaises(z.AdmissionError):z.validate_manifest(p)

    def test_kernel_known_absolute_and_squared_errors(self):
        self.assertEqual(z.tile_error_sums([1,-2,3],[3,-1,-1]),(7,21,3))
        self.assertEqual(z.tile_error_sums([4,4],[4,4]),(0,0,2))
        self.assertEqual(z.tile_error_sums([0,0],[0,4]),(4,16,2))
        self.assertEqual(z.tile_error_sums([-2,3],[0,0]),(5,13,2)) # no clipping

    def test_nonfinite_and_malformed_values_rejected(self):
        for value in (float('nan'),float('inf'),-float('inf'),True,'1',None,10**1000):
            for p,t in (([value],[0]),([0],[value])):
                with self.assertRaises(z.AdmissionError):z.tile_error_sums(p,t)
        for p,t in (([],[]),([1],[1,2]),([0]*4097,[0]*4097),((1,),[1]),([1e308],[-1e308])):
            with self.assertRaises(z.AdmissionError):z.tile_error_sums(p,t)

    def test_tile_coordinate_guards(self):
        good={'condition':0,'window':0,'horizon':1,'first_neuron':0,'target_time':519,'predictions':[0,1],'targets':[1,0]}
        self.assertEqual(z._admit_tile(good,0,0,1,0,519),2)
        for field,value in [('condition',1),('window',1),('horizon',0),('first_neuron',1),('target_time',520),('window',False)]:
            bad=dict(good);bad[field]=value
            with self.assertRaises(z.AdmissionError):z._admit_tile(bad,0,0,1,0,519)
        bad=dict(good);bad['first_neuron']=71720
        with self.assertRaises(z.AdmissionError):z._admit_tile(bad,0,0,1,71720,519)

    def test_complete_scorer_refuses_empty_and_successful_prefix(self):
        with self.assertRaises(z.AdmissionError):z.score_complete(z.expected_manifest(),[])
        tile={'condition':0,'window':0,'horizon':1,'first_neuron':0,'target_time':519,'predictions':[1,2],'targets':[0,0]}
        with self.assertRaises(z.AdmissionError):z.score_complete(z.expected_manifest(),[tile])
        with self.assertRaises(z.AdmissionError):z.score_complete(z.expected_manifest(),[tile,tile])

    def test_invented_complete_reducer_and_condition_weighting(self):
        # Reduced geometry injected ONLY in this test; production admission and
        # full official metadata are tested separately. No full-size numeric claim.
        plan={'endpoints':[{'condition':c,'num_windows':c+1,'first_target_start':10}
                           for c in range(9)]}
        tiles=[]
        for c in range(9):
            for w in range(c+1):
                for h in range(2):
                    for n in range(2):
                        tiles.append({'condition':c,'window':w,'horizon':h+1,
                                      'first_neuron':n,'target_time':10+w+h,
                                      'predictions':[(c+1)*(h+1)*(n+1)],'targets':[0]})
        with patch.object(z,'validate_manifest',return_value=plan), patch.object(z,'NEURONS',2), patch.object(z,'HORIZON',2):
            scored=z.score_complete({},tiles)
            self.assertEqual(scored['coordinates'],180)
            self.assertEqual(scored['all_nine_condition_macro']['mae_by_horizon'],[7.5,15])
            self.assertAlmostEqual(scored['all_nine_condition_macro']['mse_by_horizon'][0],2.5*285/9)
            self.assertEqual(scored['per_condition'][1]['mae'],4.5)
            # Weighting windows globally would yield 9.5, not 7.5, at h=1.
            self.assertNotEqual(scored['all_nine_condition_macro']['mae_by_horizon'][0],9.5)
            with self.assertRaises(z.AdmissionError):z.score_complete({},tiles+[tiles[-1]])
            with self.assertRaises(z.AdmissionError):z.score_complete({},tiles[:-1])
            bad=copy.deepcopy(tiles);bad[-1]['targets']=[float('nan')]
            with self.assertRaises(z.AdmissionError):z.score_complete({},bad)

    def test_compensated_sum_and_overflow(self):
        s=z._Sum()
        for v in (1e16,1,1):s.add(v)
        self.assertEqual(s.value(),10000000000000002)
        s=z._Sum();s.add(1e308)
        with self.assertRaises(z.AdmissionError):s.add(1e308)

if __name__=='__main__':unittest.main(verbosity=2)
