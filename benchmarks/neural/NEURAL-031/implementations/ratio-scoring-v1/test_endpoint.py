"""Generated full-size software controls. No authentic observations or model runs."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import endpoint as ep
import score as cli


def fixture():
    """Unequal mouse support makes pooling spines produce the wrong answer."""
    support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
               'folds': [], 'request_rows': 774, 'query_targets_included': False}
    bundle = {'schema': 'neural031_ordinary_submission_bundle_v1', 'candidate_id': 'NEURAL-031', 'outputs': []}
    target = {'schema': 'neural031_ratio_targets_v1', 'candidate_id': 'NEURAL-031', 'mice': list(ep.MICE), 'rows': []}
    for fold in range(20):
        count, missing = (90, 24) if fold == 0 else (36, 1)
        rowids = list(range(len(target['rows']), len(target['rows']) + count))
        views = {view: {kind: {'bytes': 1, 'sha256': hashlib.sha256(f'{fold}/{view}/{kind}'.encode()).hexdigest()}
                        for kind in ('data', 'manifest')} for view in ep.VIEWS}
        support['folds'].append({'fold': fold, 'rowids': rowids, 'views': views})
        value = 2.0 + fold / 10
        for index, rowid in enumerate(rowids):
            observed = int(index >= missing)
            target['rows'].append({'rowid': rowid, 'mouse': fold, 'request': 1, 'observed': observed,
                                   'y': value if observed else None, 'baseline_new': index % 2,
                                   'compartment': int(index % 3 == 0)})
        for view in ep.VIEWS:
            bundle['outputs'].append({'schema': 'neural031_ordinary_prediction_v1', 'candidate_id': 'NEURAL-031',
                'fold': fold, 'view': view, 'input_manifest': views[view]['manifest'],
                'rows': [{'row_id': rowid, 'prediction': value + (fold + 1 if view == 'baseline' else .5)}
                         for rowid in rowids]})
    for rowid in range(774, 1143):
        target['rows'].append({'rowid': rowid, 'mouse': rowid % 20, 'request': 0, 'observed': 0,
                              'y': None, 'baseline_new': 0, 'compartment': 0})
    return support, bundle, target


def flag(*labels):
    return {'kind': 'list', 'value': list(labels)}


class EndpointTests(unittest.TestCase):
    def test_ratio_and_distinct_request_and_target_eligibility(self):
        result = ep.eligibility(2.0, 3.0, flag('New Spine'), flag())
        self.assertTrue(result['request'] and result['observed'] and result['baseline_new'])
        self.assertEqual(result['y'], 1.5)
        for label in ep.LABELS:
            result = ep.eligibility(2., 3., flag(), flag(label))
            self.assertTrue(result['request'])
            self.assertFalse(result['observed'])
            self.assertIsNone(result['y'])
        self.assertEqual(ep.eligibility(2., 0., flag(), flag())['y'], 0.)

    def test_nonexclusive_reasons_and_no_epsilon_or_imputation(self):
        result = ep.eligibility(0., 3., flag('Absent', 'Shaft Spine'), flag())
        self.assertEqual(set(result['baseline_reasons']), {'baseline_absent', 'baseline_shaft_spine', 'baseline_not_positive'})
        self.assertFalse(result['request'])
        self.assertIsNone(result['y'])
        for later in (-1., math.inf, math.nan):
            self.assertFalse(ep.eligibility(2., later, flag(), flag())['observed'])
        self.assertIn('ratio_nonfinite', ep.eligibility(1e-308, 1e308, flag(), flag())['target_reasons'])

    def test_source_flag_representation_not_silently_changed(self):
        self.assertTrue(ep.flag_membership({'kind': 'str', 'value': 'prefix Absent suffix'})['Absent'])
        self.assertFalse(ep.flag_membership(flag('prefix Absent suffix'))['Absent'])
        with self.assertRaises(ValueError):
            ep.flag_membership({'kind': 'list', 'value': 'Absent'})

    def test_full_panel_equal_mouse_not_pooled_spine_estimator(self):
        support, bundle, targets = fixture()
        result = ep.score(support, bundle, targets)
        self.assertEqual((result['raw_rows'], result['request_rows'], result['scored_rows'], result['unavailable_rows']),
                         (1143, 774, 731, 43))
        self.assertAlmostEqual(result['macro']['baseline_mae'], 10.5)
        self.assertAlmostEqual(result['macro']['neural_mae'], .5)
        self.assertAlmostEqual(result['primary'], 10.)
        pooled = (66 + sum(35 * (fold + 1) for fold in range(1, 20))) / 731
        self.assertNotAlmostEqual(result['macro']['baseline_mae'], pooled)
        self.assertEqual(result['positive_mouse_differences'], 20)
        self.assertEqual(len(result['mice']), 20)
        for row in result['mice']:
            self.assertEqual(sum(s['scored_rows'] for s in row['strata'] if s['field'] == 'compartment'), row['scored_rows'])
        self.assertAlmostEqual(result['macro']['no_change_mae'], 1.95)

    def test_training_median_excludes_query_mouse_and_equalizes_mice(self):
        result = ep.score(*fixture())
        for fold, row in enumerate(result['mice']):
            other_values = sorted(2 + other / 10 for other in range(20) if other != fold)
            expected = abs(other_values[9] - (2 + fold / 10))
            self.assertAlmostEqual(row['training_median_mae'], expected)
        rows = [{'mouse': 0, 'y': 1.}] + [{'mouse': 1, 'y': 7.}] * 40
        self.assertEqual(ep.balanced_median(rows), 1.)

    def test_constant_outputs_are_valid_and_do_not_claim_gain(self):
        support, bundle, targets = fixture()
        for output in bundle['outputs']:
            for row in output['rows']:
                row['prediction'] = 1.
        result = ep.score(support, bundle, targets)
        self.assertEqual(result['primary'], 0.)
        self.assertAlmostEqual(result['macro']['baseline_mae'], result['macro']['no_change_mae'])

    def test_all_missing_target_requests_still_require_predictions(self):
        support, bundle, targets = fixture()
        del bundle['outputs'][0]['rows'][0]  # This row has an unavailable target.
        with self.assertRaises(ValueError):
            ep.score(support, bundle, targets)

    def test_duplicate_reordered_cross_mouse_and_manifest_ids_fail(self):
        for mutation in ('duplicate', 'reorder', 'cross_mouse', 'manifest'):
            support, bundle, targets = fixture()
            if mutation == 'duplicate':
                bundle['outputs'][0]['rows'][1]['row_id'] = bundle['outputs'][0]['rows'][0]['row_id']
            elif mutation == 'reorder':
                bundle['outputs'][0]['rows'].reverse()
            elif mutation == 'cross_mouse':
                support['folds'][1]['rowids'][0] = support['folds'][0]['rowids'][0]
            else:
                bundle['outputs'][0]['input_manifest'] = support['folds'][0]['views']['neural']['manifest']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                ep.score(support, bundle, targets)

    def test_invalid_predictions_and_boolean_identity_fail(self):
        for value in (True, -1., math.inf, math.nan, '1', 10**400):
            support, bundle, targets = fixture()
            bundle['outputs'][0]['rows'][0]['prediction'] = value
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                ep.score(support, bundle, targets)
        support, bundle, targets = fixture()
        bundle['outputs'][0]['rows'][0]['row_id'] = False
        with self.assertRaises(ValueError):
            ep.score(support, bundle, targets)

    def test_partial_panel_and_invalid_target_support_fail(self):
        for mutation in ('mouse_name', 'no_targets_mouse', 'missing_row', 'extra_target', 'null_observed', 'changed_mouse'):
            support, bundle, targets = fixture()
            if mutation == 'mouse_name':
                targets['mice'][0] = 'invented'
            elif mutation == 'no_targets_mouse':
                for row in targets['rows']:
                    if row['mouse'] == 1:
                        row.update(observed=0, y=None)
            elif mutation == 'missing_row':
                targets['rows'].pop()
            elif mutation == 'extra_target':
                targets['rows'][0].update(observed=1, y=0.)
            elif mutation == 'null_observed':
                targets['rows'][24]['y'] = None
            else:
                targets['rows'][24]['mouse'] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                ep.score(support, bundle, targets)

    def test_near_max_finite_scores_do_not_overflow(self):
        self.assertEqual(ep.mean([1e308] * 100), 1e308)
        self.assertEqual(ep.mean([1e308, -1e308]), 0.)

    def test_private_open_barrier_and_exact_hash(self):
        support, bundle, targets = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in (('support', support), ('submission', bundle), ('targets', targets)):
                (root / name).write_text(json.dumps(value))
            target_hash = hashlib.sha256((root / 'targets').read_bytes()).hexdigest()
            result = cli.run(root / 'support', root / 'submission', root / 'targets', target_hash)
            self.assertAlmostEqual(result['primary'], 10.)
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                cli.run(root / 'support', root / 'submission', root / 'targets', '0' * 64)
            bundle['outputs'].pop()  # Final output missing must fail before target access.
            (root / 'submission').write_text(json.dumps(bundle))
            original = cli.read_json
            reads = []
            def observed_read(path, *args):
                reads.append(Path(path).name)
                return original(path, *args)
            with patch.object(cli, 'read_json', observed_read), self.assertRaises(ValueError):
                cli.run(root / 'support', root / 'submission', root / 'targets', target_hash)
            self.assertEqual(reads, ['support', 'submission'])

    def test_json_duplicate_keys_and_nonstandard_numbers_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for text in ('{"x": 1, "x": 2}', '{"x": NaN}', '{"x": Infinity}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    cli.read_json(path, 100)
            path.write_text('{"x": 1}')
            with self.assertRaisesRegex(ValueError, 'byte cap'):
                cli.read_json(path, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
