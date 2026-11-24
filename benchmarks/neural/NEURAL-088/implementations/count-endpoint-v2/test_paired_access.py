"""Generated complete-panel controls; no empirical neural data or model calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('paired_access', HERE / 'paired_access.py')
paired = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paired)


def fixture():
    rows = [dict(edge_id=f'e{i}', pre_id=1 + i % 21, post_id=100 + i,
                 projection='generated', sampling_weight=1 + i % 3) for i in range(6691)]
    def predictions(anatomy, joint):
        return {view: [dict(edge_id=row['edge_id'], mean=fn(row)) for row in rows]
                for view, fn in zip(paired.scorer.VIEWS, (anatomy, joint))}
    bindings = {view: {'query_observations_sha256': str(index) * 64, 'fit_validation_exposure_sha256': 'f' * 64}
                for index, view in enumerate(paired.scorer.VIEWS)}
    protocol = dict(rows=rows, rate_floor=1e-9, fixed_reference_views=predictions(lambda r: 2, lambda r: 1),
                    information_bindings={mode: copy.deepcopy(bindings) for mode in paired.MODES})
    submissions = {'direct_observation': predictions(lambda r: 3, lambda r: r['pre_id']),
                   'frozen_program': predictions(lambda r: 4, lambda r: 1)}
    counts = [dict(edge_id=row['edge_id'], count=0) for row in rows]
    return protocol, submissions, counts


class PairedAccessControls(unittest.TestCase):
    def test_complete_panel_signs_equal_neuron_weight_and_single_private_read(self):
        protocol, submissions, counts = fixture()
        calls = []
        result = paired.compare(protocol, submissions, lambda: calls.append('read') or counts)
        self.assertEqual(calls, ['read'])
        self.assertEqual(result['status'], 'scored')
        self.assertEqual(result['edge_n'], 6691)
        self.assertEqual(result['unique_presynaptic_n'], 21)
        self.assertEqual(result['mode_results']['direct_observation']['primary']['value'], 22)
        self.assertEqual(result['mode_results']['frozen_program']['primary']['value'], 2)
        contrasts = result['direct_minus_program']
        self.assertEqual(contrasts['joint_view_primary_difference'], 20)
        self.assertEqual(contrasts['by_view']['anatomy']['equal_presynaptic_loss_difference'], -2)
        self.assertEqual([item['loss_difference'] for item in contrasts['by_view']['anatomy_plus_in_vivo']['per_presynaptic']],
                         [2 * (pre - 1) for pre in range(1, 22)])
        self.assertEqual(result['information_binding_status'], 'operator_declared_equal_not_delivery_attested')

    def test_null_contrast_and_shuffled_key_order(self):
        protocol, submissions, counts = fixture()
        submissions['frozen_program'] = copy.deepcopy(submissions['direct_observation'])
        for values in submissions['frozen_program'].values():
            values.reverse()
        counts.reverse()
        result = paired.compare(protocol, submissions, lambda: counts)
        self.assertEqual(result['direct_minus_program']['joint_view_primary_difference'], 0)
        self.assertEqual(result['mode_results']['direct_observation'], result['mode_results']['frozen_program'])

    def test_both_modes_validate_before_any_target_read(self):
        for defect in ('missing_program_edge', 'duplicate_direct_edge', 'one_mode', 'one_view', 'injected_target', 'invalid_mean'):
            protocol, submissions, _ = fixture()
            if defect == 'missing_program_edge': submissions['frozen_program']['anatomy_plus_in_vivo'].pop()
            elif defect == 'duplicate_direct_edge': submissions['direct_observation']['anatomy'][1] = submissions['direct_observation']['anatomy'][0]
            elif defect == 'one_mode': del submissions['direct_observation']
            elif defect == 'one_view': del submissions['frozen_program']['anatomy']
            elif defect == 'injected_target': submissions['frozen_program']['anatomy'][0]['count'] = 0
            elif defect == 'invalid_mean': submissions['direct_observation']['anatomy_plus_in_vivo'][0]['mean'] = float('nan')
            with self.subTest(defect=defect):
                result = paired.compare(protocol, submissions, lambda: self.fail('Invalid mode reached targets'))
                self.assertEqual(result['status'], 'invalid_submission')
                self.assertEqual(result['private_callback_invocations'], 0)
                self.assertIsNone(result['mode_results'])
                self.assertIsNone(result['direct_minus_program'])

    def test_complete_cardinality_and_matching_information_are_operator_requirements(self):
        for defect in ('subset', 'twenty_pre', 'query_mismatch', 'exposure_mismatch', 'malformed_digest', 'candidate_reference'):
            protocol, submissions, _ = fixture()
            if defect == 'subset': protocol['rows'].pop()
            elif defect == 'twenty_pre':
                for row in protocol['rows']:
                    if row['pre_id'] == 21: row['pre_id'] = 20
            elif defect == 'query_mismatch': protocol['information_bindings']['frozen_program']['anatomy']['query_observations_sha256'] = 'b' * 64
            elif defect == 'exposure_mismatch': protocol['information_bindings']['frozen_program']['anatomy_plus_in_vivo']['fit_validation_exposure_sha256'] = 'c' * 64
            elif defect == 'malformed_digest': protocol['information_bindings']['direct_observation']['anatomy']['query_observations_sha256'] = ''
            elif defect == 'candidate_reference': protocol['fixed_reference_views']['anatomy'].pop()
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                paired.compare(protocol, submissions, lambda: self.fail('Invalid operator protocol reached targets'))

    def test_target_failure_does_not_score_a_subset(self):
        protocol, submissions, counts = fixture()
        counts.pop()
        with self.assertRaises(ValueError):
            paired.compare(protocol, submissions, lambda: counts)

    def test_one_overflow_arm_has_no_complete_paired_result(self):
        protocol, submissions, counts = fixture()
        submissions['frozen_program']['anatomy_plus_in_vivo'][0]['mean'] = sys.float_info.max
        result = paired.compare(protocol, submissions, lambda: counts)
        self.assertEqual(result['status'], 'valid_unscorable_arithmetic')
        self.assertIsNone(result['direct_minus_program']['joint_view_primary_difference'])
        self.assertEqual(result['direct_minus_program']['by_view'], {view: None for view in paired.scorer.VIEWS})
        self.assertEqual(result['mode_results']['frozen_program']['edge_n'], 6691)
        json.dumps(result, allow_nan=False)

    def test_cli_malformed_modes_never_open_absent_targets(self):
        protocol, _, _ = fixture()
        scratch = Path(os.environ['NEURAL088_TEST_TMP'])
        self.assertFalse(scratch.is_symlink(), 'NEURAL088_TEST_TMP must not be a symlink')
        scratch.mkdir(mode=0o700, exist_ok=True)  # The owned parent must already exist.
        scratch = scratch.resolve(strict=True)
        self.assertTrue(scratch.is_dir(), 'NEURAL088_TEST_TMP must name an owned scratch directory')
        with tempfile.TemporaryDirectory(prefix='neural088-paired-generated-', dir=scratch) as folder:
            root = Path(folder)
            self.assertEqual(root.parent, scratch)
            print(json.dumps({'generated_cli_scratch_root': str(root), 'scratch_parent': str(scratch)}), flush=True)
            (root / 'protocol.json').write_text(json.dumps(protocol))
            (root / 'submissions.json').write_text('{}')
            run = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'paired_access.py'),
                                  '--protocol', str(root / 'protocol.json'), '--submissions', str(root / 'submissions.json'),
                                  '--targets', str(root / 'absent-targets.json'), '--output', str(root / 'report.json')],
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 2, run.stderr)
            result = json.loads((root / 'report.json').read_text())
            self.assertEqual(result['private_callback_invocations'], 0)
            self.assertFalse((root / 'absent-targets.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
