"""Generated controls only; no authentic NSD images, labels or model outputs."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bounded_panel', ROOT / 'evaluator.py')
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
core = ev.core
H = 'a' * 64


def fixtures(folder):
    # Deliberately unequal development cohorts: a pooled image mean is wrong.
    samples = [{'sample_id': f's{s}-{i}', 'subject_id': str(s), 'stimulus_id': str(i),
                'session_ids': ['generated']} for s, n in [(1, 3), (2, 2)] for i in range(n)]
    extraction = {'pixel_policy': 'source256_then425_rgb_chw_01', 'ssim_policy': 'explicit_2d_gaussian_v1',
                  'preprocessing_sha256': H, **{f'{f}_extractor_sha256': H for f in core.FEATURES}}
    protocol = {'task_id': core.TASK_ID, 'policy': 'prospective-prepared-panel-v1', 'scope': 'declared_subjects',
                'protected_pool_receipt_sha256': H, 'exposure_ledger_sha256': H, 'rights_review_sha256': H,
                'generation_policy': 'one_sample_per_subject_stimulus', 'samples': samples, 'extraction': extraction}
    rng = np.random.default_rng(30343)
    ramp = np.tile(np.linspace(.1, .9, 425, dtype=np.float32), (425, 1))
    pixels = np.stack([np.stack([ramp, ramp.T, ramp]) for _ in samples])
    real = {'pixels425': pixels, **{key: rng.normal(size=(5, 7)).astype(np.float32) for key in core.FEATURES}}
    prediction = {key: (value if key == 'pixels425' else value[[2, 0, 1, 4, 3]]) for key, value in real.items()}
    def bundle(name, arrays, order=None):
        order = list(range(5)) if order is None else order
        members = {}
        for key, array in arrays.items():
            path = folder / f'{name}-{key}.npy'
            np.save(path, array[order], allow_pickle=False)
            members[key] = {'path': path.name, 'sha256': ev.sha256(path)}
        return {'format': 'npy-members-v1', 'arrays': members,
                'samples': [copy.deepcopy(samples[i]) for i in order], 'extraction': copy.deepcopy(extraction)}
    reference = bundle('real', real)
    # Nontrivial cross-subject row permutation tests sample identity, not order.
    shifted = bundle('shifted', prediction, [4, 2, 0, 3, 1])
    conditions = []
    for role in ('pretrained', 'target_only', 'neural_free'):
        conditions.append({'role': role, 'name': role, 'bundle': copy.deepcopy(reference if role == 'pretrained' else shifted),
            'target_training_membership_sha256': H, 'diffusion_prior_sha256': H, 'tuning_budget_sha256': H,
            'generation_budget_sha256': H, 'encoder_initialization_sha256': H, 'checkpoint_sha256': H,
            'initialization_exposure_sha256': H, 'encoder_route': 'released_encoder',
            'image_pretraining_route': 'released_multi_subject_checkpoint' if role == 'pretrained' else 'none',
            'neural_input': role != 'neural_free'})
    return {'protocol': protocol, 'reference': reference, 'conditions': conditions}, real, prediction


class GuardedFeatures:
    def __init__(self, arrays):
        self.arrays = arrays
        self.requests = []

    def read(self, key, rows):
        if len(rows) > ev.FEATURE_BLOCK:
            raise AssertionError('unbounded feature materialization')
        self.requests.extend(rows)
        return self.arrays[key][rows]


class ArithmeticControls(unittest.TestCase):
    def test_all982_distractors_and_cross_block_ties(self):
        # First and final images tie; every other distractor is anticorrelated.
        # A convenient first-block-only implementation would incorrectly give 1.
        real = np.tile([-1., 1., 0.], (982, 1))
        real[[0, 981]] = [1., -1., 0.]
        a, b = GuardedFeatures({'clip': real}), GuardedFeatures({'clip': real})
        score = ev.identification(a, b, 'clip', list(range(982)))
        self.assertAlmostEqual(score[0], 980 / 981)
        self.assertAlmostEqual(score[981], 980 / 981)
        np.testing.assert_allclose(score[1:981], 2 / 981, rtol=0, atol=0)
        self.assertEqual(set(a.requests), set(range(982)))

    def test_independent_scalar_pearson_oracle_and_axis(self):
        # Scalar centering and Python sums are independent of block BLAS layout.
        rng = np.random.default_rng(719)
        r, p = rng.normal(size=(35, 9)), rng.normal(size=(35, 9))
        def corr(x, y):
            xc = [float(v) - sum(x) / len(x) for v in x]
            yc = [float(v) - sum(y) / len(y) for v in y]
            return sum(a*b for a, b in zip(xc, yc)) / (sum(a*a for a in xc) * sum(b*b for b in yc))**.5
        expected = [sum(corr(r[i], p[j]) < corr(r[j], p[j]) for i in range(35) if i != j) / 34 for j in range(35)]
        np.testing.assert_array_equal(ev.identification(GuardedFeatures({'clip': r}), GuardedFeatures({'clip': p}),
                                                      'clip', list(range(35))), expected)

    def test_undefined_and_nonfinite_feature_rows_rejected(self):
        for array in (np.ones((17, 4)), np.full((17, 4), np.nan), np.full((17, 4), np.inf)):
            with self.assertRaises(ValidationError):
                ev.identification(GuardedFeatures({'clip': array}), GuardedFeatures({'clip': array}), 'clip', list(range(17)))


ValidationError = ev.ValidationError


class PanelControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.manifest, cls.real, cls.prediction = fixtures(cls.folder)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_complete_panel_parity_identity_alignment_and_macro(self):
        observed = ev.evaluate(self.manifest, self.folder)
        for role, prediction in [('pretrained', self.real), ('target_only', self.prediction), ('neural_free', self.prediction)]:
            subject_means = []
            for subject, indices in [('1', [0, 1, 2]), ('2', [3, 4])]:
                expected = core.metric_panel({k: v[indices] for k, v in self.real.items()},
                                             {k: v[indices] for k, v in prediction.items()})
                actual = observed['conditions'][role]['by_subject'][subject]
                for key, values in expected.items():
                    np.testing.assert_allclose(actual['per_stimulus'][key], values, rtol=0, atol=1e-14)
                subject_means.append({k: float(v.mean()) for k, v in expected.items()})
            for key in core.METRICS:
                self.assertAlmostEqual(observed['conditions'][role]['macro_subject_mean'][key],
                                       (subject_means[0][key] + subject_means[1][key]) / 2)
        self.assertEqual(set(observed['directions']), set(core.METRICS))
        self.assertEqual(observed['directions']['effnet'], 'lower')
        self.assertFalse(observed['research_qualified'])
        self.assertFalse(observed['native_equivalence_verified'])

    def test_mapping_and_reads_are_bounded(self):
        r = ev.MappedBundle(self.folder, self.manifest['reference'], self.manifest['protocol']['samples'],
                            self.manifest['protocol']['extraction'])
        try:
            self.assertTrue(all(isinstance(v, ev.ArrayLayout) for v in r.arrays.values()))
            # Copied values remain valid after the per-read mapping is closed.
            np.testing.assert_array_equal(r.read('clip', [0]), self.real['clip'][[0]])
            with self.assertRaises(ValidationError): r.read('pixels425', [0, 1])
            original = r.read
            def bounded(key, rows):
                self.assertLessEqual(len(rows), 1 if key == 'pixels425' else ev.FEATURE_BLOCK)
                return original(key, rows)
            with patch.object(r, 'read', side_effect=bounded):
                ev.metric_panel(r, r, [0, 1, 2])
        finally:
            r.close()
        self.assertEqual(r.arrays, {})

    def test_wrong_identity_hash_population_and_recipe_rejected(self):
        for fault in ('hash', 'identity', 'missing', 'duplicate', 'recipe', 'paper'):
            m = copy.deepcopy(self.manifest)
            b = m['reference']
            if fault == 'hash': b['arrays']['clip']['sha256'] = '0' * 64
            if fault == 'identity': b['samples'][0]['stimulus_id'] = 'other'
            if fault == 'missing': b['samples'].pop()
            if fault == 'duplicate': b['samples'][1] = b['samples'][0]
            if fault == 'recipe': b['extraction']['ssim_policy'] = 'native_claim'
            if fault == 'paper': m['protocol']['scope'] = 'paper_four_subjects'
            with self.subTest(fault=fault), self.assertRaises(ValidationError):
                ev.evaluate(m, self.folder)

    def test_comparator_policy_preserved(self):
        for field in ('target_training_membership_sha256', 'diffusion_prior_sha256', 'tuning_budget_sha256',
                      'generation_budget_sha256', 'encoder_initialization_sha256', 'encoder_route', 'image_pretraining_route', 'neural_input'):
            m = copy.deepcopy(self.manifest)
            c = m['conditions'][1]
            c[field] = {'encoder_route': 'random_init', 'image_pretraining_route': 'released_multi_subject_checkpoint',
                        'neural_input': False}.get(field, 'b' * 64)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ev.evaluate(m, self.folder)

    def test_same_size_changed_array_detected_after_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / 'changed.npy'
            np.save(path, self.real['clip'])
            spec = copy.deepcopy(self.manifest['reference'])
            # Other paths remain valid by converting them to absolute paths.
            for member in spec['arrays'].values(): member['path'] = str(self.folder / member['path'])
            spec['arrays']['clip'] = {'path': str(path), 'sha256': ev.sha256(path)}
            r = ev.MappedBundle(folder, spec, self.manifest['protocol']['samples'], self.manifest['protocol']['extraction'])
            try:
                changed = self.real['clip'].copy(); changed[0, 0] += 1
                np.save(path, changed)
                with self.assertRaises(ValidationError): r.verify_unchanged()
            finally:
                r.close()

    def test_cli_and_no_overwrite(self):
        path, output = self.folder / 'manifest.json', self.folder / 'report.json'
        path.write_text(json.dumps(self.manifest))
        command = [sys.executable, '-B', str(ROOT / 'evaluator.py'), str(path), '--output', str(output)]
        run = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report['input_manifest_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        before = output.read_bytes()
        again = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(again.returncode, 2)
        self.assertEqual(before, output.read_bytes())


if __name__ == '__main__':
    unittest.main()
