"""Generated numerical controls only; no source benchmark performance."""
import unittest
import numpy as np
from memory_reduction import verify_reduction


class ReductionTests(unittest.TestCase):
    def test_original_and_chunk_local_reduction_are_bitwise_equal(self):
        rng = np.random.default_rng(821)
        for dtype in [np.float32,np.float64]:
            chunks = [(np.exp(rng.uniform(-9,5,(n,17,45,384))).astype(dtype))[...,::2]
                      for n in [3,2,4]]
            control=verify_reduction(chunks)
            self.assertTrue(control['bitwise_equal'])
            self.assertEqual(control['maximum_absolute_difference'],0.0)
            self.assertEqual(control['output_shape'],[9,45,17])


if __name__=='__main__':
    unittest.main()
