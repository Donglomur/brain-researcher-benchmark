"""Generated metadata/output checks; no authentic signals or target access."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core import ContractError
import preflight
from test_evaluator import panel


class PreflightTests(unittest.TestCase):
    def test_complete_output_is_unscored(self):
        public, _, candidate = panel()
        result = preflight.inspect_submission(public, candidate)
        self.assertEqual(result['status'], 'valid_submission')
        self.assertEqual(result['query_trials'], 9)
        self.assertEqual(result['query_sessions'], 9)
        self.assertEqual(result['predicted_tokens'], 18)
        self.assertEqual(result['empty_predictions'], 0)
        self.assertNotIn('score', result)
        self.assertIsNone(result['scientific_success'])
        self.assertFalse(result['scoring_complexity_qualified'])
        self.assertFalse(result['private_targets_loaded'])

    def test_complete_empty_outputs_and_token_formatting(self):
        public, _, candidate = panel()
        candidate['predictions'].reverse()
        candidate['predictions'][0]['tokens'] = []
        candidate['predictions'][1]['tokens'] = ' aa AA | '
        result = preflight.inspect_submission(public, candidate)
        self.assertEqual(result['predicted_tokens'], 17)
        self.assertEqual(result['empty_predictions'], 1)
        self.assertEqual(candidate['predictions'][1]['tokens'], ' aa AA | ')

    def test_bad_support_or_vocabulary_rejected(self):
        for change in ('missing', 'duplicate', 'unknown', 'blank', 'packet'):
            with self.subTest(change=change):
                public, _, candidate = panel()
                if change == 'missing': candidate['predictions'].pop()
                elif change == 'duplicate': candidate['predictions'][1] = candidate['predictions'][0]
                elif change == 'unknown': candidate['predictions'][0]['case_id'] = 'f' * 64
                elif change == 'blank': candidate['predictions'][0]['tokens'] = 'BLANK'
                else: candidate['packet_id'] = 'f' * 64
                with self.assertRaises(ContractError):
                    preflight.inspect_submission(public, candidate)

    def test_only_public_and_submission_are_opened(self):
        public, _, candidate = panel()
        with patch.object(preflight, 'read_json', side_effect=[public, candidate]) as read, \
             patch.object(preflight, 'write_json') as write, contextlib.redirect_stdout(io.StringIO()):
            code = preflight.main(['--public', 'public.json', '--submission', 'output.json',
                                   '--output', 'report.json'])
        self.assertEqual(code, 0)
        self.assertEqual([call.args for call in read.call_args_list], [('public.json',), ('output.json',)])
        self.assertEqual(write.call_args.args[1]['status'], 'valid_submission')

    def test_invalid_public_stops_before_submission(self):
        with patch.object(preflight, 'read_json', return_value={}) as read, \
             patch.object(preflight, 'write_json') as write, contextlib.redirect_stdout(io.StringIO()):
            code = preflight.main(['--public', 'public.json', '--submission', 'output.json',
                                   '--output', 'report.json'])
        self.assertEqual(code, 3)
        read.assert_called_once_with('public.json')
        self.assertEqual(write.call_args.args[1]['status'], 'invalid_operator_packet')

    def test_invalid_submission_is_not_an_operator_error(self):
        public, _, candidate = panel()
        candidate['predictions'].pop()
        with patch.object(preflight, 'read_json', side_effect=[public, candidate]) as read, \
             patch.object(preflight, 'write_json') as write, contextlib.redirect_stdout(io.StringIO()):
            code = preflight.main(['--public', 'public.json', '--submission', 'output.json',
                                   '--output', 'report.json'])
        self.assertEqual(code, 2)
        self.assertEqual(read.call_count, 2)
        self.assertEqual(write.call_args.args[1]['status'], 'invalid_submission')

    def test_fresh_cli_needs_no_features_labels_or_targets(self):
        public, _, candidate = panel()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            (root / 'public.json').write_text(json.dumps(public))
            (root / 'submission.json').write_text(json.dumps(candidate))
            result = subprocess.run([
                sys.executable, '-E', '-S', '-B', str(Path(__file__).with_name('preflight.py')),
                '--public', str(root / 'public.json'), '--submission', str(root / 'submission.json'),
                '--output', str(root / 'report.json')], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / 'report.json').read_text())
            self.assertEqual(report['status'], 'valid_submission')
            self.assertEqual(set(path.name for path in root.iterdir()),
                             {'public.json', 'submission.json', 'report.json'})
            self.assertNotIn('score', report)


if __name__ == '__main__':
    unittest.main(verbosity=2)
