"""Generated scalar mean controls; no authentic traces or saved references."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _local_analysis():
    here = Path(__file__).resolve().parent
    transport = _load('_neural038_mean_precision_delivery', here / 'delivery_io.py')
    absent = object()
    previous = sys.modules.get('delivery_io', absent)
    sys.modules['delivery_io'] = transport
    try:
        return _load('_neural038_mean_precision_analysis', here / 'analysis_core.py')
    finally:
        if previous is absent:
            sys.modules.pop('delivery_io', None)
        else:
            sys.modules['delivery_io'] = previous


AFTER = _local_analysis()


class MeanPrecisionTests(unittest.TestCase):
    def test_finite_subnormal_means_preserved_at_task_reducer_sizes(self):
        tiny = float.fromhex('0x0.0000000000001p-1022')
        for count in (1, 3, 9, 10, 13, 108):
            with self.subTest(count=count):
                self.assertEqual(AFTER.mean([tiny] * count), tiny)
                self.assertEqual(AFTER.mean([-tiny] * count), -tiny)
        # The exact mean is 2/3 of the smallest subnormal, rounding to tiny.
        self.assertEqual(AFTER.mean([tiny] * 5 + [-tiny]), tiny)

    def test_ordinary_scale_unchanged(self):
        for values, expected in (([2., 5., 8.], 5.), ([-3., 0., 3.], 0.),
                                 ([1., 2., 3., 4.], 2.5)):
            with self.subTest(values=values):
                self.assertEqual(AFTER.mean(values), expected)

    def test_large_representable_mean_and_signed_cancellation(self):
        maximum = sys.float_info.max
        self.assertEqual(AFTER.mean([maximum, maximum]), maximum)
        self.assertEqual(AFTER.mean([maximum, -maximum, 3.]), 1.)

    def test_original_macro_uses_repaired_mean_revision_stays_separate(self):
        tiny = float.fromhex('0x0.0000000000001p-1022')
        blocks = {name: {'means': {'context_interaction': tiny}}
                  for name in AFTER.BLOCKS}
        blocks['revision_pool']['means']['context_interaction'] = 2 * tiny
        actual = AFTER.summarize_blocks(blocks)
        self.assertEqual(actual['original_macro_interaction'], tiny)
        self.assertEqual(actual['revision_mean_interaction'], 2 * tiny)

    def test_empty_and_nonfinite_means_remain_refused(self):
        for values in ([], [math.nan], [math.inf], [-math.inf]):
            with self.subTest(values=values):
                with self.assertRaises((ValueError, OverflowError)):
                    AFTER.mean(values)


if __name__ == '__main__':
    unittest.main()
