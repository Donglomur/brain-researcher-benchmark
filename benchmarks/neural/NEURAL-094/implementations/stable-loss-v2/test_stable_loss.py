"""Generated probability/scalar controls; no source data, fitting or model calls."""
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'regional-comparison/complete_regional/source'


def load(name, path, expected=None):
    raw = path.read_bytes()
    if expected is not None:
        assert hashlib.sha256(raw).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load('n094_old_score', PRIOR / 'numerics/score_adapter.py',
           '1794e1a74b598524593b6ff0a9820ff645c360ce880b7fcb706f04c8d6600ec3')
new = load('n094_stable_score', HERE / 'score_adapter.py')
core = load('n094_core', PRIOR / 'numerics/metric_core.py',
            '41da920bd4d1d7ba1932e2ba9b6e37bf85a119276cdeb771e2d5218c5445ed60')
arithmetic = load('n094_independent', PRIOR / 'regional_arithmetic.py',
                  '180c96be2f87dfc0f801fc444b3c9d57cf0486292b5e5327447e040aed0eb47c')


def pin(text):
    return hashlib.sha256(text.encode()).hexdigest()


def probability_pair():
    """Real three-class probabilities with finite cancelling log-loss effects."""
    small = math.nextafter(1.0, 0.0)
    a = math.exp(-2.0)
    left = np.asarray([[a, 1-a, 0], [small, 1-small, 0], [1, 0, 0]]
                      + [[1, 0, 0]] * 7, dtype=np.float64)
    right = np.asarray([[1, 0, 0], [1, 0, 0], [a, 1-a, 0]]
                       + [[1, 0, 0]] * 7, dtype=np.float64)
    return core.probabilities(left, np), core.probabilities(right, np)


def whole_records(effects):
    """Complete invented39-session/10-mouse scalar interface, no real identities."""
    roster, records = [], []
    views = ['candidate:' + a for a in old.ARMS] + ['trusted:' + r for r in old.REFERENCES] + ['analytic:uniform']
    for index in range(39):
        mouse_index = 0 if index < 3 else 1 + (index - 3) // 4
        descriptor = {'path': f'generated/{index}.json', 'bytes': 1, 'sha256': pin(str(index))}
        source = {'ordinal': index+1, 'session': f'generated-session-{index}',
                  'mouse': f'generated-mouse-{mouse_index}', 'session_token': pin(f'session-{index}'),
                  'query_tokens': [pin(f'{index}-{j}') for j in range(10)],
                  'query_source_rows': list(range(10)),
                  'public_manifests': {arm: dict(descriptor) for arm in old.ARMS},
                  'private_mapping': dict(descriptor)}
        roster.append(source)
        records.append({'schema': 'neural094-choice-session-score-v1',
                        'status': 'complete_paired_choice_session',
                        **{k: source[k] for k in ('ordinal', 'session', 'mouse', 'session_token')},
                        'candidate_sha256': pin('candidate'), 'reference_sha256': pin('reference'),
                        'query_rows': 10, 'case_removal_for_probability_or_performance': False,
                        'metrics': {key: {'natural_log_loss': core.extended(1.0),
                                         'multiclass_Brier_mean_sum3': 1.0, 'top1_accuracy': 0.0} for key in views},
                        'contrasts': {name: core.extended(effects[index]) for name in old.CONTRASTS}})
    return records, roster


class StableLossControls(unittest.TestCase):
    def test_real_probabilities_preserve_positive_and_negative_effect(self):
        left, right = probability_pair()
        y = np.zeros(10, dtype=np.int64)
        a, b = (old.trial_losses(p, y, np) for p in (left, right))
        expected = math.fsum(float(v) for v in a-b) / 10
        self.assertGreater(expected, 0.0)
        self.assertEqual(old.paired_effect(a, b, core, np)['value'], 0.0)
        self.assertEqual(new.paired_effect(a, b, core, np)['value'], expected)
        self.assertEqual(new.paired_effect(b, a, core, np)['value'], -expected)
        tokens = [pin(f'case-{i}') for i in range(10)]
        views = {name: {'tokens': tokens, 'probabilities': left if name == 'common_context' else right}
                 for name in arithmetic.REGIONAL_VIEWS}
        independent = arithmetic.paired_trial_metrics(tokens, y, views)['metrics']['contrasts'][
            'left_gain_over_common_context__natural_log_loss']
        arithmetic.assert_engineering_equivalent(new.paired_effect(a, b, core, np), independent)

    def test_trial_reordering_preserves_admitted_effect(self):
        left, right = probability_pair()
        y = np.zeros(10, dtype=np.int64)
        a, b = (old.trial_losses(p, y, np) for p in (left, right))
        expected = new.paired_effect(a, b, core, np)
        for order in (list(reversed(range(10))), [0, 2, 1] + list(range(3, 10))):
            self.assertEqual(new.paired_effect(a[order], b[order], core, np), expected)

    def test_nonfinite_and_zero_semantics(self):
        cases = [([math.inf], [0.0], 'positive_infinity'),
                 ([0.0], [math.inf], 'negative_infinity'),
                 ([math.inf], [math.inf], 'undefined'),
                 ([math.inf, 0.0], [0.0, math.inf], 'undefined'),
                 ([2.0, 0.0], [0.0, 2.0], 'finite')]
        for left, right, status in cases:
            with self.subTest(status=status, left=left):
                actual = new.paired_effect(np.array(left), np.array(right), core, np)
                self.assertEqual(actual, old.paired_effect(np.array(left), np.array(right), core, np))
                self.assertEqual(actual['status'], status)
        self.assertEqual(new._stable_mean([0.0, 0.0]), 0.0)
        with self.assertRaisesRegex(ValueError, 'Nonempty'):
            new._stable_mean([])

    def test_complete39_nested_mouse_mean_preserves_cancellation(self):
        tiny = 2.0**-53
        records, roster = whole_records([2.0, tiny, -2.0] + [0.0]*36)
        args = records, roster, pin('candidate'), pin('reference'), core
        result = new.aggregate_reports(*args)
        self.assertEqual(result['contrasts'][old.PRIMARY]['value'], (tiny/3)/10)
        self.assertEqual(result['required_sessions'], 39)
        self.assertEqual(result['required_mice'], 10)
        self.assertEqual(result['mouse_records'][0]['session_count'], 3)
        self.assertEqual(result['session_records'], records)
        with self.assertRaises(ValueError):
            new.aggregate_reports(records[:-1], roster, pin('candidate'), pin('reference'), core)

    def test_equal_mouse_mean_and_nonfinite_status(self):
        # Each mouse has a constant effect; their unequal session counts must
        # not make the final result a pooled-session mean.
        effects = [2.0]*3 + [2.0**-53]*4 + [-2.0]*4 + [0.0]*28
        records, roster = whole_records(effects)
        result = new.aggregate_reports(records, roster, pin('candidate'), pin('reference'), core)
        self.assertEqual(result['contrasts'][old.PRIMARY]['value'], 2.0**-53/10)
        for first, second, expected in ((math.inf, 0.0, 'positive_infinity'),
                                         (math.inf, -math.inf, 'undefined')):
            records, roster = whole_records([first]*3 + [second]*4 + [0.0]*32)
            result = new.aggregate_reports(records, roster, pin('candidate'), pin('reference'), core)
            self.assertEqual(result['contrasts'][old.PRIMARY]['status'], expected)

    def test_ordinary_effect_matches_existing_scorer(self):
        left = np.array([0.2, 0.7, 0.5])
        right = np.array([0.1, 0.3, 0.9])
        self.assertAlmostEqual(new.paired_effect(left, right, core, np)['value'],
                               old.paired_effect(left, right, core, np)['value'], places=15)


if __name__ == '__main__':
    print(f'Generated software controls only; Python {sys.version.split()[0]}, NumPy {np.__version__}; no native stack qualification.', flush=True)
    unittest.main(verbosity=2)
