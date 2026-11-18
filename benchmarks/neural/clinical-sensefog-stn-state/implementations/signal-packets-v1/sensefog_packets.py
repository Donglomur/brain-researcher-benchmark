"""Operator-only projection of complete SenseFOG native LFP packet support.

No clinical labels, movements, candidate code, file parser or model is accepted.
The callback supplies already calibrated, trusted channel-major native samples.
Declared provenance is not authenticated here; this is not participant isolation.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import types

TASK = 'clinical-sensefog-stn-state'
MAPPER_SHA256 = 'd833d2c7637d73ce047578788a75c0ab30a98cee89b694efde27b5f79fe8ef40'
MAPPER_PATH = Path(__file__).resolve().parent.parent / 'recording-lag-controls' / 'sensefog_pairing.py'
_raw = MAPPER_PATH.read_bytes()
if hashlib.sha256(_raw).hexdigest() != MAPPER_SHA256:
    raise ValueError('reviewed recording-grid mapper source changed')
_mapper = types.ModuleType('_sensefog_packet_mapper')
exec(compile(_raw, str(MAPPER_PATH), 'exec'), _mapper.__dict__)
require, keys, integer = _mapper.require, _mapper.keys, _mapper.integer


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def canonical_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _hash(value, name):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), name + ': SHA256')
    return value


def _metadata(document, grid, segments):
    keys(document, 'schema task grid_sha256 segments', 'signal metadata')
    require(document['schema'] == 'sensefog_signal_metadata_v1' and document['task'] == TASK,
            'signal metadata identity')
    require(document['grid_sha256'] == canonical_sha256(grid), 'signal metadata/grid mismatch')
    require(type(document['segments']) is list, 'signal metadata segments')
    result = {}
    for row in document['segments']:
        keys(row, 'segment_id signal_sha256 calibration_receipt_sha256 channels', 'signal metadata row')
        sid = _mapper.identity(row['segment_id'])
        require(sid in segments and sid not in result, 'unknown/duplicate signal metadata segment')
        _hash(row['signal_sha256'], 'declared signal source')
        _hash(row['calibration_receipt_sha256'], 'declared calibration receipt')
        require(type(row['channels']) is list, 'channel metadata list')
        require(len(row['channels']) == len(segments[sid]['channels']), 'complete channel metadata')
        for channel, cid in zip(row['channels'], segments[sid]['channels']):
            keys(channel, 'channel_id hemisphere physical_unit montage', 'channel metadata')
            require(channel['channel_id'] == cid, 'exact source channel order required')
            require(channel['hemisphere'] in ('left', 'right'), 'authenticated hemisphere required')
            require(channel['physical_unit'] in ('V', 'mV', 'uV'), 'explicit electrical unit required')
            require(type(channel['montage']) is str and
                    re.fullmatch(r'[A-Za-z0-9_.:+/() -]{1,128}', channel['montage']),
                    'explicit target-free source montage description required')
        # Do not assume two channels; each observed montage must account for both hemispheres.
        require({c['hemisphere'] for c in row['channels']} == {'left', 'right'},
                'bilateral montage required; no invented channel')
        result[sid] = row
    require(set(result) == set(segments), 'every observed segment needs signal metadata')
    return result


def _mask(runs, start, end):
    out = []
    for a, b, missing, artifact in runs:
        left, right = max(a, start), min(b, end)
        if left < right:
            out.extend([[missing, artifact] for _ in range(right - left)])
    require(len(out) == end - start, 'complete exact mask slice required')
    return out


def project_packets(grid, signal_metadata, aliases, read_segment, *, max_cases,
                    max_packet_values, max_total_values, max_output_bytes):
    """Project all original cores, available support, and every supported lag.

    read_segment(segment_id, tuple(channel_ids), local_start, local_end) must return
    a list of channel lists on precisely that half-open native sample interval.
    All non-missing values are finite calibrated numbers; missing values are None.
    Each unique requested interval is read once, without retries or fallback.

    The entire returned object is evaluator-only. Only an individual member of
    result['packets'] is a candidate public observation. The manifest, alias
    mapping and callback must never be provided to a participant.
    """
    for value, name in ((max_packet_values, 'max_packet_values'),
                        (max_total_values, 'max_total_values'),
                        (max_output_bytes, 'max_output_bytes')):
        integer(value, 1, name)
    require(callable(read_segment), 'trusted reader callback required')
    # Freeze mutable caller declarations before entering the external callback.
    grid = json.loads(canonical_bytes(grid))
    signal_metadata = json.loads(canonical_bytes(signal_metadata))
    aliases = json.loads(canonical_bytes(aliases))
    maps = _mapper.build_maps(grid, max_cases=max_cases)
    segments = {s['segment_id']: s for s in grid['segments']}
    records = {r['recording_id']: r for r in grid['recordings']}
    folds = {f['heldout_person']: f for f in grid['folds']}
    metadata = _metadata(signal_metadata, grid, segments)
    case_ids = maps['original_case_ids']
    require(type(aliases) is dict and set(aliases) == set(case_ids), 'complete private alias mapping')
    require(all(type(a) is str and re.fullmatch('[0-9a-f]{32}', a) for a in aliases.values()),
            'opaque 128-bit case aliases required')
    require(len(set(aliases.values())) == len(aliases), 'duplicate public alias')
    normalized_masks = {
        sid: {c: _mapper.mask_runs(s['masks'][c], s['sample_count']) for c in s['channels']}
        for sid, s in segments.items()
    }
    by_recording = {rid: [] for rid in records}
    for sid, segment in segments.items():
        a = segment['recording_start_sample']
        by_recording[segment['recording_id']].append((a, a + segment['sample_count'], sid))
    for intervals in by_recording.values():
        intervals.sort()
    plans, requests = [], {}

    def add_plan(cid, role, multiple, sid, interval, core, reason):
        rec = case_info[cid]
        row = {'case_id': cid, 'case_token': aliases[cid], 'participant': rec['participant'],
               'recording_id': rec['recording_id'], 'segment_id': sid, 'role': role,
               'multiple': multiple, 'status': 'available' if reason is None else 'unavailable',
               'reason': reason, 'packet_sha256': None}
        if reason is None:
            segment = segments[sid]
            offset = segment['recording_start_sample']
            a, b = interval[0] - offset, interval[1] - offset
            require(0 <= a < b <= segment['sample_count'], 'planned interval outside source segment')
            require(interval[0] <= core[0] < core[1] == interval[1], 'support/core alignment')
            key = (sid, a, b)
            count = len(segment['channels']) * (b - a)
            require(count <= max_packet_values, 'packet value cap; no channel/sample truncation')
            requests[key] = count
            row['_request'] = key
            row['_core_relative'] = [core[0] - interval[0], core[1] - interval[0]]
            row['_relative_sample_start'] = interval[0] - core[0]
            row['_sample_rate_hz'] = records[segment['recording_id']]['sample_rate_hz']
        plans.append(row)

    case_info = {c['case_id']: r for r in grid['recordings'] for c in r['cases']}
    # Original primary cores remain available even if training dependence/history is unavailable.
    for rid, rec in records.items():
        rate = rec['sample_rate_hz']
        h = folds[rec['participant']]['lookback_samples_by_rate'][str(rate)]
        for case in rec['cases']:
            cid, start = case['case_id'], case['start_sample']
            end = start + 2 * rate
            owner = next((x for x in by_recording[rid] if x[0] <= start and end <= x[1]), None)
            sid = owner[2] if owner else None
            core_reason = (None if owner else 'recording_has_no_observed_segment'
                           if not by_recording[rid] else 'recipient_core_crosses_gap_or_acquisition_boundary')
            add_plan(cid, 'original_core', None, sid, [start, end], [start, end], core_reason)
            support_reason = core_reason or ('unestablished_lookback' if h is None else
                                             'recipient_history_outside_segment' if end - h < owner[0] else None)
            interval = None if h is None else [end - h, end]
            add_plan(cid, 'original_authorized_support', None, sid, interval, [start, end], support_reason)
    # Use the exact pinned mapper, including full-history mask matching and all twenty lags.
    for row in maps['maps']:
        add_plan(row['case_id'], 'lag_authorized_support', row['multiple'], row['segment_id'],
                 row['donor_support'], row['donor_core'], None if row['status'] == 'supported' else row['reason'])
    requested_values = sum(requests.values())
    require(requested_values <= max_total_values, 'whole operation value cap; no partial cohort')

    slices = {}
    for key in requests:
        sid, start, end = key
        channels = tuple(segments[sid]['channels'])
        values = read_segment(sid, channels, start, end)
        require(type(values) is list and len(values) == len(channels), 'reader complete ordered channels')
        clean = []
        for cid, vector in zip(channels, values):
            require(type(vector) is list and len(vector) == end - start, 'reader exact half-open sample grid')
            mask = _mask(normalized_masks[sid][cid], start, end)
            for value, (missing, _) in zip(vector, mask):
                if missing:
                    require(value is None, 'missing samples must be explicit nulls')
                else:
                    require(type(value) in (int, float) and math.isfinite(value),
                            'non-missing samples must be finite calibrated numbers')
            # Copy values/masks so a mutable callback cannot alter previously read support.
            clean.append((list(vector), mask))
        slices[key] = clean

    packets = {}
    for plan in plans:
        if plan['status'] != 'available':
            continue
        sid, _, _ = plan['_request']
        packet = {'schema': 'sensefog_native_lfp_packet_v1', 'case_token': plan['case_token'],
                  'sample_rate_hz': plan['_sample_rate_hz'],
                  'relative_sample_start': plan['_relative_sample_start'],
                  'core_sample_interval': plan['_core_relative'], 'channels': []}
        for index, ((values, mask), info) in enumerate(zip(slices[plan['_request']], metadata[sid]['channels'])):
            packet['channels'].append({'channel_token': 'c%04d' % index,
                'hemisphere': info['hemisphere'], 'physical_unit': info['physical_unit'],
                'montage': info['montage'],
                'values': list(values), 'missing': [m[0] for m in mask],
                'artifact': [m[1] for m in mask]})
        digest = canonical_sha256(packet)
        if digest in packets:
            require(packets[digest] == packet, 'packet digest collision')
        else:
            packets[digest] = packet
        plan['packet_sha256'] = digest
        for field in ('_request', '_core_relative', '_relative_sample_start', '_sample_rate_hz'):
            del plan[field]
    result = {'schema': 'sensefog_operator_packet_projection_v1', 'task': TASK,
              'grid_sha256': canonical_sha256(grid),
              'signal_metadata_sha256': canonical_sha256(signal_metadata),
              'private_aliases_sha256': canonical_sha256(aliases),
              'mapper_sha256': MAPPER_SHA256, 'original_case_count': len(case_ids),
              'requested_lag_count': 20, 'unique_source_reads': len(requests),
              'source_values_requested': requested_values, 'private_manifest': plans,
              'packets': packets, 'readiness': False,
              'interpretation': 'Operator extraction only; declared provenance, full source cohort, '
                                'clinical clocks/targets, candidate isolation and model outcomes remain unqualified.'}
    require(len(canonical_bytes(result)) <= max_output_bytes, 'whole output byte cap; no partial export')
    return result
