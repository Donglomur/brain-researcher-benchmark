"""Generated cache-to-original-score controls; no authentic inputs or AI calls."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import join as j

BYTE = 65536
WORK = 32 * 1024**2
PINS = {'store_sha256': '1' * 64, 'candidate_sha256': '2' * 64,
        'schedule_sha256': '3' * 64, 'provider_source_sha256': '4' * 64}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_cache_fixture(root):
    path = HERE.parent / 'original-private-cache-v1/test_cache.py'
    spec = importlib.util.spec_from_file_location('joined_generated_cache_fixture', path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    store, base, specs, arrays = module.fixture(root)
    cache = module.make_cache(store)
    return module, store, cache, base, specs, arrays


def context(job):
    return {key: getattr(job.context, key) for key in j.SOURCE_CONTEXT_KEYS}


def coords(layer=0):
    return {'session_index': 0, 'field_index': 1, 'layer': layer, 'lag_index': 20, 'lag_bins': 0}


def run_for(layers=(0, 1)):
    return j.make_run(**PINS, condition='paper_data', working_limit=WORK,
                      generated_contexts=[coords(layer) for layer in layers], generated_requests=3 * len(layers))


def source_targets(job, arrays):
    y = np.empty((len(arrays[job.qid_id]), job.output_columns), dtype='<f8')
    for shard in job.response_shards:
        y[np.asarray(shard.row_positions)] = arrays[shard.object_id]
    return y


def frozen(run, cache, job, specs, arrays):
    feature = next(s for s in specs if s.object_id == job.feature_id)
    y = source_targets(job, arrays)
    value = j.freeze_job(run, context=context(job), qid=arrays[job.qid_id],
                         time_indices=arrays[job.time_id], outputs=job.output_columns,
                         support_class_sha256='5' * 64, target_sha256=sha(y.tobytes()),
                         feature={'sha256': feature.sha256, 'bytes': feature.bytes,
                                  'fortran_order': feature.fortran_order},
                         bundle_for_held=lambda held: cache.get(job, held),
                         byte_limit=BYTE, working_limit=WORK, max_bundle_bytes=1024**2)
    return value, y


def raw_prediction(value, variant=0):
    value = np.array(value, dtype='<f4' if variant == 0 else '>f8',
                     order='C' if variant == 0 else 'F')
    out = io.BytesIO(); np.save(out, value, allow_pickle=False)
    return out.getvalue(), np.asarray(value, dtype='<f8')


def closure(public, raw):
    return {'schema': 'language-private-invocation-closure/v1',
            'request_sha256': public.public_id, 'candidate_sha256': PINS['candidate_sha256'],
            'provider_source_sha256': PINS['provider_source_sha256'],
            'natural_exit_zero': True, 'owned_processes_absent': True,
            'private_view_retired': True, 'transport_sha256': sha(raw)}


def materialize_small(root, *, constant=False):
    module, store, cache, base, specs, arrays = load_cache_fixture(root / 'input')
    run = run_for()
    c = module.c
    jobs = [base, c.V.FeatureJob(c.V.JobContext('p1_1', 'unit', 'context', 1, 20, 0),
                               base.feature_id, base.qid_id, base.time_id,
                               base.response_shards, base.output_columns)]
    plans = [frozen(run, cache, job, specs, arrays) for job in jobs]
    writer = j.CompactWriter(root / 'packed', run, output_limit=1024**2,
                             working_limit=WORK, byte_limit=BYTE)
    expected = []
    try:
        for job_index, (job, (plan, y)) in enumerate(zip(jobs, plans)):
            writer.begin_job(plan)
            result = np.empty_like(y)
            for index, held in enumerate(np.unique(arrays[job.qid_id])):
                public = writer.request(cache.get(job, float(held)))
                select = arrays[job.qid_id] == held
                values = np.ones_like(y[select]) if constant else (y[select] * .25 + np.arange(len(y[select]))[:, None])
                raw, canonical = raw_prediction(values, (index + job_index) % 2)
                writer.accept(request_id=public.public_id, raw_prediction=raw, closure=closure(public, raw))
                result[select] = canonical
            np.testing.assert_array_equal(writer.finish_job(), result)
            expected.append(result)
        receipt = writer.finish()
    finally:
        writer.close()
    return run, plans, expected, receipt, store.private_metrics(), cache.private_metrics()


class JoinControls(unittest.TestCase):
    def test_real_cache_to_compact_ids_to_packed_rows_and_original_pearson(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name)
            run, plans, expected, receipt, store_metrics, cache_metrics = materialize_small(root)
            reader = j.CompactReader(root / 'packed', run, receipt, receipt_sha256=sha(j.encoded(receipt)),
                                     read_limit=1024**2, working_limit=WORK)
            try:
                for (plan, y), prediction in zip(plans, expected):
                    result = reader.score_job(plan, y)
                    self.assertEqual(result['predictions'].tobytes(), prediction.tobytes())
                    oracle = j.ORIGINAL.pooled_pearson(y, prediction)
                    np.testing.assert_array_equal(result['correlations'], oracle)
                    self.assertFalse(result['scientific_qualification'])
                finished = reader.finish()
            finally:
                reader.close()
            self.assertTrue(finished['compact_request_identity_join_verified'])
            self.assertFalse(finished['protected_execution_qualified'])
            self.assertFalse(receipt['provider_journal_independently_verified'])
            self.assertEqual(receipt['jobs'], 2)
            self.assertEqual(receipt['requests'], 6)
            self.assertTrue(receipt['software_callback_requests_not_AI_API_calls'])
            self.assertEqual(receipt['frozen_bundle_bytes'], receipt['dispatched_bundle_bytes'])
            self.assertGreater(cache_metrics['hits'], 0)
            self.assertGreater(store_metrics['bytes_read'], 0)

    def test_constant_predictions_preserve_original_undefined_pearson(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name)
            run, plans, _, receipt, _, _ = materialize_small(root, constant=True)
            reader = j.CompactReader(root / 'packed', run, receipt, receipt_sha256=sha(j.encoded(receipt)),
                                     read_limit=1024**2, working_limit=WORK)
            try:
                for plan, y in plans:
                    result = reader.score_job(plan, y)
                    self.assertTrue(np.isnan(result['correlations']).all())
                reader.finish()
            finally:
                reader.close()

    def test_private_target_pin_rejects_changed_values_before_scoring(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name)
            run, plans, _, receipt, _, _ = materialize_small(root)
            reader = j.CompactReader(root / 'packed', run, receipt, receipt_sha256=sha(j.encoded(receipt)),
                                     read_limit=1024**2, working_limit=WORK)
            try:
                plan, y = plans[0]
                changed = y.copy(); changed[0, 0] += 1
                with self.assertRaises(ValueError):
                    reader.score_job(plan, changed)
                self.assertTrue(reader.failed)
            finally:
                reader.close()

    def test_wrong_request_candidate_provider_transport_and_closure_are_refused(self):
        for fault in ('request', 'candidate', 'provider', 'transport', 'closure', 'shape'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=HERE) as name:
                root = Path(name)
                _, _, cache, job, specs, arrays = load_cache_fixture(root / 'input')
                run = run_for((0,)); plan, y = frozen(run, cache, job, specs, arrays)
                writer = j.CompactWriter(root / 'packed', run, output_limit=1024**2,
                                         working_limit=WORK, byte_limit=BYTE)
                try:
                    writer.begin_job(plan)
                    held = float(np.unique(arrays[job.qid_id])[0])
                    public = writer.request(cache.get(job, held))
                    prediction = y[arrays[job.qid_id] == held]
                    if fault == 'shape':
                        prediction = prediction[:-1]
                    raw, _ = raw_prediction(prediction)
                    record = closure(public, raw)
                    request = public.public_id
                    if fault == 'request': request = 'f' * 64
                    if fault == 'candidate': record['candidate_sha256'] = 'f' * 64
                    if fault == 'provider': record['provider_source_sha256'] = 'f' * 64
                    if fault == 'transport': record['transport_sha256'] = 'f' * 64
                    if fault == 'closure': record['owned_processes_absent'] = False
                    with self.assertRaises(ValueError):
                        writer.accept(request_id=request, raw_prediction=raw, closure=record)
                    self.assertTrue(writer.failed)
                    self.assertFalse((root / 'packed/MANIFEST.json').exists())
                finally:
                    writer.close()

    def test_out_of_order_bundle_and_incomplete_job_poison_collection(self):
        for fault in ('order', 'incomplete'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(dir=HERE) as name:
                root = Path(name)
                _, _, cache, job, specs, arrays = load_cache_fixture(root / 'input')
                run = run_for((0,)); plan, _ = frozen(run, cache, job, specs, arrays)
                writer = j.CompactWriter(root / 'packed', run, output_limit=1024**2,
                                         working_limit=WORK, byte_limit=BYTE)
                try:
                    writer.begin_job(plan)
                    with self.assertRaises(ValueError):
                        if fault == 'order':
                            writer.request(cache.get(job, float(np.unique(arrays[job.qid_id])[1])))
                        else:
                            writer.finish_job()
                    self.assertTrue(writer.failed)
                finally:
                    writer.close()

    def test_private_target_hash_is_absent_from_public_descriptor(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name)
            _, _, cache, job, specs, arrays = load_cache_fixture(root / 'input')
            run = run_for((0,)); plan, y = frozen(run, cache, job, specs, arrays)
            private_hash = sha(y.tobytes())
            self.assertIn(private_hash.encode(), plan.authority_json)
            writer = j.CompactWriter(root / 'packed', run, output_limit=1024**2,
                                     working_limit=WORK, byte_limit=BYTE)
            try:
                writer.begin_job(plan)
                public = writer.request(cache.get(job, -2.))
                self.assertNotIn(private_hash.encode(), public.public_json)
                for value in PINS.values():
                    self.assertNotIn(value.encode(), public.public_json)
            finally:
                writer.close()

    def test_full_source_schedule_is_exact_and_generated_scope_cannot_make_a_panel(self):
        full = j.make_run(**PINS, condition='paper_data_author_code', working_limit=512 * 1024**2)
        binding = json.loads(full.binding_json)
        self.assertEqual(len(full.contexts), 58926)
        self.assertEqual(binding['jobs'], 58926)
        self.assertEqual(binding['requests'], 6776076)
        self.assertEqual(binding['job_context_sha256'], j.FULL_CONTEXT_SHA)
        with self.assertRaises(ValueError):
            j.OriginalPanel(run_for(), working_limit=WORK)

    def test_all224_generated_mapping_cannot_bypass_original_request_total(self):
        # Exercise every canonical output coordinate with small generated input
        # authorities. This does not create the full packed store or pretend
        # these two-group supports equal the authentic source's support roster.
        work = 512 * 1024**2
        run = j.make_run(**PINS, condition='paper_data', working_limit=work)
        panel = j.OriginalPanel(run, working_limit=work)
        qid = np.array([-0., 1.], dtype='<f8')
        times = np.array([0, 1], dtype='<i8')
        feature = {'sha256': '6' * 64, 'bytes': 608, 'fortran_order': False}
        packets, targets = {}, {}
        v = j.B.V
        def oid(n):
            return 'obj-' + str(uuid.UUID(int=n, version=4))
        for width in {1, *j.SOURCE_PANEL.SESSION_UNITS.values()}:
            y = np.arange(2 * width, dtype='<f8').reshape(2, width) / 100. + .1
            targets[width] = sha(y.tobytes())
            shards = tuple(v.ResponseShard(float(label), oid(10 + k), (k,))
                           for k, label in enumerate(qid))
            context_value = v.JobContext('p1_1', 'unit', 'context', 0, 20, 0)
            source_job = v.FeatureJob(context_value, oid(1), oid(2), oid(3), shards, width)
            packets[width] = {}
            for held in qid:
                selection = v.select_rows(source_job, qid, times, float(held), working_limit=WORK)
                allowed = {s.object_id: y[np.asarray(s.row_positions)].copy() for s in shards if s.label != held}
                packets[width][float(held)] = j.B.build_bundle(selection, qid, times, allowed,
                                                              byte_limit=BYTE, working_limit=WORK)
        callbacks = 0
        for packed_context in j.L.iter_source_contexts():
            source = j._context_from_coordinates(packed_context)
            width = j.SOURCE_PANEL.SESSION_UNITS[source['session']] if source['field'] == 'unit' else 1
            def provide(held):
                nonlocal callbacks
                callbacks += 1
                return packets[width][held]
            job = j.freeze_job(run, context=source, qid=qid, time_indices=times, outputs=width,
                               support_class_sha256='5' * 64, target_sha256=targets[width], feature=feature,
                               bundle_for_held=provide, byte_limit=BYTE, working_limit=WORK,
                               max_bundle_bytes=1024**2)
            score = (packed_context['field_index'] / 20. + source['layer'] / 1000.
                     + source['lag_index'] / 100000. + np.arange(width, dtype='<f8') / 10000000.)
            panel.add(job, score)
        self.assertEqual(callbacks, 2 * 58926)
        arrays = 0
        fields = list(j.SOURCE_PANEL.SOURCE_FILES)
        for sid in j.L.SESSIONS:
            for field, shape in j.SOURCE_PANEL.shapes(sid).items():
                if field == 'unit':
                    unit, lag, layer = np.indices(shape)
                elif len(shape) == 1:
                    layer = np.arange(shape[0]); unit = lag = 0
                else:
                    lag, layer = np.indices(shape); unit = 0
                expected = fields.index(field) / 20. + layer / 1000. + lag / 100000. + unit / 10000000.
                np.testing.assert_array_equal(panel.panel[sid][field], expected)
                arrays += 1
        self.assertEqual(arrays, 224)
        # All jobs and output slots alone must not masquerade as the complete
        # original6,776,076-request route. No source reducer is called here.
        with self.assertRaises(ValueError):
            panel.finish()


if __name__ == '__main__':
    unittest.main()
