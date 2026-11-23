"""Generated four-method input controls; no EEG, learned models or paper replay."""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).with_name('score_panel.py')
SPEC = importlib.util.spec_from_file_location('reproduction_panel', MODULE)
panel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(panel)


def fixture():
    roster = {'schema': 'physiop300_operator_roster_v1', 'subjects': []}
    predictions = {'schema': 'physiop300_reproduction_predictions_v1',
                   'repetitions': ['fit-a', 'fit-b', 'fit-c'], 'cells': []}
    methods = {'EEGPT': [.1, .4, .6, .9], 'BENDR': [.9, .6, .4, .1],
               'BIOT': [.5, .5, .5, .5], 'LaBraM': [.1, .7, .2, .8]}
    for sid in ('1', '2', '3', '4', '5', '6', '7', '9', '11'):
        events = [{'event_id': f'{sid}-recording-{i // 2}-event-{i}',
                   'recording_id': f'{sid}-recording-{i // 2}', 'target': y}
                  for i, y in enumerate((0, 0, 1, 1))]
        roster['subjects'].append({'subject_id': sid, 'events': events})
        for repetition, (method, probabilities) in itertools.product(predictions['repetitions'], methods.items()):
            predictions['cells'].append({'subject_id': sid, 'repetition': repetition, 'method': method,
                'probabilities': [{'event_id': event['event_id'], 'p_target': probability}
                                  for event, probability in zip(events, probabilities)]})
    return roster, predictions


class ReproductionPanelTests(unittest.TestCase):
    def test_original_four_method_panel_matches_hand_calculated_metrics(self):
        result = panel.score_reproduction_panel(*fixture())
        self.assertEqual(result['methods'], ['EEGPT', 'BENDR', 'BIOT', 'LaBraM'])
        self.assertEqual(len(result['cells']), 108)
        self.assertNotIn('candidate_minus_reference', result)
        self.assertIsNone(result['source_panel_aggregate'])
        self.assertFalse(result['paper_reproduction_established'])
        expected = {'EEGPT': (1., 1., 1.), 'BENDR': (0., 0., -1.),
                    'BIOT': (.5, .5, 0.), 'LaBraM': (.75, .5, 0.)}
        for cell in result['cells']:
            auc, bac, kappa = expected[cell['method']]
            self.assertEqual(cell['auroc'], auc)
            for rule in ('ge', 'gt'):
                self.assertEqual(cell['threshold_metrics'][rule]['balanced_accuracy'], bac)
                self.assertEqual(cell['threshold_metrics'][rule]['cohen_kappa'], kappa)

    def test_improvement_reference_cells_have_identical_arithmetic(self):
        roster, reproduction = fixture()
        improvement = copy.deepcopy(reproduction)
        improvement['schema'] = 'physiop300_predictions_v1'
        for cell in reproduction['cells']:
            if cell['method'] == 'EEGPT':
                extra = copy.deepcopy(cell)
                extra['method'] = 'candidate'
                improvement['cells'].append(extra)
        old_role = panel.score_panel(roster, improvement)
        new_role = panel.score_reproduction_panel(roster, reproduction)
        self.assertEqual([cell for cell in old_role['cells'] if cell['method'] != 'candidate'],
                         new_role['cells'])
        self.assertEqual(len(old_role['cells']), 135)
        self.assertEqual(len(old_role['candidate_minus_reference']), 108)

    def test_reproduction_does_not_accept_a_fifth_candidate(self):
        roster, predictions = fixture()
        extra = copy.deepcopy(predictions['cells'][0])
        extra['method'] = 'candidate'
        predictions['cells'].append(extra)
        with self.assertRaisesRegex(panel.PanelError, 'unexpected or duplicate panel cell'):
            panel.score_reproduction_panel(roster, predictions)

    def test_every_original_method_subject_and_repetition_is_required(self):
        for missing in ('EEGPT', 'BENDR', 'BIOT', 'LaBraM'):
            roster, predictions = fixture()
            predictions['cells'] = [c for c in predictions['cells'] if c['method'] != missing]
            with self.subTest(method=missing), self.assertRaisesRegex(panel.PanelError, 'all 108 cells'):
                panel.score_reproduction_panel(roster, predictions)
        roster, predictions = fixture()
        roster['subjects'].pop(0)
        with self.assertRaisesRegex(panel.PanelError, 'complete nine'):
            panel.score_reproduction_panel(roster, predictions)
        roster, predictions = fixture()
        predictions['repetitions'].pop()
        with self.assertRaisesRegex(panel.PanelError, 'three repetition'):
            panel.score_reproduction_panel(roster, predictions)

    def test_strict_event_join_and_label_custody(self):
        for mutation in ('missing', 'duplicate', 'foreign', 'target'):
            roster, predictions = fixture()
            rows = predictions['cells'][0]['probabilities']
            if mutation == 'missing':
                rows.pop()
            elif mutation == 'duplicate':
                rows.append(copy.deepcopy(rows[0]))
            elif mutation == 'foreign':
                rows[0]['event_id'] = roster['subjects'][1]['events'][0]['event_id']
            else:
                rows[0]['target'] = 0
            with self.subTest(mutation=mutation), self.assertRaises(panel.PanelError):
                panel.score_reproduction_panel(roster, predictions)

    def test_permutations_do_not_change_event_identity(self):
        roster, predictions = fixture()
        expected = panel.score_reproduction_panel(roster, predictions)
        roster['subjects'].reverse()
        predictions['cells'].reverse()
        for subject in roster['subjects']:
            subject['events'].reverse()
        for cell in predictions['cells']:
            cell['probabilities'].reverse()
        self.assertEqual(panel.score_reproduction_panel(roster, predictions), expected)

    def test_undefined_class_support_keeps_all_twelve_original_cells(self):
        roster, predictions = fixture()
        for event in roster['subjects'][0]['events']:
            event['target'] = 0
        result = panel.score_reproduction_panel(roster, predictions)
        self.assertEqual(len(result['cells']), 108)
        self.assertEqual(result['undefined_cells'], 12)
        self.assertEqual(sum(c['auroc'] is None for c in result['cells']), 12)
        self.assertIsNone(result['source_panel_aggregate'])

    def test_schema_and_cli_selection_keep_roles_explicit(self):
        roster, predictions = fixture()
        with self.assertRaisesRegex(panel.PanelError, 'prediction schema'):
            panel.score_panel(roster, predictions)
        wrong_schema = copy.deepcopy(predictions)
        wrong_schema['schema'] = 'physiop300_predictions_v1'
        with self.assertRaisesRegex(panel.PanelError, 'prediction schema'):
            panel.score_reproduction_panel(roster, wrong_schema)
        with tempfile.TemporaryDirectory(prefix='p300-reproduction-control-') as temporary:
            root = Path(temporary)
            roster_path, prediction_path = root / 'roster.json', root / 'predictions.json'
            roster_path.write_text(json.dumps(roster))
            prediction_path.write_text(json.dumps(predictions))
            command = [sys.executable, '-I', '-S', '-B', str(MODULE),
                       '--operator-roster', str(roster_path), '--predictions', str(prediction_path)]
            selected = subprocess.run(command + ['--panel', 'reproduction'],
                                      capture_output=True, text=True, timeout=10)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(json.loads(selected.stdout), panel.score_reproduction_panel(roster, predictions))
            default = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(default.returncode, 2)
            self.assertEqual(default.stdout, '')
            self.assertIn('prediction schema', default.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
