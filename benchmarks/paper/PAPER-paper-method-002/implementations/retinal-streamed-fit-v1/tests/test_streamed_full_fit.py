"""One analytical source-composition campaign; no native model/data execution.

Six unittest methods exercise the real streamed reduction, source transition,
production FitRuntime methods and fixed scheduler. Generated optimizer/model
primitives do not establish JAX/Optax/neural numerical equivalence or readiness.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
_helper = ModuleType('bounded_control_files')
_helper.__file__ = str(HERE / 'control_runtime.py')
exec(compile((HERE / 'control_runtime.py').read_bytes(), _helper.__file__, 'exec'), _helper.__dict__)


def scalar_pearson(left, right):
    n = len(left)
    a, b = math.fsum(left) / n, math.fsum(right) / n
    covariance = math.fsum((x - a) * (y - b) for x, y in zip(left, right))
    denominator = math.sqrt(math.fsum((x - a) ** 2 for x in left) *
                            math.fsum((y - b) ** 2 for y in right))
    if n < 2 or denominator == 0:
        raise ValueError('undefined generated Pearson')
    return covariance / denominator


class StreamedFullFitSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('SOURCE_INPUT_ROOT', str(HERE.parent))).resolve(strict=True)
        chosen = os.environ.get('ARTIFACT_DIR')
        if chosen is None:
            temporary = tempfile.TemporaryDirectory(prefix='retinal-streamed-fit-control-')
            cls.addClassCleanup(temporary.cleanup)
            chosen = str(Path(temporary.name).resolve(strict=True) / 'artifacts')
        cls.files = _helper.CampaignFiles(source, HERE, chosen)
        import numpy as np
        if sys.version_info[:2] != (3, 11) or np.__version__ != '1.26.3':
            raise RuntimeError('selected analytical Python3.11 and NumPy1.26.3 required')
        cls.np = np
        cls.runtime = cls.files.module('fit_runtime.py')
        cls.loop = cls.files.module('fit_loop.py')
        cls.streamed = cls.files.module('frozen/comparison_streamed_batch.py')
        cls.transition = cls.files.module('source_transition.py')
        cls.model = cls.files.module('frozen/model_operation.py')
        cls.loading = cls.files.module('source_loading.py')
        old_loading = sys.modules.get('source_loading')
        sys.modules['source_loading'] = cls.loading
        try:
            cls.full_fit = cls.files.module('full_fit.py')
        finally:
            if old_loading is None:
                del sys.modules['source_loading']
            else:
                sys.modules['source_loading'] = old_loading
        cls.backend_source = cls.files.module('analytical_backend.py', helper=True)
        cls.oracle = cls.files.module('oracle/analytical_reference.py', helper=True)

    def backend(self):
        return self.backend_source.build_backend(self.np)

    def stats(self):
        return {key: 0 for key in (
            'training_singletons_completed', 'last_training_batch_completed_rows',
            'completed_original_gradient_batches', 'last_global_mean_denominator',
            'validation_singletons_completed', 'last_validation_batch_completed_rows',
            'completed_original_validation_batches', 'test_singletons_completed')}

    def assert_tree_close(self, actual, expected, backend):
        expected = backend.arrays(expected)
        left, lspec = backend.tree_util.tree_flatten(actual)
        right, rspec = backend.tree_util.tree_flatten(expected)
        self.assertEqual(lspec, rspec)
        for a, b in zip(left, right):
            self.assertEqual(self.np.asarray(a).shape, self.np.asarray(b).shape)
            self.assertTrue(bool(self.np.allclose(a, b, rtol=2e-12, atol=2e-12)),
                            'independent generated arithmetic mismatch')

    def batch(self, rows, start):
        x, labels, masks = self.oracle.batch_operands(rows, start=start)
        currents = self.np.zeros((rows, 287), dtype=self.np.float64)
        currents[:, 0] = x
        return (currents, self.np.asarray(labels), self.np.asarray(masks, dtype=self.np.float64)), (x, labels, masks)

    def test_01_streamed_256_and_153_updates_match_independent_oracle(self):
        backend, stats = self.backend(), self.stats()
        reference_opt, reference_state = self.oracle.initial_parameters(), self.oracle.zero_state()
        opt, state = backend.arrays(reference_opt), backend.arrays(reference_state)
        initial = (self.np.array([3., 7.]),)
        for rows, start in ((256, 0), (153, 256)):
            (currents, labels, mask), operand = self.batch(rows, start)
            loss, gradients = self.oracle.batch_reference(reference_opt, *operand)
            expected = self.oracle.momentum_transition(reference_opt, reference_state, gradients)
            result = self.runtime.streamed_step(
                backend.gradient, opt, state, backend.optimizers, currents, labels, mask, initial,
                np=self.np, jnp=backend.jnp, tree_util=backend.tree_util,
                tree_map=backend.tree_map, l2_norm=backend.l2_norm, optax=backend.optax,
                streamed_gradient=self.streamed.streamed_gradient,
                source_transition=self.transition.source_transition, check=lambda stage: None,
                stats=stats, validate=backend.validate)
            self.assertTrue(math.isclose(result['loss'], loss, rel_tol=2e-12, abs_tol=2e-12))
            for key in ('normalized', 'proposed_updates', 'parameters', 'optimizer_states'):
                self.assert_tree_close(result[key], expected[key], backend)
            self.assertEqual(stats['last_global_mean_denominator'], rows)
            self.assertEqual(result['updates'], 1)
            group_ids = tuple(id(group) for group in opt)
            self.assertTrue(all(ids == group_ids and state_id == id(initial)
                                for ids, state_id in backend.observations[-rows:]))
            opt, state = result['parameters'], result['optimizer_states']
            reference_opt, reference_state = expected['parameters'], expected['optimizer_states']
        self.assertEqual(stats['training_singletons_completed'], 409)
        self.assertEqual(stats['completed_original_gradient_batches'], 2)
        self.assertGreater(backend.l2_norm(state), 0.)
        self.assertEqual(initial[0].tolist(), [3., 7.])
        currents, labels, mask = self.batch(153, 0)[0]
        def zero_gradient(*args):
            return backend.jnp.asarray(1.), backend.tree_map(lambda value: value * 0., opt)
        with self.assertRaisesRegex(ValueError, 'five finite positive group norms'):
            self.runtime.streamed_step(zero_gradient, opt, state, backend.optimizers,
                currents, labels, mask, initial, np=self.np, jnp=backend.jnp,
                tree_util=backend.tree_util, tree_map=backend.tree_map, l2_norm=backend.l2_norm,
                optax=backend.optax, streamed_gradient=self.streamed.streamed_gradient,
                source_transition=self.transition.source_transition, check=lambda stage: None,
                stats=self.stats(), validate=backend.validate)

    def generated_runtime(self):
        np, backend = self.np, self.backend()
        runtime = object.__new__(self.runtime.FitRuntime)
        runtime.np, runtime.jnp = np, backend.jnp
        runtime.tree_map, runtime.tree_util = backend.tree_map, backend.tree_util
        runtime.codec, runtime.model = backend.codec, self.model
        runtime.streamed, runtime.transition = self.streamed, self.transition.source_transition
        runtime.l2_norm, runtime.optax = backend.l2_norm, backend.optax
        runtime.deadline, runtime.checkpoint_notice = time.monotonic() + 120., None
        runtime.opt = backend.arrays(self.oracle.initial_parameters())
        runtime.optimizer_states = backend.arrays(self.oracle.zero_state())
        runtime.optimizers, runtime.gradient = backend.optimizers, backend.gradient
        runtime.states = (np.array([3., 7.]),)
        runtime.initial_model_state = runtime.codec.encode_tree(runtime.states, np, backend.tree_util, role='model_state')
        # The generated finite guard is explicitly not the native physical transform.
        runtime.physical_parameters = lambda value: backend.validate('generated_parameters', value)
        runtime.history, runtime.updates, runtime.stats = [], 0, self.stats()
        runtime.selected_snapshot_sha256, runtime.selected_predictions = None, None
        class ArrayOperand:
            def __init__(self, value): self.value, self.shape = value, value.shape
            def numpy(self): return self.value
        batches = [self.batch(256, 0)[0], self.batch(153, 256)[0]]
        runtime.dataloader = [(None, *(ArrayOperand(value) for value in batch)) for batch in batches]
        row = np.arange(3047)
        group = np.where(row < 1024, 0, np.where(row < 2048, 1, 2))
        local = np.where(group == 0, row, np.where(group == 1, row - 1024, row - 2048)) / 1024.
        base_prediction = group * 10. + local
        base_target = (2 - group) * 10. + local
        offsets = np.arange(147) / 1000.
        validation_prediction = base_prediction[:, None] + offsets
        validation_targets = base_target[:, None] + offsets
        mask = ((row[:, None] + np.arange(147)[None, :]) % 13 != 0).astype(np.float64)
        val_currents = np.zeros((3047, 287), dtype=np.float64)
        val_currents[:, 0] = row
        runtime.val_loader = [(None, ArrayOperand(chunk)) for chunk in
                              (val_currents[:1024], val_currents[1024:2048], val_currents[2048:])]
        runtime.val_ids = np.arange(3047)
        test_currents = np.zeros((128, 287), dtype=np.float64)
        test_currents[:, 0] = np.arange(128) + 10000
        runtime.arrays = {'currents': test_currents, 'mask': mask, 'val_targets': validation_targets}
        runtime.meta = {'splits': {'test': list(range(128))}}
        runtime.test_parameter_ids = []
        def predict(parameters, currents):
            indices = currents[:, 0].astype(int)
            if int(indices[0]) >= 10000:
                runtime.test_parameter_ids.append(id(parameters))
                return (indices[:, None] - 10000) / 10. + offsets + float(backend.coordinates(parameters).sum())
            if len(runtime.history) < 2:
                return validation_prediction[indices]
            return -validation_targets[indices]
        runtime.predict = predict
        return runtime, backend, validation_prediction

    def test_02_real_fit_methods_global_validation_first_tie_and_detached_test(self):
        runtime, backend, predictions = self.generated_runtime()
        np = self.np
        labels, mask = runtime.arrays['val_targets'], runtime.arrays['mask']
        expected_sites = [scalar_pearson(
            [float(labels[i, site]) for i in range(3047) if mask[i, site]],
            [float(predictions[i, site]) for i in range(3047) if mask[i, site]]) for site in range(147)]
        expected_mean = math.fsum(expected_sites) / 147
        chunk_means = [self.model.masked_pearson(predictions[a:b], labels[a:b], mask[a:b])['mean']
                       for a, b in ((0, 1024), (1024, 2048), (2048, 3047))]
        self.assertGreater(math.fsum(chunk_means) / 3. - expected_mean, 1.)
        schedule = self.loop.Schedule(3, (256, 153), (1024, 1024, 999), 128)
        result = self.loop._run_loop(runtime, schedule)
        self.assertEqual((result['updates'], result['epochs_completed']), (6, 3))
        self.assertEqual(result['best_epoch_zero_based'], 0)
        self.assertTrue(math.isclose(result['best_validation_mean'], expected_mean, rel_tol=1e-12, abs_tol=1e-12))
        self.assertEqual([record['selected'] for record in runtime.history], [True, False, False])
        self.assertEqual([record['updates'] for record in runtime.history], [2, 4, 6])
        expected_opt, expected_state = self.oracle.initial_parameters(), self.oracle.zero_state()
        first_snapshot = None
        for epoch in range(3):
            losses = []
            for rows, start in ((256, 0), (153, 256)):
                operands = self.oracle.batch_operands(rows, start=start)
                loss, gradient = self.oracle.batch_reference(expected_opt, *operands)
                expected = self.oracle.momentum_transition(expected_opt, expected_state, gradient)
                expected_opt, expected_state = expected['parameters'], expected['optimizer_states']
                losses.append(loss)
            self.assertTrue(math.isclose(runtime.history[epoch]['epoch_sum_of_batch_mean_L1'], sum(losses), rel_tol=2e-12))
            if epoch == 0: first_snapshot = expected_opt
        self.assert_tree_close(runtime.opt, expected_opt, backend)
        self.assert_tree_close(runtime.optimizer_states, expected_state, backend)
        self.assert_tree_close(result['best_snapshot'], first_snapshot, backend)
        for old, new in zip(backend.tree_util.tree_leaves(result['best_snapshot']), backend.tree_util.tree_leaves(runtime.opt)):
            self.assertFalse(np.shares_memory(old, new))
        self.assertEqual(runtime.stats['training_singletons_completed'], 3 * 409)
        self.assertEqual(runtime.stats['validation_singletons_completed'], 3 * 3047)
        self.assertEqual(runtime.stats['test_singletons_completed'], 128)
        self.assertEqual(result['test_predictions'].shape, (128, 147))
        self.assertEqual(runtime.test_parameter_ids, [id(result['best_snapshot'])] * 128)
        expected_first = float(sum(self.oracle.tree_to_coordinates(first_snapshot)))
        self.assertTrue(np.allclose(result['test_predictions'][0], expected_first + np.arange(147) / 1000.))
        selected_before = backend.coordinates(result['best_snapshot']).copy()
        for leaf in backend.tree_util.tree_leaves(runtime.opt): leaf[...] += 100.
        self.assertTrue(np.array_equal(selected_before, backend.coordinates(result['best_snapshot'])))
        with self.assertRaises(TypeError):
            self.runtime.streamed_test_prediction(runtime.predict, result['best_snapshot'], runtime.arrays['currents'],
                labels=labels[:128], np=np, check=lambda stage: None, stats=self.stats())
        runtime.states[0][0] = 99.
        with self.assertRaisesRegex(ValueError, 'initial state mutated'):
            runtime.model_state_unchanged()

    def cheap_runtime(self, *, mean=.25, wrong_tail=False):
        class CounterRuntime:
            def __init__(self): self.steps = self.validations = self.snapshots = self.tests = 0
            def start_epoch(self, epoch): self.epoch = epoch
            def training_batches(self):
                for rows in (256,) * 47 + ((152 if wrong_tail else 153),): yield rows, rows
            def step(self, batch): self.steps += 1; return {'loss': float(batch)}
            def validation_chunks(self):
                for rows in (1024, 1024, 999): yield rows, rows
            def validation_metric(self, chunks): self.validations += 1; return mean
            def snapshot(self): self.snapshots += 1; return {'generated_epoch': self.epoch}
            def record_epoch(self, record, snapshot, chunks): pass
            def final_test(self, snapshot): self.tests += 1; return 128, 'generated feature-only sentinel'
        return CounterRuntime()

    def test_03_public_profile_is_fixed_and_completes_1008_updates(self):
        runtime = self.cheap_runtime()
        result = self.loop.run_production(runtime)
        self.assertEqual((runtime.steps, runtime.validations, runtime.snapshots, runtime.tests), (1008, 21, 1, 1))
        self.assertEqual((result['training_rows_per_epoch'], result['validation_rows_per_epoch'], result['test_rows']), (12185, 3047, 128))
        self.assertEqual(result['best_epoch_zero_based'], 0)
        with self.assertRaises(TypeError): self.loop.run_production(runtime, schedule=self.loop.PRODUCTION_SCHEDULE)
        broken = self.cheap_runtime(wrong_tail=True)
        with self.assertRaisesRegex(ValueError, 'training chunk row count mismatch'):
            self.loop.run_production(broken)
        self.assertEqual((broken.steps, broken.validations, broken.tests), (47, 0, 0))

    def test_04_undefined_or_nonfinite_validation_never_reaches_test(self):
        for mean in (-1., float('nan'), float('inf')):
            with self.subTest(mean=mean):
                runtime = self.cheap_runtime(mean=mean)
                with self.assertRaises(ValueError): self.loop.run_production(runtime)
                self.assertEqual(runtime.tests, 0)
        predictions = self.np.ones((3047, 147))
        targets = self.np.arange(3047)[:, None] + self.np.zeros((3047, 147))
        with self.np.errstate(invalid='ignore', divide='ignore'):
            with self.assertRaisesRegex(ValueError, 'undefined per-site Pearson'):
                self.model.masked_pearson(predictions, targets, self.np.ones_like(predictions))
        with self.assertRaisesRegex(ValueError, 'support'):
            self.model.masked_pearson(targets, targets, self.np.zeros_like(predictions))

    def test_05_test_target_archive_member_rejected_before_materialization(self):
        metadata = {key: None for key in self.loading.META_FIELDS}
        metadata['test_targets_included'] = False
        metadata['arrays'] = {key: {} for key in self.loading.ARRAY_NAMES}
        meta = self.files.write('input/model_metadata.json', json.dumps(metadata).encode())
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(self.loading.ARRAY_NAMES | {'test_targets'}):
                archive.writestr(name + '.npy', b'generated invalid payload; must never be loaded')
        packet = self.files.write('input/model_arrays.npz', stream.getvalue())
        manifest = self.files.write('input/manifest.json', json.dumps({
            'schema': 'jaxley-streamed-fit-input-files-v1', 'files': {
                'model_arrays.npz': {}, 'model_metadata.json': {},
                'morphologies/20161028_1.swc': {}}}).encode())
        original_open = zipfile.ZipFile.open
        calls = []
        def forbidden_member_open(*args, **kwargs):
            calls.append(True)
            raise AssertionError('forbidden archive member materialized')
        zipfile.ZipFile.open = forbidden_member_open
        try:
            with self.assertRaisesRegex(ValueError, 'exact unique NPZ members; no TEST targets'):
                self.loading.packet_preflight(packet, meta)
        finally:
            zipfile.ZipFile.open = original_open
        self.assertEqual(calls, [])
        touched = []
        def forbidden_native(*args, **kwargs):
            touched.append(True)
            raise AssertionError('native scientific loader reached before rejected preflight')
        original_requirements = self.full_fit.runtime_requirements
        original_loader = self.full_fit.load_frozen_sources
        self.full_fit.runtime_requirements = self.full_fit.load_frozen_sources = forbidden_native
        generated_output = self.files.output / 'failed-fit'
        # The real wrapper caps its failure RESULT body at65536B. Reserve that
        # cumulative external write ceiling before it creates any file.
        self.assertLessEqual(self.files.written + 65536, _helper.MAX_FIXTURE_WRITES)
        self.files.written += 65536
        try:
            with self.assertRaisesRegex(ValueError, 'exact unique NPZ members; no TEST targets'):
                self.full_fit.run(manifest, generated_output, 1.)
        finally:
            self.full_fit.runtime_requirements = original_requirements
            self.full_fit.load_frozen_sources = original_loader
        self.assertEqual(touched, [])
        result_path = generated_output / 'RESULT.json'
        self.assertLessEqual(result_path.stat().st_size, 65536)
        report = json.loads(result_path.read_text())
        self.assertFalse(report['complete'])
        self.assertEqual(report['scientific_status'], 'UNQUALIFIED')
        self.assertEqual((report['optimizer_updates'], report['validation_checks']), (0, 0))
        self.assertFalse(report['test_targets_consumed'])
        self.assertFalse(report['test_score_computed'])

    def test_06_external_output_root_is_disjoint_fresh_and_bounded(self):
        for forbidden in (self.files.source_root, self.files.source_root.parent, self.files.source_root / 'generated'):
            with self.subTest(path=str(forbidden)):
                with self.assertRaises(ValueError): _helper.output_root(forbidden, (self.files.source_root, HERE))
                with self.assertRaises(ValueError):
                    self.full_fit.run(self.files.output / 'unused-manifest.json', forbidden, 1.)
        alias = self.files.output / 'source-alias'
        alias.symlink_to(self.files.source_root, target_is_directory=True)
        try:
            with self.assertRaises(ValueError): _helper.output_root(alias / 'generated', (self.files.source_root, HERE))
            with self.assertRaisesRegex(ValueError, 'ordinary existing output directory ancestry'):
                self.full_fit.run(self.files.output / 'unused-manifest.json', alias / 'generated', 1.)
        finally:
            alias.unlink()
        with self.assertRaisesRegex(ValueError, 'fresh'):
            _helper.output_root(self.files.output, (self.files.source_root, HERE))
        with self.assertRaisesRegex(ValueError, 'allowance'):
            self.files.write('oversized.bin', bytes(_helper.MAX_FIXTURE_WRITES + 1))
        self.assertLessEqual(self.files.written, 81920)


if __name__ == '__main__':
    unittest.main(verbosity=2)
