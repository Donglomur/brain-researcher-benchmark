"""Generated software controls only; no authentic observations or saved answers."""
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import delivery_io as transport
import evaluate as evaluator
from analysis_core import BLOCKS, FIELDS, ORIGINAL, REVISION
from scorer_core import fingerprint


def components(index, row):
    # Closed-form fixture oracle, independent of analysis_core's trace arithmetic.
    matched = (7 if index == 3 else 3 * (index + 1)) + row
    unmatched = (4 if index == 3 else index + 1) + row / 2
    opto = (3 if index == 3 else 2) + row / 4
    return dict(zip(FIELDS, (matched, unmatched, opto, matched - unmatched,
                             matched - opto, unmatched - opto)))


def fixture(root):
    (root / 'arrays').mkdir()
    blocks, inputs, report_blocks = [], [], []
    for index, (name, count) in enumerate(zip(BLOCKS, evaluator.COUNTS)):
        revision = index == 3
        frames = 200 if revision else 300
        start, end = (123, 126) if revision else (125, 128)
        keys = [('revision_row_' if revision else 'source_row_') + str(row)
                for row in range(count)]
        conditions = REVISION if revision else ORIGINAL
        arrays = {condition: np.full((count, frames), 9000., dtype=np.float64)
                  for condition in conditions}
        rows = []
        for row, key in enumerate(keys):
            values = components(index, row)
            m, u, o = [values[field] for field in FIELDS[:3]]
            if revision:
                selected = {'matched': m + np.array([-1., 0., 1.]),
                            'unmatched': u + np.array([-2., 0., 2.]),
                            'opto': o + np.array([-3., 0., 3.])}
            else:
                selected = {'visF1': 100. + row, 'visF2': 20. - row,
                            'vis1OptoF1': 100. + row + m + np.array([-1., 0., 1.]),
                            'vis2OptoF1': 20. - row + u + np.array([-2., 0., 2.]),
                            'optoF1': o + np.array([-3., 0., 3.])}
            for condition, value in selected.items():
                arrays[condition][row, start:end] = value
            rows.append({'cell_key': key, 'availability': 'observed', **values})
        descriptors = {}
        for condition, array in arrays.items():
            body = io.BytesIO()
            np.save(body, array, allow_pickle=False)
            path = 'arrays/' + name + '_' + condition + '.npy'
            (root / path).write_bytes(body.getvalue())
            descriptors[condition] = {'path': path, **transport.pin(body.getvalue())}
        kind = 'revision' if revision else 'original'
        blocks.append({'block_id': name, 'kind': kind, 'cells': [
            {'cell_key': key, 'availability': 'observed'} for key in keys]})
        members = (['panelGI_new_' + key for key in REVISION] if revision else
                   ['panelGI_expt%d_' % (index + 1) + key for key in (*ORIGINAL, 'stim')])
        inputs.append({'block_id': name, 'kind': kind, 'cell_keys': keys,
                       'shape': [count, frames], 'window': [start, end],
                       'arrays': descriptors, 'source_members': members,
                       'source_full_condition_shape': [count if revision else count + 50, frames],
                       'animal_identity': None,
                       **({'revision_independence_established': False} if revision else {})})
        report_blocks.append({'block_id': name, 'cells': rows, 'valid_cells': count,
                              'means': components(index, (count - 1) / 2)})
    panel = {'schema': 'neural038-panel-v1', 'generation': 'e' * 64, 'blocks': blocks}
    panel['packet_id'] = fingerprint(panel)
    inputs = {'schema': 'neural038-input-v1', 'packet_id': panel['packet_id'], 'blocks': inputs}
    report = {'schema': 'neural038-investigation-v1', 'packet_id': panel['packet_id'],
              'blocks': report_blocks,
              'original_macro_interaction': (4 + 7 + 8.25) / 3,
              'revision_mean_interaction': 29.75}
    # Original D means are 2 + 4/2, 4 + 6/2, and 6 + 4.5/2.
    return panel, inputs, report


class NumericalInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.panel, self.inputs, self.report = fixture(self.root)

    def run_report(self):
        return evaluator.evaluate(self.root, self.panel, self.inputs, self.report)

    def replace_array(self, block, condition, transform):
        record = self.inputs['blocks'][block]['arrays'][condition]
        path = self.root / record['path']
        array = np.load(path, allow_pickle=False)
        transform(array)
        with path.open('wb') as handle:
            np.save(handle, array, allow_pickle=False)
        record.update(transport.pin(path.read_bytes()))

    def test_complete_866_operand_closed_form_oracle(self):
        result = self.run_report()
        self.assertEqual(result['status'], 'scored')
        self.assertTrue(result['full_numeric_reconstruction'])
        self.assertEqual(result['numeric_fields'], 866)
        self.assertEqual(result['numeric_fields_within_tolerance'], 866)
        self.assertIsNone(result['access_mode_result'])

    def test_wrong_but_well_shaped_report_is_not_correct(self):
        self.report['blocks'][0]['cells'][0]['context_interaction'] += 1
        result = self.run_report()
        self.assertFalse(result['full_numeric_reconstruction'])
        self.assertEqual(result['numeric_fields_within_tolerance'], 865)

    def test_submission_order_is_not_biological_identity(self):
        self.report['blocks'].reverse()
        for block in self.report['blocks']:
            block['cells'].reverse()
        self.assertTrue(self.run_report()['full_numeric_reconstruction'])

    def test_unequal_original_block_sizes_do_not_change_macro_weights(self):
        self.report['original_macro_interaction'] = (4 * 9 + 7 * 13 + 8.25 * 10) / 32
        self.assertFalse(self.run_report()['full_numeric_reconstruction'])

    def test_missing_duplicate_boolean_and_invented_availability_reject(self):
        pristine = copy.deepcopy(self.report)
        for mutation in ('missing', 'duplicate', 'boolean', 'availability'):
            with self.subTest(mutation=mutation):
                self.report = copy.deepcopy(pristine)
                cells = self.report['blocks'][0]['cells']
                if mutation == 'missing':
                    cells.pop()
                elif mutation == 'duplicate':
                    cells[1] = copy.deepcopy(cells[0])
                elif mutation == 'boolean':
                    cells[0]['opto_only'] = True
                else:
                    cells[0]['availability'] = 'unobserved'
                with patch.object(evaluator, 'load_array', side_effect=AssertionError('Read too early')):
                    with self.assertRaises(ValueError):
                        self.run_report()

    def test_reduced_public_scope_cannot_be_scored(self):
        self.panel['blocks'][0]['cells'].pop()
        self.panel['packet_id'] = fingerprint({k: v for k, v in self.panel.items() if k != 'packet_id'})
        self.inputs['packet_id'] = self.panel['packet_id']
        with self.assertRaises(ValueError):
            evaluator.metadata(self.panel, self.inputs)

    def test_native_windows_and_revision_provenance_are_enforced(self):
        pristine = copy.deepcopy(self.inputs)
        for mutation in ('window', 'independence', 'condition'):
            with self.subTest(mutation=mutation):
                self.inputs = copy.deepcopy(pristine)
                block = self.inputs['blocks'][3]
                if mutation == 'window':
                    block['window'] = [125, 128]
                elif mutation == 'independence':
                    block['revision_independence_established'] = True
                else:
                    block['source_members'][0] = 'panelGI_expt1_visF1'
                with self.assertRaises(ValueError):
                    self.run_report()

    def test_false_availability_and_infinity_reject(self):
        self.replace_array(0, 'visF1', lambda array: array.__setitem__((0, 125), np.nan))
        with self.assertRaisesRegex(ValueError, 'availability'):
            self.run_report()
        self.replace_array(0, 'visF1', lambda array: array.__setitem__((0, 0), np.inf))
        with self.assertRaisesRegex(ValueError, 'Infinity'):
            self.run_report()

    def test_all_missing_block_is_retained_without_partial_score(self):
        self.replace_array(0, 'visF1', lambda array: array.__setitem__((slice(None), 125), np.nan))
        for cell in self.panel['blocks'][0]['cells']:
            cell['availability'] = 'unobserved'
        self.panel['packet_id'] = fingerprint({k: v for k, v in self.panel.items() if k != 'packet_id'})
        self.inputs['packet_id'] = self.report['packet_id'] = self.panel['packet_id']
        block = self.report['blocks'][0]
        for cell in block['cells']:
            cell['availability'] = 'unobserved'
            cell.update(dict.fromkeys(FIELDS))
        block['valid_cells'] = 0
        block['means'] = dict.fromkeys(FIELDS)
        self.report['original_macro_interaction'] = None
        result = self.run_report()
        self.assertEqual(result['status'], 'insufficient_source_support')
        self.assertIsNone(result['max_scaled_error'])

    def test_array_digest_and_declared_shape_are_checked(self):
        record = self.inputs['blocks'][0]['arrays']['visF1']
        path = self.root / record['path']
        body = path.read_bytes()
        path.write_bytes(body + b'trailing')
        with self.assertRaises(ValueError):
            self.run_report()
        record.update(transport.pin(path.read_bytes()))
        with self.assertRaisesRegex(ValueError, 'payload'):
            self.run_report()

    def test_cli_pins_and_duplicate_json_fields(self):
        for name, value in [('panel.json', self.panel), ('input.json', self.inputs),
                            ('submission.json', self.report)]:
            (self.root / name).write_bytes(transport.canonical(value))
        arguments = ['evaluate.py', '--public-root', str(self.root), '--panel-sha256',
                     transport.pin((self.root / 'panel.json').read_bytes())['sha256'],
                     '--input-sha256', transport.pin((self.root / 'input.json').read_bytes())['sha256'],
                     '--submission', str(self.root / 'submission.json'),
                     '--output', str(self.root / 'score.json')]
        with patch('sys.argv', arguments):
            evaluator.main()
        self.assertTrue(transport.json_file(self.root / 'score.json')['full_numeric_reconstruction'])
        arguments[4] = '0' * 64
        with patch('sys.argv', arguments), self.assertRaises(ValueError):
            evaluator.main()
        with self.assertRaises(ValueError):
            transport.decode(b'{"schema":1,"schema":2}')


if __name__ == '__main__':
    unittest.main()
