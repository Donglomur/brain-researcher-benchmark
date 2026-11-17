"""Required real-library seam on generated signals; no historical-equivalence claim.

Run separately using the explicitly pinned hosted test environment. Missing or
mismatched dependencies are errors, never skips or analytic fallbacks.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import types
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import inputs
import preprocess


class RequiredElephantControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No conditional skip: CI must install exactly this declared modern test
        # backend. It is not reconstructed evidence for the authors' runtime.
        cls.versions = json.loads((HERE / 'dependencies/elephant-test-versions.json').read_text())
        cls.backend = preprocess.ElephantBackend(cls.versions)
        print(json.dumps({'scope': 'generated-required-elephant-seam',
                          'backend_provenance': cls.backend.provenance}, sort_keys=True))

    def test_literal_author_helper_with_real_elephant_and_pca(self):
        from elephant.kernels import GaussianKernel
        from elephant.statistics import instantaneous_rate
        from quantities import ms
        import neo
        path = HERE / 'reference/rat_utils.py'
        body = path.read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(),
                         'e90bac90d46b91a13604728ba893aa36343c2fd2a4c634a4c0dcf84b0b461623')
        selected = [n for n in ast.parse(body).body if isinstance(n, ast.FunctionDef)
                    and n.name == 'convert_spikes_to_rates']
        self.assertEqual(len(selected), 1)
        namespace = {'np': np, 'PCA': preprocess.PCA, 'GaussianKernel': GaussianKernel,
                     'instantaneous_rate': instantaneous_rate, 'ms': ms, 'neo': neo,
                     'MARBLE': types.SimpleNamespace(construct_dataset=lambda **kw: kw)}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
        signals = np.zeros((128, 4), dtype=np.float32)
        signals[[0, 47, 127], 0] = [2, -0.5, 1]
        signals[[9, 63, 110], 1] = [1, 3.25, 1]
        signals[[31, 75], 2] = 1
        signals[[17, 83, 115], 3] = 1
        with contextlib.redirect_stdout(io.StringIO()):
            graph, labels, author_pca = namespace['convert_spikes_to_rates'](signals.T, pca_n=3)
        rates, receipt = preprocess.source_rates(signals, self.backend)
        segment, our_pca = preprocess.project_segment(rates, [f'generated:{n}' for n in range(128)], 3)
        np.testing.assert_array_equal(graph['anchor'], segment['anchor'])
        np.testing.assert_array_equal(graph['vector'], segment['vector'])
        np.testing.assert_array_equal(author_pca.components_, our_pca.components_)
        self.assertEqual((graph['k'], graph['delta']), (15, 1.5))
        self.assertIsNone(labels)
        self.assertTrue(receipt['native_elephant_backend_used'])
        self.assertEqual(segment['omitted_terminal_anchor'], 'generated:127')

    def test_nonzero_magnitude_collapse_and_empty_channel(self):
        signals = np.zeros((128, 3), dtype=np.float32)
        signals[[0, 64, 127], 0] = [2, -0.5, 4.25]
        signals[[0, 64, 127], 1] = 1
        rates, receipt = preprocess.source_rates(signals, self.backend)
        np.testing.assert_array_equal(rates[:, 0], rates[:, 1])
        np.testing.assert_array_equal(rates[:, 2], np.zeros(128))
        self.assertEqual(receipt['nonzero_events_per_neuron'], [3, 3, 0])
        self.assertEqual(receipt['negative_values'], 1)
        self.assertEqual(receipt['nonintegral_values'], 2)
        self.assertFalse(receipt['backend']['historical_paper_runtime_verified'])

    def test_impulse_gaussian_clock_units_and_boundary_loss(self):
        # Fixed generated 129-bin support keeps the interior kernel far enough
        # from both boundaries. This asserts the selected current backend's
        # uncorrected boundaries; it does not infer the paper's library version.
        signals = np.zeros((129, 3), dtype=np.float32)
        signals[64, 0] = signals[0, 1] = signals[128, 2] = 1
        rates, receipt = preprocess.source_rates(signals, self.backend)
        offsets = np.arange(-30, 31, dtype=np.float64)
        expected_hz = 1000 * np.exp(-0.5 * (offsets / 10)**2) / (10 * np.sqrt(2 * np.pi))
        np.testing.assert_allclose(rates[34:95, 0], expected_hz, rtol=1e-12, atol=1e-12)
        self.assertEqual(int(np.argmax(rates[:, 0])), 64)
        self.assertLess(float(rates[:, 1].sum()), float(rates[:, 0].sum()) * 0.6)
        self.assertLess(float(rates[:, 2].sum()), float(rates[:, 0].sum()) * 0.6)
        np.testing.assert_allclose(rates[:, 1], rates[::-1, 2], rtol=1e-12, atol=1e-12)
        self.assertEqual(receipt['backend']['sampling_period_ms'], 1.0)
        self.assertEqual(receipt['backend']['sigma_ms'], 10.0)

    def test_mismatched_declared_runtime_refused(self):
        wrong = {**self.versions, 'elephant': 'unverified-runtime'}
        with self.assertRaises(inputs.InputError):
            preprocess.ElephantBackend(wrong)


if __name__ == '__main__':
    unittest.main(verbosity=2)
