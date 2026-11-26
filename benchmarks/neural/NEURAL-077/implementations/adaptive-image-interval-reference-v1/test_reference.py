"""Generated source controls only: no authentic EEG, model or scientific score."""
import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('adaptive_reference_runner_controls', HERE / 'runner.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
MODULES = None
SCRATCH = None
READ = WRITE = 0
IDS = tuple(f'q-{i:032x}' for i in range(6400))


def synthetic(gain=20, baseline=0, post=10):
    # Analytic raster intervals, no implication of authentic EEG.
    return {'gain': gain, 'columns': [[[baseline, baseline]] * 280 + [[post, post]] * 840 for _ in range(2)]}


def generated_record(value=0, demo=None):
    row = {'trial_id': IDS[0], 'channels': [[value] * 1024, [value] * 1024]}
    if demo is not None:
        row.update(trial_id=f'demo-{demo}', target=(0, 1, 0, 1)[demo])
    return row


def fake_provenance(i, demo=False):
    a = MODULES['observer']; viewer = MODULES['viewer']
    cap = not demo and i in (0, 6399)
    count = 6 if demo or cap else 1
    attempts = []; state = viewer.initial_state()
    for j in range(count):
        action = a.action_at(j, i if demo else None)
        state = viewer.transition(state, action, 'four_demo')
        clipped = j < count - 1 or cap
        evidence = {'schema': 'erp-rendered-warning-evidence-v1', 'template_rgb': a.pin(b'generated'),
            'scanlines': a.pin(b'generated'), 'channels': [
                {'channel': name, 'roi_xyxy': [1030, top, 1030 + len(a.WARNING) * 6, top + 7],
                 'pixels': a.pin(b'generated'), 'clipped': clipped} for name, top in (('Cz', 185), ('Pz', 445))],
            'both_channels_unclipped': not clipped}
        attempts.append({'action': action, 'state': state, 'image': {'file': f'FRAME-{j}.png', **a.pin(b'generated')},
            'display': viewer.display_metadata(state, {'target': (0, 1, 0, 1)[i]} if demo else {}),
            'resolution': a.resolution(a.GAINS[j]), 'warning_evidence': evidence})
    projection = {'condition': a.CONDITION, 'trial_id': f'demo-{i}' if demo else IDS[i],
                  'demonstration': i if demo else None, 'attempts': attempts, 'selected_index': count - 1,
                  'selected_gain': a.GAINS[count - 1], 'outcome': 'cap_clipped' if cap else 'unclipped'}
    return {'record': a.pin(b'generated'), 'projection': a.pin(a.encode(projection)),
            **{k: projection[k] for k in ('trial_id', 'selected_gain', 'selected_index', 'outcome', 'attempts')},
            'attempted_images': count}


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.a, self.m = MODULES['observer'], MODULES['reference']
        self.budget = self.a.Budget(96 * 1024**2, 28 * 1024**2, 50)

    def tearDown(self):
        global READ, WRITE
        READ += self.budget.read; WRITE += self.budget.written
        self.temp.cleanup()

    def model(self):
        return self.m.fit([synthetic(post=-10), synthetic(post=10)] * 2,
                          [fake_provenance(i, True) for i in range(4)])

    def raster_features(self, record, gain):
        state = MODULES['viewer'].initial_state()
        state['units_per_division'] = gain
        image = MODULES['raster'].render(record, state, 'four_demo')
        return self.m.extract(MODULES['codec'].scanlines(image), gain)


class Geometry(Base):
    def test_flat_signal_native_geometry_and_cross_gain_rounding_bound(self):
        signal = 17.25
        mids = []
        for gain in self.a.GAINS:
            feature = self.raster_features(generated_record(signal), gain)
            for column in (0, 137, 279, 500, 1118):
                lo, hi = feature['columns'][0][column]
                self.assertLessEqual(lo, signal); self.assertGreaterEqual(hi, signal)
                self.assertAlmostEqual(hi - lo, gain / 30)
                self.assertLessEqual(abs((lo + hi) / 2 - signal), gain / 60 + 1e-12)
            mids.append((gain, sum(feature['columns'][0][500]) / 2))
        for g, v in mids:
            for h, w in mids:
                self.assertLessEqual(abs(v - w), (g + h) / 60 + 1e-12)

    def test_rendered_plateau_baseline_subtraction_contains_true_native_difference(self):
        record = generated_record(3.25)
        for channel in record['channels']:
            channel[300:] = [20.5] * 724
        for gain in self.a.GAINS:
            feature = self.raster_features(record, gain)
            pre = self.m.mean_interval(feature['columns'][0][10:250])
            post = self.m.mean_interval(feature['columns'][0][600:656])
            difference = self.m.subtract(post, pre)
            self.assertLessEqual(difference[0], 17.25)
            self.assertGreaterEqual(difference[1], 17.25)
            self.assertLessEqual(abs(sum(difference) / 2 - 17.25), gain / 30 + 1e-11)

    def test_audited_projection_selects_gain_and_commits_every_attempt(self):
        record = generated_record(61)
        directory = self.root / 'record'
        value, committed = self.a.observe_record(record, None, directory, MODULES, self.budget)
        feature, provenance = r.projected_features(directory, {'record': committed, 'trial_id': IDS[0]}, None, MODULES, self.budget)
        self.assertEqual((feature['gain'], provenance['selected_gain'], len(provenance['attempts'])), (50, 50, 2))
        self.assertEqual(provenance['record'], committed)
        self.assertEqual(provenance['attempts'][1]['resolution']['native_units_per_vertical_pixel'], 50 / 30)
        self.assertNotIn('channels', feature)
        path = directory / 'FRAME-0.png'; path.chmod(0o600); path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Frozen content'):
            r.projected_features(directory, {'record': committed, 'trial_id': IDS[0]}, None, MODULES, self.budget)

    def test_cap_clipped_all_missing_retains_six_attempts_and_half_probability(self):
        record = generated_record(3001)
        directory = self.root / 'cap'
        _, committed = self.a.observe_record(record, None, directory, MODULES, self.budget)
        feature, provenance = r.projected_features(directory, {'record': committed, 'trial_id': IDS[0]}, None, MODULES, self.budget)
        probability, quality = self.m.predict(feature, self.model())
        self.assertEqual((provenance['outcome'], provenance['attempted_images']), ('cap_clipped', 6))
        self.assertTrue(all(v is None for row in feature['columns'] for v in row))
        self.assertEqual(probability, .5); self.assertTrue(quality['no_shared_support'])
        r.validate_quality(quality, probability)

    def test_exact_four_demo_labels_fixed_and_query_does_not_mutate_model(self):
        model = self.model(); before = copy.deepcopy(model)
        self.m.validate_model(model)
        for post in (-3000, 0, 3000):
            q = synthetic(1000, post=post)
            p, quality = self.m.predict(q, model)
            self.assertTrue(math.isfinite(p)); r.validate_quality(quality, p)
        self.assertEqual(model, before)
        with self.assertRaisesRegex(ValueError, 'Exactly four'):
            self.m.fit(model['demos'][:3], model['provenance'][:3])
        model['labels'][0] = 1
        with self.assertRaisesRegex(ValueError, 'labels'):
            self.m.validate_model(model)

    def test_same_column_support_rejects_disjoint_equal_coverage(self):
        model = self.model(); query = synthetic()
        for channel in range(2):
            for x in range(280, 1120):
                if x % 2:
                    query['columns'][channel][x] = None
                else:
                    model['demos'][0]['columns'][channel][x] = None
        p, q = self.m.predict(query, model)
        self.assertEqual(p, .5); self.assertEqual(q['shared_support_fraction'], 0)

    def test_interval_gap_direction_resolution_and_missing_baseline(self):
        model = self.model()
        positive, q = self.m.predict(synthetic(post=10), model)
        negative, _ = self.m.predict(synthetic(post=-10), model)
        self.assertGreater(positive, .5); self.assertLess(negative, .5)
        self.assertGreater(q['interval_distances'][0], q['interval_distances'][1])
        ambiguous = synthetic(gain=1000)
        ambiguous['columns'] = [[[-100, 100]] * 1120 for _ in range(2)]
        p, _ = self.m.predict(ambiguous, model); self.assertEqual(p, .5)
        missing = synthetic()
        missing['columns'] = [[None] * 280 + row[280:] for row in missing['columns']]
        p, q = self.m.predict(missing, model); self.assertEqual(p, .5)
        self.assertEqual(q['baseline_coverage'], [0, 0])

    def test_invalid_feature_values_fail_before_zero_support_fallback(self):
        for value in (float('nan'), float('inf'), True, '0'):
            bad = synthetic(); bad['columns'][0][0] = [value, value]
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.predict(bad, self.model())
        bad = synthetic(); bad['gain'] = True
        with self.assertRaises(ValueError): self.m.validate_features(bad)
        bad = synthetic(); bad['columns'][0].pop()
        with self.assertRaises(ValueError): self.m.validate_features(bad)

    def test_projection_admission_binds_prefix_selection_and_complete_pin(self):
        value = fake_provenance(0)
        r.validate_provenance(value, None, MODULES)
        for field in ('projection', 'selected_index', 'attempts'):
            bad = copy.deepcopy(value)
            if field == 'projection': bad[field] = self.a.pin(b'wrong')
            if field == 'selected_index': bad[field] = 0
            if field == 'attempts': bad[field][0]['action'] = {'action': 'gain', 'units_per_division': 1000}
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.validate_provenance(bad, None, MODULES)

    def test_source_loading_is_bounded_and_charged_before_query_work(self):
        meter = r.SourceMeter(1, 30)
        with self.assertRaisesRegex(ValueError, 'read cap'):
            r.dependencies(Path(MODULES['observer'].__file__).parents[5], meter)
        self.assertGreater(meter.read, 1)

    def test_first_response_rejects_boolean_probability_and_wrong_gain(self):
        probability, quality = self.m.predict(synthetic(1000), self.model())
        result = {'trial_id': IDS[0], 'target_probability': probability,
                  'quality': quality, 'observation': fake_provenance(0)}
        r.validate_response(result, IDS[0], probability, MODULES)
        bad = copy.deepcopy(result); bad['target_probability'] = True
        with self.assertRaisesRegex(ValueError, 'nonboolean'):
            r.validate_response(bad, IDS[0], 1, MODULES)
        bad = copy.deepcopy(result)
        bad['quality']['native_units_per_vertical_pixel'] = 20 / 30
        bad['quality']['in_range_sample_placement_rounding_bound_native'] = 20 / 60
        with self.assertRaisesRegex(ValueError, 'observed gain'):
            r.validate_response(bad, IDS[0], probability, MODULES)


class Collection(Base):
    def inventory(self):
        p = self.a.pin(b'generated')
        return {'demos': [{'ordinal': i, 'trial_id': f'demo-{i}', 'record': p} for i in range(4)],
                'queries': [{'ordinal': i, 'trial_id': identifier, 'record': p} for i, identifier in enumerate(IDS)]}

    def generated_collection(self, fail_at=None):
        capture = self.root / 'capture'; capture.mkdir()
        output = self.root / 'output'
        feature = synthetic(1000, post=0); model = self.m.fit([feature] * 4, [fake_provenance(i, True) for i in range(4)])
        probability, quality = self.m.predict(feature, model)
        # Orchestration control replaces image extraction and numerical work only;
        # real audited rendered geometry and reference math are exercised above.
        calls = []
        def projection(directory, row, demo, modules, budget):
            if demo is None:
                self.assertTrue((output / 'MODEL.json').exists())
                self.assertEqual(calls[:4], list(range(4)))
                if fail_at == row['ordinal']:
                    raise ValueError('generated failure')
            calls.append(demo if demo is not None else row['ordinal'] + 4)
            provenance = fake_provenance(row['ordinal'], demo is not None)
            return synthetic(provenance['selected_gain'], post=0), provenance
        def predicted(q, model):
            detail = copy.deepcopy(quality)
            detail['native_units_per_vertical_pixel'] = q['gain'] / 30
            detail['in_range_sample_placement_rounding_bound_native'] = q['gain'] / 60
            return probability, detail
        with patch.object(r, 'capture_inventory', return_value=self.inventory()), \
             patch.object(r, 'projected_features', side_effect=projection), \
             patch.object(self.m, 'predict', side_effect=predicted):
            expected = r.collect(capture, self.a.pin(b'capture'), output, MODULES, self.budget)
        self.assertEqual(len(calls), 6404)
        return output, expected

    def test_full6400_first_outputs_frozen_before_queries_and_endpoint_compatible(self):
        output, expected = self.generated_collection()
        predictions = r.admit(output, expected, MODULES, self.budget)
        self.assertEqual(tuple(predictions), IDS)
        self.assertEqual(set(predictions.values()), {.5})
        receipt = self.a.decode((output / 'COMPLETE.json').read_bytes())
        self.assertEqual(len(receipt['rows']), 6400)
        first = self.a.decode((output / 'RESPONSE-0000.json').read_bytes())
        last = self.a.decode((output / 'RESPONSE-6399.json').read_bytes())
        self.assertEqual(first['observation']['outcome'], 'cap_clipped')
        self.assertEqual(len(last['observation']['attempts']), 6)

    def test_failure_retains_first_outputs_and_never_emits_complete(self):
        with self.assertRaisesRegex(ValueError, 'generated failure'):
            self.generated_collection(fail_at=2)
        output = self.root / 'output'
        self.assertTrue((output / 'RESPONSE-0000.json').exists())
        self.assertTrue((output / 'RESPONSE-0001.json').exists())
        self.assertFalse((output / 'COMPLETE.json').exists())
        failure = self.a.decode((output / 'FAILED.json').read_bytes())
        self.assertEqual((failure['completed_queries'], failure['uncompleted_queries']), (2, 6398))

    def test_original_inventory_rejects_partial_extra_target_and_wrong_condition(self):
        p = self.a.pin(b'generated'); inventory = self.inventory()
        value = {'schema': 'erp-adaptive-observation-complete-v1', 'status': 'complete_observation_only',
                 'condition': self.a.CONDITION, 'intent': p, **inventory,
                 'private_target_reads': 0, 'predictions': 0, 'scoring_performed': False}
        self.a.validate_inventory(value)
        for mutation in ('partial', 'target', 'condition'):
            bad = copy.deepcopy(value)
            if mutation == 'partial': bad['queries'].pop()
            if mutation == 'target': bad['queries'][0]['target'] = 1
            if mutation == 'condition': bad['condition'] = 'fixed20'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.a.validate_inventory(bad)

    def test_corrupt_first_output_blocks_target_loader(self):
        output, expected = self.generated_collection()
        path = output / 'RESPONSE-6399.json'; path.chmod(0o600); path.write_bytes(b'corrupt')
        called = []
        with self.assertRaises(ValueError):
            r.evaluate_complete(output, expected, MODULES, self.budget, lambda ids: called.append(ids))
        self.assertEqual(called, [])

    def test_existing_target_last_ordering_and_join_endpoint_unchanged(self):
        order = []
        predictions = dict.fromkeys(IDS, .5)
        def admitted(*_): order.append('all6400_public'); return predictions
        def labels(ids):
            order.append('private')
            self.assertEqual(ids, set(IDS))
            return {f'generated-person-{i}': [(IDS[i * 200 + j], int(j < 40)) for j in range(200)] for i in range(32)}
        with patch.object(r, 'admit', side_effect=admitted):
            result = r.evaluate_complete(None, None, MODULES, self.budget, labels)
        self.assertEqual(order, ['all6400_public', 'private'])
        self.assertEqual(len(result['participants']), 32)
        self.assertEqual(result['participant_macro_balanced_accuracy'], .5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--suite', choices=('geometry', 'collection', 'ordering', 'response', 'all'), default='all')
    args = parser.parse_args()
    SCRATCH = args.scratch_root.resolve(); SCRATCH.mkdir(parents=True, exist_ok=True)
    MODULES = r.dependencies(args.repository_root)
    classes = {'geometry': [Geometry], 'collection': [Collection], 'all': [Geometry, Collection], 'ordering': [], 'response': []}[args.suite]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in classes)
    if args.suite == 'ordering':
        suite.addTest(Collection('test_existing_target_last_ordering_and_join_endpoint_unchanged'))
    if args.suite == 'response':
        suite.addTest(Geometry('test_first_response_rejects_boolean_probability_and_wrong_gain'))
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'tests': count, 'run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skips': len(result.skipped), 'generated_only': True,
        'scientific_qualification': False, 'named_read_bytes': READ, 'artifact_bytes_written': WRITE}))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun == count and not result.skipped else 1)
