"""Generated complete4209-job controls; no original payload or model execution."""
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout as p


def module(name, path, expected=None):
    if expected:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


INPUTS = module('layout_original_inputs', HERE.parent / 'original-inputs-v1/inputs.py',
                '9a363fb93293cfc5f9fc9caad9f61a708e42618dc0afc9a7a48d9f9d7f41436a')
_old_inputs = sys.modules.get('inputs')
try:
    sys.modules['inputs'] = INPUTS
    ORIGINAL = module('layout_original_prediction', HERE.parent / 'original-inputs-v1/prediction.py',
                      '53476538f93cecea0c2bbcc1c1ff4da4d17ce34ee57fa56d69ae0d48003690e4')
finally:
    if _old_inputs is None:
        sys.modules.pop('inputs', None)
    else:
        sys.modules['inputs'] = _old_inputs
CENSUS = module('layout_source_census', HERE.parent / 'original-support-census-v1/census.py')


def fixture():
    n, w, u = 96, 10, 3
    geometry = {'id': 'p1_1', 'person': 'p1', 'time_bins': n, 'word_rows': w, 'units': u, 'llm_layers': 33}
    timing = np.array([[.1, 1.], [1.1, 2.], [2.1, 3.], [3.1, 4.],
                       [4.1, 5.], [5.1, 6.], [6.1, 7.], [7.1, 8.], [.3, .7], [8.1, 9.]])
    qid = np.array([1., 1., 2., 2., 3., 3., 4., 4., 99999., 5.])
    speaker = np.ones(n, dtype=np.uint8); speaker[14:18] = 0
    keep = {'sem_syn': np.array([1, 0, 1, 1, 1, 1, 1, 1, 1, 1], dtype=bool),
            'word2vec': np.array([1, 1, 1, 1, 0, 1, 1, 1, 1, 1], dtype=bool)}
    session = {'session': geometry['id'], 'timing': timing, 'qid': qid,
               'fr': np.arange(n*u, dtype=float).reshape(n, u)**2,
               'speaker': speaker.astype(float)[:, None]}
    for family in INPUTS.FAMILIES:
        layers = 1 if family in ('sem_syn', 'word2vec', 'syn') else 33
        a = np.arange(w*30*layers, dtype=float).reshape(w, 30, layers)
        a = a + .25*np.sin(a)
        if family in keep:
            a[~keep[family], 0, 0] = np.nan
        session[family] = a
    row = CENSUS.session_census(geometry, timing, qid, speaker, keep, response_member_sha256='1'*64)
    CENSUS.compact_rosters(row)
    return geometry, session, row


def wrapper(geometry, row):
    payload = sum(g['layers']*g['rows']*g['output_columns']*8 for g in row['field_lag_groups'])
    return ({'schema': 'language-original-source-support-census/v1', 'sessions': [row],
             'jobs': row['jobs'], 'source_requests': row['source_requests'],
             'proven_class_held_units': row['proven_class_held_units'], 'original_result_arrays': 16,
             'costs': {'raw_prediction_f64_payload_bytes': payload}}, {'sessions': [geometry]})


class LayoutControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry, cls.session, cls.row = fixture()

    def plan(self, row=None):
        census, geometry = wrapper(self.geometry, self.row if row is None else row)
        return p.plan_layout(census, geometry, require_full_roster=False)

    def test_every_equal_feature_key_has_identical_X_across_complete_original_lattice(self):
        scheduled = list(p.iter_job_layout(self.row, self.geometry))
        self.assertEqual(len(scheduled), 4209)
        arrays, references, count = {}, {}, 0
        for job, plan in zip(ORIGINAL.iter_jobs(self.session), scheduled):
            self.assertEqual(tuple(job[k] for k in ('field', 'layer', 'lag_index', 'lag_bins')),
                             tuple(plan[k] for k in ('field', 'layer', 'lag_index', 'lag_bins')))
            key = plan['feature_key_sha256']
            if key in arrays:
                np.testing.assert_array_equal(arrays[key], job['x'])
            else:
                arrays[key] = job['x'].copy()
            references[job['field'], job['layer'], job['lag_bins']] = key
            count += 1
        self.assertEqual(count, 4209)
        for layer in range(33):
            for lag in range(-20, 20):
                base = references['population', layer, lag]
                self.assertEqual(base, references['unit', layer, lag])
                self.assertEqual(base, references['time_shuffle', layer, lag])
            self.assertEqual(references['population', layer, -20], references['population', layer, 0])
            self.assertNotEqual(references['population', layer, 1], references['population', layer, 2])
            self.assertNotEqual(references['population', layer, -10], references['sentence_swap', layer, -10])
        result = self.plan()
        self.assertEqual(sum(x.nbytes for x in arrays.values()),
                         result['array_payload_and_canonical_header_costs']['unique_full_X_payload_bytes'])
        self.assertEqual(len(arrays), result['distinct_features'])
        # This is a storage-sharing proof only, not a multi-feature candidate input.
        self.assertFalse(result['protected_execution_qualified'])

    def test_response_shards_match_original_targets_and_exclude_held_rows(self):
        source = {}
        for job in ORIGINAL.iter_jobs(self.session):
            source.setdefault((job['field'], job['lag_index']), job)
        stores = list(p.response_store(self.row, self.geometry))
        payload = headers = shard_count = 0
        for store in stores:
            class_row = self.row['support_classes'][store['response_class']]
            jobs = [source[tuple(x)] for x in class_row['field_lag_groups']]
            first = jobs[0]
            for job in jobs[1:]:
                np.testing.assert_array_equal(first['y'], job['y'])
                np.testing.assert_array_equal(first['qid'], job['qid'])
                np.testing.assert_array_equal(first['time_indices'], job['time_indices'])
            labels = np.unique(first['qid'])
            shards = {str(q): np.flatnonzero(first['qid'] == q) for q in labels}
            for held in shards:
                exposed = p.visible_shards(list(shards), held)
                self.assertNotIn(held, exposed)
                rows = np.sort(np.concatenate([shards[x] for x in exposed]))
                np.testing.assert_array_equal(rows, np.flatnonzero(first['qid'] != float(held)))
                self.assertFalse(np.intersect1d(rows, shards[held]).size)
            for rows in shards.values():
                value = first['y'][rows]
                payload += value.nbytes
                stream = io.BytesIO(); np.save(stream, value, allow_pickle=False)
                headers += len(stream.getvalue())-value.nbytes
                shard_count += 1
        result = self.plan()
        costs = result['array_payload_and_canonical_header_costs']
        self.assertEqual(payload, costs['response_shard_payload_bytes'])
        self.assertEqual(headers, costs['response_shard_npy_header_bytes'])
        self.assertEqual(shard_count, result['response_shards'])

    def test_response_target_and_shuffle_do_not_change_feature_identity(self):
        sha = '2'*64
        self.assertEqual(p.feature_key('p1_1', 'population', 5, -10, sha),
                         p.feature_key('p1_1', 'time_shuffle', 5, -10, sha))
        self.assertEqual(p.feature_key('p1_1', 'population', 5, -10, sha),
                         p.feature_key('p1_1', 'unit', 5, 0, sha))
        self.assertEqual(p.feature_key('p1_1', 'sem_syn', 0, -3, sha),
                         p.feature_key('p1_1', 'sem_syn_shuffle', 0, -1, sha))
        for field, layer, lag, changed in [('sentence_swap', 5, -10, sha), ('population', 6, -10, sha),
                                          ('population', 5, 1, sha), ('population', 5, -10, '3'*64),
                                          ('random_token', 5, -10, sha)]:
            self.assertNotEqual(p.feature_key('p1_1', 'population', 5, -10, sha),
                                p.feature_key('p1_1', field, layer, lag, changed))

    def test_complete_costs_file_counts_and_digest_repeatability(self):
        result = self.plan()
        self.assertEqual(result, self.plan())
        self.assertEqual(result['source_jobs'], 4209)
        self.assertEqual(result['source_result_arrays'], 16)
        self.assertEqual(result['source_requests'], self.row['source_requests'])
        self.assertEqual(result['fixed_record_index_bytes']['request'], self.row['source_requests']*192)
        self.assertEqual(result['fixed_record_index_bytes']['job'], 4209*256)
        self.assertEqual(result['artifact_file_count'], sum(result['artifact_file_counts'].values()))
        self.assertEqual(result['arrays_and_six_fixed_indexes_bytes'],
                         sum(result['array_payload_and_canonical_header_costs'].values()) +
                         sum(result['fixed_record_index_bytes'].values()))
        population, units = ORIGINAL.smooth_targets(self.session['fr'])
        self.assertEqual(population.nbytes+units.nbytes,
                         result['array_payload_and_canonical_header_costs']['base_population_and_unit_response_payload_bytes'])

    def test_partial_roster_not_accepted_as_full_original_plan(self):
        census, geometry = wrapper(self.geometry, self.row)
        with self.assertRaises(ValueError):
            p.plan_layout(census, geometry)

    def test_packed_stream_and_private_observation_map_costs_files(self):
        result = self.plan()
        classes = self.row['support_classes']
        rows = sum(v['signature']['rows'] for v in classes.values())
        costs = result['array_payload_and_canonical_header_costs']
        files = result['artifact_file_counts']
        self.assertEqual(costs['private_observation_map_payload_bytes'], 24*rows)
        self.assertEqual(costs['private_observation_map_npy_header_bytes'], 3*128*len(classes))
        self.assertEqual(files['private_observation_map_npy'], 3*len(classes))
        self.assertEqual(files['packed_prediction_f64le_stream'], 1)
        self.assertEqual(costs['packed_prediction_stream_header_bytes'], 0)
        self.assertNotIn('packed_job_prediction_npy', files)
        self.assertNotIn('packed_prediction_npy_header_bytes', costs)
        self.assertNotIn('root_layout_manifest', files)
        self.assertEqual(files['six_fixed_record_indexes'], 6)
        self.assertEqual(result['fixed_record_index_bytes']['request'], result['source_requests']*192)
        self.assertEqual(result['fixed_record_index_bytes']['job'], result['source_jobs']*256)
        # Concrete generated maps store metadata only. They do not replace the
        # independently retained source base-response matrices with predictions.
        payload = headers = 0
        for value in classes.values():
            n = value['signature']['rows']
            for dtype in ('<f8', '<i8', '<i8'):
                array = np.arange(n, dtype=dtype)
                buffer = io.BytesIO(); np.save(buffer, array, allow_pickle=False)
                payload += array.nbytes
                headers += len(buffer.getvalue())-array.nbytes
        self.assertEqual(payload, costs['private_observation_map_payload_bytes'])
        self.assertEqual(headers, costs['private_observation_map_npy_header_bytes'])

    def test_exact_source_context_order_and_canonical_digest(self):
        scheduled = list(p.iter_job_layout(self.row, self.geometry))
        expected = list(p.iter_source_contexts(('p1_1',)))
        actual = [{key: item[key] for key in p.CONTEXT_KEYS} for item in scheduled]
        self.assertEqual(actual, expected)
        digest = hashlib.sha256(b''.join(p.encoded(c) for c in expected)).hexdigest()
        self.assertEqual(self.plan()['schedule_digests']['ordered_source_job_context_sha256'], digest)
        full = list(p.iter_source_contexts())
        self.assertEqual(len(full), 58926)
        self.assertEqual(len({tuple(r[k] for k in p.CONTEXT_KEYS) for r in full}), 58926)
        self.assertEqual(full[0], dict(session_index=0, field_index=0, layer=0, lag_index=0, lag_bins=-20))
        self.assertEqual(full[-1], dict(session_index=13, field_index=15, layer=0, lag_index=2, lag_bins=-1))
        self.assertEqual([r['session_index'] for r in full[4209:4211]], [1, 1])

    def test_boolean_coordinate_is_not_integer_metadata(self):
        row = copy.deepcopy(self.row)
        row['field_lag_groups'][0]['lag_index'] = False
        with self.assertRaises(ValueError):
            self.plan(row)

    def test_mutated_source_lattice_or_class_mapping_rejected(self):
        mutations = [lambda x: x['field_lag_groups'].pop(),
                     lambda x: x['field_lag_groups'][0].update(layers=32),
                     lambda x: x['field_lag_groups'][0].update(output_columns=2),
                     lambda x: x['field_lag_groups'][0].update(source_requests=1),
                     lambda x: x.update(source_requests=1)]
        for mutate in mutations:
            row = copy.deepcopy(self.row); mutate(row)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.plan(row)
        row = copy.deepcopy(self.row)
        item = next(iter(row['support_classes'].values()))
        item['signature']['ordered_time_indices_sha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.plan(row)

    def test_no_missing_duplicate_or_ambiguous_held_shard(self):
        for shards, held in [(['a'], 'a'), (['a', 'a'], 'a'), (['a', 'b'], 'c'), (['a', ''], 'a')]:
            with self.subTest(shards=shards, held=held), self.assertRaises(ValueError):
                p.visible_shards(shards, held)
        self.assertEqual(p.visible_shards(['a', 'b', 'c'], 'b'), ('a', 'c'))


if __name__ == '__main__':
    unittest.main()
