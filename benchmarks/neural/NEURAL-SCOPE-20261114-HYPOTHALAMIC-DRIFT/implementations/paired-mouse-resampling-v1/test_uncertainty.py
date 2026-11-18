"""Generated full-cohort numerical controls; no authentic biological values."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hypodrift_uncertainty', HERE / 'uncertainty.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
sys.modules['scorer'] = u.s
fixture_spec = importlib.util.spec_from_file_location('hypodrift_fixture',
                    HERE.parent / 'fixed-origin-forecast' / 'test_scorer.py')
fixtures = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixtures)


def replace_mouse_losses(report, values):
    """Rebuild the public summary from explicit generated paired mouse losses."""
    mice, by_mouse = {}, {}
    for row in report['mice']:
        mid, group = row['mouse_id'], row['group']
        mice[mid] = group
        pair = values(mid, group)
        row.update(candidate_mse=None if pair is None else pair[0],
                   reference_mse=None if pair is None else pair[1],
                   paired_loss_reduction=None if pair is None else pair[1] - pair[0])
        if pair is None:
            row['eligible_neuron_denominator'] = 0
        by_mouse[mid] = {'candidate': [] if pair is None else [pair[0]],
                        'reference': [] if pair is None else [pair[1]]}
    recomputed = u.s.aggregate(mice, by_mouse)
    for key in u.SUMMARY_FIELDS:
        if key != 'mice':
            report[key] = recomputed[key]
    return report


class ResamplingControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p, t, r = fixtures.fixture()
        cls.actual_scorer_report = u.s.score(p, t, r)

    def report(self):
        return copy.deepcopy(self.actual_scorer_report)

    def draw(self, report, **kwargs):
        return u.resample(report, seed=73, replicates=100, **kwargs)

    def test_existing_full_cohort_scorer_exact_constant_effect(self):
        out = self.draw(self.report())
        self.assertEqual(out['point_paired_loss_reduction'], 1.0)
        self.assertEqual(out['interval'], {'lower': 1.0, 'upper': 1.0})
        self.assertEqual(sum(row['mice'] for row in out['strata']), 31)
        self.assertEqual(out['replicates_completed'], 100)
        self.assertIsNone(out['scientific_improvement_decision'])

    def test_paired_draws_preserve_shared_between_mouse_variation(self):
        report = replace_mouse_losses(self.report(),
                lambda mid, group: (float(int(mid.rsplit('m', 1)[1])),
                                    float(int(mid.rsplit('m', 1)[1])) + 2.0))
        out = self.draw(report)
        self.assertAlmostEqual(out['interval']['lower'], 2.0)
        self.assertAlmostEqual(out['interval']['upper'], 2.0)

    def test_equal_groups_not_pooled_31_mice(self):
        report = replace_mouse_losses(self.report(),
                lambda mid, group: (100.0 if group == 'LH-MCH' else 0.0, 0.0))
        out = self.draw(report)
        self.assertEqual(out['point_paired_loss_reduction'], -20.0)
        self.assertEqual(out['interval'], {'lower': -20.0, 'upper': -20.0})
        self.assertNotEqual(out['point_paired_loss_reduction'], -700 / 31)

    def test_seeded_reproducibility_and_input_order_invariance(self):
        report = replace_mouse_losses(self.report(),
                lambda mid, group: (0.0, float(int(mid.rsplit('m', 1)[1]))))
        out = self.draw(report)
        report['mice'].reverse()
        report['groups'].reverse()
        self.assertEqual(self.draw(report), out)
        self.assertLess(out['interval']['lower'], out['interval']['upper'])

    def test_one_missing_mouse_keeps_point_but_refuses_interval_without_rng(self):
        report = self.report()
        absent = report['mice'][0]['mouse_id']
        replace_mouse_losses(report, lambda mid, group: None if mid == absent else (0.0, 1.0))
        self.assertTrue(report['primary_defined'])
        with patch.object(u.random, 'Random', side_effect=AssertionError('must not resample')):
            out = self.draw(report)
        self.assertFalse(out['interval_defined'])
        self.assertEqual(out['point_paired_loss_reduction'], 1.0)
        self.assertIsNone(out['interval'])
        self.assertEqual(out['replicates_completed'], 0)
        self.assertEqual(out['ineligible_mouse_ids'], [absent])

    def test_missing_group_retains_undefined_primary(self):
        report = replace_mouse_losses(self.report(),
                lambda mid, group: None if group == 'LH-MCH' else (0.0, 1.0))
        out = self.draw(report)
        self.assertFalse(out['interval_defined'])
        self.assertIsNone(out['point_paired_loss_reduction'])
        self.assertEqual(len(out['ineligible_mouse_ids']), 7)

    def test_exact_paired_aggregation_and_support_tampering_refuse(self):
        mutations = [
            lambda r: r['mice'][0].update(paired_loss_reduction=10),
            lambda r: r.update(candidate_mse=0.1),
            lambda r: r['groups'][0].update(eligible_mouse_denominator=5),
            lambda r: r['mice'][0].update(mouse_id=r['mice'][1]['mouse_id']),
            lambda r: r['mice'][0].update(group='LH-MCH'),
            lambda r: r['mice'][0].update(eligible_neuron_denominator=True),
            lambda r: r['mice'][0].update(candidate_mse=True),
            lambda r: r['mice'][0].update(reference_mse=float('nan')),
            lambda r: r.update(origin_after_session=9.0),
            lambda r: r['mice'].pop()]
        for mutate in mutations:
            report = self.report()
            mutate(report)
            with self.subTest(mutation=mutate), self.assertRaises(u.s.ContractError):
                self.draw(report)

    def test_configuration_bounds_and_nearest_rank_definition(self):
        for seed, reps, mass in [(True, 100, .95), (-1, 100, .95), (2**64, 100, .95),
                                 (1, True, .95), (1, 99, .95), (1, 100001, .95),
                                 (1, 100, True), (1, 100, float('nan')), (1, 100, 1.0)]:
            with self.subTest(seed=seed, reps=reps, mass=mass), self.assertRaises(u.s.ContractError):
                u.resample(self.actual_scorer_report, seed=seed, replicates=reps, interval_mass=mass)
        self.assertEqual(u.nearest_rank(list(range(100)), .025), 2)
        self.assertEqual(u.nearest_rank(list(range(100)), .975), 97)

    def test_draw_uses_exactly_one_shared_index_per_mouse(self):
        grouped, _, _ = u.admit_summary(self.actual_scorer_report)
        class Fixed:
            def __init__(self): self.sizes = []
            def randrange(self, n): self.sizes.append(n); return 0
        rng = Fixed()
        self.assertEqual(u._draw_paired_effect(grouped, rng), 1.0)
        self.assertEqual(rng.sizes, [6]*18 + [7]*7 + [6]*6)

    def test_cli_requires_trusted_pin_before_read_and_creates_private_output(self):
        with patch.object(u.s, 'read_document', side_effect=AssertionError('must not open')):
            with self.assertRaises(u.s.ContractError):
                u.main(['--score-report', 'PRIVATE', '--score-report-sha256', 'bad',
                        '--seed', '73', '--replicates', '100', '--output', 'UNUSED'])
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'diagnostic.json'
            args = ['--score-report', 'OPERATOR_REPORT', '--score-report-sha256', 'd'*64,
                    '--seed', '73', '--replicates', '100', '--output', str(output)]
            with patch.object(u.s, 'read_document', return_value=(self.actual_scorer_report, 'd'*64)) as read:
                u.main(args)
                read.assert_called_once_with('OPERATOR_REPORT', 'd'*64)
            out = json.loads(output.read_bytes())
            self.assertEqual(out['score_report_sha256'], 'd'*64)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with patch.object(u.s, 'read_document', return_value=(self.actual_scorer_report, 'd'*64)):
                with self.assertRaises(FileExistsError): u.main(args)


if __name__ == '__main__':
    unittest.main(verbosity=1)
