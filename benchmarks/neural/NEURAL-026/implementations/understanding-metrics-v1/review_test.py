"""Independent generated numerical review; no authentic neural data or model runs."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('neural026_reviewed_score', HERE / 'score.py')
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)
MICE = ('cfa17', 'cfa19', 'cfa20', 'cfa22', 'cfa24')
AREAS = ('M1', 'S1')


def digest(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def fixture(folder, *, legacy=False, candidate_offset=0.0):
    """All50 cases, unequal fold counts and cell scales; engineered only."""
    folder = Path(folder)
    folder.mkdir()
    design = {'schema': 'neural026_design_v1', 'cases': []}
    private, submitted, records = {}, {}, []
    # Thirty query trials once per mouse/area; each role has unequal fold sizes.
    partitions = [list(range(a, b)) for a, b in [(1, 5), (5, 10), (10, 16), (16, 23), (23, 31)]]
    for mi, mouse in enumerate(MICE):
        for ai, area in enumerate(AREAS):
            for fold, ids in enumerate(partitions):
                cid = f'{mouse}_{area}_fold{fold}'
                row = {'case_id': cid, 'mouse': mouse, 'area': area, 'fold': fold,
                       'train_id': sorted(set(range(1, 31)) - set(ids)), 'query_id': ids,
                       'matched_counts': {'1': 15, '2': 15}}
                design['cases'].append(row)
                trials = np.asarray(ids, dtype=np.int64)
                # Scale differs by mouse, area and joint, and shifts by fold;
                # pooled-vs-fold variance and flattened-vs-biological weighting differ.
                t = np.arange(51, dtype=np.float64)[None, :, None] / 51.0
                j = np.arange(24, dtype=np.float64)[None, None, :]
                scale = 0.25 + 0.07 * mi + 0.03 * ai + j / 24.0
                y = (100 * mi + 20 * ai + trials[:, None, None] + t) * scale
                nuisance_error = 2.0 + mi + 0.3 * ai + j / 12.0
                neural_error = 0.4 + 0.15 * mi + 0.2 * ai + fold / 3.0 + j / 60.0 + candidate_offset
                neural = y + neural_error
                reference = {'trial_id': trials, 'nuisance': y + nuisance_error,
                             'neural': y + 0.75 * nuisance_error,
                             'shifted': y + 1.1 * nuisance_error}
                values = {'trial_id': trials, 'neural': neural}
                if legacy:
                    values.update(nuisance=y + 1.0, shifted=y + 3.0)
                path = folder / (cid + '.npz')
                np.savez(path, **values)
                records.append({'case_id': cid, 'file': path.name, **digest(path)})
                private[cid] = ({'trial_id': trials, 'y': y}, reference)
                submitted[cid] = values
    manifest = {'schema': score.LEGACY_SCHEMA if legacy else score.NEW_SCHEMA, 'cases': records}
    (folder / 'submission.json').write_text(json.dumps(manifest))
    return design, private, submitted


def replace_case(folder, cid, values):
    folder = Path(folder)
    path = folder / (cid + '.npz')
    np.savez(path, **values)
    manifest = json.loads((folder / 'submission.json').read_text())
    for row in manifest['cases']:
        if row['case_id'] == cid:
            row.update(digest(path))
    (folder / 'submission.json').write_text(json.dumps(manifest))


def independent_oracle(design, private, submitted):
    # Pool raw target samples directly; never call the scorer's moments/scoring.
    cell_means = []
    per_mouse = []
    for mouse in MICE:
        by_area = []
        for area in AREAS:
            rows = [c for c in design['cases'] if c['mouse'] == mouse and c['area'] == area]
            y = np.concatenate([private[c['case_id']][0]['y'].reshape(-1, 24) for c in rows])
            pred = np.concatenate([submitted[c['case_id']]['neural'].reshape(-1, 24) for c in rows])
            ref = np.concatenate([private[c['case_id']][1]['nuisance'].reshape(-1, 24) for c in rows])
            values = []
            for joint in range(24):
                truth = y[:, joint].tolist()
                mu = math.fsum(truth) / len(truth)
                sst = math.fsum((v - mu) ** 2 for v in truth)
                reference_sse = math.fsum((float(v) - target) ** 2 for v, target in zip(ref[:, joint], truth))
                candidate_sse = math.fsum((float(v) - target) ** 2 for v, target in zip(pred[:, joint], truth))
                values.append((reference_sse - candidate_sse) / sst)
            by_area.append(math.fsum(values) / 24)
            cell_means.append(math.fsum(values) / 24)
        per_mouse.append(math.fsum(by_area) / 2)
    return math.fsum(per_mouse) / 5, per_mouse, cell_means


class IndependentNumericReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_direct_oracle_unequal_folds_and_biological_weighting(self):
        design, private, submitted = fixture(self.root / 'candidate')
        result = score.evaluate(self.root / 'candidate', design, lambda cid: private[cid])
        expected, by_mouse, _ = independent_oracle(design, private, submitted)
        self.assertAlmostEqual(result['primary_value'], expected, places=12)
        for actual, value in zip(result['per_mouse'], by_mouse):
            self.assertAlmostEqual(actual['incremental_ev'], value, places=12)
        self.assertEqual(result['complete_cases'], 50)
        self.assertEqual(result['independent_mice'], 5)

    def test_candidate_nuisance_and_shifted_cannot_manipulate_primary(self):
        folder = self.root / 'candidate'
        design, private, submitted = fixture(folder, legacy=True)
        before = score.evaluate(folder, design, lambda cid: private[cid])
        for cid, values in submitted.items():
            values['nuisance'] = values['nuisance'] + 100.0
            values['shifted'] = values['shifted'] - 75.0
            replace_case(folder, cid, values)
        after = score.evaluate(folder, design, lambda cid: private[cid])
        self.assertEqual(before['primary_value'], after['primary_value'])
        self.assertFalse(after['candidate_nuisance_used'])
        self.assertFalse(after['candidate_shifted_used'])

    def test_negative_gain_is_retained(self):
        design, private, submitted = fixture(self.root / 'candidate', candidate_offset=20.0)
        result = score.evaluate(self.root / 'candidate', design, lambda cid: private[cid])
        expected, _, _ = independent_oracle(design, private, submitted)
        self.assertLess(result['primary_value'], 0)
        self.assertAlmostEqual(result['primary_value'], expected, places=12)

    def test_gain_above_one_is_not_clipped(self):
        design, private, submitted = fixture(self.root / 'candidate')
        for target, ref in private.values():
            ref['nuisance'] = target['y'] + 100.0
        result = score.evaluate(self.root / 'candidate', design, lambda cid: private[cid])
        expected, _, _ = independent_oracle(design, private, submitted)
        self.assertGreater(result['primary_value'], 1)
        self.assertAlmostEqual(result['primary_value'], expected, places=10)

    def test_nonzero_squared_error_underflow_cannot_be_reported_as_perfect(self):
        folder = self.root / 'candidate'
        design, private, submitted = fixture(folder)
        for cid, values in submitted.items():
            values['neural'] = private[cid][0]['y'].copy()
        cid = design['cases'][-1]['case_id']
        private[cid][0]['y'][0, 0, 0] = 0.0
        submitted[cid]['neural'][0, 0, 0] = 1e-170
        # Positive in exact arithmetic but smaller than float64's least subnormal
        # after squaring; accepting it as zero would falsely report perfect fit.
        from decimal import Decimal
        self.assertGreater(Decimal('1e-170') ** 2, 0)
        for key, values in submitted.items():
            replace_case(folder, key, values)
        with self.assertRaisesRegex(FloatingPointError, 'underflow'):
            score.evaluate(folder, design, lambda key: private[key])

    def test_last_case_extra_key_rejected_before_any_private_callback(self):
        folder = self.root / 'candidate'
        design, private, submitted = fixture(folder)
        cid = design['cases'][-1]['case_id']
        values = dict(submitted[cid], leaked=np.ones((1,), dtype=np.float64))
        replace_case(folder, cid, values)
        calls = []
        with self.assertRaises(ValueError):
            score.evaluate(folder, design, lambda key: calls.append(key) or private[key])
        self.assertEqual(calls, [])

    def test_last_case_reordered_trial_ids_rejected_before_private_callback(self):
        folder = self.root / 'candidate'
        design, private, submitted = fixture(folder)
        cid = design['cases'][-1]['case_id']
        values = dict(submitted[cid], trial_id=submitted[cid]['trial_id'][::-1])
        replace_case(folder, cid, values)
        calls = []
        with self.assertRaises(ValueError):
            score.evaluate(folder, design, lambda key: calls.append(key) or private[key])
        self.assertEqual(calls, [])

    def test_one_constant_joint_refuses_complete_primary(self):
        design, private, _ = fixture(self.root / 'candidate')
        for row in design['cases']:
            if row['mouse'] == MICE[-1] and row['area'] == 'S1':
                private[row['case_id']][0]['y'][:, :, -1] = 7.0
        with self.assertRaisesRegex(ValueError, 'positive pooled variance'):
            score.evaluate(self.root / 'candidate', design, lambda cid: private[cid])

    def test_reference_id_mismatch_refuses_score(self):
        design, private, _ = fixture(self.root / 'candidate')
        cid = design['cases'][-1]['case_id']
        private[cid][1]['trial_id'] = private[cid][1]['trial_id'][::-1]
        with self.assertRaisesRegex(ValueError, 'query ID'):
            score.evaluate(self.root / 'candidate', design, lambda cid: private[cid])

    def test_duplicate_fold_support_rejected_before_private_callback(self):
        design, private, _ = fixture(self.root / 'candidate')
        corrupt = copy.deepcopy(design)
        corrupt['cases'][1]['query_id'] = corrupt['cases'][0]['query_id']
        calls = []
        with self.assertRaises(ValueError):
            score.evaluate(self.root / 'candidate', corrupt, lambda cid: calls.append(cid) or private[cid])
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
