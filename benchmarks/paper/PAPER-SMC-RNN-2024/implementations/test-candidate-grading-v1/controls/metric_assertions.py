"""Generated four-metric assertions; never a scorer or numerical evaluator.

The parent explicitly maps its selected report fields to canonical metric keys.
Binary-exact fixture values include increases, decreases, ties and negative
metrics. They imply no gain invariance or real scientific improvement.
"""

METRIC_KEYS = ('co-bps', 'vel R2', 'psth R2', 'fp-bps')
DATASET_RESULT_KEY = 'mc_maze_20_split'
CANONICAL_EVALUATOR = {
    'bytes': 18292,
    'sha256': '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476',
}


def canonical_case():
    """Return fresh canonical result payloads and independent static deltas."""
    reference = {'co-bps': 0.125, 'vel R2': -0.25, 'psth R2': 0.5, 'fp-bps': -0.125}
    candidate = {'co-bps': 0.25, 'vel R2': -0.5, 'psth R2': 0.75, 'fp-bps': -0.125}
    delta = {'co-bps': 0.125, 'vel R2': -0.25, 'psth R2': 0.25, 'fp-bps': 0.0}
    return {
        'reference': [{DATASET_RESULT_KEY: reference}],
        'candidate': [{DATASET_RESULT_KEY: candidate}],
        'delta': delta,
    }


def assert_vectors(testcase, observed_reference, observed_candidate, observed_delta):
    """Assert the generated case after the caller explicitly maps report fields.

    Each argument is a dict keyed by the four canonical metric names, not an
    entire production report or canonical result list. This function performs
    no schema inference, data loading, metric calculation or callback execution.
    Exact equality is intentional for these binary-exact generated scalars.
    Negative R2 and bits-per-spike values are allowed; booleans are not numbers
    for this contract. No assertion treats an unchanged metric as a gain law.
    """
    import math

    case = canonical_case()
    expected_reference = case['reference'][0][DATASET_RESULT_KEY]
    expected_candidate = case['candidate'][0][DATASET_RESULT_KEY]
    for role, observed, expected in (
        ('reference', observed_reference, expected_reference),
        ('candidate', observed_candidate, expected_candidate),
        ('candidate_minus_reference', observed_delta, case['delta']),
    ):
        testcase.assertIs(type(observed), dict, role)
        testcase.assertEqual(set(observed), set(METRIC_KEYS), role)
        for key in METRIC_KEYS:
            value = observed[key]
            testcase.assertIn(type(value), (int, float), role + ':' + key)
            testcase.assertTrue(math.isfinite(value), role + ':' + key)
            testcase.assertEqual(value, expected[key], role + ':' + key)
    for key in METRIC_KEYS:
        testcase.assertEqual(observed_delta[key], observed_candidate[key] - observed_reference[key], key)
    return {'canonical_metric_keys': list(METRIC_KEYS),
            'delta_direction': 'candidate_minus_reference',
            'negative_metrics_allowed': True,
            'generated_fixture_only': True,
            'gain_invariance_claimed': False}
