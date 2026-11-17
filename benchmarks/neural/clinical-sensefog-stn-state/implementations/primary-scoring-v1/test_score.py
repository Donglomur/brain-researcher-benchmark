"""Generated software controls only; no clinical data or native libraries."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sensefog_score', HERE / 'sensefog_score.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture():
    people = ['person_%02d' % k for k in range(12)]
    grid = {'schema': 'sensefog_target_free_pairing_input_v2', 'task': mod.TASK,
            'participants': people, 'folds': [], 'recordings': [], 'segments': []}
    for i, person in enumerate(people):
        grid['folds'].append({'heldout_person': person,
                             'training_people': [p for p in people if p != person],
                             'lookback_samples_by_rate': {'1': 2},
                             'dependence_samples_by_rate': {'1': 10},
                             'method_receipt_sha256': 'a' * 64})
        stride = 50 if i == 0 else 100
        rid = 'recording_%02d' % i
        grid['recordings'].append({'recording_id': rid, 'participant': person,
                                   'day_id': 'day_1', 'session_id': 'session_%02d' % i,
                                   'sample_rate_hz': 1, 'sample_count': 1000,
                                   'window_stride_samples': stride, 'window_origin_sample': 0,
                                   'cases': [{'case_id': rid + '_case_%d' % start, 'start_sample': start}
                                             for start in range(0, 999, stride)]})
        grid['segments'].append({'segment_id': 'segment_%02d' % i, 'recording_id': rid,
                                 'acquisition_stratum': 'generated_constant', 'recording_start_sample': 0,
                                 'sample_count': 1000, 'channels': ['left', 'right'],
                                 'masks': {c: [[0, 1000, False, False]] for c in ['left', 'right']}})
    policy = {'schema': 'sensefog_score_policy_v1', 'task': mod.TASK,
              'classes': ['walking', 'freezing', 'voluntary_stop'],
              'finite_probability_floor': 1e-8, 'bootstrap_replicates': 200, 'bootstrap_seed': 12}
    targets = {'schema': 'sensefog_protected_targets_v1', 'task': mod.TASK,
               'grid_sha256': mod.canonical_sha256(grid), 'label_protocol_sha256': 'b' * 64, 'rows': []}
    predictions = {'schema': 'sensefog_predictions_v1', 'task': mod.TASK,
                   'grid_sha256': mod.canonical_sha256(grid), 'policy_sha256': mod.canonical_sha256(policy), 'rows': []}
    for i, rec in enumerate(grid['recordings']):
        for j, case in enumerate(rec['cases']):
            true_index = j % 3
            targets['rows'].append({'case_id': case['case_id'], 'participant': rec['participant'],
                                    'status': 'evaluable', 'label': policy['classes'][true_index]})
            p = .1 if i == 0 else .9
            probabilities = [(1-p)/2] * 3
            probabilities[true_index] = p
            predictions['rows'].append({'case_id': case['case_id'], 'probabilities': probabilities})
    return grid, policy, targets, predictions


def rebind(grid, policy, targets, predictions):
    targets['grid_sha256'] = predictions['grid_sha256'] = mod.canonical_sha256(grid)
    predictions['policy_sha256'] = mod.canonical_sha256(policy)


def paired_fixture(grid, policy, targets, predictions):
    labels = {r['case_id']: r for r in targets['rows']}
    paired = {'schema': 'sensefog_paired_predictions_v1', 'task': mod.TASK,
              'grid_sha256': mod.canonical_sha256(grid), 'policy_sha256': mod.canonical_sha256(policy), 'rows': []}
    for row in mod._mapper.build_maps(grid, max_cases=200)['maps']:
        if row['status'] != 'supported':
            continue
        target = labels[row['case_id']]
        true_index = 0 if target['label'] is None else policy['classes'].index(target['label'])
        p = .2 if target['participant'] == grid['participants'][0] else .8
        probabilities = [(1-p)/2] * 3
        probabilities[true_index] = p
        paired['rows'].append({'case_id': row['case_id'], 'multiple': row['multiple'],
                               'probabilities': probabilities})
    return paired


class ScoringControls(unittest.TestCase):
    def evaluate(self, docs, paired=None):
        return mod.score(*docs, max_cases=200, paired_predictions=paired)

    def test_primary_is_equal_person_not_pooled_or_class_balanced(self):
        docs = fixture()
        report = self.evaluate(docs)
        expected = (-math.log(.1) - 11 * math.log(.9)) / 12
        pooled = (-20 * math.log(.1) - 110 * math.log(.9)) / 130
        self.assertAlmostEqual(report['primary']['score'], expected)
        self.assertNotAlmostEqual(report['primary']['score'], pooled)
        self.assertEqual(report['original_case_count'], 130)
        self.assertEqual(len(report['primary']['participant_folds']), 12)
        self.assertEqual(report['primary']['participant_folds'][0]['class_counts'],
                         {'walking': 7, 'freezing': 7, 'voluntary_stop': 6})
        self.assertEqual(report['primary']['participant_folds'][0]['evaluable_cases'], 20)
        self.assertEqual(report['primary']['units'], 'nats')

    def test_unknown_targets_stay_in_census_and_undefined_full_cohort(self):
        docs = fixture()
        for row in docs[2]['rows']:
            if row['participant'] == 'person_11':
                row.update(status='ambiguous', label=None)
        report = self.evaluate(docs)
        self.assertIsNone(report['primary']['score'])
        self.assertEqual(report['primary']['participants_without_evaluable_windows'], ['person_11'])
        self.assertEqual(report['original_case_count'], 130)
        self.assertEqual(report['primary']['participant_folds'][-1]['status_counts'], {'ambiguous': 10})
        self.assertIsNone(report['primary']['participant_cluster_percentile_interval_95']['lower'])

    def test_all_unknown_has_no_invented_score_or_paired_support(self):
        docs = fixture()
        for row in docs[2]['rows']:
            row.update(status='missing_annotation', label=None)
        paired = paired_fixture(*docs)
        report = self.evaluate(docs, paired)
        self.assertIsNone(report['primary']['score'])
        self.assertEqual(report['paired_diagnostics']['evaluable_transform_count'], 0)
        self.assertEqual(report['paired_diagnostics']['distinct_map_supported_transform_count'], 20)
        self.assertIsNone(report['paired_diagnostics']['equal_transform_mean_delta_nats'])
        self.assertTrue(all(len(t['participants_without_paired_support']) == 12
                            for t in report['paired_diagnostics']['transforms']))

    def test_finite_probability_rule_floors_then_renormalizes_all_classes(self):
        self.assertAlmostEqual(mod.probability_loss([0, 1, 0], 0, 3, .01), math.log(1.02) - math.log(.01))
        self.assertAlmostEqual(mod.probability_loss([0, 1, 0], 1, 3, .01), math.log(1.02))
        self.assertTrue(math.isfinite(mod.probability_loss([0, 1, 0], 0, 3, 5e-324)))

    def test_invalid_probabilities_fail_even_on_unknown_target(self):
        for p in ([True, 0, 0], [float('nan'), 0, 1], [float('inf'), 0, 0],
                  [-.1, .5, .6], [1.1, 0, 0], [.1, .2, .3], [.5, .5], [0, 0, 0]):
            docs = fixture()
            docs[2]['rows'][0].update(status='ambiguous', label=None)
            docs[3]['rows'][0]['probabilities'] = p
            with self.subTest(p=p), self.assertRaises(ValueError):
                self.evaluate(docs)

    def test_missing_duplicate_unknown_predictions_rejected(self):
        for kind in ('missing', 'duplicate', 'unknown'):
            docs = fixture()
            if kind == 'missing':
                docs[3]['rows'].pop()
            elif kind == 'duplicate':
                docs[3]['rows'][-1] = copy.deepcopy(docs[3]['rows'][0])
            else:
                docs[3]['rows'][0]['case_id'] = 'alien'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.evaluate(docs)

    def test_label_census_group_and_class_failures_rejected(self):
        for kind in ('missing', 'duplicate', 'person', 'class', 'unknown_nonnull', 'evaluable_null'):
            docs = fixture()
            if kind == 'missing': docs[2]['rows'].pop()
            if kind == 'duplicate': docs[2]['rows'][-1] = copy.deepcopy(docs[2]['rows'][0])
            if kind == 'person': docs[2]['rows'][0]['participant'] = 'person_01'
            if kind == 'class': docs[2]['rows'][0]['label'] = 'invented_new_state'
            if kind == 'unknown_nonnull': docs[2]['rows'][0]['status'] = 'ambiguous'
            if kind == 'evaluable_null': docs[2]['rows'][0]['label'] = None
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.evaluate(docs)

    def test_submissions_bind_exact_grid_and_class_order_policy(self):
        for name in ('grid_sha256', 'policy_sha256'):
            docs = fixture()
            docs[3][name] = 'f' * 64
            with self.subTest(name=name), self.assertRaises(ValueError): self.evaluate(docs)
        docs = fixture()
        docs[1]['classes'].reverse()
        with self.assertRaises(ValueError): self.evaluate(docs)

    def test_full_recording_grid_and_fold_rules_reused(self):
        for kind in ('drop_case', 'drop_person', 'train_leak', 'cap'):
            docs = fixture()
            if kind == 'drop_case': docs[0]['recordings'][0]['cases'].pop()
            if kind == 'drop_person': docs[0]['participants'].pop()
            if kind == 'train_leak': docs[0]['folds'][0]['training_people'][0] = 'person_00'
            rebind(*docs)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                mod.score(*docs, max_cases=129 if kind == 'cap' else 200)

    def test_paired_delta_uses_same_cases_then_equal_people_then_equal_lags(self):
        docs = fixture()
        paired = paired_fixture(*docs)
        report = self.evaluate(docs, paired)
        expected = (-math.log(2) + 11 * math.log(.9/.8)) / 12
        transforms = report['paired_diagnostics']['transforms']
        self.assertEqual([r['multiple'] for r in transforms], [v for n in range(1, 11) for v in (n, -n)])
        for transform in transforms:
            self.assertAlmostEqual(transform['paired_participant_macro_delta_nats'], expected)
        self.assertAlmostEqual(report['paired_diagnostics']['equal_transform_mean_delta_nats'], expected)
        self.assertEqual(report['primary'], self.evaluate(docs)['primary'])
        self.assertTrue(report['paired_diagnostics']['unsupported_cases'])
        self.assertGreater(transforms[0]['participant_folds'][0]['paired_evaluable_cases'],
                           transforms[0]['participant_folds'][1]['paired_evaluable_cases'])

    def test_unavailable_null_does_not_remove_person_from_primary(self):
        docs = fixture()
        docs[0]['folds'][-1]['dependence_samples_by_rate']['1'] = None
        rebind(*docs)
        report = self.evaluate(docs, paired_fixture(*docs))
        self.assertEqual(len(report['primary']['participant_folds']), 12)
        self.assertIsNotNone(report['primary']['score'])
        for transform in report['paired_diagnostics']['transforms']:
            self.assertEqual(transform['participants_without_paired_support'], ['person_11'])
            self.assertAlmostEqual(transform['paired_participant_macro_delta_nats'],
                                   (-math.log(2) + 10 * math.log(.9/.8)) / 11)
        reasons = {r['reason'] for r in report['paired_diagnostics']['unsupported_cases'] if r['participant'] == 'person_11'}
        self.assertEqual(reasons, {'unestablished_lookback_or_training_dependence'})

    def test_missing_extra_duplicate_or_noninteger_paired_rows_rejected(self):
        for kind in ('missing', 'unsupported', 'duplicate', 'boolean'):
            docs = fixture()
            paired = paired_fixture(*docs)
            if kind == 'missing': paired['rows'].pop()
            if kind == 'unsupported': paired['rows'][0].update(case_id='recording_00_case_0', multiple=-1)
            if kind == 'duplicate': paired['rows'][-1] = copy.deepcopy(paired['rows'][0])
            if kind == 'boolean': paired['rows'][0]['multiple'] = True
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.evaluate(docs, paired)

    def test_per_case_variation_cannot_compare_different_primary_support(self):
        docs = fixture()
        # Deliberately worsen only the first case, unsupported by negative lags.
        docs[3]['rows'][0]['probabilities'] = [.001, .4995, .4995]
        paired = paired_fixture(*docs)
        report = self.evaluate(docs, paired)
        negative = next(t for t in report['paired_diagnostics']['transforms'] if t['multiple'] == -1)
        positive = next(t for t in report['paired_diagnostics']['transforms'] if t['multiple'] == 1)
        base_expected = (-math.log(2) + 11 * math.log(.9/.8)) / 12
        self.assertAlmostEqual(negative['paired_participant_macro_delta_nats'], base_expected)
        self.assertLess(positive['paired_participant_macro_delta_nats'], base_expected)

    def test_bootstrap_resamples_people_is_reproducible_and_is_not_window_sem(self):
        policy = fixture()[1]
        first = mod.cluster_interval([1.0, 1.0, 1.0], policy)
        self.assertEqual((first['lower'], first['upper']), (1.0, 1.0))
        self.assertEqual(mod.cluster_interval([1.0, 4.0], policy), mod.cluster_interval([1.0, 4.0], policy))
        self.assertIsNone(mod.cluster_interval([1.0], policy)['lower'])

    def cli(self, base, docs, *, bad_hash=False, output_cap=2000000):
        command = [sys.executable, '-I', '-S', '-B', str(HERE / 'sensefog_score.py')]
        for name, value in zip(('grid', 'policy', 'targets', 'predictions'), docs):
            raw = (json.dumps(value) + '\n').encode()
            path = base / (name + '.json')
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            command.extend(['--' + name, str(path), '--' + name + '-sha256',
                            '0' * 64 if name == 'targets' and bad_hash else digest])
        command.extend(['--output', str(base / 'score.json'), '--max-input-bytes', '2000000',
                        '--max-output-bytes', str(output_cap), '--max-cases', '200'])
        return subprocess.run(command, capture_output=True, timeout=20, umask=0o077)

    def test_real_cli_frozen_bytes_exclusive_output_and_caps(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            result = self.cli(base, fixture())
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads((base / 'score.json').read_bytes())
            self.assertAlmostEqual(report['primary']['score'], (-math.log(.1)-11*math.log(.9))/12)
            self.assertEqual(set(report['input_byte_sha256']), {'grid', 'policy', 'targets', 'predictions'})
            self.assertEqual((base / 'score.json').stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(self.cli(base, fixture()).returncode, 0)
        for options in ({'bad_hash': True}, {'output_cap': 1}):
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                result = self.cli(base, fixture(), **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((base / 'score.json').exists())

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_constants(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'input.json'
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    mod.read_frozen(path, hashlib.sha256(raw).hexdigest(), len(raw))


if __name__ == '__main__':
    unittest.main(verbosity=2)
