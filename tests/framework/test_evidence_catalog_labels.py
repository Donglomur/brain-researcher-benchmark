"""Distinct published evidence must remain distinguishable in task navigation."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('evidence_catalog_labels', ROOT / 'src/neurobench/catalog.py')
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)
TASK = 'benchmarks/paper/PAPER-SMC-RNN-2024'


def record(identifier, condition):
    return {'id': identifier, 'category': 'author_model_inference_probe',
            'source': {'path': TASK + '/docs/native-cost-characterization.json'},
            'source_pointer': '/arms/' + identifier,
            'scope': 'Actual partial inference; no complete predictions or scores.',
            'condition': condition}


class RecordedEvidenceLabelTests(unittest.TestCase):
    def test_causal_and_noncausal_records_are_visible_without_deleting_evidence(self):
        rows = [record('causal', 'causal author model, 192 particles'),
                record('noncausal', 'noncausal author model, 192 particles')]
        before = copy.deepcopy(rows)
        output = catalog.render_recorded_evidence(rows, TASK)
        self.assertEqual(rows, before)
        self.assertEqual(len(output.splitlines()), 2)
        self.assertEqual(output.count('(docs/native-cost-characterization.json)'), 2)
        self.assertIn('Author model inference probe — causal author model, 192 particles', output)
        self.assertIn('Author model inference probe — noncausal author model, 192 particles', output)
        self.assertNotIn('record causal', output)
        self.assertEqual(output.count(rows[0]['scope']), 2)

    def test_same_condition_keeps_stable_record_ids_and_order(self):
        rows = [record('attempt-2', 'same permitted observation'),
                record('attempt-1', 'same permitted observation')]
        output = catalog.render_recorded_evidence(rows, TASK)
        self.assertIn('same permitted observation; record attempt-2', output)
        self.assertIn('same permitted observation; record attempt-1', output)
        self.assertLess(output.index('record attempt-2'), output.index('record attempt-1'))
        self.assertEqual(len(set(output.splitlines())), 2)

    def test_missing_none_or_empty_condition_uses_record_identity(self):
        rows = [record('missing', None), record('none', None), record('empty', '')]
        del rows[0]['condition']
        output = catalog.render_recorded_evidence(rows, TASK)
        for identifier in ('missing', 'none', 'empty'):
            self.assertIn('Author model inference probe — record ' + identifier, output)
        self.assertEqual(len(set(output.splitlines())), 3)
        self.assertNotIn('None', output)

    def test_render_normalization_cannot_hide_distinct_record_identity(self):
        rows = [record('first', 'same\ncondition'), record('second', 'same condition')]
        rows[0]['category'] = 'author-model-inference-probe'
        rows[1]['scope'] = rows[1]['scope'].replace('; ', ';\n')
        output = catalog.render_recorded_evidence(rows, TASK)
        self.assertEqual(len(set(output.splitlines())), 2)
        self.assertIn('same condition; record first', output)
        self.assertIn('same condition; record second', output)

    def test_literal_conditions_cannot_impersonate_fallback_labels(self):
        examples = ([record('x', None), record('y', 'record x')],
                    [record('x', 'c'), record('z', 'c'), record('y', 'c; record x')],
                    [record('x', None), record('y', 'record x'),
                     record('z', 'record \"x\"; condition: c')])
        for rows in examples:
            with self.subTest(rows=rows):
                output = catalog.render_recorded_evidence(rows, TASK)
                self.assertEqual(len(set(output.splitlines())), len(rows))
                self.assertIn(' — record \"x\"', output)
                self.assertIn(' — record \"y\"', output)

    def test_unambiguous_bullets_preserve_original_bytes_and_escape_added_labels(self):
        rows = [record('single', 'unneeded context'), record('other', 'other context')]
        rows[1]['scope'] = 'A different scientific scope.'
        output = catalog.render_recorded_evidence(rows, TASK)
        expected = ''.join('- [Author model inference probe](docs/native-cost-characterization.json): '
                           + row['scope'] + '\n' for row in rows)
        self.assertEqual(output, expected)
        ambiguous = [record('first', '<a>[condition]'), record('second', 'different')]
        escaped = catalog.render_recorded_evidence(ambiguous, TASK)
        self.assertIn(catalog.markdown_text('<a>[condition]'), escaped)
        self.assertNotIn('<a>', escaped)


if __name__ == '__main__':
    unittest.main()
