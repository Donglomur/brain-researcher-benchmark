"""Independent generated controls; no NSD data, model weights or scientific runs.

Full-gallery dispatch tests replace only expensive selection/pixel operations and
state that limitation explicitly. Numerical operations have separate real tests.
"""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest import mock

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / 'panel.py'
spec = importlib.util.spec_from_file_location('mindbridge_panel_under_review', MODULE)
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
native_spec = importlib.util.spec_from_file_location('mindbridge_native_features_under_review', MODULE.with_name('native_features.py'))
native = importlib.util.module_from_spec(native_spec)
native_spec.loader.exec_module(native)
H = 'a' * 64
SSIM_VERSION = 'generated-ssim-contract-only'
WORKING_BYTES = 256 * 1024**2


def fake_skimage(value=.375):
    """Only exercise source call contract; this is not SSIM numerical evidence."""
    package = ModuleType('skimage'); package.__version__ = SSIM_VERSION
    color = ModuleType('skimage.color'); color.rgb2gray = lambda a: a.mean(axis=-1)
    metrics = ModuleType('skimage.metrics'); metrics.structural_similarity = mock.Mock(return_value=value)
    return {'skimage': package, 'skimage.color': color, 'skimage.metrics': metrics}, metrics.structural_similarity


def descriptor(path, body=None):
    return {'path': path, 'bytes': 8 if body is None else len(body),
            'sha256': H if body is None else hashlib.sha256(body).hexdigest()}


def fixture(count=3, source_kind='generated_engineering_control'):
    """Exact budget counts; generated feature vectors, never authentic embeddings."""
    image_ids = [f'test:{i:04}' for i in range(count)]
    calibration = [f'cal:{i:04}' for i in range(4000)]
    arrays, images = {}, []
    for i, ident in enumerate(image_ids):
        v = np.array([i % 7 + 1, -(i % 11), i % 3 + 4, -i % 5], dtype=np.float32)
        def payload(prefix, vector):
            out = {'image_sha256': hashlib.sha256(prefix.encode()).hexdigest(),
                   'extraction_receipt_sha256': H,
                   'selection': descriptor(prefix + '/selection.npy'),
                   'rgb425': descriptor(prefix + '/rgb.npy'), 'features': {}}
            arrays[out['selection']['path']] = np.array([1., 2.], np.float32)
            arrays[out['rgb425']['path']] = np.array([1., 2.], np.float32)
            for metric in panel.FEATURES:
                out['features'][metric] = descriptor(prefix + '/' + metric + '.npy')
                arrays[out['features'][metric]['path']] = vector.copy()
            return out
        target = payload(f'target/{i}', v)
        # The index chosen by the dispatch control is3; index0 would invert every
        # feature. This catches a separately selected or fixed-index metric path.
        candidates = [payload(f'candidate/{i}/{k}', v if k == 3 else -v) for k in range(8)]
        images.append({'image_id': ident, 'target': target, 'candidates': candidates})
    p = {'schema': panel.SCHEMA, 'task_id': panel.TASK, 'source_kind': source_kind,
         'test_image_ids': image_ids, 'target_subject': 7, 'source_subjects': [1, 2, 5],
         'skimage_version': SSIM_VERSION, 'feature_pipeline_sha256': H,
         'image_prior_sha256': H,
         'calibration': {str(n): calibration[:n] for n in panel.BUDGETS}, 'rows': []}
    for budget in panel.BUDGETS:
        for arm in panel.ARMS:
            p['rows'].append({'arm': arm, 'budget': budget, 'freeze_receipt_sha256': H,
                'generation_frozen_before_target_selection': True, 'images': copy.deepcopy(images)})
    return p, arrays


def dispatch(packet, arrays):
    """Mock expensive image/selection operations; run all feature metrics."""
    with mock.patch.object(panel, 'select_best_of_eight', return_value=SimpleNamespace(index=3)), \
         mock.patch.object(panel, 'image_pair_metrics', return_value={'pixcorr': .75, 'ssim': .5}):
        return panel.evaluate_panel(packet, lambda d: arrays[d['path']], max_working_bytes=WORKING_BYTES)


class MetricTests(unittest.TestCase):
    def test_asymmetric_predicted_column_identification(self):
        r = np.array([[1, 2, 4, 8], [2, -1, 3, 0], [0, 3, 1, -2]], np.float32)
        p = np.array([[1, 2, 3, 4], [3, 0, 4, 1], [4, 1, 0, 3]], np.float32)
        for metric in panel.FEATURES[:4]:
            np.testing.assert_array_equal(panel.feature_scores(r, p, metric), [1., 1., 0.])

    def test_strict_ties_receive_zero(self):
        a = np.array([[1, 2, 3]] * 3, np.float32)
        np.testing.assert_array_equal(panel.feature_scores(a, a, 'clip'), [0., 0., 0.])

    def test_identification_requires_source_float32(self):
        a = np.array([[1, 2, 4], [2, -1, 0]], np.float64)
        with self.assertRaises(panel.PanelError): panel.feature_scores(a, a, 'clip')

    def test_distance_retains_anti_correlation_endpoint(self):
        a = np.array([[1, 2, 4], [2, -1, 0]], np.float32)
        for metric in ('effnet_b', 'swav'):
            np.testing.assert_allclose(panel.feature_scores(a, -a, metric), [2., 2.], atol=2e-7)

    def test_undefined_shape_dtype_and_nonfinite_features_refused(self):
        good = np.array([[1, 2, 4], [2, -1, 0]], np.float32)
        for bad in (np.ones_like(good), good[:1], good.astype(np.int64), good[:, :2],
                    np.array([[1, 2, 4], [np.nan, -1, 0]], np.float32)):
            with self.subTest(shape=bad.shape, dtype=str(bad.dtype)), self.assertRaises(panel.PanelError):
                panel.feature_scores(good, bad, 'clip')

    def test_actual_best_of_eight_uses_first_maximum(self):
        target = np.arange(257 * 768, dtype=np.float32).reshape(257, 768) + 1
        candidates = [-target, -target, target, target, -target, -target, -target, -target]
        result = panel.select_best_of_eight(target, iter(candidates))
        self.assertEqual(result.index, 2)
        self.assertEqual(len(result.cosine_similarities), 8)

    def test_actual_best_of_eight_refuses_truncation(self):
        a = np.ones((257, 768), np.float32)
        with self.assertRaises(ValueError): panel.select_best_of_eight(a, [a] * 7)

    def test_literal_ssim_arguments_and_pixel_identity(self):
        a = np.linspace(0, 1, 3 * 425 * 425, dtype=np.float32).reshape(3, 425, 425)
        modules, ssim = fake_skimage()
        with mock.patch.dict(sys.modules, modules):
            result = panel.image_pair_metrics(a, a, skimage_version=SSIM_VERSION)
        self.assertAlmostEqual(result['pixcorr'], 1.)
        self.assertEqual(result['ssim'], .375)
        self.assertEqual(ssim.call_args.kwargs,
            {'multichannel': True, 'gaussian_weights': True, 'sigma': 1.5,
             'use_sample_covariance': False, 'data_range': 1.0})
        self.assertEqual(ssim.call_args.args[0].shape, (425, 425))

    def test_nonfinite_ssim_backend_result_refused(self):
        a = np.linspace(0, 1, 3 * 425 * 425, dtype=np.float32).reshape(3, 425, 425)
        modules, _ = fake_skimage(float('nan'))
        with mock.patch.dict(sys.modules, modules), self.assertRaises(panel.PanelError):
            panel.image_pair_metrics(a, a, skimage_version=SSIM_VERSION)

    def test_ssim_version_range_dimensions_and_variance_guards(self):
        a = np.linspace(0, 1, 3 * 425 * 425, dtype=np.float32).reshape(3, 425, 425)
        modules, ssim = fake_skimage()
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(panel.PanelError): panel.image_pair_metrics(a, a, skimage_version='unavailable')
            for bad in (np.ones_like(a), a[:, :424], a * 2, a.astype(np.int64)):
                with self.assertRaises(panel.PanelError):
                    panel.image_pair_metrics(bad, bad, skimage_version=SSIM_VERSION)
        ssim.assert_not_called()


class PanelTests(unittest.TestCase):
    def test_complete_48_cells_and_one_common_candidate(self):
        packet, arrays = fixture()
        result = dispatch(packet, arrays)
        self.assertEqual(result['condition_count'], 6)
        self.assertEqual(result['finding_count'], 48)
        self.assertEqual(len(result['findings']), 48)
        for row in result['conditions']:
            self.assertEqual(row['selected_candidate_indices'], [3] * 3)
            self.assertEqual(set(row['means']), set(panel.METRICS))
            np.testing.assert_allclose(row['per_image']['effnet_b'], 0, atol=2e-7)
        self.assertFalse(result['scientific_qualification'])
        self.assertEqual((result['reproduction'], result['improvement']), ('unknown', 'unknown'))
        self.assertFalse(result['deployable_target_blind_selection'])

    def test_input_reordering_preserves_identity_and_condition_scores(self):
        packet, arrays = fixture(); expected = dispatch(packet, arrays)
        packet['rows'].reverse()
        for row in packet['rows']: row['images'].reverse()
        actual = dispatch(packet, arrays)
        self.assertEqual(actual, expected)

    def test_production_requires_982_and_generated_mode_is_explicit(self):
        packet, _ = fixture()
        packet['source_kind'] = 'operator_prepared_source'
        with self.assertRaises(panel.PanelError): panel.validate_packet(packet)
        packet['source_kind'] = 'generated_engineering_control'
        self.assertEqual(len(panel.validate_packet(packet)), 3)
        del packet['source_kind']
        with self.assertRaises(panel.PanelError): panel.validate_packet(packet)

    def test_full_982_gallery_and_six_conditions_dispatch_with_mocked_image_paths(self):
        packet, arrays = fixture(982, 'operator_prepared_source')
        result = dispatch(packet, arrays)
        self.assertEqual(result['images_per_condition'], 982)
        self.assertEqual(result['finding_count'], 48)
        self.assertEqual([len(r['per_image']['clip']) for r in result['conditions']], [982] * 6)
        self.assertFalse(result['scientific_qualification'])

    def test_late_invalid_metadata_prevents_every_payload_read(self):
        for mutation in ('freeze', 'candidate', 'target', 'descriptor', 'image', 'row'):
            packet, _ = fixture(); row = packet['rows'][-1]
            if mutation == 'freeze': row['generation_frozen_before_target_selection'] = False
            elif mutation == 'candidate': row['images'][-1]['candidates'].pop()
            elif mutation == 'target': row['images'][-1]['target']['image_sha256'] = 'b' * 64
            elif mutation == 'descriptor': row['images'][-1]['candidates'][-1]['selection']['path'] = '../escape'
            elif mutation == 'image': row['images'][-1]['image_id'] = 'replacement'
            else: row['arm'] = packet['rows'][0]['arm']; row['budget'] = packet['rows'][0]['budget']
            loader = mock.Mock(side_effect=AssertionError('unexpected target/payload access'))
            with self.subTest(mutation=mutation), self.assertRaises(panel.PanelError):
                panel.evaluate_panel(packet, loader, max_working_bytes=WORKING_BYTES)
            loader.assert_not_called()

    def test_insufficient_working_budget_refuses_before_selection_payload_access(self):
        packet, _ = fixture(); loader = mock.Mock(side_effect=AssertionError('unexpected payload access'))
        with self.assertRaises(panel.PanelError):
            panel.evaluate_panel(packet, loader, max_working_bytes=1)
        loader.assert_not_called()

    def test_missing_metrics_and_mismatched_target_lineage_refused(self):
        for mutation in ('metric', 'lineage', 'cohort', 'bool_budget'):
            packet, _ = fixture(); target = packet['rows'][-1]['images'][-1]['target']
            if mutation == 'metric': target['features'].pop('swav')
            elif mutation == 'lineage': target['extraction_receipt_sha256'] = 'b' * 64
            elif mutation == 'cohort': packet['source_subjects'] = [1, 2, 7]
            else: packet['rows'][-1]['budget'] = True
            with self.assertRaises(panel.PanelError): panel.validate_packet(packet)

    def test_calibration_prefix_counts_and_test_disjointness(self):
        for mutation in ('count', 'prefix', 'overlap', 'duplicate'):
            packet, _ = fixture()
            if mutation == 'count': packet['calibration']['500'].pop()
            elif mutation == 'prefix': packet['calibration']['1500'][0] = 'cal:-001'
            elif mutation == 'overlap':
                packet['test_image_ids'][0] = packet['calibration']['500'][0]
            else: packet['calibration']['4000'][1] = packet['calibration']['4000'][0]
            with self.assertRaises(panel.PanelError): panel.validate_packet(packet)


class FileBoundaryTests(unittest.TestCase):
    def write(self, root, name, raw):
        (root / name).write_bytes(raw)
        return descriptor(name, raw)

    def npy(self, array):
        b = io.BytesIO(); np.save(b, array, allow_pickle=False); return b.getvalue()

    def test_exact_file_and_cumulative_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); raw = self.npy(np.array([1, 2], np.float32))
            d = self.write(root, 'a.npy', raw)
            reader = panel.FileArrays(root, max_read_bytes=len(raw) + 1, max_array_bytes=4096)
            np.testing.assert_array_equal(reader(d), [1, 2])
            self.assertEqual(reader.read_bytes, len(raw) + 1)
            with self.assertRaises(panel.PanelError): reader(d)

    def test_growth_probe_reads_only_original_extent_plus_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); path = root / 'growing.bin'
            path.write_bytes(b'original'); requested = []
            real_fdopen = panel.os.fdopen
            class GrowingReader:
                def __init__(self, *args, **kwargs): self.stream = real_fdopen(*args, **kwargs)
                def __enter__(self): self.stream.__enter__(); return self
                def __exit__(self, *args): return self.stream.__exit__(*args)
                def read(self, n):
                    requested.append(n)
                    with path.open('ab') as target: target.write(b'x' * 65536)
                    return self.stream.read(n)
            with mock.patch.object(panel.os, 'fdopen', GrowingReader), self.assertRaises(panel.PanelError):
                panel.stable_bytes(path, None, 1024**2)
            self.assertEqual(requested, [len(b'original') + 1])

    def test_bad_digest_trailing_and_nonfinite_payloads_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cases = [self.npy(np.array([1, 2], np.float32)) + b'x',
                     self.npy(np.array([1, np.nan], np.float32))]
            for i, raw in enumerate(cases):
                d = self.write(root, f'{i}.npy', raw)
                with self.assertRaises(panel.PanelError):
                    panel.FileArrays(root, max_read_bytes=4096, max_array_bytes=4096)(d)
            d = self.write(root, 'wrong.npy', self.npy(np.array([1, 2], np.float32)))
            d['sha256'] = H
            with self.assertRaises(panel.PanelError):
                panel.FileArrays(root, max_read_bytes=4096, max_array_bytes=4096)(d)

    def test_declared_huge_npy_and_object_dtype_refused_before_array_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for i, (dtype, shape) in enumerate((('<f8', (2**40,)), ('|O', (1,)))):
                b = io.BytesIO(); np.lib.format.write_array_header_1_0(b,
                    {'descr': dtype, 'fortran_order': False, 'shape': shape})
                d = self.write(root, f'{i}.npy', b.getvalue() + b'\x00' * 8)
                with mock.patch.object(np, 'frombuffer', side_effect=AssertionError('must reject before allocation')):
                    with self.assertRaises(panel.PanelError):
                        panel.FileArrays(root, max_read_bytes=4096, max_array_bytes=4096)(d)

    def test_fortran_integer_and_four_dimensional_arrays_refused(self):
        arrays = [np.asfortranarray(np.ones((2, 3), np.float32)),
                  np.array([1, 2], np.int64), np.ones((1, 1, 1, 2), np.float32)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for i, a in enumerate(arrays):
                d = self.write(root, f'{i}.npy', self.npy(a))
                with self.assertRaises(panel.PanelError):
                    panel.FileArrays(root, max_read_bytes=4096, max_array_bytes=4096)(d)

    def test_linked_input_and_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); raw = self.npy(np.array([1, 2], np.float32))
            d = self.write(root, 'a.npy', raw)
            (root / 'symlink.npy').symlink_to(root / 'a.npy')
            (root / 'hardlink.npy').hardlink_to(root / 'a.npy')
            for name in ('a.npy', 'symlink.npy', 'hardlink.npy', '../escape.npy'):
                bad = dict(d, path=name)
                with self.assertRaises(panel.PanelError):
                    panel.FileArrays(root, max_read_bytes=4096, max_array_bytes=4096)(bad)

    def test_json_duplicate_keys_nonfinite_and_cli_wrong_hash(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(panel.PanelError): panel.strict_json(raw)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); packet = root / 'packet.json'
            packet.write_text('{}'); output = root / 'output.json'
            run = subprocess.run([sys.executable, '-B', str(MODULE), str(packet), str(root), str(output),
                '--packet-sha256', H, '--max-read-bytes', '4096', '--max-array-bytes', '4096',
                '--max-working-bytes', str(WORKING_BYTES)],
                capture_output=True, text=True, timeout=30)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('operator-selected complete packet digest', run.stderr)
            self.assertFalse(output.exists())

    def test_cli_success_writes_exclusive_private_result_with_mocked_computation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); packet = root / 'packet.json'; packet.write_bytes(b'{}')
            output = root / 'output.json'
            args = [str(packet), str(root), str(output), '--packet-sha256', hashlib.sha256(b'{}').hexdigest(),
                    '--max-read-bytes', '4096', '--max-array-bytes', '4096',
                    '--max-working-bytes', str(WORKING_BYTES)]
            with mock.patch.object(panel, 'evaluate_panel', return_value={'scientific_qualification': False}):
                panel.main(args)
                with self.assertRaises(FileExistsError): panel.main(args)
            result = json.loads(output.read_bytes())
            self.assertFalse(result['scientific_qualification'])
            self.assertEqual(result['payload_read_charge_bytes'], 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


class NativeBoundaryTests(unittest.TestCase):
    """Mocked admission guards only; no torch transforms or model inference."""
    def test_source_runtime_exact_versions_and_local_suffixes(self):
        torch, vision = ModuleType('torch'), ModuleType('torchvision')
        torch.__version__, vision.__version__ = '2.0.1+cpu', '0.15.2+cpu'
        with mock.patch.dict(sys.modules, {'torch': torch, 'torchvision': vision}):
            self.assertEqual(native.require_source_runtime(), (torch, vision))
            for tv, vv in (('2.0.2', '0.15.2'), ('2.0.1', '0.16.0')):
                torch.__version__, vision.__version__ = tv, vv
                with self.assertRaises(ValueError): native.require_source_runtime()

    def test_incomplete_bank_and_nonboolean_role_refused_before_images(self):
        vision = ModuleType('torchvision'); vision.transforms = object()
        with mock.patch.object(native, 'require_source_runtime', return_value=(object(), vision)), \
             mock.patch.dict(sys.modules, {'torchvision': vision}):
            for models, role in (({}, True), (dict.fromkeys(native.MODEL_REQUIREMENTS), 1)):
                with self.assertRaises(ValueError):
                    native.extract_image(None, models, reconstruction=role, target_dtype=None)

    def test_training_model_or_bound_method_owner_refused_before_images(self):
        class TrainingModel:
            training = True
            def encode(self, value): raise AssertionError('no model call admitted')
        vision = ModuleType('torchvision'); vision.transforms = object()
        with mock.patch.object(native, 'require_source_runtime', return_value=(object(), vision)), \
             mock.patch.dict(sys.modules, {'torchvision': vision}):
            for bad in (TrainingModel(), TrainingModel().encode):
                models = {name: (lambda value: value) for name in native.MODEL_REQUIREMENTS}
                models['clip'] = bad
                with self.assertRaises(ValueError):
                    native.extract_image(None, models, reconstruction=True, target_dtype=None)


if __name__ == '__main__':
    unittest.main()
