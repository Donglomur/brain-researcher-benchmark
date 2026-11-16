"""Project an exact clock/ephys plan from already accepted complete evidence.

No directory census, HTTP, signal decode, reference generation or import I/O.
The caller must authenticate the three named accepted inputs before calling.
"""
from collections import Counter
from pathlib import PurePosixPath

MIB = 1024 * 1024
INPUT_PINS = {
    'COMPLETE_SIGNAL_MEMBER_PLAN.json': (1221223, 'cf46a2d8a3a291b42cd7e4d504899acde793089f35c710f4ffa39ccde35fc4d7'),
    'METADATA_CENSUS.json': (297915, '32eb2e735df48d33797e951bef0af4bb9bf6dda52bb705ac372a40a27c154e19'),
    'CLOSURE_SUMMARY.json': (95102, 'd5ed32bd6c9ff595a04e5cfa934a24a012b669e96d56a682f4d41b44e6a04d51'),
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def project(signal_plan, census, summary):
    all_members = signal_plan['members']
    chosen = [x for x in all_members if x['role'] in ('frame_times', 'electrical_NPZ')]
    need(Counter(x['role'] for x in chosen) == {'frame_times': 34, 'electrical_NPZ': 229},
         'complete two-family membership')
    keys = [(x['file_id'], x['name']) for x in chosen]
    need(len(set(keys)) == 263, 'duplicate selected member identity')
    metadata = {(x['file_id'], x['name']): x['metadata'] for x in census['records']}
    need(len(metadata) == len(census['records']) == 263, 'complete unique accepted metadata')
    movie_summary = {(x['file_id'], x['movie_directory']): x for x in summary['per_movie']}
    need(len(movie_summary) == 34, 'complete accepted movie summary')
    joined = []
    used_metadata = set()
    for member in chosen:
        path = PurePosixPath(member['name'])
        need(not path.is_absolute() and '..' not in path.parts, 'member path')
        if member['role'] == 'frame_times':
            metadata_name = str(path.with_name('movie_metadata.json'))
        else:
            metadata_name = str(path.with_suffix('.json'))
        key = (member['file_id'], metadata_name)
        need(key in metadata, 'missing exact companion metadata')
        m = metadata[key]; used_metadata.add(key)
        for field in ('subject_id', 'session', 'cell_number'):
            need(m[field] == member[field], 'member/metadata biological identity mismatch')
        row = dict(member, metadata_name=metadata_name)
        if member['role'] == 'frame_times':
            movie = movie_summary[(member['file_id'], member['movie_directory'])]
            need(m['movie_frame_num'] == movie['declared_frames'], 'declared frame count mismatch')
            row['declared_frame_count'] = m['movie_frame_num']
            row['declared_movie_start_seconds'] = m['movie_start_time']
            row['declared_frame_rate_hz'] = m['movie_frame_rate']
        else:
            need(m['data_header'] == ['time','voltage','stimulus'] and
                 m['data_units'] == ['s','mV','pA'] and m['recording_mode'] == 'current clamp',
                 'unqualified channel/units/mode declaration')
            row['electrical_metadata'] = {k:m[k] for k in ('sweep_number','sample_rate',
                'sweep_start_time','sweep_end_time','data_header','data_units','recording_mode',
                'ljp','ljp_corrected','primarysignallpf','neutralizationenable')}
        joined.append(row)
    need(used_metadata == set(metadata), 'unjoined complete metadata')
    totals = {'members': len(chosen),
              'compressed_member_bytes': sum(x['compressed_member_bytes'] for x in chosen),
              'decoded_member_file_bytes': sum(x['decoded_member_file_bytes'] for x in chosen),
              'header_plus_payload_entity_upper_bytes': sum(x['prospective_header_plus_payload_entity_upper_bytes'] for x in chosen)}
    need(totals == {'members':263,'compressed_member_bytes':468553334,
         'decoded_member_file_bytes':549414968,'header_plus_payload_entity_upper_bytes':468579361},
         'accepted complete clock/ephys extent mismatch')
    need(all(summary['complete_clock_and_electrical_stage'][k] == v for k,v in totals.items()),
         'accepted summary join')
    # One new full-family operation: twelve 1-byte object barriers followed by
    # three ranges per member. Fresh canonical resolution for every range;
    # at most four redirects and one terminal206 for each logical range.
    ranges = 12 + 3*263
    responses = ranges * 5
    records = responses + 1
    partitions = dict(compressed_range_bodies=512*MIB, decoded_member_files=576*MIB,
                      HTTP_records=64*MIB, science_metadata=16*MIB,
                      owner_and_originals=16*MIB, independent_audit=32*MIB,
                      interrupted_output_reserve=64*MIB)
    need(records*16384 <= partitions['HTTP_records'], 'HTTP descriptor partition')
    need(totals['header_plus_payload_entity_upper_bytes']+12 <= partitions['compressed_range_bodies'],
         'compressed range partition')
    need(totals['decoded_member_file_bytes'] <= partitions['decoded_member_files'],
         'decoded member partition')
    return {'schema':'voltron-complete-clock-ephys-prospective-plan-v1','selected':False,
        'input_pins':INPUT_PINS,'members':joined,'totals':totals,
        'scope':{'subjects':6,'cells':12,'movies':34,'frame_NPY':34,'electrical_NPZ':229},
        'network_recipe':{'logical_ranges':ranges,'HTTP_response_upper':responses,
            'raw_record_upper':records,'record_bytes_cap':16384,'header_bytes_cap':4096,
            'complete_entity_body_upper_bytes':totals['header_plus_payload_entity_upper_bytes']+12,
            'complete_body_plus_header_upper_bytes':totals['header_plus_payload_entity_upper_bytes']+12+responses*4096,
            'fresh_canonical_resolution_per_range':True,'retries':0,
            'strong_ETag_IfMatch_CRC_required':True,
            'existing_engine_caps_are_unchanged_and_incompatible':True,
            'new_exact_caller_transport_binding_needed':True},
        'prospective_resources':{'retention_partitions':partitions,'retention_total_bytes':sum(partitions.values()),
            'host_bytes':128*MIB,'array_file_cap_bytes':12*MIB,'NPZ_inner_total_cap_bytes':32*MIB,
            'worst_case_all_NPZ_inner_file_decode_bytes':229*32*MIB,
            'primary_and_audit_NPZ_inner_file_decode_bytes':2*229*32*MIB,
            'primary_and_audit_NPY_plus_NPZ_decode_bytes':2*229*32*MIB+2*23735992,
            'execution_wall_seconds':7200,'execution_CPU_seconds':300,
            'serial_independent_audit_wall_seconds':300,'serial_independent_audit_CPU_seconds':120,
            'whole_wall_seconds':7500,'whole_CPU_seconds':420,
            'explicit_read_budget_bytes':20*1024*MIB,
            'note':'Prospective ceilings, not measured throughput, observed inner extents, guaranteed format fit, or an execution selection.'},
        'retention_note':'Keep authenticated compressed bodies and decoded NPY/NPZ members. Inner arrays are decoded serially for QC and not separately persisted. Failed bytes remain quarantined; no overwrite or automatic retry.',
        'decoder_note':'Structural/data-integrity QC only. No reconstructed clock, inferred sample-rate fix, time offset, event detector, valid-interval adjudication or optical input is supplied.'}
