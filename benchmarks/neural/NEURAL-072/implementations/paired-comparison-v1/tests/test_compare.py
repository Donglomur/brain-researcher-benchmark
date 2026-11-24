"""Generated controls; no authentic Narratives inputs or participant trials."""
import contextlib
import copy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neural072_pair', ROOT / 'compare.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
fixture_spec = importlib.util.spec_from_file_location(
    'neural072_generated_fixture', ROOT.parent / 'initial-evaluator-v1/tests/test_evaluator.py')
fixtures = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixtures)


class PairedControls(unittest.TestCase):
    def setUp(self):
        self.p, self.c, features, train, self.targets = fixtures.fixture()
        reference = e.scorer.freeze_reference(self.p, self.c, features, train)
        self.raw = e.scorer.encode(reference)
        self.expected = e.scorer.sha256(self.raw)
        self.baseline = {
            'schema': e.scorer.CANDIDATE_SCHEMA, 'task_id': 'NEURAL-072',
            'protocol_sha256': e.legacy.digest(self.p), 'cases_sha256': e.legacy.digest(self.c),
            'contextual': {rid: copy.deepcopy(values['lexical'])
                           for rid, values in reference['predictions'].items()},
        }
        self.candidate = copy.deepcopy(self.baseline)
        self.candidate['contextual'] = copy.deepcopy(self.targets)

    def compare(self):
        return e.compare(self.p, self.c, self.targets, self.baseline,
                         self.candidate, self.raw, self.expected)

    def test_perfect_candidate_matches_preserved_scores_and_independent_sse_oracle(self):
        report = self.compare()
        self.assertFalse(report['scientific_qualified'])
        self.assertFalse(report['submission_ready'])
        self.assertEqual(report['target_ids'], self.c['target_ids'])
        self.assertEqual(report['counts']['runs'], len(self.targets))
        self.assertEqual(report['reports']['candidate']['listener_macro_r2']['contextual'], 1.)
        expected_cells = {}
        for run in self.c['runs']:
            if run['split'] != 'test':
                continue
            rid = run['id']
            y = e.legacy.np.asarray(self.targets[rid])
            baseline = e.legacy.np.asarray(self.baseline['contextual'][rid])
            sst = ((y - y.mean(axis=0)) ** 2).sum(axis=0)
            errors = ((y - baseline) ** 2).sum(axis=0)
            expected_cells[(run['listener'], run['story_family'])] = errors / sst
        for cell in report['paired_cells']:
            expected = expected_cells[(cell['listener'], cell['story_family'])]
            e.legacy.np.testing.assert_allclose(cell['delta_r2_by_target'], expected, rtol=1e-14)
        a = report['reports']['candidate']['listener_macro_contrasts']['contextual_minus_lexical']
        b = report['reports']['baseline']['listener_macro_contrasts']['contextual_minus_lexical']
        self.assertAlmostEqual(report['paired_listener_macro_delta_r2'], a - b)
        self.assertGreater(report['paired_listener_macro_delta_r2'], 0.)

    def test_identical_submissions_have_zero_paired_interval_despite_marginal_uncertainty(self):
        self.baseline = copy.deepcopy(self.candidate)
        report = self.compare()
        self.assertEqual(report['paired_listener_macro_delta_r2'], 0.)
        self.assertEqual(report['paired_uncertainty']['intervals_95'][e.DELTA], [0., 0.])
        marginal = report['reports']['candidate']['uncertainty']['intervals_95']['contextual_minus_lexical']
        self.assertGreater(marginal[1], marginal[0])

    def test_reversing_candidates_preserves_signed_effect_and_paired_interval(self):
        forward = self.compare()
        self.baseline, self.candidate = self.candidate, self.baseline
        reverse = self.compare()
        self.assertAlmostEqual(reverse['paired_listener_macro_delta_r2'], -forward['paired_listener_macro_delta_r2'])
        low, high = forward['paired_uncertainty']['intervals_95'][e.DELTA]
        e.legacy.np.testing.assert_allclose(reverse['paired_uncertainty']['intervals_95'][e.DELTA], [-high, -low])

    def test_multirun_pooling_target_macro_and_listener_macro_oracle(self):
        def report(errors):
            return {'cells': [
                {'listener': listener, 'story_family': family, 'runs': ['r1', 'r2'],
                 'scored_rows_by_run': {'r1': 3, 'r2': 6}, 'sst_by_target': [10., 1000.],
                 'sse_by_target': {'contextual': values}}
                for (listener, family), values in errors.items()]}
        left = report({('s1', 'a'): [10., 1000.], ('s1', 'b'): [10., 1000.], ('s2', 'a'): [0., 0.]})
        right = report({('s1', 'a'): [0., 0.], ('s1', 'b'): [0., 0.], ('s2', 'a'): [10., 1000.]})
        cells = e.paired_cells(left, right)
        self.assertEqual([c['delta_r2_by_target'] for c in cells], [[1., 1.], [1., 1.], [-1., -1.]])
        self.assertEqual(e.legacy.summarize(cells)[e.DELTA], 0.)
        self.assertNotEqual(sum(c['contrasts'][e.DELTA] for c in cells) / len(cells), 0.)
        right['cells'][0]['scored_rows_by_run']['r2'] = 5
        with self.assertRaisesRegex(e.ContractError, 'run/row support differs'):
            e.paired_cells(left, right)

    def test_either_submission_must_cover_complete_identical_panel(self):
        mutations = [lambda x: x['contextual'].pop('s1_3'),
                     lambda x: x['contextual'].__setitem__('extra', [[0.]]),
                     lambda x: x['contextual'].__setitem__('s1_3', [[0.]]),
                     lambda x: x.__setitem__('cases_sha256', '0' * 64),
                     lambda x: x.__setitem__('lexical', {}),
                     lambda x: x['contextual']['s1_3'][0].__setitem__(0, float('nan'))]
        for side in ('baseline', 'candidate'):
            for mutate in mutations:
                baseline, candidate = copy.deepcopy(self.baseline), copy.deepcopy(self.candidate)
                mutate(baseline if side == 'baseline' else candidate)
                with self.subTest(side=side, mutation=mutate), self.assertRaises(e.ContractError):
                    e.validate_pair(self.p, self.c, baseline, candidate, self.raw, self.expected)

    def test_one_operator_reference_is_required_for_both_submissions(self):
        with self.assertRaisesRegex(e.ContractError, 'commitment mismatch'):
            e.compare(self.p, self.c, self.targets, self.baseline, self.candidate, b'{}', self.expected)
        with self.assertRaisesRegex(e.ContractError, 'trusted reference SHA-256'):
            e.compare(self.p, self.c, self.targets, self.baseline, self.candidate, self.raw, None)

    def test_more_than_ten_percent_empty_paired_draws_rejected_without_rounding(self):
        original = e.legacy.bootstrap
        calls = []
        def bootstrap(cells, count, seed):
            calls.append(cells)
            if len(calls) <= 2:
                return original(cells, count, seed)
            return {'empty': 1, 'requested': 3}
        with mock.patch.object(e.legacy, 'bootstrap', bootstrap), self.assertRaisesRegex(e.ContractError, 'empty crossed-cluster'):
            self.compare()

    def test_cli_exclusive_report_and_rejection_before_protected_targets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = {'protocol': self.p, 'cases': self.c, 'baseline': self.baseline,
                      'candidate': self.candidate, 'targets': self.targets}
            for name, value in values.items():
                (root / name).write_bytes(e.scorer.encode(value))
            (root / 'reference').write_bytes(self.raw)
            args = [arg for name in (*values, 'reference') for arg in ('--' + name, str(root / name))]
            args += ['--expected-reference-sha256', self.expected, '--output', str(root / 'report')]
            with contextlib.redirect_stdout(io.StringIO()):
                e.main(args)
            frozen = (root / 'report').read_bytes()
            report = e.scorer.decode(frozen)
            self.assertEqual(report['input_file_sha256']['reference'], self.expected)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as failed:
                e.main(args)
            self.assertEqual(failed.exception.code, 2)
            self.assertEqual((root / 'report').read_bytes(), frozen)
            # Both sides must reject malformed support without opening targets.
            for side in ('baseline', 'candidate'):
                original = (root / side).read_bytes()
                (root / side).write_bytes(b'{}')
                protected = root / 'targets'
                real_read = Path.read_bytes
                def guarded_read(path):
                    if path == protected:
                        raise AssertionError('protected targets opened before pair validation')
                    return real_read(path)
                with mock.patch.object(Path, 'read_bytes', guarded_read), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failed:
                    e.main(args)
                self.assertEqual(failed.exception.code, 2)
                (root / side).write_bytes(original)


if __name__ == '__main__':
    unittest.main()
