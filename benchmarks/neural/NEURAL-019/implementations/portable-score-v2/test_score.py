"""Generated software controls only; no original public/private arrays or fits."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import io
import json
import math
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('portable_neural019', HERE / 'score.py')
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)


def pin(path):
    return {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def scalar_r2(y, p):
    """Independent scalar arithmetic, deliberately no production metric call."""
    axes = []
    for axis in range(2):
        truth = [float(value) for value in y[:, :, axis].flat]
        pred = [float(value) for value in p[:, :, axis].flat]
        mean = math.fsum(truth) / len(truth)
        sse = math.fsum((a - b) ** 2 for a, b in zip(truth, pred))
        sst = math.fsum((a - mean) ** 2 for a in truth)
        if all(value == truth[0] for value in truth):
            return None
        axes.append(1 - sse / sst)
    return math.fsum(axes) / 2


class NeverResolve:
    def __fspath__(self):
        raise AssertionError('Private path resolved before candidate validation')


class PortableControls(unittest.TestCase):
    fixture_payload_bytes_written = 0

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='neural019-generated-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name).resolve()
        self.paths = {name: self.root / (name + '.npz') for name in ('public', 'submission', 'gold')}
        self.paths.update(grade=self.root / 'grade.json', commit=self.root / 'commit.json')
        self.groups = np.repeat([8, 13, 18, 20, 23, 31, 34, 37], [2, 3, 5, 7, 11, 17, 31, 50])
        self.public = {
            'trial_ids': np.asarray([f'generated-{i:03d}' for i in range(126)]),
            'velocity_left_edges_ms': np.arange(-150, 550, 5),
            'velocity_axes': np.asarray(['x', 'y']),
            'velocity_units': np.asarray('m/s'),
            'panel_fingerprint': np.asarray('1' * 64),
        }
        # Unequal group counts and variances distinguish group macro from pooled R2.
        clock = np.arange(140, dtype=np.float64) - 69.5
        scales = (1 + np.arange(126) % 7)[:, None]
        self.truth = np.stack((scales * clock, -2 * scales * clock), axis=-1)
        self.prediction = self.truth + np.asarray([3.0, -4.0])
        self.write_npz('public', {'assessment_trial_ids' if key == 'trial_ids' else key: value
                                  for key, value in self.public.items()})
        self.write_npz('gold', dict(self.public, velocity=self.truth, trial_types=self.groups))
        self.write_npz('submission', dict(self.public, velocity=self.prediction))
        self.assets = copy.deepcopy(score.ASSETS)
        self.assets['public']['packet'] = pin(self.paths['public'])
        self.assets['private']['targets'] = pin(self.paths['gold'])
        self.grade = {
            'status': 'scored_with_independent_arithmetic_check',
            'scientific_score_computed': True,
            'all_public_submissions_validated_before_targets': True,
            'target_loader_invocations': 1, 'new_fits': 0, 'pass_threshold': None,
            'trial_count': 126, 'groups': 8, 'units': 'm/s', 'metrics': {}, 'validations': {},
            'independent_arithmetic': {
                'passed': True, 'checks': 704, 'trials': 126, 'groups': 8,
                'fits_performed_by_auditor': 0, 'reference_core_imported_by_auditor': False,
                'tolerance': {'absolute': 1e-10, 'relative_to_independent_value': 1e-10},
                'metrics': {},
            },
        }
        for i, arm in enumerate(score.ARMS):
            value = float(i - 2)
            self.grade['metrics'][arm] = {
                'macro_r2': value, 'defined': True,
                'pooled': {'uniform_axis_r2': value},
                'per_type': [{'trial_type': int(group), 'trials': int((self.groups == group).sum())}
                             for group in np.unique(self.groups)],
            }
            self.grade['independent_arithmetic']['metrics'][arm] = {
                'macro_r2': value, 'pooled': {'uniform_axis_r2': value},
            }
            self.grade['validations'][arm] = {
                'status': 'public_submission_valid', 'cases': 126, 'bins': 140,
                'axes': ['x', 'y'], 'units': 'm/s', 'target_loader_invocations': 0,
            }
        self.commit = {
            'source_freeze_sha256': score.REFERENCE_FREEZE,
            'status': 'predictions_frozen_before_private_grade',
            'producer_removed_and_absent': True, 'producer_execution_sha256': 'a' * 64,
            'files': {name: {'bytes': 1, 'sha256': 'b' * 64} for name in score.REFERENCE_FILES},
        }
        self.write_references()
        self.asset_patch = patch.object(score, 'ASSETS', self.assets)
        self.asset_patch.start()
        self.addCleanup(self.asset_patch.stop)
        original_freeze = score.frozen_submission
        def counted_freeze(source, destination, expected):
            try:
                return original_freeze(source, destination, expected)
            finally:
                if Path(destination).exists():
                    type(self).fixture_payload_bytes_written += Path(destination).stat().st_size
        frozen_patch = patch.object(score, 'frozen_submission', counted_freeze)
        frozen_patch.start()
        self.addCleanup(frozen_patch.stop)

    def write_bytes(self, path, raw):
        path.write_bytes(raw)
        type(self).fixture_payload_bytes_written += len(raw)

    def write_npz(self, name, values):
        # Compress deterministic fixtures to keep repeated complete-panel controls small.
        stream = io.BytesIO()
        np.savez_compressed(stream, **values)
        self.write_bytes(self.paths[name], stream.getvalue())

    def write_references(self):
        self.write_bytes(self.paths['grade'], json.dumps(self.grade).encode())
        self.write_bytes(self.paths['commit'], json.dumps(self.commit).encode())
        self.assets['private']['reference_grade'] = pin(self.paths['grade'])
        self.assets['private']['reference_commit'] = pin(self.paths['commit'])

    def evaluate(self, **changes):
        kwargs = dict(action='score', submission=self.paths['submission'], public_packet=self.paths['public'],
                      private_targets=self.paths['gold'], reference_grade=self.paths['grade'],
                      reference_commit=self.paths['commit'])
        kwargs.update(changes)
        return score.evaluate(**kwargs)

    def test_scalar_endpoint_and_all_four_signed_comparisons(self):
        result, code = self.evaluate()
        self.assertEqual((code, result['status'], result['target_loader_invocations']), (0, 'scored', 1))
        expected = math.fsum(scalar_r2(self.truth[self.groups == group], self.prediction[self.groups == group])
                             for group in np.unique(self.groups)) / 8
        pooled = scalar_r2(self.truth, self.prediction)
        self.assertAlmostEqual(result['primary_metric'], expected, places=12)
        self.assertAlmostEqual(result['metrics']['pooled']['uniform_axis_r2'], pooled, places=12)
        self.assertGreater(abs(expected - pooled), 1e-8)
        for i, arm in enumerate(score.ARMS):
            self.assertAlmostEqual(result['signed_differences']['candidate_minus_' + arm]['macro_r2'],
                                   expected - (i - 2), places=12)
        self.assertFalse(result['candidate_code_executed'])
        self.assertEqual(result['new_fits'], 0)

    def test_case_reordering_fortran_signed_values_preserves_score(self):
        original, _ = self.evaluate()
        order = np.arange(125, -1, -1)
        candidate = dict(self.public, trial_ids=self.public['trial_ids'][order],
                         velocity=np.asfortranarray(self.prediction[order]))
        # Keep an explicit stored-NPZ control alongside compressed fixtures.
        stream = io.BytesIO()
        np.savez(stream, **candidate)
        self.write_bytes(self.paths['submission'], stream.getvalue())
        reordered, code = self.evaluate()
        self.assertEqual(code, 0)
        self.assertEqual(reordered['metrics'], original['metrics'])

    def test_invalid_prediction_never_resolves_private_paths(self):
        candidate = dict(self.public, velocity=self.prediction.copy())
        candidate['velocity'][0, 0, 0] = np.nan
        self.write_npz('submission', candidate)
        result, code = self.evaluate(private_targets=NeverResolve(), reference_grade=NeverResolve(),
                                     reference_commit=NeverResolve())
        self.assertEqual((code, result['status'], result['target_loader_invocations']),
                         (2, 'invalid_submission', 0))

    def test_wrong_case_or_clock_or_fingerprint_rejected(self):
        for field, value in [('trial_ids', np.asarray(['other'] * 126)),
                             ('velocity_left_edges_ms', np.arange(-145, 555, 5)),
                             ('panel_fingerprint', np.asarray('2' * 64))]:
            with self.subTest(field=field):
                self.write_npz('submission', dict(self.public, velocity=self.prediction, **{field: value}))
                result, code = self.evaluate(private_targets=NeverResolve(), reference_grade=NeverResolve(),
                                             reference_commit=NeverResolve())
                self.assertEqual((code, result['status'], result['target_loader_invocations']),
                                 (2, 'invalid_submission', 0))

    def test_validate_never_resolves_private_assets(self):
        result, code = self.evaluate(action='validate', private_targets=NeverResolve(),
                                     reference_grade=NeverResolve(), reference_commit=NeverResolve())
        self.assertEqual((code, result['status']), (0, 'valid_prediction_contract'))
        self.assertFalse(result['private_assets_read'])
        self.assertEqual(result['target_loader_invocations'], 0)

    def test_bad_reference_stops_before_target_loader(self):
        self.commit['producer_removed_and_absent'] = False
        self.write_references()
        result, code = self.evaluate(private_targets=NeverResolve())
        self.assertEqual((code, result['status'], result['target_loader_invocations']), (2, 'scoring_error', 0))
        self.assertIn('stopped/frozen', result['error'])

    def test_public_and_target_pin_changes_rejected(self):
        for name in ('public', 'gold'):
            with self.subTest(name=name):
                original = self.paths[name].read_bytes()
                self.write_bytes(self.paths[name], original + b'x')
                result, code = self.evaluate()
                self.assertEqual(code, 2)
                self.assertFalse(result['scientific_score_computed'])
                self.assertEqual(result['target_loader_invocations'], 0)
                self.write_bytes(self.paths[name], original)

    def test_constant_group_axis_retained_and_primary_undefined(self):
        self.truth[self.groups == 8, :, 0] = 0.1
        self.write_npz('gold', dict(self.public, velocity=self.truth, trial_types=self.groups))
        self.assets['private']['targets'] = pin(self.paths['gold'])
        result, code = self.evaluate()
        self.assertEqual(code, 0)
        self.assertIsNone(result['primary_metric'])
        self.assertEqual(len(result['metrics']['per_type']), 8)
        self.assertIsNone(result['metrics']['per_type'][0]['axis_r2'][0])
        self.assertEqual(result['metrics']['per_type'][0]['axis_sst'][0], 0)
        self.assertTrue(all(row['macro_r2'] is None for row in result['signed_differences'].values()))

    def test_cli_explicit_paths_and_no_output_overwrite(self):
        output = self.root / 'result.json'
        argv = ['validate', '--submission', str(self.paths['submission']),
                '--public-packet', str(self.paths['public']), '--output', str(output)]
        self.assertEqual(score.main(argv), 0)
        self.assertEqual(json.loads(output.read_text())['status'], 'valid_prediction_contract')
        with self.assertRaises(FileExistsError):
            score.main(argv)
        self.assertEqual(json.loads(output.read_text())['status'], 'valid_prediction_contract')

    def test_linked_submission_rejected_before_targets(self):
        linked = self.root / 'linked.npz'
        linked.symlink_to(self.paths['submission'])
        result, code = self.evaluate(submission=linked, private_targets=NeverResolve(),
                                     reference_grade=NeverResolve(), reference_commit=NeverResolve())
        self.assertEqual((code, result['status'], result['target_loader_invocations']),
                         (2, 'invalid_submission', 0))


    def evaluate_with_replacement(self, name, replace):
        original = score.pinned
        replaced = []
        def captured(path, *args):
            value = original(path, *args)
            if path == self.paths[name]:
                replace()
                replaced.append(name)
            return value
        with patch.object(score, 'pinned', captured):
            result, code = self.evaluate()
        self.assertEqual(replaced, [name])
        self.assertEqual((code, result['status']), (0, 'scored'))
        return result

    def test_public_metadata_parsed_from_authenticated_capture(self):
        changed = {'assessment_trial_ids' if key == 'trial_ids' else key: value
                   for key, value in self.public.items()}
        changed['panel_fingerprint'] = np.asarray('2' * 64)
        result = self.evaluate_with_replacement('public', lambda: self.write_npz('public', changed))
        self.assertEqual(result['panel_fingerprint'], '1' * 64)

    def test_target_metrics_use_authenticated_capture(self):
        changed = dict(self.public, velocity=self.truth + 1000, trial_types=self.groups)
        result = self.evaluate_with_replacement('gold', lambda: self.write_npz('gold', changed))
        expected = math.fsum(scalar_r2(self.truth[self.groups == group], self.prediction[self.groups == group])
                             for group in np.unique(self.groups)) / 8
        self.assertAlmostEqual(result['primary_metric'], expected, places=12)
        self.assertEqual(result['target_loader_invocations'], 1)

    def test_reference_values_use_authenticated_capture(self):
        changed = copy.deepcopy(self.grade)
        for arm in score.ARMS:
            changed['metrics'][arm]['macro_r2'] = -10.0
            changed['metrics'][arm]['pooled']['uniform_axis_r2'] = -10.0
            changed['independent_arithmetic']['metrics'][arm]['macro_r2'] = -10.0
            changed['independent_arithmetic']['metrics'][arm]['pooled']['uniform_axis_r2'] = -10.0
        result = self.evaluate_with_replacement('grade',
                    lambda: self.write_bytes(self.paths['grade'], json.dumps(changed).encode()))
        self.assertEqual(result['reference_values']['phase_only']['macro_r2'], -2.0)

    def test_reference_lineage_uses_authenticated_capture(self):
        changed = dict(self.commit, producer_removed_and_absent=False)
        result = self.evaluate_with_replacement('commit',
                    lambda: self.write_bytes(self.paths['commit'], json.dumps(changed).encode()))
        self.assertTrue(result['scientific_score_computed'])

    def test_historical_module_executes_authenticated_source_bytes(self):
        source = self.root / 'probe.py'
        original_body = b'SENTINEL = 1\n'
        self.write_bytes(source, original_body)
        original = score.verified_source
        def captured(name):
            value = original(name)
            self.write_bytes(source, b'SENTINEL = 2\n')
            return value
        with patch.object(score, 'LEGACY', self.root), \
             patch.object(score, 'SOURCE_PINS', {'probe.py': hashlib.sha256(original_body).hexdigest()}), \
             patch.object(score, 'verified_source', captured):
            module = score.load_module('probe')
        self.assertEqual(module.SENTINEL, 1)

    def test_active_submitted_program_dependency_matches_scorer(self):
        manifest = json.loads((HERE.parent / 'submitted-program-v1' / 'DEPENDENCIES.json').read_text())
        expected = manifest['files']['benchmarks/neural/NEURAL-019/implementations/portable-score-v2/score.py']
        self.assertEqual(expected, pin(HERE / 'score.py'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
