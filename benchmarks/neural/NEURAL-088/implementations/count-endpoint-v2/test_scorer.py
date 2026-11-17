"""Generated controls only: no empirical observations, targets or predictions."""
import copy
from decimal import Decimal, localcontext
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('count_endpoint', HERE / 'scorer.py')
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)


def fixture():
    rows = [dict(edge_id='a', pre_id=1, post_id=10, projection='A-B', sampling_weight=1),
            dict(edge_id='b', pre_id=1, post_id=11, projection='A-B', sampling_weight=3),
            dict(edge_id='c', pre_id=2, post_id=10, projection='A-B', sampling_weight=1)]
    def paired(anatomy, joint):
        return {view: [{'edge_id': row['edge_id'], 'mean': value} for row, value in zip(rows, values)]
                for view, values in zip(scorer.VIEWS, (anatomy, joint))}
    candidate = paired([1, 1, 1], [1, 3, 5])
    references = paired([1, 1, 1], [2, 2, 2])
    targets = [{'edge_id': row['edge_id'], 'count': 0} for row in rows]
    return rows, candidate, references, targets


class CountEndpointControls(unittest.TestCase):
    def test_weighted_within_neuron_equal_between_neurons(self):
        rows, candidate, references, targets = fixture()
        result = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)
        self.assertEqual(result['primary']['value'], 7.5)
        self.assertEqual(result['primary']['direction'], 'lower')
        self.assertEqual(result['arms']['candidate']['anatomy_plus_in_vivo']['equal_presynaptic_mean_absolute_count_error'], 3.75)
        self.assertEqual(result['fixed_reference_anatomy_minus_joint']['equal_presynaptic_loss_difference'], -2)
        self.assertEqual(result['fixed_reference_joint_minus_candidate_joint']['equal_presynaptic_loss_difference'], -3.5)
        self.assertEqual(result['private_callback_invocations'], 1)

    def test_weakened_candidate_anatomy_cannot_improve_primary(self):
        rows, candidate, references, targets = fixture()
        before = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)
        for item in candidate['anatomy']:
            item['mean'] = 100000
        after = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)
        self.assertEqual(before['primary'], after['primary'])
        self.assertEqual(before['fixed_reference_anatomy_minus_joint'], after['fixed_reference_anatomy_minus_joint'])
        self.assertNotEqual(before['candidate_self_contrast_descriptive_only'], after['candidate_self_contrast_descriptive_only'])

    def test_id_alignment_and_role_separation(self):
        rows, candidate, references, targets = fixture()
        before = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)
        for views in (candidate, references):
            for values in views.values():
                values.reverse()
        targets.reverse()
        self.assertEqual(before, scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9))
        references['anatomy'] = copy.deepcopy(references['anatomy_plus_in_vivo'])
        equal = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)
        self.assertEqual(equal['fixed_reference_anatomy_minus_joint']['equal_presynaptic_loss_difference'], 0)
        self.assertEqual(before['primary'], equal['primary'])

    def test_invalid_candidates_never_load_targets(self):
        def forbidden():
            self.fail('Malformed candidate reached private loader')
        for defect in ('missing', 'extra', 'duplicate', 'wrong_id', 'nan', 'negative', 'bool', 'huge_int', 'one_view', 'extra_field'):
            rows, candidate, references, _ = fixture()
            values = candidate['anatomy_plus_in_vivo']
            if defect == 'missing': values.pop()
            elif defect == 'extra': values.append({'edge_id': 'extra', 'mean': 1})
            elif defect == 'duplicate': values[1] = dict(values[0])
            elif defect == 'wrong_id': values[0]['edge_id'] = 'wrong'
            elif defect == 'nan': values[0]['mean'] = float('nan')
            elif defect == 'negative': values[0]['mean'] = -1
            elif defect == 'bool': values[0]['mean'] = True
            elif defect == 'huge_int': values[0]['mean'] = 10**400
            elif defect == 'one_view': del candidate['anatomy']
            elif defect == 'extra_field': values[0]['count'] = 0
            with self.subTest(defect=defect):
                result = scorer.grade(rows, candidate, references, forbidden, rate_floor=1e-9)
                self.assertEqual(result['status'], 'invalid_submission')
                self.assertEqual(result['private_callback_invocations'], 0)

    def test_invalid_operator_roster_references_and_targets_raise(self):
        for defect in ('duplicate_pair', 'bool_endpoint', 'zero_weight', 'nan_weight', 'negative_weight', 'missing_reference', 'target_duplicate', 'fractional_target', 'bool_target', 'target_id'):
            rows, candidate, references, targets = fixture()
            if defect == 'duplicate_pair': rows[1]['post_id'] = 10
            elif defect == 'bool_endpoint': rows[0]['pre_id'] = True
            elif defect == 'zero_weight': rows[0]['sampling_weight'] = 0
            elif defect == 'nan_weight': rows[0]['sampling_weight'] = float('nan')
            elif defect == 'negative_weight': rows[0]['sampling_weight'] = -1
            elif defect == 'missing_reference': references['anatomy'].pop()
            elif defect == 'target_duplicate': targets[1] = dict(targets[0])
            elif defect == 'fractional_target': targets[0]['count'] = 0.5
            elif defect == 'bool_target': targets[0]['count'] = False
            elif defect == 'target_id': targets[0]['edge_id'] = 'wrong'
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)

    def test_frozen_floor_and_raw_count_mae(self):
        rows, candidate, references, targets = fixture()
        for values in candidate.values():
            for item in values:
                item['mean'] = 0
        targets[0]['count'] = 1
        result = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=.25)
        expected_first_loss = 2 * (.25 - 1 + math.log(4))
        expected = ((expected_first_loss + 3 * .5) / 4 + .5) / 2
        self.assertAlmostEqual(result['primary']['value'], expected)
        arm = result['arms']['candidate']['anatomy_plus_in_vivo']
        self.assertEqual(arm['floored_predictions'], 3)
        self.assertEqual(arm['equal_presynaptic_mean_absolute_count_error'], .125)
        for floor in (0, -1, True, float('inf'), float('nan')):
            with self.subTest(floor=floor), self.assertRaises(ValueError):
                scorer.grade(rows, candidate, references, lambda: targets, rate_floor=floor)

    def test_independent_decimal_precision(self):
        for count in (1, 3, 127, 2**32, 2**53):
            for mean in (math.nextafter(float(count), 0), math.nextafter(float(count), math.inf), count * .99, count * 1.01, count * .5, count * 2):
                with localcontext() as ctx:
                    ctx.prec = 140
                    y, mu = Decimal(count), Decimal(mean)
                    expected = float(2 * (mu - y + y * (y.ln() - mu.ln())))
                actual = scorer.poisson_deviance(count, mean, 1e-9)
                self.assertGreater(actual, 0)
                self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12), (count, mean, actual, expected))
        self.assertEqual(scorer.poisson_deviance(0, 2, 1e-9), 4)
        self.assertEqual(scorer.poisson_deviance(7, 7, 1e-9), 0)

    def test_weighted_reduction_extremes(self):
        tiny = float.fromhex('0x0.0000000000001p-1022')
        # Normalizing tiny/large weights first would underflow and lose half.
        self.assertEqual(scorer.weighted_mean([1e308, tiny], [tiny, 1e308]), 2 * tiny)
        self.assertEqual(scorer.weighted_mean([1e308, 1e308], [1e308, 1e308]), 1e308)
        self.assertEqual(scorer.weighted_mean([-4, -2], [1, 1]), -3)

    def test_overflow_has_no_qualified_score_or_dropped_rows(self):
        for role in ('candidate', 'fixed_reference'):
            for view in scorer.VIEWS:
                rows, candidate, references, targets = fixture()
                paired = candidate if role == 'candidate' else references
                paired[view][0]['mean'] = sys.float_info.max
                result = scorer.grade(rows, candidate, references, lambda: targets, rate_floor=1e-9)
                self.assertEqual(result['status'], 'valid_unscorable_arithmetic')
                self.assertIsNone(result['primary']['value'])
                self.assertEqual(result['edge_n'], 3)
                self.assertEqual(result['arms'][role][view]['unsupported_arithmetic_edges'], 1)
                json.dumps(result, allow_nan=False)

    def test_cli_and_private_load_order(self):
        rows, candidate, references, targets = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            protocol = dict(rows=rows, rate_floor=1e-9, fixed_reference_views=references)
            for name, value in (('protocol', protocol), ('candidate', candidate), ('targets', targets)):
                (root / (name + '.json')).write_text(json.dumps(value))
            command = [sys.executable, '-I', '-B', str(HERE / 'scorer.py'), '--protocol', str(root / 'protocol.json'),
                       '--candidate', str(root / 'candidate.json'), '--targets', str(root / 'targets.json'), '--output', str(root / 'report.json')]
            run = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads((root / 'report.json').read_text())
            self.assertEqual(report['primary']['value'], 7.5)
            self.assertEqual(len(report['protocol_sha256']), 64)
            (root / 'targets.json').unlink()
            candidate['anatomy'].pop()
            (root / 'candidate.json').write_text(json.dumps(candidate))
            run = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 2, run.stderr)
            report = json.loads((root / 'report.json').read_text())
            self.assertEqual(report['private_callback_invocations'], 0)
            (root / 'candidate.json').write_text('{"anatomy": [], "anatomy": []}')
            with self.assertRaises(ValueError):
                scorer.read_json(root / 'candidate.json')
            (root / 'candidate.json').write_text('[NaN]')
            with self.assertRaises(ValueError):
                scorer.read_json(root / 'candidate.json')


if __name__ == '__main__':
    unittest.main(verbosity=2)
