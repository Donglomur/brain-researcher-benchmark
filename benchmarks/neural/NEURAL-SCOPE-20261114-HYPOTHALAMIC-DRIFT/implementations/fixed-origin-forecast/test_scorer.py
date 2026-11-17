"""Invented full-support fixtures only; no original animal identities or signals."""
import copy
import hashlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scorer as s


def fixture():
    mice, cells, pred = [], [], []
    for gi, (group, (nmice, ncells)) in enumerate(s.GROUPS.items()):
        for mi in range(nmice):
            mid = f'invented-g{gi}-m{mi}'
            mice.append({'mouse_id': mid, 'group': group})
            for ni in range(ncells // nmice + (mi < ncells % nmice)):
                nid = f'invented-n{ni}'
                cells.append({'mouse_id': mid, 'neuron_id': nid,
                              'valid_stable_seconds': [20.0] * 63,
                              'event_counts': [0] * 63, 'missing_reasons': [None] * 63})
                pred.append({'mouse_id': mid, 'neuron_id': nid, 'log_rates': [0.0] * 36})
    targets = {'schema': 'hypodrift-targets-v1', 'task_id': s.TASK_ID,
               'states': s.STATES[:], 'sessions': list(range(1, 22)),
               'producer_receipt_sha256': 'a' * 64, 'cohort_receipt_sha256': 'b' * 64,
               'mice': mice, 'cells': cells}
    prediction = {'schema': 'hypodrift-prediction-v1', 'task_id': s.TASK_ID,
                  'states': s.STATES[:], 'sessions': list(range(10, 22)), 'cells': pred}
    comparator = {'schema': 'hypodrift-comparator-v1', 'reference_id': 'invented-fixed-reference',
                  'selection_receipt_sha256': 'c' * 64, 'prediction': copy.deepcopy(prediction)}
    for c in comparator['prediction']['cells']:
        c['log_rates'] = [1.0] * 36
    return prediction, targets, comparator


class ScientificControls(unittest.TestCase):
    def setUp(self):
        self.p, self.t, self.r = fixture()

    def grade(self):
        return s.score(self.p, self.t, self.r)

    def test_exact_integer_session_labels(self):
        self.p['sessions'][0] = 10.0
        with self.assertRaises(s.ContractError): s.admit_prediction(self.p)
        self.p['sessions'][0] = 10
        self.t['sessions'][0] = True
        with self.assertRaises(s.ContractError): s.admit_targets(self.t)
        self.t['sessions'][0] = 1.0
        with self.assertRaises(s.ContractError): s.admit_targets(self.t)
        self.t['sessions'][0] = 1
        self.r['prediction']['sessions'][0] = 10.0
        with self.assertRaises(s.ContractError): self.grade()

    def test_perfect_and_paired_full_denominators(self):
        out = self.grade()
        self.assertEqual((out['candidate_mse'], out['reference_mse'], out['paired_loss_reduction']), (0, 1, 1))
        self.assertEqual(out['cohort']['eligible_future_state_slots'], 59796)
        self.assertEqual(len(out['cell_support']), 1661)
        self.assertEqual(sum(x['eligible_neuron_denominator'] for x in out['mice']), 1661)

    def test_groups_equal_not_pooled_mice_or_neurons(self):
        groups = {m['mouse_id']: m['group'] for m in self.t['mice']}
        for c in self.p['cells']:
            c['log_rates'] = [float(list(s.GROUPS).index(groups[c['mouse_id']]))] * 36
        out = self.grade()
        self.assertEqual(out['candidate_mse'], 6)
        self.assertEqual([g['candidate_mse'] for g in out['groups']], [0, 1, 4, 9, 16])

    def test_equal_mice_inside_group(self):
        mid = self.t['mice'][0]['mouse_id']
        for c in self.p['cells']:
            if c['mouse_id'] == mid:
                c['log_rates'] = [1.0] * 36
        self.assertAlmostEqual(self.grade()['candidate_mse'], 1 / 30)

    def test_equal_sessions_and_states_not_exposure_or_slot_pooling(self):
        cell, pred = self.t['cells'][0], self.p['cells'][0]
        # Wake is observed once with error 4; NREM twelve times with error 0.
        for i in range(27, 63):
            if i % 3 == 2 or (i % 3 == 0 and i != 27):
                cell['valid_stable_seconds'][i] = None
                cell['event_counts'][i] = None
                cell['missing_reasons'][i] = 'invented missing state'
        cell['valid_stable_seconds'][27] = 2000.0
        pred['log_rates'][0] = 2.0
        out = self.grade()
        n = sum(c['mouse_id'] == cell['mouse_id'] for c in self.t['cells'])
        self.assertAlmostEqual(out['candidate_mse'], 2 / n / 6 / 5)
        self.assertEqual(out['cell_support'][0]['eligible_state_denominator'], 2)
        self.assertEqual(out['cell_support'][0]['states'][0]['denominator'], 1)

    def test_exact_twenty_seconds_and_units_and_baseline_exclusion(self):
        for c in self.t['cells']:
            c['event_counts'] = [10000] * 27 + [1] * 36
        for c in self.p['cells']:
            c['log_rates'] = [math.log1p(3)] * 36  # 1 event / 20 s = 3/min.
        out = self.grade()
        self.assertEqual(out['candidate_mse'], 0)
        self.assertEqual(out['cohort']['eligible_future_state_slots'], 59796)

    def test_underexposure_and_missing_are_not_zero_rate_targets(self):
        for c in self.t['cells']:
            c['valid_stable_seconds'][27] = 19.999
        self.p['cells'][0]['log_rates'][0] = 999.0
        out = self.grade()
        self.assertEqual(out['candidate_mse'], 0)
        self.assertEqual(out['cohort']['eligible_future_state_slots'], 59796 - 1661)

    def test_acute_and_chronic_reported_separately(self):
        for c in self.p['cells']:
            c['log_rates'] = [2.0] * 9 + [0.0] * 27
        out = self.grade()
        self.assertEqual(out['candidate_mse'], 1)
        self.assertEqual(out['phase_diagnostics']['acute_sessions10_12']['candidate_mse'], 4)
        self.assertEqual(out['phase_diagnostics']['chronic_sessions13_21']['candidate_mse'], 0)

    def test_empty_group_primary_undefined_full_support_retained(self):
        mids = {m['mouse_id'] for m in self.t['mice'] if m['group'] == 'LH-MCH'}
        for c in self.t['cells']:
            if c['mouse_id'] in mids:
                c['valid_stable_seconds'][27:] = [None] * 36
                c['event_counts'][27:] = [None] * 36
                c['missing_reasons'][27:] = ['unobserved'] * 36
        out = self.grade()
        self.assertFalse(out['primary_defined'])
        self.assertIsNone(out['candidate_mse'])
        self.assertEqual(len(out['mice']), 31)
        self.assertEqual(out['groups'][3]['eligible_mouse_denominator'], 0)

    def test_full_support_missing_duplicate_foreign_and_group_refusal(self):
        original = self.p['cells'][-1]
        self.p['cells'][-1] = self.p['cells'][0]
        with self.assertRaises(s.ContractError): self.grade()
        self.p['cells'][-1] = original
        self.p['cells'][-1]['neuron_id'] = 'foreign'
        with self.assertRaises(s.ContractError): self.grade()
        self.p['cells'].pop()
        with self.assertRaises(s.ContractError): self.grade()
        self.p, self.t, self.r = fixture()
        self.t['mice'][0]['group'] = 'LH-MCH'
        with self.assertRaises(s.ContractError): self.grade()

    def test_missing_nonfinite_negative_or_boolean_predictions_refuse(self):
        for bad in (None, math.nan, math.inf, -0.1, True):
            self.p['cells'][0]['log_rates'][0] = bad
            with self.subTest(bad=bad), self.assertRaises(s.ContractError): self.grade()
        self.p['cells'][0]['log_rates'] = [0] * 35
        with self.assertRaises(s.ContractError): self.grade()

    def test_target_count_exposure_missing_and_state_contracts(self):
        cell = self.t['cells'][0]
        for sec, count, why in ((None, 0, 'missing'), (None, None, None), (0, 1, None),
                                (20, True, None), (20, -1, None), (20, 1.5, None),
                                (-1, 0, None), (math.inf, 0, None)):
            cell['valid_stable_seconds'][27], cell['event_counts'][27], cell['missing_reasons'][27] = sec, count, why
            with self.subTest(sec=sec, count=count), self.assertRaises(s.ContractError): self.grade()
        self.t['states'] = ['wake', 'REM', 'NREM']
        with self.assertRaises(s.ContractError): self.grade()

    def test_comparator_identical_mask_and_support_required(self):
        self.r['prediction']['cells'][0]['neuron_id'] = 'invented-foreign'
        with self.assertRaises(s.ContractError): self.grade()
        self.r['prediction']['cells'][0] = copy.deepcopy(self.p['cells'][0])
        self.r['selection_receipt_sha256'] = 'unbound'
        with self.assertRaises(s.ContractError): self.grade()

    def test_representable_mean_no_overflow_and_unrepresentable_loss_refusal(self):
        self.assertEqual(s.mean([1e308, 1e308]), 1e308)
        self.p['cells'][0]['log_rates'][0] = 1e308
        with self.assertRaises(s.ContractError): self.grade()
        self.assertTrue(math.isfinite(s.target_log_rate(10 ** 400, 20)))


class InterfaceControls(unittest.TestCase):
    def test_required_trusted_identities_precede_private_opens(self):
        with patch.object(s.os, 'open', side_effect=AssertionError('unexpected open')):
            with self.assertRaises(s.ContractError): s.read_document('PRIVATE', 'bad')
        prediction, _, _ = fixture()
        calls = []
        def read(path, expected=None):
            calls.append(path)
            if path != 'P': raise AssertionError('trusted open before both identities admitted')
            return prediction, 'd' * 64
        with patch.object(s, 'read_document', read), self.assertRaises(s.ContractError):
            s.main(['--prediction', 'P', '--targets', 'PRIVATE', '--targets-sha256', 'a' * 64,
                    '--comparator', 'REFERENCE', '--comparator-sha256', 'bad', '--output', 'OUT'])
        self.assertEqual(calls, ['P'])

    def test_nonblocking_nofollow_regular_file_admission(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); regular = root / 'regular.json'; regular.write_bytes(b'{}')
            fifo = root / 'fifo'; os.mkfifo(fifo)
            link = root / 'link'; link.symlink_to(regular)
            for path in (fifo, link, root):
                with self.subTest(path=path.name), self.assertRaises(s.ContractError):
                    s.read_document(path, hashlib.sha256(b'{}').hexdigest())
            self.assertEqual(s.read_document(regular, hashlib.sha256(b'{}').hexdigest())[0], {})

    def test_strict_json_duplicate_nonfinite_and_pinned_read(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(s.ContractError): s.decode(raw)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'generated.json'; p.write_bytes(b'{}')
            with self.assertRaises(s.ContractError): s.read_document(p, '0' * 64)
            self.assertEqual(s.read_document(p, hashlib.sha256(b'{}').hexdigest())[0], {})

    def test_cli_rejects_public_submission_before_any_trusted_open(self):
        calls = []
        def read(path, expected=None):
            calls.append(path)
            return {}, '0' * 64
        with patch.object(s, 'read_document', read), self.assertRaises(s.ContractError):
            s.main(['--prediction', 'public', '--targets', 'PRIVATE', '--targets-sha256', 'a' * 64,
                    '--comparator', 'REFERENCE', '--comparator-sha256', 'b' * 64, '--output', 'OUT'])
        self.assertEqual(calls, ['public'])

    def test_cli_complete_dispatch_and_exclusive_output(self):
        p, t, r = fixture()
        docs = {'P': p, 'T': t, 'R': r}; calls = []
        def read(path, expected=None):
            calls.append((path, expected)); return docs[path], 'd' * 64
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'report.json'
            argv = ['--prediction', 'P', '--targets', 'T', '--targets-sha256', 'a' * 64,
                    '--comparator', 'R', '--comparator-sha256', 'b' * 64, '--output', str(output)]
            with patch.object(s, 'read_document', read): s.main(argv)
            report = json.loads(output.read_bytes())
            self.assertEqual(report['paired_loss_reduction'], 1)
            self.assertEqual(calls, [('P', None), ('T', 'a' * 64), ('R', 'b' * 64)])
            with patch.object(s, 'read_document', read), self.assertRaises(FileExistsError): s.main(argv)


if __name__ == '__main__':
    unittest.main()
