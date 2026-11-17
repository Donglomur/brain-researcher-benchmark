"""Generated engineering controls; independent scalar metric oracles, no NSD data."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mindeye_component', ROOT / 'evaluator.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def reference():
    ids = [str(i) for i in range(1000)]
    return dict(task_id=e.TASK, contract_sha256=e.CONTRACT_SHA256,
                code_revision=e.CODE_REVISION, dataset_revision=e.DATA_REVISION,
                subject=1, image_ids=ids, retrieval_pools=e.freeze_pools(ids),
                feature_space='openclip:ViT-bigG-14:laion2b_s39b_b160k:256x1664-tokens',
                image_features_sha256='1'*64, population_manifest_sha256='2'*64,
                feature_extraction_receipt_sha256='3'*64)


def ledger():
    return dict(target_subject=1, calibration_session_zero_based=0,
                protected_sessions_zero_based=[1, 2], calibration_image_ids=['a', 'b'],
                protected_image_ids=['c', 'd'], checkpoint_pretraining_subjects=list(range(2, 9)),
                checkpoint_pretraining_image_ids=['a', 'c'], checkpoint_sha256='a'*64,
                image_model_resources_sha256='b'*64, calibration_trial_manifest_sha256='c'*64,
                protected_trial_manifest_sha256='d'*64, training_regime='released_shared_adaptation')


class Metrics(unittest.TestCase):
    def test_independent_asymmetric_scalar_oracle(self):
        # Independently specified worker oracle: row and column winners differ.
        images = np.eye(3)
        brain = np.array([[1, .1, .1], [1, .8, .1], [.1, .1, 1]])
        actual = e.retrieval_draw(brain, images)
        self.assertAlmostEqual(actual['image_retrieval'], 2/3)
        self.assertEqual(actual['brain_retrieval'], 1)
        transposed = e.retrieval_draw(images, brain)
        self.assertEqual(transposed['image_retrieval'], 1)
        self.assertAlmostEqual(transposed['brain_retrieval'], 2/3)

    def test_complete_30_by_300_kernel_and_draw_uncertainty(self):
        # Independent reviewer's planar fixture plus orthogonal distractors.
        b, i = np.zeros((300, 299)), np.zeros((300, 299))
        for j, (ba, ia) in enumerate(zip([0, 50, 70], [0, 20, 90])):
            b[j, :2] = [np.cos(np.deg2rad(ba)), np.sin(np.deg2rad(ba))]
            i[j, :2] = [np.cos(np.deg2rad(ia)), np.sin(np.deg2rad(ia))]
        for j in range(3, 300):
            b[j, j-1] = i[j, j-1] = 1
        ids = list(map(str, range(300)))
        result = e.score_aligned_features(ids, [ids.copy() for _ in range(30)], b, i)
        self.assertAlmostEqual(result['image_retrieval']['mean'], 1)
        self.assertAlmostEqual(result['brain_retrieval']['mean'], 299/300)
        self.assertAlmostEqual(result['brain_retrieval']['draw_sem'], 0)
        # population SD, not sample SD; normal interval not clipped.
        summary = e._summary([0, 1])
        self.assertAlmostEqual(summary['draw_sem'], .5/np.sqrt(2))
        self.assertLess(summary['draw_normal_95_interval'][0], 0)

    def test_pearson_strict_ties_and_column_semantics(self):
        self.assertEqual(e.reconstruction_identification(np.eye(3), np.eye(3))['mean'], 1)
        self.assertEqual(e.reconstruction_identification(np.eye(3), np.roll(np.eye(3), 1, axis=0))['mean'], 0)
        real = np.array([[3, 0, 1, 2], [1, 0, 2, 3], [0, 3, 2, 1]])
        pred = np.array([[2, 1, 3, 0], [0, 1, 3, 2], [3, 0, 2, 1]])
        from statistics import correlation
        expected = [sum(correlation(real[j], pred[j]) > correlation(real[k], pred[j])
                        for k in range(3) if k != j)/2 for j in range(3)]
        np.testing.assert_allclose(e.reconstruction_identification(real, pred)['per_image'], expected)
        self.assertAlmostEqual(e.paired_pearson(real, real * 3 + 4)['mean'], 1)

    def test_notebook_orientation_differs_from_paper_prose(self):
        real = [[-1,-3,3,-1,-2],[-2,2,2,0,-2],[3,-3,-3,-2,-2]]
        pred = [[3,-2,2,0,-1],[-3,2,-1,-1,3],[1,-1,0,1,-3]]
        self.assertEqual(e.reconstruction_identification(real, pred)['mean'], 1)
        self.assertAlmostEqual(e.reconstruction_identification(pred, real)['mean'], 2/3)

    def test_invalid_similarity_fails_closed(self):
        for bad in [np.zeros((3, 3)), np.full((3, 3), np.nan), np.full((3, 3), np.inf)]:
            with self.assertRaises(ValueError): e.retrieval_draw(bad, np.eye(3))
        with self.assertRaisesRegex(ValueError, 'tied maximum'):
            e.retrieval_draw(np.ones((3, 3)), np.eye(3))
        with self.assertRaises(ValueError): e.reconstruction_identification(np.ones((3, 3)), np.eye(3))
        with self.assertRaises(ValueError): e.retrieval_draw(np.eye(2), np.eye(3))

    def test_repeat_outputs_not_mean_input_and_two_repeat_weight(self):
        ids, features = e.aggregate_repeat_embeddings([5, 2, 5, 8, 8, 8],
            [[1, 2], [7, 8], [4, 5], [2, 3], [4, 5], [6, 7]])
        self.assertEqual(ids, [2, 5, 8])
        np.testing.assert_allclose(features, [[7, 8], [2, 3], [4, 5]])
        with self.assertRaises(ValueError): e.aggregate_repeat_embeddings([1]*4, np.eye(4))


class Boundary(unittest.TestCase):
    def test_reference_requires_full_paper_population_and_pinned_source(self):
        ref = reference()
        self.assertEqual(len(e.validate_reference(ref)), 1000)
        for key, value in [('subject', 3), ('subject', True), ('image_ids', ref['image_ids'][:999]),
                           ('code_revision', 'main'), ('feature_extraction_receipt_sha256', None)]:
            altered = copy.deepcopy(ref); altered[key] = value
            with self.assertRaises(ValueError): e.validate_reference(altered)

    def test_pool_pinning_identity_and_bad_draws(self):
        ref = reference()
        self.assertEqual(ref['retrieval_pools'], e.freeze_pools(ref['image_ids']))
        self.assertNotEqual(ref['retrieval_pools'], e.freeze_pools(ref['image_ids'], 43))
        # Local RNG must not change global sampling state.
        np.random.seed(17); expected = np.random.random()
        np.random.seed(17); e.freeze_pools(ref['image_ids']); self.assertEqual(np.random.random(), expected)
        for bad in [ref['retrieval_pools'][:29], [['x']*300]*30, [ref['image_ids'][:301]]*30]:
            with self.assertRaises(ValueError): e.validate_pools(ref['image_ids'], bad)

    def test_candidate_identity_and_native_feature_boundary(self):
        ref = reference()
        candidate = dict(reference_manifest_digest=e.digest(ref), image_ids=ref['image_ids'],
                         subject=1, feature_space=ref['feature_space'], checkpoint_sha256='a'*64,
                         exposure_ledger_sha256='b'*64, brain_features_sha256='c'*64)
        # Low dimensional vectors are valid numerical controls, never native packets.
        with self.assertRaisesRegex(ValueError, '256\\*1664'):
            e.evaluate(ref, candidate, np.ones((1000, 2)), np.ones((1000, 2)))
        candidate['image_ids'] = ref['image_ids'][:-1] + ['absent']
        with self.assertRaisesRegex(ValueError, 'population'):
            e.evaluate(ref, candidate, np.ones((1000, 2)), np.ones((1000, 2)))
        candidate['reference_manifest_digest'] = 'a'*64
        with self.assertRaisesRegex(ValueError, 'bound'):
            e.evaluate(ref, candidate, np.ones((1000, 2)), np.ones((1000, 2)))

    def test_exposure_overlap_and_first_session(self):
        result = e.exposure_audit(ledger())
        self.assertEqual(result['checkpoint_test_image_overlap'], ['c'])
        self.assertFalse(result['scientific_qualification'])
        x = ledger(); x['checkpoint_pretraining_image_ids'] = None
        self.assertIsNone(e.exposure_audit(x)['checkpoint_test_image_overlap'])
        for key, value in [('calibration_session_zero_based', 1), ('calibration_session_zero_based', False),
                           ('protected_sessions_zero_based', [0]), ('calibration_image_ids', ['c']),
                           ('checkpoint_pretraining_subjects', list(range(1, 8)))]:
            x = ledger(); x[key] = value
            with self.assertRaises(ValueError): e.exposure_audit(x)

    def test_shared_vs_single_exposure_never_total_equivalence(self):
        baseline = ledger(); baseline.update(training_regime='single_subject_from_scratch',
            checkpoint_pretraining_subjects=[], checkpoint_pretraining_image_ids=[])
        result = e.compare_exposure(ledger(), baseline)
        self.assertFalse(result['equal_total_neural_exposure_verified'])
        missing = ledger(); del missing['checkpoint_pretraining_image_ids']
        with self.assertRaises(ValueError): e.exposure_audit(missing)
        wrong = copy.deepcopy(baseline); wrong['checkpoint_pretraining_image_ids'] = ['c']
        with self.assertRaises(ValueError): e.exposure_audit(wrong)
        unequal = copy.deepcopy(baseline); unequal['calibration_trial_manifest_sha256'] = 'f'*64
        with self.assertRaises(ValueError): e.compare_exposure(ledger(), unequal)
        baseline['image_model_resources_sha256'] = 'c'*64
        with self.assertRaises(ValueError): e.compare_exposure(ledger(), baseline)

    def test_comparison_pool_lock(self):
        a = dict(reference_manifest_digest='a', pool_digest='b', subject=1,
                 population_manifest_sha256='c', metrics={name: e._summary([1]*30)
                   for name in ['image_retrieval', 'brain_retrieval']})
        self.assertEqual(e.paired_comparison(a, a)['candidate_minus_baseline']['image_retrieval']['mean'], 0)
        b = copy.deepcopy(a); b['pool_digest'] = 'wrong'
        with self.assertRaises(ValueError): e.paired_comparison(a, b)

    def test_array_hash_and_cli_reference_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'features.npy'; np.save(p, np.eye(3))
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            np.testing.assert_equal(e._load_array(p, sha), np.eye(3))
            with self.assertRaises(ValueError): e._load_array(p, '0'*64)
            r = Path(folder) / 'ref.json'; r.write_text(json.dumps(reference()))
            proc = subprocess.run([sys.executable, str(ROOT/'evaluator.py'), 'score',
                '--reference', str(r), '--reference-sha256', '0'*64, '--candidate', str(r),
                '--image-features', str(p), '--brain-features', str(p)], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('trusted reference SHA-256 mismatch', proc.stderr)

    def test_required_assets(self):
        assets = e.required_adaptation_assets(7)
        self.assertIn('wds/subj07/train/0.tar', assets['required_paths'])
        self.assertIn('betas_all_subj07_fp32_renorm.hdf5', assets['required_paths'])
        self.assertFalse(assets['full_native_inference_manifest_complete'])

if __name__ == '__main__': unittest.main()
