"""Generated private store/cache controls; no authentic source files."""
import hashlib
import gc
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import weakref

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cache as c

WORK = 64 * 1024**2
READ = 8 * 1024**2


def fixture(root, **variants):
    path = HERE.parent / 'original-immutable-views-v1/test_views.py'
    spec = importlib.util.spec_from_file_location('cache_generated_store_fixture', path)
    helper = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(helper)
    finally:
        sys.path.remove(str(path.parent))
    helper.v = c.V
    _, job, specs, arrays = helper.disk_fixture(root, **variants)
    store = c.FileStore(root, specs, read_limit=READ, working_limit=WORK, max_objects=20)
    return store, job, specs, arrays


def make_cache(store, *, payload_limit=65536, entries=16):
    return c.BundleCache(store, payload_limit=payload_limit, entry_limit=entries,
                         metadata_limit=262144, bundle_byte_limit=READ)


def expected_training(job, arrays, held):
    qid = arrays[job.qid_id]
    y = np.empty((len(qid), job.output_columns), dtype='<f8')
    for shard in job.response_shards:
        y[np.asarray(shard.row_positions)] = arrays[shard.object_id]
    return y[qid != held]


class CacheControls(unittest.TestCase):
    def test_first_load_authenticates_once_and_later_response_load_charges_reread(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, specs, arrays = fixture(Path(name) / 'store')
            target = job.response_shards[0].object_id
            size = next(s.bytes for s in specs if s.object_id == target)
            first = store.load(target)
            self.assertEqual(first.tobytes(), arrays[target].tobytes())
            before = store.private_metrics()
            self.assertEqual(before['full_authentications'], 1)
            self.assertEqual(before['bytes_read'], size)
            self.assertEqual(before['read_charged'], size + 1)
            self.assertEqual(before['rereads'], 0)
            again = store.load(target)
            after = store.private_metrics()
            self.assertEqual(again.tobytes(), first.tobytes())
            self.assertEqual(after['full_authentications'], 1)
            self.assertEqual(after['rereads'], 1)
            self.assertEqual(after['bytes_read'], 2 * size)
            self.assertEqual(after['read_charged'], 2 * (size + 1))
            self.assertEqual(after['auth_bytes_read'], size)
            self.assertEqual(after['reread_bytes_read'], size)

    def test_retained_maps_are_reused_and_returned_view_metadata_is_isolated(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, _, arrays = fixture(Path(name) / 'store')
            first = store.load(job.qid_id)
            before = store.private_metrics()
            first.shape = (2, 3)
            second = store.load(job.qid_id)
            self.assertEqual(second.shape, (6,))
            self.assertEqual(second.tobytes(), arrays[job.qid_id].tobytes())
            self.assertEqual(store.private_metrics()['bytes_read'], before['bytes_read'])
            for value in (first, second):
                self.assertFalse(value.flags.writeable)
                with self.assertRaises(ValueError):
                    value.setflags(write=True)

    def test_identical_allowed_inputs_hit_across_feature_and_layer_changes(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, _, arrays = fixture(Path(name) / 'store')
            cache = make_cache(store)
            first = cache.get(job, -2.)
            before = store.private_metrics()
            context = c.V.JobContext('p1_1', 'unit', 'context', 1, 20, 0)
            other_id = next(k for k, value in arrays.items()
                            if value.shape == (6, 30) and k != job.feature_id)
            other = c.V.FeatureJob(context, other_id, job.qid_id, job.time_id,
                                   job.response_shards, job.output_columns)
            again = cache.get(other, -2.)
            self.assertEqual(first, again)
            self.assertEqual(store.private_metrics()['bytes_read'], before['bytes_read'])
            self.assertEqual(cache.private_metrics()['builds'], 1)
            self.assertEqual(cache.private_metrics()['hits'], 1)
            decoded = c.B.decode_bundle(first, byte_limit=READ, working_limit=WORK)
            self.assertEqual(decoded.train_y.tobytes(), expected_training(job, arrays, -2.).tobytes())

    def test_held_response_and_unrelated_feature_files_are_not_opened(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, specs, arrays = fixture(Path(name) / 'store')
            held = next(s.object_id for s in job.response_shards if s.label == -2.)
            unrelated = next(k for k, value in arrays.items()
                             if value.shape == (6, 30) and k != job.feature_id)
            removed = {held, unrelated, job.feature_id}
            for spec in specs:
                if spec.object_id in removed:
                    (Path(name) / 'store' / spec.relative_path).unlink()
            raw = make_cache(store).get(job, -2.)
            decoded = c.B.decode_bundle(raw, byte_limit=READ, working_limit=WORK)
            self.assertEqual(decoded.train_y.tobytes(), expected_training(job, arrays, -2.).tobytes())
            self.assertEqual(store.private_metrics()['full_authentications'], 4)

    def test_byte_and_entry_eviction_rebuilds_preserve_current_allowed_responses(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, _, arrays = fixture(Path(name) / 'store')
            cache = make_cache(store, payload_limit=224, entries=1)
            packets = []
            for held in (-2., 0., -2.):
                raw = cache.get(job, held); packets.append(raw)
                decoded = c.B.decode_bundle(raw, byte_limit=READ, working_limit=WORK)
                self.assertEqual(decoded.train_y.tobytes(), expected_training(job, arrays, held).tobytes())
                metrics = cache.private_metrics()
                self.assertLessEqual(metrics['entries'], 1)
                self.assertLessEqual(metrics['payload_bytes'], 224)
            self.assertEqual(packets[0], packets[2])
            metrics = cache.private_metrics()
            self.assertEqual((metrics['hits'], metrics['misses'], metrics['builds'], metrics['evictions']),
                             (0, 3, 3, 2))
            self.assertEqual(metrics['built_payload_bytes'], sum(map(len, packets)))
            self.assertEqual(metrics['evicted_payload_bytes'], len(packets[0]) + len(packets[1]))
            self.assertGreater(store.private_metrics()['rereads'], 0)

    def test_selected_file_mutation_refuses_a_cached_packet(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, specs, _ = fixture(Path(name) / 'store')
            cache = make_cache(store); cache.get(job, -2.)
            selected = next(s.object_id for s in job.response_shards if s.label != -2.)
            path = Path(name) / 'store' / next(s.relative_path for s in specs if s.object_id == selected)
            path.chmod(0o644)
            with path.open('r+b') as f:
                f.seek(-1, os.SEEK_END); old = f.read(1); f.seek(-1, os.SEEK_END); f.write(bytes([old[0] ^ 1]))
            path.chmod(0o444)
            before = store.private_metrics()['bytes_read']
            with self.assertRaises(ValueError):
                cache.get(job, -2.)
            self.assertEqual(store.private_metrics()['bytes_read'], before)
            self.assertTrue(cache.private_metrics()['failed'])

    def test_read_budget_refuses_before_open_and_never_refunds_prior_reads(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            _, job, specs, _ = fixture(Path(name) / 'store')
            selected = next(s for s in specs if s.object_id == job.response_shards[0].object_id)
            for limit, first in ((selected.bytes, False), (selected.bytes + 1, True)):
                store = c.FileStore(Path(name) / 'store', specs, read_limit=limit,
                                     working_limit=WORK, max_objects=20)
                if first:
                    store.load(selected.object_id)
                charged = store.private_metrics()['read_charged']
                with mock.patch.object(c.os, 'open', side_effect=AssertionError('No I/O admitted')):
                    with self.assertRaises(ValueError):
                        store.load(selected.object_id)
                self.assertEqual(store.private_metrics()['read_charged'], charged)
                self.assertTrue(store.private_metrics()['failed'])

    def test_ordinary_readonly_single_link_and_exact_body_are_required(self):
        for fault in ('writable', 'symlink', 'hardlink', 'content'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=HERE) as name:
                store, job, specs, _ = fixture(Path(name) / 'store')
                selected = job.response_shards[0].object_id
                path = Path(name) / 'store' / next(s.relative_path for s in specs if s.object_id == selected)
                outside = Path(name) / 'outside.npy'
                if fault == 'writable':
                    path.chmod(0o644)
                elif fault == 'symlink':
                    path.rename(outside); path.symlink_to(outside)
                elif fault == 'hardlink':
                    os.link(path, outside)
                else:
                    path.chmod(0o644)
                    with path.open('r+b') as f:
                        f.seek(-1, os.SEEK_END); old = f.read(1); f.seek(-1, os.SEEK_END); f.write(bytes([old[0] ^ 1]))
                    path.chmod(0o444)
                with self.assertRaises(ValueError):
                    store.load(selected)
                self.assertTrue(store.private_metrics()['failed'])

    def test_changed_input_objects_after_construction_do_not_rebind_authority(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, job, specs, arrays = fixture(Path(name) / 'store')
            selected = next(s for s in specs if s.object_id == job.response_shards[0].object_id)
            original = arrays[selected.object_id].tobytes()
            object.__setattr__(selected, 'sha256', 'f' * 64)
            actual = store.load(selected.object_id)
            self.assertEqual(actual.tobytes(), original)

    def test_one_cache_attachment_does_not_create_a_session_reference_cycle(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            store, _, _, _ = fixture(Path(name) / 'store')
            cache = make_cache(store)
            with self.assertRaises(ValueError):
                make_cache(store)
            store_ref, cache_ref = weakref.ref(store), weakref.ref(cache)
            enabled = gc.isenabled()
            gc.disable()
            try:
                del cache
                self.assertIsNone(cache_ref())
                del store
                self.assertIsNone(store_ref())
            finally:
                if enabled:
                    gc.enable()

    def test_constructor_snapshot_admission_is_included_in_reported_peak(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            _, _, specs, _ = fixture(Path(name) / 'store')
            admission = len(specs) * 8192
            store = c.FileStore(Path(name) / 'store', specs, read_limit=READ,
                                 working_limit=admission, max_objects=20)
            self.assertEqual(store.private_metrics()['peak_working_admission'], admission)
            self.assertEqual(store.private_metrics()['bytes_read'], 0)
            with mock.patch.object(c, '_spec_snapshot', side_effect=AssertionError('Snapshot before admission')):
                with self.assertRaises(ValueError):
                    c.FileStore(Path(name) / 'store', specs, read_limit=READ,
                                working_limit=admission - 1, max_objects=20)


if __name__ == '__main__':
    unittest.main()
