"""Bounded complete NEURAL-099 assumed-support count preparation.

Importing this file opens nothing and imports no native modules. Authentic CLI
execution requires separate exact admission. The output remains evaluator-only;
this construction does not establish physical observation or process isolation.
"""
from array import array
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat


PROFILE = {'source_files': 26, 'source_trial_rows': 5238, 'region_cells': 49,
           'eligible_clusters': 1387, 'unassigned_clusters': 666,
           'source_events': 1224589, 'source_units': 2053,
           'source_hash_bytes': 455615424, 'case_count': 9867}
COUNT_BYTES = 15787200
MAX_METADATA_BYTES = 4194304
MAX_OUTPUT_BYTES = 25165824
RUNTIME = {'h5py': '3.13.0', 'hdf5': '1.14.6', 'numpy': '2.2.6'}
CONTRACT_PINS = {
    'support': {'bytes':69757,'sha256':'35a59c971f015b2b58d923098be21ff208fd889e7fbbe7dd6af233afa38b5e8b'},
    'cohort': {'bytes':11197,'sha256':'87f7087dce132a08d4edbc89ab0f982f0672c2bc8f89e29fd2ee40fda5e575eb'},
    'protocol': {'bytes':3365,'sha256':'9d76c4d149b2a99c2609225d511c720607f77f547d3b3aae0cfe50dd2fe71a7a'},
}
MODULE_NAMES = ('runtime_io', 'event_source', 'stream_counts', 'count_oracle', 'count_packet')


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def _pin(path):
    body = Path(path).read_bytes()
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def _read_pin(path, pin, maximum=MAX_METADATA_BYTES):
    require(type(pin) is dict and type(pin.get('bytes')) is int
            and 0 < pin['bytes'] <= maximum, 'Unbounded metadata pin')
    with Path(path).open('rb') as stream:
        body = stream.read(pin['bytes']+1)
    require(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
            'Input bytes or SHA-256 differ from the frozen binding: '+str(path))
    return body


def _load_modules(binding):
    require(set(binding) == set(MODULE_NAMES), 'Incomplete preparation source binding')
    result = {}
    for name in MODULE_NAMES:
        path = Path(__file__).with_name(name+'.py')
        body = _read_pin(path, binding[name])
        spec = importlib.util.spec_from_file_location('neural099_preparation_'+name, path)
        module = importlib.util.module_from_spec(spec)
        # Execute the already authenticated bytes, not a second path lookup.
        exec(compile(body, str(path), 'exec'), module.__dict__)
        result[name] = module
    return result


def asset_cases(asset, timing, animal_id):
    regions = {}
    for ordinal in asset['eligible_unit_row_ordinals']:
        _, region, _ = asset['source_unit_row_values'][ordinal]
        regions[region] = regions.get(region, 0)+1
    cases = []
    for trial in timing['rows']:
        for region in sorted(regions):
            row = trial['row_ordinal']
            cases.append({'case_id': asset['asset_id']+':'+str(row)+':'+region,
                          'asset_id': asset['asset_id'], 'animal_id': animal_id,
                          'source_trial_row': row, 'source_trial_id': trial['source_trial_id'],
                          'trial_start_seconds': trial['start_time'],
                          'trial_stop_seconds': trial['stop_time'], 'region': region,
                          'source_cluster_count': regions[region]})
    return cases


def prepare_asset_counts(asset, timing, animal_id, descriptors, *, production, oracle):
    """Count every selected cluster twice and compare before regional sums.

    At most one cluster's chunks are retained for reuse by the two algorithms.
    Source metadata bounds that cluster by 86,703 events, not the whole cohort.
    Production sums flat uint64 counters; reference sums nested Python rows.
    """
    anchors = [row['start_time'] for row in timing['rows']]
    production.make_grid(anchors)  # strict complete chronology before values
    require(type(asset['spike_times']['shape'][0]) is int
            and 0 <= asset['spike_times']['shape'][0] <= 86703,
            'Asset event extent exceeds the admitted replay bound')
    cases = asset_cases(asset, timing, animal_id)
    rows = asset['source_unit_row_values']
    expected_ordinals = asset['eligible_unit_row_ordinals']
    regions = sorted({rows[ordinal][1] for ordinal in expected_ordinals})
    flat = {region: array('Q', [0])*(len(anchors)*200) for region in regions}
    require(all(value.itemsize == 8 for value in flat.values()), 'uint64 counter width unavailable')
    reference = {region: {'history_counts': [[0]*100 for _ in anchors],
                          'response_counts': [[0]*100 for _ in anchors]} for region in regions}
    seen, records, total_events, compared = [], [], 0, 0
    denominator = {region: 0 for region in regions}
    for descriptor in descriptors:
        ordinal = descriptor['source_unit_row']
        require(len(seen) < len(expected_ordinals) and ordinal == expected_ordinals[len(seen)],
                'Selected source-unit order changed, repeated or omitted')
        cluster_id, region, quality = rows[ordinal]
        require(descriptor['asset_id'] == asset['asset_id']
                and descriptor['cluster_id'] == cluster_id and descriptor['region'] == region
                and descriptor['quality'] == quality, 'Descriptor identity differs from frozen anatomy')
        extent = descriptor['declared_spike_count']
        require(type(extent) is int and 0 <= extent <= asset['spike_times']['shape'][0]
                and type(descriptor['source_global_start']) is int
                and type(descriptor['source_global_stop']) is int
                and 0 <= descriptor['source_global_start'] <= descriptor['source_global_stop']
                    <= asset['spike_times']['shape'][0]
                and descriptor['source_global_stop']-descriptor['source_global_start'] == extent,
                'Invalid bounded source cluster extent')
        chunks, retained = [], 0
        for chunk in descriptor['chunks']:
            require(type(chunk) is dict and set(chunk) == {'source_start','spikes'},
                    'Unexpected source chunk fields')
            require(type(chunk['spikes']) is list and 0 < len(chunk['spikes']) <= 65536,
                    'Unbounded source chunk')
            retained += len(chunk['spikes'])
            require(retained <= extent, 'Source cluster exceeds its frozen extent')
            chunks.append(chunk)
        require(retained == extent, 'Source cluster payload is incomplete')
        first = production.count_cluster(anchors, chunks, declared_spike_count=extent)
        second = oracle.count_cluster(anchors, chunks, declared_spike_count=extent)
        compared += production.compare_cluster(first, second, asset_id=asset['asset_id'],
                                                cluster_id=cluster_id)
        for trial in range(len(anchors)):
            for window_offset, field in ((0,'history_counts'), (100,'response_counts')):
                for bin_index, count in enumerate(first[field][trial]):
                    flat[region][trial*200+window_offset+bin_index] += count
                reference[region][field][trial] = [a+b for a,b in
                    zip(reference[region][field][trial], second[field][trial])]
        denominator[region] += 1
        records.append({'source_unit_row': ordinal, 'cluster_id': cluster_id, 'region': region,
                        'source_global_start': descriptor['source_global_start'],
                        'source_global_stop': descriptor['source_global_stop'],
                        'source_spikes_consumed': extent, 'event_partition': first['event_partition']})
        total_events += extent
        seen.append(ordinal)
    require(seen == expected_ordinals, 'Selected cluster roster is incomplete')
    require(total_events <= asset['spike_times']['shape'][0], 'Selected event total exceeds source')
    output = []
    total_bins = 0
    for case in cases:
        trial, region = case['source_trial_row'], case['region']
        require(denominator[region] == case['source_cluster_count'], 'Region denominator changed')
        result = {'case_id': case['case_id']}
        for window_offset, field in ((0,'history_counts'), (100,'response_counts')):
            start = trial*200+window_offset
            vector = list(flat[region][start:start+100])
            require(vector == reference[region][field][trial], 'Independent regional sum mismatch')
            result[field] = vector
            total_bins += len(vector)
        output.append(result)
    row_digest = hashlib.sha256()
    for row in output:
        row_digest.update(canonical(row))
    return output, {'asset_id': asset['asset_id'], 'animal_id': animal_id,
                    'source_cluster_count': len(seen), 'region_denominators': denominator,
                    'selected_events_consumed': total_events, 'cluster_bins_compared': compared,
                    'regional_bins_compared': total_bins, 'cluster_event_audit': records,
                    'row_semantic_sha256': row_digest.hexdigest()}


def join_inputs(schema, timing, support, cohort, runtime_io):
    assets = schema['assets']
    require(type(assets) is list and len(assets) == 26
            and type(timing['records']) is list and len(timing['records']) == 26
            and type(support['assets']) is list and len(support['assets']) == 26,
            'Exact source, timing and support record counts required')
    timings = {record['asset_id']: record for record in timing['records']}
    supports = {record['asset_id']: record for record in support['assets']}
    require(len(assets) == len(timings) == len(supports) == 26, 'Complete source cohort required')
    require([asset['asset_id'] for asset in assets] == sorted(timings)
            and set(timings) == set(supports) == set(cohort['asset_to_animal']),
            'Source, timing, support and animal rosters differ')
    require(len({asset['source_subject_id'] for asset in assets}) == 26
            and set(cohort['source_to_animal']) == {asset['source_subject_id'] for asset in assets},
            'Exact source-subject identity mapping required')
    totals = dict.fromkeys(PROFILE, 0)
    cases = []
    for asset in assets:
        aid, subject = asset['asset_id'], asset['source_subject_id']
        saved, declared = timings[aid], supports[aid]
        for a,b in (('source_bytes','bytes'), ('source_sha256','sha256'),
                    ('source_path','source_path'), ('source_subject_id','source_subject_id')):
            require(asset[a] == saved[b], 'Timing lineage differs from exact source')
        require(declared['source_asset'] == {'bytes':asset['source_bytes'],
                'path':asset['source_path'], 'sha256':asset['source_sha256']}, 'Support lineage differs')
        require(cohort['asset_to_animal'][aid] == cohort['source_to_animal'][subject],
                'Animal grouping differs from frozen identity binding')
        rows = saved['rows']
        require(len(rows) == asset['source_trial_rows'] == declared['source_trial_rows']
                and [r['row_ordinal'] for r in rows] == list(range(len(rows))),
                'Actual source trial row roster changed')
        runtime_io.validate_trial_rows([r['source_trial_id'] for r in rows],
            [r['start_time'] for r in rows], [r['stop_time'] for r in rows], expected_rows=len(rows))
        unit_rows = asset['source_unit_row_values']
        named = {'BIC','MGd','MGm','MGv','MZMG','SG'}
        require(len(unit_rows) == asset['spike_times_index']['shape'][0]
                and len({r[0] for r in unit_rows}) == len(unit_rows)
                and all(len(r) == 3 and type(r[0]) is int and r[0] >= 0
                        and r[1] in named | {' '} and r[2] in {'good','mua'} for r in unit_rows),
                'Complete unique literal source unit rows required')
        selected = [i for i,r in enumerate(unit_rows) if r[1] in named]
        unassigned = [i for i,r in enumerate(unit_rows) if r[1] == ' ']
        require(asset['eligible_unit_row_ordinals'] == selected
                and asset['unassigned_unit_row_ordinals'] == unassigned
                and asset['eligible_cluster_count'] == len(selected)
                and asset['unassigned_cluster_count'] == len(unassigned),
                'Enumerated source membership differs from declared counts')
        by_region = {}
        for ordinal in asset['eligible_unit_row_ordinals']:
            cluster, region, _ = asset['source_unit_row_values'][ordinal]
            by_region.setdefault(region, []).append(cluster)
        require(len(declared['regions']) == len({r['region'] for r in declared['regions']}),
                'Repeated declared region entry')
        require(all(r['cluster_count'] == len(r['cluster_ids'])
                    and len(set(r['cluster_ids'])) == len(r['cluster_ids'])
                    for r in declared['regions']), 'Declared regional denominator differs from membership')
        require({r['region']: sorted(r['cluster_ids']) for r in declared['regions']} ==
                {region: sorted(ids) for region, ids in by_region.items()}, 'Anatomical membership differs')
        group_cases = asset_cases(asset, saved, cohort['asset_to_animal'][aid])
        cases.extend(group_cases)
        values = (1,len(rows),len(by_region),asset['eligible_cluster_count'],
                  asset['unassigned_cluster_count'],asset['spike_times']['shape'][0],
                  asset['spike_times_index']['shape'][0],asset['source_bytes'],len(group_cases))
        for key,value in zip(PROFILE,values): totals[key] += value
    require(totals == PROFILE, 'Whole-source support differs from selected profile')
    return assets, timings, cases


def _asset_read(root_fd, asset, timing, animal, modules, h5api):
    io = modules['runtime_io']
    name = Path(asset['source_path']).name
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd)
    with os.fdopen(descriptor,'rb') as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == asset['source_bytes'],
                'Source is not the authenticated regular file')
        digest, consumed = hashlib.sha256(), 0
        while chunk := source.read(min(1048576,asset['source_bytes']-consumed+1)):
            consumed += len(chunk)
            require(consumed <= asset['source_bytes'], 'Source grew beyond frozen bounds')
            digest.update(chunk)
        require(consumed == asset['source_bytes'] and digest.hexdigest() == asset['source_sha256']
                and io._file_signature(before) == io._file_signature(os.fstat(source.fileno())),
                'Source authentication or unchanged-state check failed')
        source.seek(0)
        with h5api.File(source,'r',rdcc_nbytes=1048576) as handle:
            descriptors = modules['event_source'].iter_selected_clusters(
                handle,h5api=h5api,asset_bounds=asset)
            result, audit = prepare_asset_counts(asset,timing,animal,descriptors,
                production=modules['stream_counts'],oracle=modules['count_oracle'])
        require(io._file_signature(before) == io._file_signature(os.fstat(source.fileno())),
                'Source changed during event preparation')
    audit.update(source_bytes_hashed=consumed, index_values_decoded=asset['spike_times_index']['shape'][0],
                 selected_event_value_bytes=audit['selected_events_consumed']*8)
    return result,audit


def write_json_new(path, value, maximum):
    body = canonical(value)
    require(len(body) <= maximum, 'Output metadata exceeds finite bound')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor,'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authenticated-preparation',action='store_true')
    parser.add_argument('--binding',required=True)
    parser.add_argument('--binding-sha256',required=True)
    parser.add_argument('--binding-bytes',required=True,type=int)
    parser.add_argument('--raw-root',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args(argv)
    require(args.execute_authenticated_preparation, 'Separate exact admission and explicit flag required')
    # Portable intake only: authoring helper bindings.py is deliberately not
    # imported or executed here. The launcher authenticates coordinator bytes;
    # every fixed sibling module is authenticated before metadata/native access.
    from pathlib import PurePosixPath
    import math
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate binding/metadata JSON key')
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError('Nonfinite binding/metadata JSON value')
    def decode(body):
        def number(value):
            result=float(value)
            if not math.isfinite(result):nonfinite(value)
            return result
        return json.loads(body,object_pairs_hook=pairs,parse_constant=nonfinite,parse_float=number)
    binding = decode(_read_pin(args.binding,{'bytes':args.binding_bytes,'sha256':args.binding_sha256},65536))
    require(type(binding) is dict and set(binding) == {'schema','profile','coordinator','modules','inputs'}
            and binding['schema'] == 'neural099-portable-preparation-binding/v1',
            'Exact versioned portable preparation binding required')
    require(type(binding['profile']) is dict and set(binding['profile']) == set(PROFILE)
            and all(type(binding['profile'][key]) is int and binding['profile'][key] == value
                    for key,value in PROFILE.items()), 'Unselected complete-source profile')
    require(type(binding['modules']) is dict and set(binding['modules']) == set(MODULE_NAMES),
            'Exact sibling source-module roles required')
    require(type(binding['inputs']) is dict
            and set(binding['inputs']) == {'schema','timing','support','cohort','protocol'},
            'Exact five scientific metadata inputs required')
    def locator(path):
        require(type(path) is str and 0 < len(path) <= 4096 and '\x00' not in path
                and '\\' not in path and not PurePosixPath(path).is_absolute()
                and str(PurePosixPath(path)) == path and path != '.',
                'Expected a canonical binding-relative file locator')
        return (Path(args.binding).resolve().parent/path).resolve()
    entries = [(binding['coordinator'],65536,True)]
    entries += [(entry,65536,False) for entry in binding['modules'].values()]
    entries += [(entry,MAX_METADATA_BYTES,True) for entry in binding['inputs'].values()]
    for entry,maximum,has_path in entries:
        require(type(entry) is dict and set(entry) == ({'path','bytes','sha256'} if has_path else {'bytes','sha256'}),
                'Unexpected pin fields or source-location override')
        require(type(entry['bytes']) is int and 0 < entry['bytes'] <= maximum,
                'Invalid bounded source/metadata size')
        require(type(entry['sha256']) is str and len(entry['sha256']) == 64
                and all(c in '0123456789abcdef' for c in entry['sha256']), 'Invalid SHA-256 pin')
        if has_path: locator(entry['path'])
    for role,expected in CONTRACT_PINS.items():
        require({key:binding['inputs'][role][key] for key in ('bytes','sha256')} == expected,
                'Scientific input differs from the selected published contract: '+role)
    require(locator(binding['coordinator']['path']) == Path(__file__).resolve(),
            'Portable binding points at a different coordinator location')
    modules = _load_modules(binding['modules'])
    docs = {name:decode(_read_pin(locator(value['path']),value)) for name,value in binding['inputs'].items()}
    assets,timings,cases = join_inputs(docs['schema'],docs['timing'],docs['support'],docs['cohort'],
                                     modules['runtime_io'])
    output = Path(args.output)
    require(output.is_absolute() and not output.exists() and not output.is_symlink(),
            'Output must be a fresh absolute directory')
    raw_root = Path(args.raw_root)
    require(raw_root.is_absolute(), 'Raw root must be absolute')
    h5api,versions = modules['runtime_io'].initialize_runtime()
    require(versions == RUNTIME, 'Unqualified native runtime version')
    output.mkdir(mode=0o700)
    root_fd = os.open(raw_root,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    audits = []
    def records():
        for asset in assets:
            rows,audit = _asset_read(root_fd,asset,timings[asset['asset_id']],
                docs['cohort']['asset_to_animal'][asset['asset_id']],modules,h5api)
            audits.append(audit)
            yield from rows
    try:
        packet = modules['count_packet'].write_packet(output/'counts.u64le',cases,records(),max_bytes=COUNT_BYTES)
    finally:
        os.close(root_fd)
    require(len(audits) == 26 and packet['bytes'] == COUNT_BYTES, 'Incomplete packet preparation')
    require(packet['bytes'] == 15787200 and packet['sha256'] ==
            'f10a48794f2778b7f208b4323315e3ca034e58ee268e7653306e189f2c20e536',
            'Portable preparation differs from the exact selected count packet')
    row_digests = {asset['asset_id']:hashlib.sha256() for asset in assets}
    with modules['count_packet'].verify_packet(output/'counts.u64le',cases,packet,
                                               max_bytes=COUNT_BYTES) as reader:
        for case in cases:
            record = reader.read_private(case['case_id'])
            require(record['case'] == case, 'Packet round-trip changed case metadata')
            row = {'case_id':case['case_id'], 'history_counts':record['history_counts'],
                   'response_counts':record['response_counts']}
            row_digests[case['asset_id']].update(canonical(row))
    require(all(row_digests[a['asset_id']].hexdigest() == a['row_semantic_sha256'] for a in audits),
            'Prepared packet count round-trip differs from compared regional counts')
    cases_pin = write_json_new(output/'cases.json',cases,MAX_METADATA_BYTES)
    require(cases_pin == {'bytes':2755199,'sha256':
            '4cf619e8c06b012b299a45aaab1397c31ebe6cafee00db985077783f026e0582'},
            'Portable preparation differs from the exact selected private case bytes')
    audit_pin = write_json_new(output/'count-verification.json',audits,MAX_METADATA_BYTES)
    require(COUNT_BYTES+cases_pin['bytes']+audit_pin['bytes']+65536 <= MAX_OUTPUT_BYTES,
            'Prepared artifacts exceed total logical write bound')
    receipt = {'schema':'neural099-assumed-support-count-preparation/v1',
        'input_binding_sha256':args.binding_sha256,'profile':PROFILE,'packet':packet,
        'cases':cases_pin,'count_verification':audit_pin,'runtime':versions,
        'logical_full_file_hash_bytes':sum(a['source_bytes_hashed'] for a in audits),
        'logical_index_bytes':sum(a['index_values_decoded']*8 for a in audits),
        'logical_selected_event_bytes':sum(a['selected_event_value_bytes'] for a in audits),
        'all_cluster_bins_compared':sum(a['cluster_bins_compared'] for a in audits),
        'all_regional_bins_compared':sum(a['regional_bins_compared'] for a in audits),
        'packet_all_rows_round_trip_verified':True,
        'logical_prepared_packet_read_bytes':COUNT_BYTES*2,
        'physical_io_bytes':None,'native_working_memory_bytes':None,
        'observation_coverage_verified':False,'physiological_rate_qualified':False,
        'model_or_training_execution':False,'scientific_readiness_promoted':False}
    receipt_pin = write_json_new(output/'COMPLETE.json',receipt,65536)
    print(json.dumps({'complete':str(output/'COMPLETE.json'),**receipt_pin},sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
