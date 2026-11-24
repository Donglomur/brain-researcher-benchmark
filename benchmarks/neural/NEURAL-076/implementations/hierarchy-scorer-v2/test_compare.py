"""Generated paired-route controls; no neural data, model, or authentic target."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
for name in ('core', 'io_utils', 'artifacts', 'score', 'compare'):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
import artifacts
import compare
import core
import score


def public_fixture():
    people, counter = {}, 0
    for person in core.PEOPLE:
        people[person] = {}
        for phase, n in [('imagery', 500), ('perception', 1750)]:
            people[person][phase + '_ids'] = ['q%024x' % i for i in range(counter, counter + n)]
            counter += n
    return {'schema': core.VERSION, 'source_design_sha256': 'a' * 64, 'people': people,
            'unit_ids': {f: core.matched_indices(f, 1024 if f == 'gist' else 1000).tolist()
                         for f in core.FAMILIES}}


def submission_fixture():
    return {'schema': 'neural076_predictions_v1', 'source_design_sha256': 'a' * 64,
            'parts': [{'key': key, 'path': 'part%d.npz' % i}
                      for i, key in enumerate(artifacts.part_keys())]}


def gold_fixture():
    gold = {p + '_' + s: np.repeat(np.arange(50), n)
            for p in core.PEOPLE for s, n in [('imagery', 10), ('perception', 35)]}
    bank = np.broadcast_to(np.arange(50, dtype=float)[:, None], (50, 1000))
    gold.update({'bank_' + f: bank for f in core.FAMILIES})
    return gold


class PairedControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = public_fixture()
        cls.submission = submission_fixture()

    def run_panel(self, undefined=False, changed=None, malformed=None):
        keys = artifacts.part_keys()
        events = []
        held_gold = gold_fixture()

        def reader(path, ids, units, expected_sha=None):
            condition = path.parent.name
            index = int(path.stem[4:])
            person, roi, family = keys[index].split('/')
            self.assertEqual(ids, self.public['people'][person]['imagery_ids'] +
                             self.public['people'][person]['perception_ids'])
            self.assertEqual(units, self.public['unit_ids'][family])
            phase = 'preflight' if expected_sha is None else 'score'
            events.append((phase, condition, index))
            sha = hashlib.sha256((condition + keys[index]).encode()).hexdigest()
            if malformed == (condition, index) and expected_sha is None:
                raise ValueError('late malformed generated block')
            if expected_sha is not None:
                self.assertEqual(expected_sha, sha)
                if changed == (condition, index):
                    raise ValueError('Submission changed after complete public validation')
            # Encoded scalar r for orchestration only; actual numerical control below.
            value = 0.
            if condition == 'first' and roi == 'HVC' and family == 'cnn7':
                value = [.8, .4, 0., -.4, -.8][core.PEOPLE.index(person)]
            if condition == 'second' and roi == 'HVC' and family == 'cnn1':
                value = .2
            if undefined and condition == 'second' and (person, roi, family) == ('Subject5', 'HVC', 'cnn1'):
                value = 9.  # sentinel converted to a real null diagnostic
            return np.broadcast_to(np.array(value), (2250, 1000)), sha

        def target():
            self.assertEqual(events, [('preflight', c, i) for c in ('first', 'second') for i in range(650)])
            events.append(('target', None, None))
            return held_gold

        def numerical(predictions, labels, bank, repeats):
            self.assertEqual(predictions.shape, (500 if repeats == 10 else 1750, 1000))
            self.assertEqual(labels.shape, (len(predictions),))
            self.assertTrue(any(bank is held_gold['bank_' + f] for f in core.FAMILIES))
            value = float(predictions[0, 0])
            missing = value == 9.
            return {'mean_r': None if missing else value, 'defined_units': 999 if missing else 1000,
                    'constant_prediction_unit_positions': [3] if missing else [],
                    'constant_target_unit_positions': [], 'unit_count': 1000}

        with patch.object(compare, 'load', side_effect=reader), \
             patch.object(compare, 'feature_score', side_effect=numerical):
            result = compare.assess_pair(self.submission, self.submission, self.public,
                                         'first', 'second', target)
        return result, events

    def test_both_full_panels_precede_one_target_and_preserve_paired_effects(self):
        result, events = self.run_panel()
        self.assertEqual(result['status'], 'scored')
        self.assertEqual(result['target_loader_calls'], 1)
        self.assertEqual(events, [('preflight', c, i) for c in ('first', 'second') for i in range(650)] +
                         [('target', None, None)] +
                         [('score', c, i) for c in ('first', 'second') for i in range(650)])
        self.assertEqual(result['coverage_per_condition']['phase_cells'], 1300)
        actual = list(result['primary_difference']['per_person'].values())
        np.testing.assert_allclose(actual, [1., .6, .2, -.2, -.6], atol=1e-14)
        self.assertAlmostEqual(result['primary_difference']['mean'], .2)
        self.assertAlmostEqual(result['conditions']['first']['primary']['mean'], 0.)
        self.assertAlmostEqual(result['conditions']['second']['primary']['mean'], -.2)
        self.assertAlmostEqual(result['signed_contrast_differences'][
            'imagery_legacy_cnn5to8_minus_cnn1to4_HVC_minus_LVC']['mean'], .05)
        self.assertEqual(result['primary_difference']['independent_participants'], 5)
        self.assertEqual(len(result['conditions']['first']['cell_diagnostics']), 1300)
        self.assertEqual(len(result['conditions']['second']['ordered_prediction_sha256']), 650)
        self.assertEqual(result['per_person_cell_differences']['Subject5']['imagery']['HVC']['cnn7'], -.8)
        json.dumps(result, allow_nan=False)

    def test_undefined_second_condition_propagates_without_dropping_person(self):
        result, _ = self.run_panel(undefined=True)
        self.assertEqual(result['status'], 'complete_with_undefined_correlations')
        self.assertIsNone(result['primary_difference']['mean'])
        self.assertIsNone(result['primary_difference']['per_person']['Subject5'])
        self.assertEqual(result['primary_difference']['undefined_participants'], ['Subject5'])
        self.assertIsNone(result['per_person_cell_differences']['Subject5']['imagery']['HVC']['cnn1'])
        self.assertEqual(result['conditions']['second']['undefined_phase_cells'], 2)
        self.assertIsNone(result['absolute_imagery_companion_difference']['mean'])

    def test_missing_or_wrong_source_second_collection_never_loads_targets(self):
        for fault in ('missing', 'source'):
            bad = copy.deepcopy(self.submission)
            if fault == 'missing':
                bad['parts'].pop()
            else:
                bad['source_design_sha256'] = 'b' * 64
            with patch.object(compare, 'load', return_value=(None, 'c' * 64)) as reader:
                result = compare.assess_pair(self.submission, bad, self.public, 'first', 'second',
                                             lambda: self.fail('target read'))
            self.assertEqual(reader.call_count, 650)
            self.assertEqual(result['target_loader_calls'], 0)
            self.assertEqual(result['failed_condition'], 'second')
            self.assertIsNone(result['primary_difference'])

    def test_late_second_malformed_block_precedes_targets(self):
        result, events = self.run_panel(malformed=('second', 649))
        self.assertEqual(len(events), 1300)
        self.assertEqual(result['target_loader_calls'], 0)
        self.assertEqual(result['status'], 'invalid_submission')

    def test_substitution_in_either_scoring_pass_cannot_emit_partial_comparison(self):
        for condition in ('first', 'second'):
            result, _ = self.run_panel(changed=(condition, 649))
            self.assertEqual(result['status'], 'invalid_submission')
            self.assertEqual(result['target_loader_calls'], 1)
            self.assertEqual(result['failed_condition'], condition)
            self.assertIsNone(result['primary_difference'])
            self.assertNotIn('conditions', result)

    def test_bad_private_packet_fails_after_both_complete_preflights(self):
        with patch.object(compare, 'load', return_value=(None, 'b' * 64)) as reader:
            result = compare.assess_pair(self.submission, self.submission, self.public,
                                         'first', 'second', lambda: {})
        self.assertEqual(reader.call_count, 1300)
        self.assertEqual(result['status'], 'operator_error')
        self.assertEqual(result['target_loader_calls'], 1)

    def test_real_category_correlation_preserves_negative_and_null_differences(self):
        gold = gold_fixture()
        labels, bank = gold['Subject1_imagery'], gold['bank_cnn1']
        first = core.feature_score(bank[labels], labels, bank, 10)['mean_r']
        second = core.feature_score(-bank[labels], labels, bank, 10)['mean_r']
        self.assertAlmostEqual(compare.difference(first, second), 2.)
        self.assertAlmostEqual(compare.difference(second, first), -2.)
        undefined = core.feature_score(np.zeros((500, 1000)), labels, bank, 10)['mean_r']
        self.assertIsNone(compare.difference(first, undefined))

    def test_cli_failure_retains_identity_and_refuses_report_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'report.json'
            argv = ['compare.py', '--public', 'public.json', '--operator', 'operator.json',
                    '--first', 'first/submission.json', '--second', 'second/submission.json', '--out', str(out)]
            with patch.object(sys, 'argv', argv), \
                 patch.object(compare, 'read_json', side_effect=[{}, self.submission, ValueError('bad second JSON')]), \
                 patch.object(compare, 'authenticated_public', return_value=self.public), \
                 patch.object(compare, 'load_gold') as targets:
                self.assertEqual(compare.main(), 1)
                targets.assert_not_called()
            result = json.loads(out.read_text())
            self.assertEqual(result['failed_condition'], 'second')
            with patch.object(sys, 'argv', argv), patch.object(compare, 'read_json', side_effect=ValueError('bad operator')):
                with self.assertRaises(FileExistsError):
                    compare.main()
            self.assertEqual(json.loads(out.read_text()), result)


if __name__ == '__main__':
    print('Generated-only paired controls; Python', sys.version.split()[0], 'NumPy', np.__version__)
    unittest.main(verbosity=2)
