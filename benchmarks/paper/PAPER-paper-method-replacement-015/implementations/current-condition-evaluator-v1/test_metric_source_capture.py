"""Generated source-custody controls; no bank, reference or candidate files."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import evaluate as evaluator


@contextmanager
def metric_fixture():
    original = (HERE.parent / 'original-endpoint-metrics-v1' / 'metrics.py').read_bytes()
    if hashlib.sha256(original).hexdigest() != evaluator.METRICS_SHA256:
        raise AssertionError('fixture must use the unchanged scientific kernel')
    name = 'spinal_eligible_metric_kernel'
    previous = sys.modules.get(name)
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        folder = base / 'current-condition-evaluator-v1'
        folder.mkdir()
        path = base / 'original-endpoint-metrics-v1' / 'metrics.py'
        path.parent.mkdir()
        path.write_bytes(original)
        try:
            with patch.object(evaluator, 'HERE', folder):
                yield path, original
        finally:
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class MetricSourceCaptureTests(unittest.TestCase):
    def test_unchanged_kernel_retains_dataclass_and_generated_scores(self):
        with metric_fixture() as (path, original):
            module = evaluator.load_metrics()
            self.assertEqual(Path(module.__file__), path)
            self.assertEqual(module.Prediction.__module__, module.__name__)
            values = (0., 1., 2.)
            controls = {name: module.Prediction(values, 'hz' if name in module.RATE_METHODS else 'arbitrary')
                        for name in module.SOURCE_CONTROLS}
            result = module.score_neuron(target_hz=values, controls=controls,
                                         support=(True, True, True), sampling_rate_hz=30.)
            self.assertEqual(result['scored_bins'], 3)
            self.assertEqual(result['methods']['default_cascade']['correlation']['status'], 'defined')
            self.assertAlmostEqual(result['methods']['default_cascade']['correlation']['value'], 1.)
            self.assertEqual(result['methods']['default_cascade']['rate_diagnostics'],
                             {'normalized_l1': 0., 'signed_bias': 0., 'status': 'defined'})
            self.assertEqual(path.read_bytes(), original)

    def test_replacement_after_authentication_cannot_change_executed_source(self):
        for mode in ('in_place', 'pathname'):
            with self.subTest(mode=mode), metric_fixture() as (path, original):
                ordinary_digest = evaluator.digest
                def authenticated_then_replaced(body):
                    digest = ordinary_digest(body)
                    replacement = original + b'\nGENERATED_UNAUTHENTICATED_REPLACEMENT = True\n'
                    if mode == 'pathname':
                        sibling = path.with_name('replacement.py')
                        sibling.write_bytes(replacement)
                        sibling.replace(path)
                    else:
                        path.write_bytes(replacement)
                    return digest
                with patch.object(evaluator, 'digest', authenticated_then_replaced):
                    module = evaluator.load_metrics()
                self.assertNotEqual(path.read_bytes(), original)
                self.assertFalse(hasattr(module, 'GENERATED_UNAUTHENTICATED_REPLACEMENT'))

    def test_changed_kernel_fails_authentication_before_execution(self):
        with metric_fixture() as (path, original):
            path.write_bytes(original + b"\nraise RuntimeError('generated untrusted source must not execute')\n")
            with self.assertRaisesRegex(ValueError, 'unchanged scientific metric kernel'):
                evaluator.load_metrics()


if __name__ == '__main__':
    unittest.main()
