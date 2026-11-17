"""Generated view equivalence and privacy controls; no original dataset reads."""
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import uuid

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import views as v


def object_id(index):
    return 'obj-' + str(uuid.UUID(int=index, version=4))


def feature_job(source_job):
    context = v.JobContext(**{k: source_job[k] for k in ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins')})
    shards, arrays = [], {}
    for index, label in enumerate(np.unique(source_job['qid']), 10):
        positions = tuple(int(i) for i in np.flatnonzero(source_job['qid'] == label))
        name = object_id(index)
        shards.append(v.ResponseShard(float(label), name, positions))
        arrays[name] = source_job['y'][np.asarray(positions)].copy()
    job = v.FeatureJob(context, object_id(1), object_id(2), object_id(3), tuple(shards), source_job['y'].shape[1])
    return job, arrays


def source_fixture():
    path = HERE.parent / 'original-protected-layout-v1/test_layout.py'
    spec = importlib.util.spec_from_file_location('immutable_view_source_oracle', path)
    module = importlib.util.module_from_spec(spec)
    # The imported generated fixture authenticates the unchanged original source
    # module; its imports require the sibling component directory, never data.
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    geometry, session, _ = module.fixture()
    return module.ORIGINAL, session


def disk_fixture(root, *, held_delta=0., training_delta=0., other_feature_delta=0., selected_feature_delta=0.):
    root.mkdir(mode=0o700)
    (root / 'objects').mkdir(mode=0o700)
    qid = np.array([-2., 0., -2., 3., 0., 3.], dtype='<f8')
    times = np.array([2, 3, 5, 8, 13, 21], dtype='<i8')
    x = np.arange(180, dtype='<f8').reshape(6, 30) + selected_feature_delta
    other = x + 9000. + other_feature_delta
    y = np.arange(12, dtype='<f8').reshape(6, 2) + 100.
    y[qid == -2.] += held_delta
    y[qid == 0.] += training_delta
    specs, arrays = [], {}
    def add(index, role, a):
        name = object_id(index)
        b = io.BytesIO(); np.save(b, a, allow_pickle=False); body = b.getvalue()
        relative = 'objects/' + name + '.npy'
        path = root / relative
        path.write_bytes(body); path.chmod(0o444)
        spec = v.ObjectSpec(name, relative, role, len(body), hashlib.sha256(body).hexdigest(),
                            a.shape, a.dtype.str, bool(a.flags.f_contiguous and not a.flags.c_contiguous))
        specs.append(spec); arrays[name] = a
        return name
    feature = add(1, 'features', x)
    qid_id = add(2, 'qid', qid)
    time_id = add(3, 'time', times)
    add(4, 'features', other)
    shards = []
    for i, label in enumerate(np.unique(qid), 10):
        positions = tuple(int(k) for k in np.flatnonzero(qid == label))
        name = add(i, 'responses', y[np.asarray(positions)])
        shards.append(v.ResponseShard(float(label), name, positions))
    context = v.JobContext('p1_1', 'unit', 'context', 0, 20, 0)
    job = v.FeatureJob(context, feature, qid_id, time_id, tuple(shards), 2)
    store = v.ImmutableStore(root, specs, read_limit=1024**2, working_limit=8 * 1024**2, max_objects=20)
    return store, job, specs, arrays


class ViewControls(unittest.TestCase):
    def test_complete_4209_source_jobs_match_original_predictor_inputs(self):
        original, session = source_fixture()
        total_jobs, total_requests = 0, 0
        for source_job in original.iter_jobs(session):
            job, arrays = feature_job(source_job)
            def capture(train_x, train_y, query_x, context):
                nonlocal total_requests
                selection = v.select_rows(job, source_job['qid'], source_job['time_indices'],
                                          context['held_qid'], working_limit=8 * 1024**2)
                allowed = {s.object_id: arrays[s.object_id] for s in job.response_shards
                           if s.label != context['held_qid']}
                actual = v.assemble_request(source_job['x'], selection, allowed,
                                            working_limit=8 * 1024**2)
                for value, expected in zip(actual[:3], (train_x, train_y, query_x)):
                    np.testing.assert_array_equal(value, expected)
                self.assertEqual(set(actual[3]), set(context))
                for key, expected in context.items():
                    if isinstance(expected, np.ndarray):
                        np.testing.assert_array_equal(actual[3][key], expected)
                    else:
                        self.assertEqual(actual[3][key], expected)
                total_requests += 1
                return np.zeros((len(query_x), train_y.shape[1]), dtype=np.float64)
            original.predict_job(source_job, capture, remaining_requests=len(np.unique(source_job['qid'])), sink=lambda _: None)
            total_jobs += 1
        self.assertEqual(total_jobs, 4209)
        self.assertGreater(total_requests, 20000)

    def test_extra_or_held_response_arrays_rejected(self):
        original, session = source_fixture()
        source_job = next(original.iter_jobs(session))
        job, arrays = feature_job(source_job)
        held = float(np.unique(source_job['qid'])[0])
        selection = v.select_rows(job, source_job['qid'], source_job['time_indices'], held,
                                  working_limit=8 * 1024**2)
        with self.assertRaises(ValueError):
            v.assemble_request(source_job['x'], selection, arrays, working_limit=8 * 1024**2)
        allowed = {s.object_id: arrays[s.object_id] for s in job.response_shards if s.label != held}
        allowed.pop(next(iter(allowed)))
        with self.assertRaises(ValueError):
            v.assemble_request(source_job['x'], selection, allowed, working_limit=8 * 1024**2)

    def test_public_view_is_unchanged_by_held_response_or_other_layer(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name)
            variants = ({}, {'held_delta': 12345.}, {'other_feature_delta': 54321.})
            public, private = [], []
            for i, variant in enumerate(variants):
                store, job, specs, _ = disk_fixture(root / f'store-{i}', **variant)
                plan = v.build_view(store, job, -2., descriptor_limit=65536)
                self.assertIsInstance(plan.public_json, bytes)
                public.append((plan.public_json, plan.public_id))
                private.append(hashlib.sha256(v.encoded(store.private_manifest())).hexdigest())
                held_id = next(s.object_id for s in job.response_shards if s.label == -2.)
                self.assertNotIn(held_id, {m.object_id for m in plan.private_mounts})
                self.assertNotIn(object_id(4), {m.object_id for m in plan.private_mounts})
                for spec in specs:
                    self.assertNotIn(spec.object_id.encode(), plan.public_json)
                    if spec.object_id in (held_id, object_id(4)):
                        self.assertNotIn(spec.sha256.encode(), plan.public_json)
                self.assertNotIn(str(root).encode(), plan.public_json)
                self.assertNotIn(private[-1].encode(), plan.public_json)
                self.assertTrue(all(m.read_only is True for m in plan.private_mounts))
            self.assertEqual(public[0], public[1])
            self.assertEqual(public[0], public[2])
            self.assertEqual(len(set(private)), 3)

    def test_permitted_training_or_selected_features_change_public_identity(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            hashes = []
            for i, variant in enumerate(({}, {'training_delta': 11.}, {'selected_feature_delta': 22.})):
                store, job, _, _ = disk_fixture(Path(name) / f'store-{i}', **variant)
                hashes.append(v.build_view(store, job, -2., descriptor_limit=65536).public_id)
            self.assertEqual(len(set(hashes)), 3)

    def test_cached_reuse_does_not_read_or_rehash_base_arrays(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, _, _ = disk_fixture(Path(name) / 'store')
            first = v.build_view(store, job, -2., descriptor_limit=65536)
            before = (store.read_charged, store.bytes_read, store.full_authentications)
            for _ in range(5):
                again = v.build_view(store, job, -2., descriptor_limit=65536)
                self.assertEqual(again.public_id, first.public_id)
            self.assertEqual((store.read_charged, store.bytes_read, store.full_authentications), before)

    def test_stable_cache_refuses_changed_allowed_object_before_reuse(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, specs, _ = disk_fixture(Path(name) / 'store')
            v.build_view(store, job, -2., descriptor_limit=65536)
            path = store.root / next(s.relative_path for s in specs if s.object_id == job.feature_id)
            path.chmod(0o644)
            with path.open('r+b') as f:
                f.seek(-1, os.SEEK_END); old = f.read(1); f.seek(-1, os.SEEK_END); f.write(bytes([old[0] ^ 1]))
            path.chmod(0o444)
            before = store.bytes_read
            with self.assertRaises(ValueError):
                v.build_view(store, job, -2., descriptor_limit=65536)
            self.assertEqual(store.bytes_read, before)

    def test_writable_and_mismatched_objects_fail_before_public_view(self):
        for kind in ('writable', 'contents'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=HERE) as name:
                store, job, specs, _ = disk_fixture(Path(name) / 'store')
                path = store.root / next(s.relative_path for s in specs if s.object_id == job.feature_id)
                path.chmod(0o644)
                if kind == 'contents':
                    with path.open('r+b') as f:
                        f.seek(-1, os.SEEK_END); f.write(b'X')
                    path.chmod(0o444)
                with self.assertRaises(ValueError):
                    v.build_view(store, job, -2., descriptor_limit=65536)

    def test_read_and_work_limits_refuse_before_open(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            _, job, specs, _ = disk_fixture(Path(name) / 'store')
            qid_spec = next(s for s in specs if s.object_id == job.qid_id)
            metadata = sum(v.SPEC_RESERVE + len(v.encoded(s.private_descriptor())) for s in specs)
            for limits in ({'read_limit': qid_spec.bytes, 'working_limit': 8 * 1024**2},
                           {'read_limit': 1024**2, 'working_limit': metadata}):
                store = v.ImmutableStore(Path(name) / 'store', specs, max_objects=20, **limits)
                with mock.patch.object(v.os, 'open', side_effect=AssertionError('No file open admitted')):
                    with self.assertRaises(ValueError):
                        store.authenticate(job.qid_id)
                self.assertEqual(store.bytes_read, 0)
                self.assertEqual(store.read_charged, 0)
                self.assertTrue(store.failed)
                with self.assertRaises(ValueError):
                    store.authenticate(job.qid_id)

    def test_selected_symlink_and_hardlink_refused_without_body_read(self):
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=HERE) as name:
                store, job, specs, _ = disk_fixture(Path(name) / 'store')
                path = store.root / next(s.relative_path for s in specs if s.object_id == job.feature_id)
                other = Path(name) / 'outside.npy'
                if kind == 'symlink':
                    path.rename(other)
                    path.symlink_to(other)
                else:
                    os.link(path, other)
                with self.assertRaises(ValueError):
                    store.authenticate(job.feature_id)
                self.assertEqual(store.bytes_read, 0)
                self.assertEqual(store.read_charged, 0)
                self.assertTrue(store.failed)

    def test_descriptor_limit_and_live_work_accounting(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, _, _ = disk_fixture(Path(name) / 'store')
            with self.assertRaises(ValueError):
                v.build_view(store, job, -2., descriptor_limit=1)
            self.assertEqual(store.private_metrics()['temporary_working_admission'], 0)
            plan = v.build_view(store, job, -2., descriptor_limit=65536)
            self.assertLessEqual(len(plan.public_json), 65536)
            self.assertLessEqual(store.peak_working_admission, store.working_limit)
            self.assertGreaterEqual(store.peak_working_admission,
                                    store.retained_working_admission + plan.working_admission_bytes)
            self.assertEqual(store.full_authentications, 5)

    def test_forged_selection_cannot_overlap_train_and_query(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            _, job, _, arrays = disk_fixture(Path(name) / 'store')
            selection = v.select_rows(job, arrays[job.qid_id], arrays[job.time_id], -2.,
                                      working_limit=8 * 1024**2)
            object.__setattr__(selection, 'query_positions', (1, 3))
            allowed = {s.object_id: arrays[s.object_id] for s in job.response_shards if s.label != -2.}
            with self.assertRaises(ValueError):
                v.assemble_request(arrays[job.feature_id], selection, allowed, working_limit=8 * 1024**2)

    def test_assembly_bound_precedes_index_allocation(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            _, job, _, arrays = disk_fixture(Path(name) / 'store')
            selection = v.select_rows(job, arrays[job.qid_id], arrays[job.time_id], -2.,
                                      working_limit=8 * 1024**2)
            allowed = {s.object_id: arrays[s.object_id] for s in job.response_shards if s.label != -2.}
            with mock.patch.object(v.np, 'asarray', side_effect=AssertionError('No index allocation admitted')):
                with self.assertRaises(ValueError):
                    v.assemble_request(arrays[job.feature_id], selection, allowed, working_limit=1)

    def test_store_refuses_unbounded_manifest_before_iteration(self):
        class UnboundedManifest:
            def __iter__(self):
                raise AssertionError('Unbounded manifest must not be consumed')
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            with self.assertRaises(ValueError):
                v.ImmutableStore(Path(name), UnboundedManifest(), read_limit=1024**2,
                                 working_limit=8 * 1024**2, max_objects=20)


if __name__ == '__main__':
    unittest.main()
