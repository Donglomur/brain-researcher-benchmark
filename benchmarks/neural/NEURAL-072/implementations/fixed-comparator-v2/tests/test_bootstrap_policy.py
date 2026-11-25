"""Generated complete-panel controls for the declared empty-draw policy."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

e = load('neural072_bootstrap_policy_scorer', ROOT / 'evaluator.py')
fixtures = load('neural072_bootstrap_policy_fixture',
                ROOT.parent / 'initial-evaluator-v1/tests/test_evaluator.py')

def seed_for(requested, empty):
    # Independent incidence oracle for the two diagonal listener/family cells.
    for seed in range(256):
        rng = e.legacy.np.random.default_rng(seed)
        actual = 0
        for _ in range(requested):
            listeners = rng.multinomial(2, [0.5, 0.5])
            families = rng.multinomial(2, [0.5, 0.5])
            actual += int(listeners[0] * families[0] + listeners[1] * families[1] == 0)
        if actual == empty:
            return seed
    raise AssertionError('generated bootstrap witness not found')


def inputs(requested, empty):
    protocol, cases, features, train, targets = fixtures.fixture()
    removed = {'s1_4', 's2_3'}
    cases['runs'] = [run for run in cases['runs'] if run['id'] not in removed]
    features = {key: value for key, value in features.items() if key not in removed}
    targets = {key: value for key, value in targets.items() if key not in removed}
    protocol['cases_sha256'] = e.legacy.digest(cases)
    protocol['bootstrap_replicates'] = requested
    protocol['seed'] = seed_for(requested, empty)
    e.legacy.validate(protocol, cases)
    reference = e.freeze_reference(protocol, cases, features, train)
    raw = e.encode(reference)
    expected = e.sha256(raw)
    candidate = {'schema': e.CANDIDATE_SCHEMA, 'task_id': 'NEURAL-072',
                 'protocol_sha256': e.legacy.digest(protocol),
                 'cases_sha256': e.legacy.digest(cases),
                 'contextual': {key: copy.deepcopy(value['lexical'])
                                for key, value in reference['predictions'].items()}}
    return protocol, cases, targets, candidate, raw, expected


class BootstrapPolicyControls(unittest.TestCase):
    def test_current_score_rejects_more_than_ten_percent_empty_draws(self):
        protocol, cases, targets, candidate, raw, expected = inputs(3, 1)
        reference = e.authenticated_reference(protocol, cases, raw, expected)
        joined = e.joined_prediction(protocol, cases, reference, candidate)
        historical = e.legacy.score(protocol, cases, targets, joined)
        self.assertEqual(historical['uncertainty']['requested'], 3)
        self.assertEqual(historical['uncertainty']['empty'], 1)
        with self.assertRaisesRegex(e.ContractError, 'too many empty crossed-cluster'):
            e.score(protocol, cases, targets, candidate, raw, expected)

    def test_exact_ten_percent_boundary_preserves_original_scores(self):
        protocol, cases, targets, candidate, raw, expected = inputs(10, 1)
        reference = e.authenticated_reference(protocol, cases, raw, expected)
        joined = e.joined_prediction(protocol, cases, reference, candidate)
        historical = e.legacy.score(protocol, cases, targets, joined)
        current = e.score(protocol, cases, targets, candidate, raw, expected)
        self.assertEqual(current['uncertainty']['empty'], 1)
        self.assertEqual(current['uncertainty']['requested'], 10)
        for key in ('uncertainty', 'listener_macro_contrasts', 'by_listener',
                    'by_story_family', 'temporal_null', 'counts'):
            self.assertEqual(current[key], historical[key])
        self.assertEqual(current['counts']['runs'], 2)

    def test_zero_empty_draws_and_current_pair_pin_preserve_complete_support(self):
        protocol, cases, targets, candidate, raw, expected = inputs(3, 0)
        report = e.score(protocol, cases, targets, candidate, raw, expected)
        self.assertEqual(report['uncertainty']['empty'], 0)
        self.assertEqual(report['counts']['runs'], 2)
        pair = load('neural072_bootstrap_policy_pair',
                    ROOT.parent / 'paired-comparison-v1/compare.py')
        paired = pair.compare(protocol, cases, targets, candidate, copy.deepcopy(candidate), raw, expected)
        self.assertEqual(paired['paired_listener_macro_delta_r2'], 0.)
        self.assertEqual(paired['paired_uncertainty']['intervals_95'][pair.DELTA], [0., 0.])
        self.assertEqual(paired['counts']['runs'], 2)

if __name__ == '__main__':
    unittest.main()
