"""Mandatory real-library differential on generated operands in pinned current CI.

Missing imbalanced-learn or a different runtime is a failure, never a skip.
This verifies current-runtime arithmetic; historical NumPy1.23.5 is not claimed.
No authentic neural data, representation learner, Ray worker or author pickle runs.
"""
import importlib.metadata
import os
import sys
import unittest

import _control_support as support
from _control_support import PipelineTrace, run_source, assert_trace_pair

CURRENT_RUNTIME={'numpy':'2.2.6','scipy':'1.15.3','scikit-learn':'1.6.1',
    'imbalanced-learn':'0.14.0','joblib':'1.5.3','threadpoolctl':'3.6.0'}


class HostedRealROSParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.implementation.name!='cpython' or sys.version_info[:3]!=(3,11,18):
            raise AssertionError('The adopted current-runtime control requires exact CPython3.11.18')
        actual={name:importlib.metadata.version(name) for name in CURRENT_RUNTIME}
        if actual!=CURRENT_RUNTIME:
            raise AssertionError('Exact current-runtime ROS control tuple required: '+repr(actual))
        for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
            if os.environ.get(name)!='1':
                raise AssertionError('One-thread hosted runtime required: '+name)
        # Intentionally mandatory; ImportError/PackageNotFoundError fails this job.
        from imblearn.over_sampling import RandomOverSampler
        from sklearn.linear_model import LogisticRegression
        cls.ROS=RandomOverSampler; cls.LR=LogisticRegression
        _,_,_,_,source=support.route._dependencies(support.IMPLEMENTATIONS)
        cls.evaluator=source.evaluator

    def parity(self,alternate_order):
        import numpy as np
        packet=support.tiny_packet(self.evaluator,alternate_order=alternate_order)
        source=PipelineTrace(real_ros=self.ROS,real_classifier=self.LR)
        adapter=PipelineTrace(real_ros=self.ROS,real_classifier=self.LR)
        oracle=run_source(packet,source.Sampler,source.Scaler,source.Classifier)
        with adapter.installed():
            actual=self.evaluator.evaluate(packet)
        self.assertEqual((len(source.samples),len(adapter.samples)),(6,4))
        self.assertEqual(oracle['ray_jobs'],6)
        self.assertEqual(oracle['selected_index'],0)
        self.assertEqual(actual['selected'][0]['epoch'],2)
        for k in range(3): assert_trace_pair(self,source,adapter,2*k,k)
        assert_trace_pair(self,source,adapter,1,3)
        self.assertEqual([r['pred'] for r in actual['records']],oracle['pred'])
        self.assertEqual([r['true'] for r in actual['records']],oracle['true'])
        self.assertEqual(actual['metrics']['macro_f1'],oracle['f1'])
        self.assertEqual(actual['metrics']['balanced_accuracy'],oracle['bacc'])
        ids=packet['checkpoints'][0]['ids']; split=packet['splits'][0]
        self.assertEqual([r['unit_id'] for r in actual['records']],[uid for uid in ids if uid in split['test']])
        X=np.asarray(packet['checkpoints'][0]['embeddings'],dtype=np.float32)
        for i,population in ((0,set(split['train'])),(3,set(split['train'])|set(split['val']))):
            positions=[j for j,uid in enumerate(ids) if uid in population]
            np.testing.assert_array_equal(adapter.scalers[i]['X'],X[positions][adapter.samples[i]['picked']])
            self.assertTrue(population.isdisjoint(split['test']))
        self.assertFalse(actual['research_qualified'])
        self.assertFalse(actual['full_contract_complete'])

    def test_real_ROS42_scaler_LR_literal_source_parity_in_original_generated_order(self):
        self.parity(False)

    def test_real_ROS42_parity_in_second_explicit_order_without_invariance_claim(self):
        self.parity(True)

    def test_real_seed42_is_not_substituted_and_scaling_population_changes(self):
        import numpy as np
        from sklearn.preprocessing import StandardScaler
        y=np.asarray(['EC']*10+['IN']*3)
        positions=np.arange(len(y)).reshape(-1,1)
        first,_=self.ROS(random_state=42).fit_resample(positions,y)
        other,_=self.ROS(random_state=7).fit_resample(positions,y)
        self.assertFalse(np.array_equal(first,other))
        X=np.asarray([[i*i+i*0.234567891,i%4] for i in range(len(y))],dtype=np.float32)
        scaled_before=StandardScaler().fit(X)
        scaled_after=StandardScaler().fit(X[first.ravel()])
        self.assertFalse(np.array_equal(scaled_before.mean_,scaled_after.mean_))


if __name__=='__main__':
    unittest.main(verbosity=2)
