"""Generated joint-scoring controls. No authentic labels or model execution."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import core
import score as cli
from sequence_prior import fit_prior, predict_prior
from test_evaluator import panel, rebind

HERE = Path(__file__).resolve().parent
BOOTSTRAP = ("import runpy,sys;sys.path.insert(0,sys.argv[1]);"
             "p=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_path(p,run_name='__main__')")
GRADE_FIELDS = {'status', 'metric', 'direction', 'packet_id', 'score', 'sessions',
                'query_trials', 'query_sessions', 'pooled_counts_secondary',
                'session_macro_sequence_exact_match_secondary', 'pooled_PER_secondary',
                'participant_count', 'word_boundary_token_included',
                'complete_manifest_query_coverage', 'source_panel_authentication',
                'scientific_success', 'performance_threshold'}


def unequal_panel():
    """All nine sessions have unequal token denominators and varying trial counts."""
    public, private, candidate = panel()
    private['targets'] = []; candidate['predictions'] = []
    comparator = copy.deepcopy(candidate)
    for number, original in enumerate(public['cases'][36:45], 1):
        for trial in range(1 + number % 2):
            row = original
            if trial:
                row = copy.deepcopy(original)
                row['case_id'] = core.digest(['joint-generated', number, trial])
                row['features']['path'] = 'features/' + row['case_id'] + '.npy'
                public['cases'].append(row)
            tokens = ['AA'] * (number + trial) + ['|']
            private['targets'].append({'case_id': row['case_id'], 'tokens': tokens})
            candidate['predictions'].append({'case_id': row['case_id'],
                                            'tokens': [] if number % 3 == 2 else tokens.copy()})
            comparator['predictions'].append({'case_id': row['case_id'],
                                             'tokens': [] if number % 3 == 1 else tokens.copy()})
    rebind(public, private, candidate); comparator['packet_id'] = public['packet_id']
    return public, private, candidate, comparator


def command(component, *args):
    return [sys.executable, '-I', '-S', '-B', '-c', BOOTSTRAP,
            str(component), str(component / 'score.py'), *map(str, args)]


class ComparisonTests(unittest.TestCase):
    def test_nine_unequal_sessions_preserve_absolute_grades_and_signed_differences(self):
        public, private, candidate, comparator = unequal_panel()
        result = core.compare(public, candidate, comparator, lambda: private)
        self.assertEqual(result['schema'], 'neural013-joint-per-comparison-v1')
        self.assertEqual(result['status'], 'scored')
        self.assertEqual(result['candidate_grade'], core.score(public, candidate, lambda: private))
        self.assertEqual(result['comparator_grade'], core.score(public, comparator, lambda: private))
        self.assertEqual(set(result['candidate_grade']), GRADE_FIELDS)
        sessions = ['session-%03d' % i for i in range(37, 46)]
        self.assertEqual(list(result['session_PER_differences']), sessions)
        denominators = [5, 3, 9, 5, 13, 7, 17, 9, 21]
        for i, session in enumerate(sessions):
            a, b = (result[k]['sessions'][session] for k in ('candidate_grade', 'comparator_grade'))
            self.assertEqual(a['reference_tokens'], denominators[i])
            self.assertEqual(a['reference_tokens'], b['reference_tokens'])
            self.assertEqual(a['trials'], 1 + (i + 1) % 2)
            self.assertEqual(a['trials'], b['trials'])
        self.assertEqual(list(result['session_PER_differences'].values()), [1, -1, 0] * 3)
        self.assertEqual(result['macro_PER_difference'], 0)
        self.assertEqual(result['candidate_grade']['score'], 1/3)
        self.assertEqual(result['comparator_grade']['score'], 1/3)
        self.assertEqual(result['candidate_grade']['pooled_PER_secondary'], 25/89)
        self.assertEqual(result['comparator_grade']['pooled_PER_secondary'], 27/89)
        self.assertNotEqual(result['macro_PER_difference'], 27/89 - 25/89)
        self.assertEqual(result['participant_count'], 1)
        for key in ('confidence_intervals', 'p_values', 'scientific_success'):
            self.assertIsNone(result[key])

    def test_positive_negative_and_zero_macro_are_not_clipped(self):
        public, private, perfect = panel()
        empty = copy.deepcopy(perfect)
        for row in empty['predictions']: row['tokens'] = []
        for a, b, expected in ((perfect, empty, 1), (empty, perfect, -1), (perfect, perfect, 0)):
            with self.subTest(expected=expected):
                result = core.compare(public, a, b, lambda: private)
                self.assertEqual(result['macro_PER_difference'], expected)
                self.assertEqual(set(result['session_PER_differences'].values()), {expected})

    def test_both_complete_operands_admitted_before_private(self):
        for side in ('candidate', 'comparator'):
            for change in ('missing', 'duplicate', 'unknown', 'packet', 'blank', 'extra', 'unbounded'):
                with self.subTest(side=side, change=change):
                    public, private, candidate = panel(); comparator = copy.deepcopy(candidate)
                    item = candidate if side == 'candidate' else comparator
                    if change == 'missing': item['predictions'].pop()
                    elif change == 'duplicate': item['predictions'][1] = item['predictions'][0]
                    elif change == 'unknown': item['predictions'][0]['case_id'] = 'f'*64
                    elif change == 'packet': item['packet_id'] = 'f'*64
                    elif change == 'blank': item['predictions'][0]['tokens'] = ['BLANK']
                    elif change == 'extra': item['reference'] = 'not an operand'
                    else: item['predictions'][0]['tokens'] = ['AA']*2049
                    loader = Mock(side_effect=AssertionError('private before both admissions'))
                    with self.assertRaises(core.ContractError): core.compare(public, candidate, comparator, loader)
                    loader.assert_not_called()

    def test_one_shared_target_capture_and_private_identity(self):
        public, private, candidate = panel()
        changed = copy.deepcopy(private)
        for row in changed['targets']: row['tokens'] = ['B', '|']
        for gold in (private, changed):
            loader = Mock(return_value=gold)
            result = core.compare(public, candidate, candidate, loader)
            loader.assert_called_once_with()
            self.assertEqual(result['macro_PER_difference'], 0)
            self.assertEqual(result['private_targets_canonical_sha256'], core.digest(gold))
            self.assertNotIn('targets', result)
        self.assertNotEqual(core.digest(private), core.digest(changed))

    def test_admitted_predictions_and_identities_are_snapshotted_before_callback(self):
        public, private, candidate, comparator = unequal_panel()
        expected = core.compare(public, candidate, comparator, lambda: private)
        def loader():
            candidate['predictions'][0]['tokens'].clear()
            comparator['predictions'][1]['tokens'].append('B')
            public['packet_id'] = 'f'*64
            return private
        self.assertEqual(core.compare(public, candidate, comparator, loader), expected)

    def test_invalid_private_packet_never_reaches_edit_distance(self):
        for change in ('missing', 'duplicate', 'packet', 'empty'):
            with self.subTest(change=change):
                public, private, candidate = panel()
                if change == 'missing': private['targets'].pop()
                elif change == 'duplicate': private['targets'][1] = private['targets'][0]
                elif change == 'packet': private['packet_id'] = 'f'*64
                else: private['targets'][0]['tokens'] = []
                loader = Mock(return_value=private)
                with patch.object(core, 'edit_counts', side_effect=AssertionError('unadmitted DP')) as dp:
                    with self.assertRaises(core.ContractError): core.compare(public, candidate, candidate, loader)
                loader.assert_called_once_with(); dp.assert_not_called()

    def test_sum_budget_refuses_before_either_kernel_and_boundary_is_inclusive(self):
        public, private, candidate = panel()
        # Nine pairs of length2: each individual panel81 cells, whole pair162.
        with patch.object(core, 'MAX_DP_CELLS', 81):
            self.assertEqual(core.score(public, candidate, lambda: private)['status'], 'scored')
            with patch.object(core, 'edit_counts', side_effect=AssertionError('over-budget DP')) as dp:
                result = core.compare(public, candidate, candidate, lambda: private)
            dp.assert_not_called()
        self.assertEqual(result['status'], 'unsupported_complexity')
        self.assertEqual(result['cells'], 162)
        self.assertFalse(result['comparison_available'])
        for key in ('candidate_grade', 'comparator_grade', 'session_PER_differences', 'macro_PER_difference'):
            self.assertIsNone(result[key])
        with patch.object(core, 'MAX_DP_CELLS', 162):
            self.assertEqual(core.compare(public, candidate, candidate, lambda: private)['status'], 'scored')

    def test_empty_repeated_boundary_tokens_insertion_and_tie_order(self):
        public, private, candidate = panel(); comparator = copy.deepcopy(candidate)
        for row in candidate['predictions']: row['tokens'] = []
        for row in comparator['predictions']: row['tokens'] = ['AA']*10
        result = core.compare(public, candidate, comparator, lambda: private)
        self.assertEqual(result['candidate_grade']['score'], 1)
        self.assertGreater(result['comparator_grade']['score'], 1)
        self.assertGreater(result['macro_PER_difference'], 0)
        self.assertEqual(core.edit_counts(['AA', 'B'], ['B', 'AA']),
                         {'distance': 2, 'substitutions': 2, 'deletions': 0, 'insertions': 0})
        self.assertEqual(core.edit_counts(['AA', 'AA', '|'], ['AA', '|'])['deletions'], 1)

    def test_existing_train_only_prior_uses_same_complete_endpoint(self):
        public, private, candidate = panel()
        labels = {'schema': 'neural013-training-labels-v1', 'labels': [
            {'case_id': r['case_id'], 'tokens': ['AA', '|'] if r['role'] == 'train' else ['B']}
            for r in public['cases'] if r['role'] != 'query']}
        raw = core.canonical(labels)
        public['training_labels'].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        rebind(public, private, candidate)
        model = fit_prior(public, raw); comparator = predict_prior(public, model, model['model_id'])
        result = core.compare(public, candidate, comparator, lambda: private)
        self.assertEqual(result['macro_PER_difference'], 0)
        self.assertEqual(result['comparator_grade']['query_sessions'], 9)
        self.assertEqual(result['comparator_submission_canonical_sha256'], core.digest(comparator))

    def test_comparison_cli_valid_and_sanitized_refusals(self):
        public, private, candidate, comparator = unequal_panel()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name, value in (('public', public), ('private', private), ('submission', candidate), ('comparator', comparator)):
                (root/(name+'.json')).write_bytes(core.canonical(value))
            args = ['--public', root/'public.json', '--private', root/'private.json',
                    '--submission', root/'submission.json', '--comparator-submission', root/'comparator.json',
                    '--output', root/'result.json']
            done = subprocess.run(command(HERE, *args), capture_output=True, text=True, timeout=5)
            self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads((root/'result.json').read_bytes())
            expected = core.compare(public, candidate, comparator, lambda: private)
            expected['private_targets_loaded'] = True
            self.assertEqual(result, expected)
            # Existing exclusive output rule remains intact.
            done = subprocess.run(command(HERE, *args), capture_output=True, text=True, timeout=5)
            self.assertNotEqual(done.returncode, 0)
            self.assertEqual(json.loads((root/'result.json').read_bytes()), expected)
            (root/'result.json').unlink(); (root/'comparator.json').write_text('{"bad":true}')
            (root/'private.json').unlink()
            done = subprocess.run(command(HERE, *args), capture_output=True, text=True, timeout=5)
            self.assertEqual(done.returncode, 2, done.stderr)
            result = json.loads((root/'result.json').read_bytes())
            self.assertEqual(result['status'], 'invalid_submission'); self.assertFalse(result['private_targets_loaded'])
            self.assertNotIn(str(root), (root/'result.json').read_text())
            (root/'result.json').unlink(); (root/'comparator.json').write_bytes(core.canonical(comparator))
            done = subprocess.run(command(HERE, *args), capture_output=True, text=True, timeout=5)
            self.assertEqual(done.returncode, 3, done.stderr)
            result = json.loads((root/'result.json').read_bytes())
            self.assertEqual(result['status'], 'invalid_operator_packet'); self.assertFalse(result['private_targets_loaded'])
            self.assertNotIn(str(root), (root/'result.json').read_text())

    def test_cli_combined_complexity_refusal_is_null_and_sanitized(self):
        public, private, candidate = panel()
        with patch.object(cli, 'read_json', side_effect=[public, candidate, candidate, private]), \
             patch.object(cli, 'write_json') as write, patch.object(core, 'MAX_DP_CELLS', 81), \
             patch.object(core, 'edit_counts', side_effect=AssertionError('over-budget DP')) as dp, \
             patch('builtins.print'):
            code = cli.main(['--public', 'public', '--submission', 'candidate',
                             '--comparator-submission', 'comparator', '--private', 'secret-target', '--output', 'private-result'])
        self.assertEqual(code, 2); dp.assert_not_called()
        result = write.call_args.args[1]
        self.assertTrue(result['private_targets_loaded']); self.assertFalse(result['comparison_available'])
        self.assertIsNone(result['candidate_grade']); self.assertIsNone(result['comparator_grade'])
        self.assertNotIn('secret-target', json.dumps(result))


if __name__ == '__main__':
    unittest.main(verbosity=2)
