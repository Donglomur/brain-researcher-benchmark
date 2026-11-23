"""Tiny generated finite-roster controls; no authentic data or estimator fits."""
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent/'programme'/'scientific-runtime'))
from finite_science.geometry import population
from finite_science.common import ScientificGate


def compute(matrix,axis='task'):
    return population({'arrays':{'matrix':matrix},'request':{'axis':axis}})


class FinitePopulationTests(unittest.TestCase):
    def test_original_moments_and_spectral_ratio_all_axes(self):
        # Nonconstant, unequal spectrum, with both tall and wide orientations.
        original=np.array([[1.,2.,4.],[3.,-2.,1.],[0.,5.,-3.],[2.,1.,2.],[-1.,4.,0.]])
        for matrix in (original,original.T):
            for axis in ('task','neuron','uncentered'):
                with self.subTest(shape=matrix.shape,axis=axis):
                    H=matrix.T if axis=='neuron' else matrix
                    if axis!='uncentered':H=H-H.mean(axis=0)
                    R,C=H.shape;K=H@H.T/C
                    expected_A=float(np.mean(H*H)**2)
                    expected_B=float(np.mean(K*K))
                    eig=np.linalg.svd(H,compute_uv=False)**2
                    expected_gamma=float(eig.sum()**2/(eig@eig))
                    answer=compute(matrix,axis)
                    self.assertEqual(answer['status'],'ok')
                    self.assertAlmostEqual(answer['outputs']['A'],expected_A,places=12)
                    self.assertAlmostEqual(answer['outputs']['B'],expected_B,places=12)
                    self.assertAlmostEqual(answer['outputs']['gamma'],expected_gamma,places=12)
                    self.assertEqual(answer['support']['gram_dimension'],min(R,C))
                    self.assertEqual(answer['diagnostics']['unrepresentable_raw_moments'],{})

    def test_uniform_extreme_scales_preserve_ratio_and_report_moments(self):
        matrix=np.array([[1.,0.],[-1.,0.],[0.,2.],[0.,-2.]])
        expected=25./17.
        for exponent,kind in ((600,'overflow'),(-600,'underflow')):
            for axis in ('task','neuron','uncentered'):
                with self.subTest(exponent=exponent,axis=axis):
                    reference=compute(matrix,axis)['outputs']['gamma']
                    answer=compute(np.ldexp(matrix,exponent),axis)
                    self.assertEqual(answer['status'],'ok')
                    self.assertAlmostEqual(answer['outputs']['gamma'],reference,places=14)
                    self.assertIsNone(answer['outputs']['A'])
                    self.assertIsNone(answer['outputs']['B'])
                    self.assertEqual(answer['diagnostics']['unrepresentable_raw_moments'],{'A':kind,'B':kind})
                    scaled=answer['support']['scaled_moments']
                    self.assertAlmostEqual(scaled['A']/scaled['B'],reference,places=14)
                    json.dumps(answer,allow_nan=False)
        self.assertAlmostEqual(compute(matrix)['outputs']['gamma'],expected,places=14)

    def test_large_constant_column_does_not_erase_small_signal(self):
        # Global scaling before centering would erase the second column.
        matrix=np.column_stack([np.full(4,math.ldexp(1.,1000)),
                                np.ldexp(np.array([1.,-1.,2.,-2.]),-1000)])
        for values,axis in ((matrix,'task'),(matrix.T,'neuron')):
            answer=compute(values,axis)
            self.assertEqual(answer['status'],'ok')
            self.assertAlmostEqual(answer['outputs']['gamma'],1.,places=14)
            self.assertEqual(answer['diagnostics']['unrepresentable_raw_moments'],{'A':'underflow','B':'underflow'})

    def test_nonbinary_constant_mantissa_is_exactly_removed(self):
        # Three repeated 0.8 mantissas do not necessarily average to 0.8.
        # Orthogonal centered signals have eigenvalues in ratio 1:3, PR 1.6.
        matrix=np.column_stack([np.full(3,math.ldexp(.8,1000)),
                                np.ldexp(np.array([-1.,0.,1.]),-1000),
                                np.ldexp(np.array([1.,-2.,1.]),-1000)])
        for values,axis in ((matrix,'task'),(matrix.T,'neuron')):
            answer=compute(values,axis)
            self.assertEqual(answer['status'],'ok')
            self.assertAlmostEqual(answer['outputs']['gamma'],1.6,places=14)
        answer=compute(np.full((3,2),math.ldexp(.8,1000)))
        self.assertEqual(answer['status'],'undefined_denominator')

    def test_centering_does_not_overflow_large_repeated_entries(self):
        # The old column sum overflows although every input and mean is finite.
        huge=math.ldexp(1.,1023)
        matrix=np.array([[huge,1.],[huge,2.],[huge,3.],[huge,4.]])
        answer=compute(matrix)
        self.assertEqual(answer['status'],'ok')
        self.assertAlmostEqual(answer['outputs']['gamma'],1.,places=14)
        self.assertAlmostEqual(answer['outputs']['A'],.390625,places=14)
        self.assertAlmostEqual(answer['outputs']['B'],.390625,places=14)

    def test_zero_denominator_is_not_recovered_as_dimension(self):
        for matrix in (np.zeros((4,2)),np.full((4,2),math.ldexp(1.,1023))):
            answer=compute(matrix)
            self.assertEqual(answer['status'],'undefined_denominator')
            self.assertEqual(answer['outputs'],{'A':0.,'B':0.,'gamma':None})
            json.dumps(answer,allow_nan=False)
        self.assertEqual(compute(np.zeros((2,3)),'uncentered')['status'],'undefined_denominator')

    def test_invalid_inputs_still_fail(self):
        for matrix in (np.ones(3),np.empty((0,2)),[[math.inf]],[[math.nan]]):
            with self.assertRaises(ScientificGate):compute(matrix)
        with self.assertRaises(ScientificGate):compute(np.ones((4,2)),'changed-target')


if __name__=='__main__':unittest.main(verbosity=2)
