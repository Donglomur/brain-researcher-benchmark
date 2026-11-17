"""Generated software controls only. No authentic targets or model results."""
import copy
import functools
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import core
from core import ContractError, digest, edit_counts, labels_from_source, normalize_tokens, score
from safe_io import parse_json

HERE = Path(__file__).resolve().parent


def rebind(public, private=None, submission=None):
    public['packet_id'] = digest({k: v for k, v in public.items() if k != 'packet_id'})
    for item in (private, submission):
        if item is not None:
            item['packet_id'] = public['packet_id']


def panel():
    # Written independently of SESSION_ROLES to exercise its registered scope.
    sessions = [{'session_id': 'session-%03d' % i,
                 'role': ('train' if i < 28 else 'development' if i < 37 else 'query')}
                for i in range(1, 46)]
    cases = []
    for i, session in enumerate(sessions):
        key = digest(['generated-only', i])
        cases.append(dict(case_id=key, **session, n_time_steps=2,
                          features=dict(path='features/' + key + '.npy', bytes=4224, sha256='0'*64)))
    public = dict(schema='neural013-public-v1', protocol_id='neural013-chronological-v1',
                  sessions=sessions, cases=cases,
                  training_labels=dict(path='training_labels.json', bytes=200, sha256='0'*64))
    targets = [dict(case_id=row['case_id'], tokens=['AA', '|']) for row in cases[36:]]
    private = dict(schema='neural013-targets-v1', targets=targets)
    submission = dict(schema='neural013-predictions-v1', predictions=copy.deepcopy(targets))
    rebind(public, private, submission)
    return public, private, submission


class EvaluatorTests(unittest.TestCase):
    def test_fixed_vocabulary_and_padding(self):
        inventory = json.loads((HERE/'tokens.json').read_text())
        self.assertEqual(inventory['scored_tokens'], list(core.TOKENS))
        self.assertEqual(len(core.TOKENS), 40)
        self.assertEqual(labels_from_source([1, 7, 40, 0], 3), ['AA', 'B', '|'])
        self.assertEqual(normalize_tokens(' aa AA b | '), ['AA', 'AA', 'B', '|'])
        for value in ('AA0', 'SIL', 'BLANK', 'ＡＡ', [1], None, ['AA B']):
            with self.assertRaises(ContractError):
                normalize_tokens(value)
        for ids, length in (([0], 1), ([41], 1), ([True], 1), ([1, 7], 1), ([], 0)):
            with self.assertRaises(ContractError):
                labels_from_source(ids, length)

    def test_source_split_matches_enforced_aliases(self):
        policy = json.loads((HERE/'split_policy.json').read_text())
        self.assertEqual([(r['session_id'], r['role']) for r in policy['sessions']], list(core.SESSION_ROLES))
        self.assertEqual(policy['calibration_labeled_trials_on_query_sessions'], 0)

    def test_exhaustive_distance_against_recursive_oracle(self):
        @functools.lru_cache(None)
        def oracle(a, b):
            if not a: return len(b)
            if not b: return len(a)
            return min(1 + oracle(a[1:], b), 1 + oracle(a, b[1:]),
                       (a[0] != b[0]) + oracle(a[1:], b[1:]))
        seqs = [t for length in range(4) for t in itertools.product(('AA', 'B', '|'), repeat=length)]
        for a, b in itertools.product(seqs, repeat=2):
            counts = edit_counts(a, b)
            self.assertEqual(counts['distance'], oracle(a, b))
            self.assertEqual(counts['distance'], counts['insertions'] + counts['deletions'] + counts['substitutions'])
            self.assertEqual(len(a) + counts['insertions'] - counts['deletions'], len(b))

    def test_session_weighting_and_complete_counts(self):
        public, private, candidate = panel()
        private['targets'][0]['tokens'] = ['AA']
        candidate['predictions'][0]['tokens'] = []
        # Add a second, longer trial to the first query session. Its denominator
        # must be pooled within that session, before the equal-session mean.
        extra = copy.deepcopy(public['cases'][36])
        extra['case_id'] = digest('extra-generated-trial')
        extra['features']['path'] = 'features/' + extra['case_id'] + '.npy'
        public['cases'].append(extra)
        row = dict(case_id=extra['case_id'], tokens=['AA', 'B', '|'])
        private['targets'].append(row)
        candidate['predictions'].append(copy.deepcopy(row))
        rebind(public, private, candidate)
        result = score(public, candidate, lambda: private)
        self.assertAlmostEqual(result['score'], 1/36)  # mean(1/4, eight zeros)
        self.assertEqual(result['pooled_PER_secondary'], 1/20)
        self.assertEqual(result['query_sessions'], 9)
        self.assertEqual(result['query_trials'], 10)
        self.assertEqual(result['pooled_counts_secondary']['sequence_exact_match'], .9)
        self.assertEqual(result['sessions']['session-037']['sequence_exact_match'], .5)
        self.assertEqual(result['pooled_counts_secondary']['deletions'], 1)
        self.assertEqual(result['participant_count'], 1)

    def test_empty_repeats_boundary_and_unclipped_insertion(self):
        public, private, candidate = panel()
        for row in candidate['predictions']: row['tokens'] = []
        self.assertEqual(score(public, candidate, lambda: private)['score'], 1)
        for row in candidate['predictions']: row['tokens'] = ['AA']
        self.assertEqual(score(public, candidate, lambda: private)['score'], .5)
        for row in candidate['predictions']: row['tokens'] = ['AA']*10
        self.assertGreater(score(public, candidate, lambda: private)['score'], 1)
        self.assertEqual(edit_counts(['AA', 'AA'], ['AA'])['deletions'], 1)

    def test_order_and_case_invariance(self):
        public, private, candidate = panel()
        expected = score(public, candidate, lambda: private)
        public['cases'].reverse()
        candidate['predictions'].reverse()
        private['targets'].reverse()
        for row in candidate['predictions']: row['tokens'] = 'aa |'
        rebind(public, private, candidate)
        expected['packet_id'] = public['packet_id']
        self.assertEqual(score(public, candidate, lambda: private), expected)

    def test_short_panel_and_role_swaps_fail_before_private(self):
        for change in ('short', 'role', 'query_absent', 'empty_training'):
            public, private, candidate = panel()
            if change == 'short': public['sessions'].pop()
            elif change == 'role': public['sessions'][0]['role'] = 'development'
            elif change == 'query_absent': public['cases'].pop()
            else: public['cases'] = public['cases'][27:]
            rebind(public, private, candidate)
            with self.assertRaises(ContractError):
                score(public, candidate, lambda: self.fail('private opened'))

    def test_malformed_submission_never_reads_targets(self):
        for change in ('missing', 'duplicate', 'unknown', 'blank', 'packet', 'extra', 'unbounded'):
            public, private, candidate = panel()
            if change == 'missing': candidate['predictions'].pop()
            elif change == 'duplicate': candidate['predictions'][1] = candidate['predictions'][0]
            elif change == 'unknown': candidate['predictions'][0]['case_id'] = 'f'*64
            elif change == 'blank': candidate['predictions'][0]['tokens'] = 'BLANK'
            elif change == 'packet': candidate['packet_id'] = 'f'*64
            elif change == 'extra': candidate['transcript'] = 'forbidden'
            else: candidate['predictions'][0]['tokens'] = ['AA']*2049
            with self.assertRaises(ContractError):
                score(public, candidate, lambda: self.fail('private opened'))

    def test_private_join_and_empty_target_errors(self):
        for change in ('duplicate', 'missing', 'packet', 'empty'):
            public, private, candidate = panel()
            if change == 'duplicate': private['targets'][1] = private['targets'][0]
            elif change == 'missing': private['targets'].pop()
            elif change == 'packet': private['packet_id'] = 'f'*64
            else: private['targets'][0]['tokens'] = []
            with self.assertRaises(ContractError): score(public, candidate, lambda: private)

    def test_complexity_failure_produces_no_partial_metric(self):
        public, private, candidate = panel()
        with patch.object(core, 'MAX_DP_CELLS', 1):
            result = score(public, candidate, lambda: private)
        self.assertEqual(result['status'], 'unsupported_complexity')
        self.assertIsNone(result['score'])
        self.assertNotIn('sessions', result)

    def test_json_rejects_duplicate_and_nonfinite(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'[]junk'):
            with self.assertRaises(ContractError): parse_json(body)

    def test_cli_and_private_read_boundary(self):
        public, private, candidate = panel()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name, value in (('public', public), ('private', private), ('submission', candidate)):
                (root/(name+'.json')).write_text(json.dumps(value))
            argv = [sys.executable, '-B', str(HERE/'score.py')]
            for name in ('public', 'private', 'submission'): argv += ['--'+name, str(root/(name+'.json'))]
            argv += ['--output', str(root/'result.json')]
            outcome = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            self.assertEqual(outcome.returncode, 0, outcome.stderr)
            result = json.loads((root/'result.json').read_text())
            self.assertEqual(result['score'], 0)
            self.assertEqual(result['pooled_counts_secondary']['exact_matches'], 9)
            (root/'result.json').unlink()
            (root/'submission.json').write_text('{"bad":true}')
            (root/'private.json').unlink()
            outcome = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            self.assertEqual(outcome.returncode, 2, outcome.stderr)
            result = json.loads((root/'result.json').read_text())
            self.assertEqual(result['status'], 'invalid_submission')
            self.assertFalse(result['private_targets_loaded'])
            (root/'result.json').unlink()
            (root/'submission.json').write_text(json.dumps(candidate))
            outcome = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            self.assertEqual(outcome.returncode, 3, outcome.stderr)
            self.assertNotIn(str(root), (root/'result.json').read_text())
            (root/'result.json').unlink()
            (root/'public.json').write_text('{"bad":true}')
            outcome = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            self.assertEqual(outcome.returncode, 3, outcome.stderr)
            result = json.loads((root/'result.json').read_text())
            self.assertEqual(result['status'], 'invalid_operator_packet')
            self.assertFalse(result['private_targets_loaded'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
