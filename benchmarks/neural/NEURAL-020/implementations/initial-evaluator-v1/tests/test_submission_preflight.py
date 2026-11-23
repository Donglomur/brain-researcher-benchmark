"""Generated public-packet controls; no authentic spikes or private targets."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neural020_preflight', ROOT / 'submission_preflight.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture(width=20):
    bins = np.arange(-100, 500, width, dtype=np.int64)
    query = {
        'trial_ids': np.array(['eval-0000', 'eval-0001', 'eval-0002']),
        'heldin_unit_ids': np.array(['u%02d' % i for i in range(63)]),
        'heldout_unit_ids': np.array(['u63', 'u64']),
        'bin_left_edges_ms': bins,
        'prediction_units': np.asarray('spikes_per_bin'),
        'packet_sha256': np.asarray('a' * 64),
        'visible_counts': np.ones((3, len(bins), 63)),
    }
    query['visible_counts'][0, 0, 0] = np.nan
    submission = {key: np.asarray(query[key]).copy() for key in
                  ('trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms',
                   'prediction_units', 'packet_sha256')}
    submission['expected_counts'] = np.full((3, len(bins), 2), .25)
    return query, submission


class SubmissionPreflightControls(unittest.TestCase):
    def test_public_validation_both_grids_without_private_scorer(self):
        module = p.evaluator()
        module.score_submission = mock.Mock(side_effect=AssertionError('private scorer must not run'))
        for width in (5, 20):
            query, submission = fixture(width)
            with mock.patch.object(p, 'evaluator', return_value=module):
                result = p.validate_submission(query, submission)
            self.assertEqual(result['evaluation_trials'], 3)
            self.assertEqual(result['time_bins'], 600 // width)
            self.assertEqual(result['heldout_units'], 2)
            self.assertFalse(result['private_targets_read'])
            self.assertFalse(result['score_computed'])
            self.assertFalse(result['research_qualified'])
        module.score_submission.assert_not_called()

    def test_expected_counts_can_be_zero_or_fractional(self):
        query, submission = fixture()
        submission['expected_counts'][0] = 0
        before = submission['expected_counts'].copy()
        p.validate_submission(query, submission)
        np.testing.assert_array_equal(before, submission['expected_counts'])

    def test_wrong_geometry_and_alignment_rejected(self):
        query, submission = fixture()
        for field, value in (
            ('trial_ids', submission['trial_ids'][::-1]),
            ('heldout_unit_ids', submission['heldout_unit_ids'][::-1]),
            ('bin_left_edges_ms', np.arange(0, 600, 20)),
            ('packet_sha256', np.asarray('b' * 64)),
            ('expected_counts', np.ones((2, 30, 2))),
            ('expected_counts', np.ones((3, 2, 30))),
        ):
            altered = dict(submission, **{field: value})
            with self.subTest(field=field, shape=np.shape(value)), self.assertRaises(ValueError):
                p.validate_submission(query, altered)

    def test_nonfinite_negative_and_unsafe_integer_predictions_rejected(self):
        query, submission = fixture()
        for value in (np.nan, np.inf, -1., 1 + 2j):
            altered = dict(submission, expected_counts=np.full((3, 30, 2), value))
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.validate_submission(query, altered)
        altered = dict(submission, expected_counts=np.full((3, 30, 2), 2**53 + 1, dtype=np.uint64))
        with self.assertRaisesRegex(ValueError, 'exact float64'):
            p.validate_submission(query, altered)

    def test_query_axis_coverage_and_visible_counts_checked(self):
        query, submission = fixture()
        alterations = []
        bad = copy.deepcopy(query); bad['heldin_unit_ids'][0] = 'u63'; alterations.append(bad)
        bad = copy.deepcopy(query); bad['heldin_unit_ids'] = bad['heldin_unit_ids'][:-1]; alterations.append(bad)
        bad = copy.deepcopy(query); bad['trial_ids'][1] = bad['trial_ids'][0]; alterations.append(bad)
        bad = copy.deepcopy(query); bad['visible_counts'] = np.ones((3, 30, 62)); alterations.append(bad)
        bad = copy.deepcopy(query); bad['visible_counts'][0, 0, 0] = -.5; alterations.append(bad)
        bad = copy.deepcopy(query); bad['bin_left_edges_ms'] = np.arange(0, 600, 20); alterations.append(bad)
        bad = copy.deepcopy(query); bad['packet_sha256'] = np.asarray('g' * 64); alterations.append(bad)
        for index, altered in enumerate(alterations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                p.validate_submission(altered, submission)

    def test_private_fields_and_rate_unit_conversion_refused(self):
        query, submission = fixture()
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            p.validate_submission(dict(query, target_counts=np.ones((3, 30, 2))), submission)
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            p.validate_submission(query, dict(submission, ctr_hold_bump=np.array([0, 0, 1])))
        with self.assertRaisesRegex(ValueError, 'spikes_per_bin'):
            p.validate_submission(query, dict(submission, prediction_units=np.asarray('Hz')))

    def test_cli_only_needs_public_query_and_prediction_files(self):
        query, submission = fixture()
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            np.savez_compressed(directory / 'query.npz', **query)
            np.savez_compressed(directory / 'predictions.npz', **submission)
            argv = ['--query', str(directory / 'query.npz'), '--submission',
                    str(directory / 'predictions.npz'), '--output', str(directory / 'result.json')]
            p.main(argv)
            result = json.loads((directory / 'result.json').read_text())
            self.assertEqual(result['status'], 'public_submission_preflight_passed')
            self.assertFalse(result['private_coverage_verified'])
            self.assertEqual({x.name for x in directory.iterdir()}, {'query.npz', 'predictions.npz', 'result.json'})
            with self.assertRaises(FileExistsError):
                p.main(argv)

    def test_changed_dependency_refused_before_validation(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            (directory / 'evaluator.py').write_text('raise AssertionError("must not execute")\n')
            with mock.patch.object(p, 'HERE', directory), self.assertRaisesRegex(ValueError, 'source changed'):
                p.validate_submission(*fixture())


if __name__ == '__main__':
    unittest.main()
