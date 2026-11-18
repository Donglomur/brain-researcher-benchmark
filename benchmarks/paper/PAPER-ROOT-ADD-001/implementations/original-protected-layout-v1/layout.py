"""Source-native protected-layout arithmetic from a frozen saved support census.

No original arrays, candidate code, Docker command or scientific model is read
or run. Store sharing is a prospective serialization plan, not permission to
co-expose different feature jobs or to reuse candidate memory across held qids.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
GEOMETRY_PATH = HERE.parent / 'original-inputs-v1/source-bindings.json'
CENSUS_PIN = {'bytes': 2026854, 'sha256': '3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37'}
GEOMETRY_PIN = {'bytes': 58852, 'sha256': '3b9466d243a86fec32b99a6bf71816c90bd54ef45a292f3e475adce5eeb8e1e7'}
SESSIONS = ('p1_1', 'p1_2', 'p2_1', 'p2_2', 'p3_1', 'p3_2', 'p4_1',
            'p5_1', 'p5_2', 'p6_1', 'p7_1', 'p7_2', 'p8_1', 'p8_2')
NPY_HEADER_BYTES = 128  # Proposed canonical writer profile; no file is written here.
RECORD_BYTES = {'request': 192, 'job': 256, 'feature': 256,
                'response_class': 256, 'response_shard': 128, 'base_target': 128}
CONTEXT_KEYS = ('session_index', 'field_index', 'layer', 'lag_index', 'lag_bins')
OUTPUT_LIMIT = 65536


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def positive(value):
    return type(value) is int and value > 0


def parse(raw):
    def pairs(items):
        result = {}
        for name, value in items:
            need(name not in result, 'Duplicate metadata key')
            result[name] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite metadata constant'))


def load_pinned(path, expected):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No metadata symlink')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected['bytes'] <= 3 * 1024**2, 'Exact bounded ordinary metadata')
        raw = stream.read(expected['bytes'] + 1)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        after, named = os.fstat(stream.fileno()), path.lstat()
        need(all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields),
             'Metadata changed during read')
    need(pin(raw) == expected, 'Frozen source metadata pin mismatch')
    return parse(raw)


def specs():
    rows = [('population', 'context', False, 'population', tuple(range(-20, 20)), 33),
            ('unit', 'context', False, 'unit', tuple(range(-20, 20)), 33),
            ('time_shuffle', 'context', False, 'population', tuple(range(-20, 20)), 33),
            ('random_token', 'random_token', False, 'population', (-10,), 33),
            ('sentence_swap', 'context', True, 'population', (-10,), 33)]
    rows += [(f, f, False, 'population', (-10,), 33)
             for f in ('ngram1', 'ngram3', 'ngram5', 'ngram7', 'ngram10')]
    rows += [(f + suffix, f, False, 'population', (-3, -2, -1), 1)
             for f in ('sem_syn', 'word2vec', 'syn') for suffix in ('', '_shuffle')]
    return tuple(rows)


def feature_key(session, field, layer, lag_bins, ordered_time_support_sha):
    """A sufficient source X identity; it never grants feature-union access.

    Source family/word order/PCA data are fixed per session by source pins.
    Only positive lag shifts X. Response kind and target permutation do not.
    """
    choices = {row[0]: row for row in specs()}
    need(session in SESSIONS and field in choices, 'Original session/field identity')
    _, family, swap, _, lags, layers = choices[field]
    need(type(layer) is int and 0 <= layer < layers and type(lag_bins) is int
         and lag_bins in lags and digest(ordered_time_support_sha), 'Exact source feature context')
    return {'session': session, 'family': family, 'sentence_swap': swap,
            'layer': layer, 'positive_lag_or_zero': max(lag_bins, 0),
            'ordered_time_support_sha256': ordered_time_support_sha}


def iter_source_contexts(session_ids=SESSIONS):
    """Original source coordinates alone; no support operands or array reads."""
    need(type(session_ids) in (tuple, list) and len(set(session_ids)) == len(session_ids)
         and all(s in SESSIONS for s in session_ids), 'Unique original session context roster')
    for sid in session_ids:
        for fi, (_, _, _, _, lags, layers) in enumerate(specs()):
            for layer in range(layers):
                for li, lag in enumerate(lags):
                    yield {'session_index': SESSIONS.index(sid), 'field_index': fi,
                           'layer': layer, 'lag_index': li, 'lag_bins': lag}


def validate_session(row, geometry):
    sid = geometry['id']
    need(sid in SESSIONS and row['session'] == sid and row['person'] == sid.split('_')[0],
         'Exact session/person join')
    need(all(positive(geometry[k]) for k in ('time_bins', 'units', 'word_rows', 'llm_layers'))
         and geometry['llm_layers'] == 33 and 40 < geometry['time_bins'] <= 144111
         and geometry['units'] <= 82, 'Exact bounded source geometry')
    groups, classes = row['field_lag_groups'], row['support_classes']
    need(type(groups) is list and len(groups) == 145 and type(classes) is dict
         and 0 < len(classes) <= 145, 'Complete bounded source field/lag lattice')
    expected = [(field, li, lag, layers, geometry['units'] if target == 'unit' else 1)
                for field, _, _, target, lags, layers in specs() for li, lag in enumerate(lags)]
    used, by_group = {}, {}
    for group, (field, li, lag, layers, columns) in zip(groups, expected):
        need(all(type(group[k]) is int for k in ('lag_index', 'lag_bins', 'layers', 'output_columns'))
             and (group['field'], group['lag_index'], group['lag_bins'], group['layers'], group['output_columns'])
             == (field, li, lag, layers, columns), 'Exact ordered original field/lag/layer/target lattice')
        key = group['support_class']
        need(digest(key) and key in classes, 'Bound complete source support class')
        item = classes[key]
        signature, held = item['signature'], item['held_roster']
        need(pin(encoded(signature))['sha256'] == key and signature['session'] == sid,
             'Support signature content/identity mismatch')
        target = 'centered3bin_units' if field == 'unit' else 'centered3bin_population_mean'
        need(signature['source_transform'] == target and signature['zero_padding_sentinel'] == -1,
             'Source target lineage/kind mismatch')
        need(all(digest(signature[k]) for k in ('source_response_member_sha256',
                  'ordered_time_indices_sha256', 'ordered_qid_sha256', 'ordered_response_source_rows_sha256')),
             'Complete source support/response lineage hashes')
        m, q = group['rows'], group['held_qids']
        need(positive(m) and positive(q) and 2 <= q <= m <= geometry['time_bins']
             and signature['rows'] == m and signature['held_qids'] == q and held['count'] == q,
             'Complete represented held-group support')
        need(positive(held['minimum_query_rows']) and positive(held['maximum_query_rows'])
             and 1 <= held['minimum_query_rows'] <= held['maximum_query_rows'] <= m-q+1
             and all(digest(held[k]) for k in ('held_qid_sha256', 'query_counts_sha256')),
             'Bound nonempty query partition')
        need(group['source_requests'] == layers*q, 'Exact source request multiplicity')
        used.setdefault(key, []).append([field, li])
        by_group[field, li] = group
    need(set(used) == set(classes), 'No omitted or unreferenced support classes')
    fr = {v['signature']['source_response_member_sha256'] for v in classes.values()}
    need(len(fr) == 1, 'One original response source per session')
    for key, links in used.items():
        need(classes[key]['field_lag_groups'] == links
             and classes[key]['jobs'] == sum(by_group[tuple(x)]['layers'] for x in links),
             'Exact complete support-class membership')
    need(row['jobs'] == sum(g['layers'] for g in groups) == 4209
         and row['source_requests'] == sum(g['source_requests'] for g in groups)
         and row['proven_class_held_units'] == sum(v['held_roster']['count'] for v in classes.values()),
         'Complete source jobs/requests/response-held units')
    return by_group


def iter_job_layout(row, geometry):
    """Yield all4209 job identities in unchanged source field->layer->lag order."""
    by_group = validate_session(row, geometry)
    for fi, (field, _, _, _, lags, layers) in enumerate(specs()):
        for layer in range(layers):
            for li, lag in enumerate(lags):
                g = by_group[field, li]
                support = row['support_classes'][g['support_class']]['signature']
                key = feature_key(geometry['id'], field, layer, lag, support['ordered_time_indices_sha256'])
                yield {'session': geometry['id'], 'session_index': SESSIONS.index(geometry['id']),
                       'field': field, 'field_index': fi, 'layer': layer,
                       'lag_index': li, 'lag_bins': lag, 'rows': g['rows'],
                       'columns': g['output_columns'], 'held_qids': g['held_qids'],
                       'feature_key': key, 'feature_key_sha256': pin(encoded(key))['sha256'],
                       'response_class': g['support_class']}


def response_store(row, geometry):
    """Each existing sufficient class has Q disjoint target shards totaling M*D.

    Compact census stores counts/hashes, not actual qid labels. This function
    plans a class store; it does not fabricate a per-qid delivery manifest.
    """
    validate_session(row, geometry)
    for key, item in sorted(row['support_classes'].items()):
        s, held = item['signature'], item['held_roster']
        d = geometry['units'] if s['source_transform'] == 'centered3bin_units' else 1
        yield {'session': geometry['id'], 'response_class': key, 'signature': s,
               'rows': s['rows'], 'columns': d, 'shards': held['count'],
               'held_roster': held, 'payload_bytes': 8*s['rows']*d,
               'npy_header_bytes': NPY_HEADER_BYTES*held['count'],
               'candidate_view_rule': 'Mount exactly all class shards except the current held-qid shard; never mount the parent store.'}


def visible_shards(shard_ids, held_id):
    """Pure manifest rule for a future OS view, not an isolation implementation."""
    need(type(shard_ids) in (tuple, list) and len(shard_ids) >= 2
         and all(type(x) is str and x for x in shard_ids)
         and len(set(shard_ids)) == len(shard_ids) and held_id in shard_ids,
         'Unique complete response shard roster with exact held member')
    return tuple(x for x in shard_ids if x != held_id)


def plan_layout(census, source_geometry, *, require_full_roster=True):
    need(type(census) is dict and census['schema'] == 'language-original-source-support-census/v1',
         'Original source support census schema')
    geometries = source_geometry['sessions']
    rows = census['sessions']
    need(type(rows) is list and 1 <= len(rows) <= 14 and len(rows) == len(geometries)
         and [r['session'] for r in rows] == [g['id'] for g in geometries]
         and len({r['session'] for r in rows}) == len(rows), 'Exact ordered complete geometry/census join')
    if require_full_roster:
        need(tuple(r['session'] for r in rows) == SESSIONS, 'Full original14-session roster')
    unique_features, feature_shapes = {}, {}
    job_hash, response_hash, context_hash = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    per_session, response_classes, response_shards = [], 0, 0
    response_payload = response_headers = prediction_payload = requests = jobs = 0
    base_response_payload = response_shard_references = one_job_feature_payload = 0
    source_array_payload = observation_map_rows = 0
    for row, geometry in zip(rows, geometries):
        sid, before_features = geometry['id'], len(unique_features)
        s_jobs = s_requests = s_feature_once = s_predictions = s_shards = s_responses = s_map_rows = 0
        for job in iter_job_layout(row, geometry):
            key, m, d, q = job['feature_key_sha256'], job['rows'], job['columns'], job['held_qids']
            if key in unique_features:
                need(unique_features[key] == job['feature_key'] and feature_shapes[key] == [m, 30],
                     'Shared feature identity/geometry collision')
            else:
                unique_features[key], feature_shapes[key] = job['feature_key'], [m, 30]
            job_hash.update(encoded({'ordinal': jobs, **job}))
            context_hash.update(encoded({key: job[key] for key in CONTEXT_KEYS}))
            jobs += 1; requests += q; s_jobs += 1; s_requests += q
            prediction_payload += 8*m*d; s_predictions += 8*m*d
            one_job_feature_payload += 240*m; s_feature_once += 240*m
            response_shard_references += q*(q-1)
        for store in response_store(row, geometry):
            response_hash.update(encoded(store))
            response_classes += 1; response_shards += store['shards']
            response_payload += store['payload_bytes']; response_headers += store['npy_header_bytes']
            observation_map_rows += store['rows']; s_map_rows += store['rows']
            s_shards += store['shards']; s_responses += store['payload_bytes']
        base = 8*geometry['time_bins']*(geometry['units']+1)
        base_response_payload += base
        # Same16 source output arrays: unit[U,40,33]. The nonunit
        # fields total2889values: population/time_shuffle2640 +7*33 +6*3.
        source_array_payload += 8*(geometry['units']*40*33 + 2889)
        per_session.append({'session': sid, 'person': row['person'], 'source_jobs': s_jobs,
                            'source_requests': s_requests, 'unique_feature_matrices': len(unique_features)-before_features,
                            'one_X_per_job_payload_bytes': s_feature_once,
                            'response_classes': len(row['support_classes']), 'response_shards': s_shards,
                            'response_shard_payload_bytes': s_responses,
                            'private_observation_map_rows': s_map_rows,
                            'private_observation_map_payload_bytes': 24*s_map_rows,
                            'base_population_and_unit_response_payload_bytes': base,
                            'packed_prediction_payload_bytes': s_predictions})
    need(jobs == census['jobs'] and requests == census['source_requests']
         and response_shards == census['proven_class_held_units'], 'Saved total source request/class coverage')
    if require_full_roster:
        need(jobs == 58926 and requests == 6776076 and response_shards == 202407
             and len({r['person'] for r in rows}) == 8 and census['original_result_arrays'] == 224,
             'Accepted full original source census counts unchanged')
    need(prediction_payload == census['costs']['raw_prediction_f64_payload_bytes'],
         'Saved complete prediction payload identity')
    feature_hash = hashlib.sha256()
    feature_payload = 0
    for key in sorted(unique_features):
        shape = feature_shapes[key]
        feature_hash.update(encoded({'feature_key_sha256': key, 'feature_key': unique_features[key], 'shape': shape}))
        feature_payload += shape[0]*shape[1]*8
    matrix_count = len(unique_features)
    base_files, result_files = 2*len(rows), 16*len(rows)
    records = {'request': requests, 'job': jobs, 'feature': matrix_count,
               'response_class': response_classes, 'response_shard': response_shards, 'base_target': base_files}
    index_bytes = {kind: count*RECORD_BYTES[kind] for kind, count in records.items()}
    arrays = {'unique_full_X_payload_bytes': feature_payload,
              'unique_full_X_npy_header_bytes': matrix_count*NPY_HEADER_BYTES,
              'response_shard_payload_bytes': response_payload,
              'response_shard_npy_header_bytes': response_headers,
              'private_observation_map_payload_bytes': 24*observation_map_rows,
              'private_observation_map_npy_header_bytes': 3*response_classes*NPY_HEADER_BYTES,
              'base_population_and_unit_response_payload_bytes': base_response_payload,
              'base_response_npy_header_bytes': base_files*NPY_HEADER_BYTES,
              'packed_prediction_f64_payload_bytes': prediction_payload,
              'packed_prediction_stream_header_bytes': 0,
              'all_source_result_payload_bytes': source_array_payload,
              'all_source_result_npy_header_bytes': result_files*NPY_HEADER_BYTES}
    files = {'unique_feature_npy': matrix_count, 'response_shard_npy': response_shards,
             'base_target_npy': base_files, 'packed_prediction_f64le_stream': 1,
             'private_observation_map_npy': 3*response_classes,
             'full_source_result_npy': result_files,
             'six_fixed_record_indexes': len(RECORD_BYTES),
             'private_support_npz': len(rows)}
    return {
      'schema': 'language-original-protected-layout-plan/v1',
      'status': 'metadata_only_prospective_layout_not_execution_or_storage_admission',
      'full_original_roster': require_full_roster, 'sessions': per_session,
      'source_jobs': jobs, 'source_requests': requests, 'source_result_arrays': result_files,
      'distinct_features': matrix_count, 'response_classes': response_classes,
      'response_shards': response_shards, 'candidate_views_required': requests,
      'candidate_response_shard_reference_count': response_shard_references,
      'one_X_per_feature_job_payload_bytes_before_dedup': one_job_feature_payload,
      'array_payload_and_canonical_header_costs': arrays,
      'fixed_record_width_bytes': RECORD_BYTES.copy(), 'fixed_record_counts': records,
      'fixed_record_index_bytes': index_bytes,
      'arrays_and_six_fixed_indexes_bytes': sum(arrays.values())+sum(index_bytes.values()),
      'artifact_file_counts': files, 'artifact_file_count': sum(files.values()),
      'artifact_file_count_excludes': ['root MANIFEST.json and any later runtime/view/lifecycle artifacts'],
      'schedule_digests': {'ordered_source_job_layout_sha256': job_hash.hexdigest(),
                           'ordered_source_job_context_sha256': context_hash.hexdigest(),
                           'sorted_unique_feature_store_sha256': feature_hash.hexdigest(),
                           'ordered_response_store_sha256': response_hash.hexdigest()},
      'source_job_context': {'keys_for_tuple': list(CONTEXT_KEYS),
                             'encoding': "One {session_index,field_index,layer,lag_index,lag_bins} object/job; json.dumps(sort_keys=True,separators=(',',':'),allow_nan=False)+'\\n', UTF-8; source session->field->layer->lag order.",
                             'count': jobs, 'feature_array_rehash_required_to_authenticate_contexts': False},
      'feature_identity': 'session/family/sentence-swap flag/layer/positive lag or zero/ordered supported-time hash; source inputs and word order fixed by original source pins',
      'response_identity': 'Existing sufficient support class binds full ordered rows/qids, source target kind/transform, shuffled or unshuffled response-row lineage and original fr member SHA.',
      'response_delivery': 'Q disjoint response shards per class; every held-qid view contains Q-1 exact allowed training shards and excludes held shard. Never expose full parent store or full source targets.',
      'private_observation_maps': {'per_response_class_arrays': ['qid:<f8', 'time_indices:<i8', 'response_source_rows:<i8'],
                                   'rows_across_classes': observation_map_rows,
                                   'interpretation': 'Three original ordered observation maps per sufficient response class. Recover targets independently from exact once/session population or unit base arrays and source row lineage, including -1 zero padding. No computed-target substitution and no candidate access.',
                                   'fresh_maps_materialized': False},
      'packed_prediction_store': {'file': 'PREDICTIONS.f64le', 'files': 1, 'header_bytes': 0,
                                   'dtype': '<f8', 'scope': 'One canonical primitive binary stream; exact per-job offsets/contexts live in JOBS.bin256B/job and REQUESTS.bin192B/request. Other four fixed indexes are planned store indexes. MANIFEST.json is excluded from file/byte totals.'},
      'candidate_feature_scope': 'Exactly one feature key per view. Equal response support is not permission to combine33layers/families or retain candidate state across requests.',
      'layout_digest_is_bridge_request_hash': False,
      'cost_limits': 'Exact array payload/count arithmetic from saved metadata;128B headers apply to proposed NPY feature/shard/base/observation-map/result stores only, not the one raw prediction stream. Six fixed indexes include192B/request and256B/job collector records. Excludes support NPZ sizes, root MANIFEST.json from both files and bytes, filesystem overhead, per-view metadata, lifecycle/stderr journals, failed attempts, read/re-hash/copy cost and runtime. No campaign total or peak-disk claim.',
      'source_support_metadata_contains_actual_qid_labels': False,
      'future_view_requirement': 'Recover exact qid partitions from authenticated private support operands; planner never invents qid identities from counts. Separate fresh OS process/view isolation must be proved.',
      'scientific_qualification': False, 'protected_execution_qualified': False,
      'original_data_decoded': False, 'models_or_predictions_run': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    census = load_pinned(args.census, CENSUS_PIN)
    geometry = load_pinned(GEOMETRY_PATH, GEOMETRY_PIN)
    result = plan_layout(census, geometry)
    result['metadata_inputs'] = {'census': CENSUS_PIN, 'source_geometry': GEOMETRY_PIN}
    result['planner_source'] = pin(Path(__file__).read_bytes())
    raw = encoded(result)
    need(len(raw) <= OUTPUT_LIMIT, 'Compact planning receipt cap')
    output = args.output.absolute()
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'No planning-output symlink')
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': result['status'], 'output': str(output), **pin(raw),
                      'source_requests': result['source_requests'], 'source_jobs': result['source_jobs'],
                      'features': result['distinct_features'], 'response_shards': result['response_shards']}))


if __name__ == '__main__':
    main()
