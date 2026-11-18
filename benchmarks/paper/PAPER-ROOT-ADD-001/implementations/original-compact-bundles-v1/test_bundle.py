"""Generated compact input controls; no original dataset or model execution."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock
import uuid

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bundle as b

BYTE_LIMIT = 8 * 1024**2
WORK_LIMIT = 32 * 1024**2


def opaque(index):
    return 'obj-' + str(uuid.UUID(int=index, version=4))


def job_inputs(source, *, id_offset=0):
    v = b.V
    context = v.JobContext(**{key: source[key] for key in
                             ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins')})
    shards, arrays = [], {}
    for index, label in enumerate(np.unique(source['qid']), 10 + id_offset):
        positions = tuple(int(i) for i in np.flatnonzero(source['qid'] == label))
        name = opaque(index)
        shards.append(v.ResponseShard(float(label), name, positions))
        arrays[name] = source['y'][np.asarray(positions)].copy()
    job = v.FeatureJob(context, opaque(1 + id_offset), opaque(2 + id_offset), opaque(3 + id_offset),
                       tuple(shards), source['y'].shape[1])
    return job, arrays


def fixture():
    return {'session': 'p1_1', 'field': 'unit', 'family': 'context', 'layer': 0,
            'lag_index': 20, 'lag_bins': 0,
            'qid': np.array([-0., 0., -2., 3., -2., 3.], dtype='<f8'),
            'time_indices': np.array([2, 3, 5, 8, 13, 21], dtype='<i8'),
            'x': np.arange(180, dtype='<f8').reshape(6, 30),
            'y': np.array([[100., 101.], [102., 103.], [-0., np.nextafter(0., 1.)],
                           [106., 107.], [108., 109.], [110., 111.]], dtype='<f8')}


def operands(source=None, held=-0., *, id_offset=0):
    source = fixture() if source is None else source
    job, arrays = job_inputs(source, id_offset=id_offset)
    selection = b.V.select_rows(job, source['qid'], source['time_indices'], held,
                                working_limit=WORK_LIMIT)
    allowed = {s.object_id: arrays[s.object_id] for s in job.response_shards if s.label != held}
    return source, job, selection, allowed


def encode(source, selection, allowed):
    return b.build_bundle(selection, source['qid'], source['time_indices'], allowed,
                          byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT)


def decode(raw):
    return b.decode_bundle(raw, byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT)


def descriptor(raw, source, job, *, feature_sha=None, limit=8192):
    output = io.BytesIO(); np.save(output, source['x'], allow_pickle=False)
    full_x = output.getvalue()
    return b.make_descriptor(raw, job.context,
                             feature_sha256=feature_sha or hashlib.sha256(full_x).hexdigest(),
                             feature_bytes=len(full_x), feature_fortran_order=False,
                             byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT, descriptor_limit=limit)


def original_fixture():
    path = HERE.parent / 'original-protected-layout-v1/test_layout.py'
    spec = importlib.util.spec_from_file_location('compact_original_oracle', path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module.ORIGINAL, module.fixture()[1]


class BundleControls(unittest.TestCase):
    def test_complete_4209_jobs_preserve_every_original_callback_operand(self):
        original, session = original_fixture()
        jobs = requests = 0
        for source in original.iter_jobs(session):
            job, all_arrays = job_inputs(source)
            def capture(train_x, train_y, query_x, context):
                nonlocal requests
                selection = b.V.select_rows(job, source['qid'], source['time_indices'],
                                            context['held_qid'], working_limit=WORK_LIMIT)
                allowed = {s.object_id: all_arrays[s.object_id] for s in job.response_shards
                           if s.label != context['held_qid']}
                raw = encode(source, selection, allowed)
                actual = b.assemble_request(source['x'], raw, job.context,
                                            byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT)
                for value, expected in zip(actual[:3], (train_x, train_y, query_x)):
                    np.testing.assert_array_equal(value, expected)
                    self.assertEqual(value.tobytes(order='C'), expected.tobytes(order='C'))
                self.assertEqual(set(actual[3]), set(context))
                for key, expected in context.items():
                    if isinstance(expected, np.ndarray):
                        np.testing.assert_array_equal(actual[3][key], expected)
                        self.assertEqual(actual[3][key].tobytes(), expected.tobytes())
                    else:
                        self.assertEqual(actual[3][key], expected)
                requests += 1
                return np.zeros((len(query_x), train_y.shape[1]), dtype=np.float64)
            original.predict_job(source, capture, remaining_requests=len(np.unique(source['qid'])), sink=lambda _: None)
            jobs += 1
        self.assertEqual(jobs, 4209)
        self.assertGreater(requests, 20000)

    def test_signed_zero_subnormal_and_fortran_inputs_survive_exactly(self):
        source, job, selection, allowed = operands()
        allowed = {key: np.asfortranarray(value) for key, value in allowed.items()}
        raw = encode(source, selection, allowed)
        actual = decode(raw)
        self.assertEqual(actual.qid.tobytes(), source['qid'].tobytes())
        self.assertEqual(actual.time_indices.tobytes(), source['time_indices'].tobytes())
        expected = source['y'][source['qid'] != selection.held_qid]
        self.assertEqual(actual.train_y.tobytes(), expected.tobytes())
        self.assertEqual(len(raw), 64 + 16 * len(source['qid']) + expected.nbytes)

    def test_held_target_and_private_ids_do_not_change_bundle_or_request_id(self):
        results = []
        for held_change, ids in ((0., 0), (999999., 0), (0., 100)):
            source = fixture()
            source['y'][source['qid'] == 0.] += held_change
            source, job, selection, allowed = operands(source, id_offset=ids)
            raw = encode(source, selection, allowed)
            public = descriptor(raw, source, job)
            results.append((raw, public.public_json, public.public_id))
            for name in (job.feature_id, job.qid_id, job.time_id, *allowed):
                self.assertNotIn(name.encode(), public.public_json)
                self.assertNotIn(name.encode(), raw)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])

    def test_allowed_training_and_selected_feature_changes_change_request_identity(self):
        source, job, selection, allowed = operands()
        baseline = descriptor(encode(source, selection, allowed), source, job).public_id
        first = next(iter(allowed))
        allowed[first] = allowed[first].copy(); allowed[first][0, 0] += 1.
        changed = descriptor(encode(source, selection, allowed), source, job).public_id
        self.assertNotEqual(baseline, changed)
        source, job, selection, allowed = operands()
        self.assertNotEqual(baseline, descriptor(encode(source, selection, allowed), source, job,
                                               feature_sha='a' * 64).public_id)

    def test_missing_extra_or_held_target_arrays_are_refused(self):
        source, job, selection, allowed = operands()
        broken = [dict(allowed), dict(allowed)]
        broken[0].pop(next(iter(broken[0])))
        held = next(s for s in job.response_shards if s.label == selection.held_qid)
        broken[1][held.object_id] = source['y'][source['qid'] == selection.held_qid].copy()
        for value in broken:
            with self.assertRaises(ValueError):
                encode(source, selection, value)

    def test_full_maps_must_match_the_exact_selected_row_join(self):
        source, job, selection, allowed = operands()
        for key, index, value in (('qid', 2, 88.), ('time_indices', 2, 6)):
            bad = dict(source); bad[key] = source[key].copy(); bad[key][index] = value
            with self.assertRaises(ValueError):
                encode(bad, selection, allowed)

    def test_wire_shape_padding_values_and_extent_fail_closed(self):
        source, job, selection, allowed = operands()
        raw = encode(source, selection, allowed)
        changes = [(0, b'X'), (8, struct.pack('<I', 2)), (12, struct.pack('<I', 1)),
                   (16, struct.pack('<Q', 144112)), (24, struct.pack('<Q', 6)),
                   (32, struct.pack('<Q', 83)), (40, struct.pack('<d', float('nan'))),
                   (63, b'X'), (64, struct.pack('<d', float('nan'))),
                   (64 + 8 * 6, struct.pack('<q', -1)),
                   (len(raw) - 8, struct.pack('<d', float('inf')))]
        for offset, payload in changes:
            with self.subTest(offset=offset):
                changed = bytearray(raw); changed[offset:offset + len(payload)] = payload
                with self.assertRaises(ValueError):
                    decode(bytes(changed))
        for changed in (raw[:-1], raw + b'\0'):
            with self.assertRaises(ValueError):
                decode(changed)

    def test_decode_caps_precede_numeric_views_and_mutable_buffers_are_refused(self):
        source, job, selection, allowed = operands()
        raw = encode(source, selection, allowed)
        with mock.patch.object(b.np, 'frombuffer', side_effect=AssertionError('Numeric view before admission')):
            for limits in ({'byte_limit': len(raw) - 1, 'working_limit': WORK_LIMIT},
                           {'byte_limit': BYTE_LIMIT, 'working_limit': 1}):
                with self.assertRaises(ValueError):
                    b.decode_bundle(raw, **limits)
        with self.assertRaises(ValueError):
            decode(bytearray(raw))

    def test_decoded_arrays_and_encoded_bytes_have_no_writable_alias(self):
        source, job, selection, allowed = operands()
        raw = encode(source, selection, allowed)
        expected = raw
        source['qid'][:] = 4.; source['time_indices'][:] = 8
        for value in allowed.values():
            value[:] = 9.
        self.assertEqual(raw, expected)
        decoded = decode(raw)
        for value in (decoded.qid, decoded.time_indices, decoded.train_y):
            self.assertFalse(value.flags.writeable)
            with self.assertRaises(ValueError):
                value.setflags(write=True)

    def test_forged_selection_is_revalidated_before_serialization(self):
        source, job, selection, allowed = operands()
        object.__setattr__(selection, 'query_positions', (2, 3))
        with self.assertRaises(ValueError):
            encode(source, selection, allowed)

    def test_request_descriptor_is_compact_and_context_bound(self):
        source, job, selection, allowed = operands()
        raw = encode(source, selection, allowed)
        public = descriptor(raw, source, job)
        self.assertEqual(public.public_id, hashlib.sha256(public.public_json).hexdigest())
        self.assertLess(len(public.public_json), 8192)
        json.loads(public.public_json)
        for forbidden in (b'row_positions', b'train_positions', b'query_positions', b'train_time_indices'):
            self.assertNotIn(forbidden, public.public_json)
        with self.assertRaises(ValueError):
            descriptor(raw, source, job, limit=1)
        changed_context = b.V.JobContext('p1_1', 'unit', 'context', 1, 20, 0)
        changed = b.make_descriptor(raw, changed_context, feature_sha256='a' * 64,
                                    feature_bytes=source['x'].nbytes + 128,
                                    byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT)
        same_feature = descriptor(raw, source, job, feature_sha='a' * 64)
        self.assertNotEqual(changed.public_id, same_feature.public_id)

    def test_target_kind_and_feature_geometry_cannot_be_relabelled(self):
        source, job, selection, allowed = operands()
        raw = encode(source, selection, allowed)
        wrong = b.V.JobContext('p1_1', 'population', 'context', 0, 20, 0)
        for x, context in ((source['x'], wrong), (source['x'][:-1], job.context)):
            with self.assertRaises(ValueError):
                b.assemble_request(x, raw, context, byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT)
        with self.assertRaises(ValueError):
            b.make_descriptor(raw, job.context, feature_sha256='a' * 64, feature_bytes=1,
                              byte_limit=BYTE_LIMIT, working_limit=WORK_LIMIT)


if __name__ == '__main__':
    unittest.main()
