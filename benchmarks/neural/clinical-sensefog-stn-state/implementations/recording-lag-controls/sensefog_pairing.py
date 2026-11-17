"""Evaluator-only, target-free SenseFOG common-channel lag-map construction.

No signal, target, event annotation, model, or primary loss is loaded here.
Trusted acquisition/causal-lookback provenance must be established separately.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

TASK = 'clinical-sensefog-stn-state'
SCHEMA = 'sensefog_target_free_pairing_input_v2'
MULTIPLIERS = tuple(v for k in range(1, 11) for v in (k, -k))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, expected, context):
    require(type(value) is dict and set(value) == set(expected.split()),
            context + ': exact fields required')


def integer(value, minimum, context):
    require(type(value) is int and value >= minimum, context + ': integer range')
    return value


def identity(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value),
            'invalid opaque identity')
    return value


def unique_ids(value, context):
    require(type(value) is list, context + ': list required')
    result = [identity(v) for v in value]
    require(len(set(result)) == len(result), context + ': duplicate identity')
    return result


def mask_runs(spans, length):
    """Canonicalize complete nonoverlapping two-bit missing/artifact runs."""
    require(type(spans) is list, 'mask runs must be a list')
    end = 0
    result = []
    for span in spans:
        require(type(span) is list and len(span) == 4, 'mask span shape')
        a, b, missing, artifact = span
        integer(a, 0, 'mask start'); integer(b, 1, 'mask end')
        require(a == end and a < b <= length, 'mask gap/overlap/extent')
        require(type(missing) is bool and type(artifact) is bool, 'mask bits')
        if result and result[-1][2:] == [missing, artifact]:
            result[-1][1] = b
        else:
            result.append([a, b, missing, artifact])
        end = b
    require(end == length, 'mask does not cover complete segment')
    return result


def signature(runs, start, end):
    return [(min(b, end) - max(a, start), missing, artifact)
            for a, b, missing, artifact in runs if a < end and b > start]


def build_maps(document, *, max_cases):
    """Construct all maps from a complete RECORDING grid, independent of segments.

    An unobserved recording or a case crossing a gap/acquisition boundary stays
    in the original census with unsupported rows for every requested transform.
    Logical completeness is checked; authentic release provenance is not issued.
    """
    integer(max_cases, 1, 'max_cases')
    keys(document, 'schema task participants folds recordings segments', 'input')
    require(document['schema'] == SCHEMA and document['task'] == TASK, 'task/schema')
    people = unique_ids(document['participants'], 'participants')
    require(len(people) == 12, 'all twelve participants required')
    require(all(type(document[k]) is list for k in ('folds', 'recordings', 'segments')), 'rosters must be lists')
    folds = {}
    for fold in document['folds']:
        keys(fold, 'heldout_person training_people lookback_samples_by_rate dependence_samples_by_rate method_receipt_sha256', 'fold')
        person = identity(fold['heldout_person'])
        require(person in people and person not in folds, 'unknown/duplicate fold')
        train = unique_ids(fold['training_people'], 'training_people')
        require(set(train) == set(people) - {person}, 'exact other eleven training people required')
        require(type(fold['method_receipt_sha256']) is str and
                re.fullmatch('[0-9a-f]{64}', fold['method_receipt_sha256']), 'method receipt hash')
        for field in ('lookback_samples_by_rate', 'dependence_samples_by_rate'):
            require(type(fold[field]) is dict, 'rate map required')
            for rate, value in fold[field].items():
                require(type(rate) is str and re.fullmatch('[1-9][0-9]*', rate), 'rate key')
                if value is not None:
                    integer(value, 0, field)
        folds[person] = fold
    require(set(folds) == set(people), 'all twelve outer folds required')
    recordings, seen_cases = {}, set()
    person_rates = {p: set() for p in people}
    total = 0
    for rec in document['recordings']:
        keys(rec, 'recording_id participant day_id session_id sample_rate_hz sample_count window_stride_samples window_origin_sample cases', 'recording')
        rid, person = identity(rec['recording_id']), identity(rec['participant'])
        require(rid not in recordings and person in people, 'duplicate recording/unknown participant')
        identity(rec['day_id']); identity(rec['session_id'])
        rate = integer(rec['sample_rate_hz'], 1, 'sample_rate_hz')
        length = integer(rec['sample_count'], 0, 'sample_count')
        stride = integer(rec['window_stride_samples'], 1, 'window stride')
        origin = integer(rec['window_origin_sample'], 0, 'window origin')
        require(origin < stride, 'window origin must be in one stride')
        person_rates[person].add(str(rate))
        require(type(rec['cases']) is list, 'case roster must be a list')
        starts = range(origin, max(origin, length - 2 * rate + 1), stride)
        require(len(rec['cases']) == len(starts), 'incomplete frozen RECORDING case grid')
        total += len(starts)
        require(total <= max_cases, 'complete case census exceeds explicit limit; no truncation')
        for case, start in zip(rec['cases'], starts):
            keys(case, 'case_id start_sample', 'case')
            cid = identity(case['case_id']); integer(case['start_sample'], 0, 'case start')
            require(cid not in seen_cases and case['start_sample'] == start,
                    'duplicate/out-of-order/non-grid case')
            seen_cases.add(cid)
        recordings[rid] = rec
    require(all(person_rates.values()), 'every participant needs complete recording accounting')
    for person, rates in person_rates.items():
        fold = folds[person]
        require(set(fold['lookback_samples_by_rate']) == rates and
                set(fold['dependence_samples_by_rate']) == rates, 'complete per-fold rate strata required')
        for rate in rates:
            h = fold['lookback_samples_by_rate'][rate]
            require(h is None or h >= 2 * int(rate), 'lookback omits two-second window')
    segments, by_recording = {}, {rid: [] for rid in recordings}
    for item in document['segments']:
        keys(item, 'segment_id recording_id acquisition_stratum recording_start_sample sample_count channels masks', 'segment')
        sid, rid = identity(item['segment_id']), identity(item['recording_id'])
        require(sid not in segments and rid in recordings, 'duplicate segment/unknown recording')
        identity(item['acquisition_stratum'])
        offset = integer(item['recording_start_sample'], 0, 'segment offset')
        length = integer(item['sample_count'], 1, 'segment sample_count')
        require(offset + length <= recordings[rid]['sample_count'], 'segment exceeds recording extent')
        channels = unique_ids(item['channels'], 'channels')
        require(bool(channels), 'all released channels required')
        require(type(item['masks']) is dict and set(item['masks']) == set(channels), 'exact full-channel masks required')
        masks = {c: mask_runs(item['masks'][c], length) for c in channels}
        segments[sid] = (item, masks)
        by_recording[rid].append((offset, offset + length, sid))
    for intervals in by_recording.values():
        intervals.sort()
        require(all(left[1] <= right[0] for left, right in zip(intervals, intervals[1:])),
                'overlapping or multiply owned acquisition segments')
    coverage = {p: {m: Counter() for m in MULTIPLIERS} for p in people}
    segment_counts = {sid: {m: Counter() for m in MULTIPLIERS} for sid in segments}
    rows, recording_coverage = [], []
    for rid, rec in recordings.items():
        person, rate = rec['participant'], rec['sample_rate_hz']
        h = folds[person]['lookback_samples_by_rate'][str(rate)]
        dependence = folds[person]['dependence_samples_by_rate'][str(rate)]
        gap = None if h is None or dependence is None else max(30 * rate, 2 * h, dependence)
        for multiple in MULTIPLIERS:
            lag = None if gap is None else multiple * gap
            counts = Counter()
            for case in rec['cases']:
                start, end = case['start_sample'], case['start_sample'] + 2 * rate
                owner = next(((a, b, sid) for a, b, sid in by_recording[rid] if a <= start and end <= b), None)
                sid = None if owner is None else owner[2]
                support = None if h is None else [end - h, end]
                donor = None if lag is None or owner is None else [start + lag, end + lag]
                donor_support = None if gap is None or owner is None else [end - h + lag, end + lag]
                if not by_recording[rid]:
                    reason = 'recording_has_no_observed_segment'
                elif owner is None:
                    reason = 'recipient_core_crosses_gap_or_acquisition_boundary'
                elif gap is None:
                    reason = 'unestablished_lookback_or_training_dependence'
                elif support[0] < owner[0]:
                    reason = 'recipient_history_outside_segment'
                elif donor_support[0] < owner[0] or donor_support[1] > owner[1]:
                    reason = 'donor_support_outside_segment'
                else:
                    item, masks = segments[sid]
                    local_support = [t - owner[0] for t in support]
                    local_donor = [t - owner[0] for t in donor_support]
                    reason = ('full_support_channel_mask_mismatch' if any(
                        signature(masks[c], *local_support) != signature(masks[c], *local_donor)
                        for c in item['channels']) else 'supported')
                counts[reason] += 1; coverage[person][multiple][reason] += 1
                if sid is not None:
                    segment_counts[sid][multiple][reason] += 1
                rows.append({'case_id': case['case_id'], 'participant': person, 'recording_id': rid,
                             'segment_id': sid, 'multiple': multiple, 'lag_samples': lag,
                             'recipient_core': [start, end], 'recipient_support': support,
                             'donor_core': donor, 'donor_support': donor_support,
                             'status': 'supported' if reason == 'supported' else 'unsupported', 'reason': reason})
            recording_coverage.append({'participant': person, 'recording_id': rid,
                'day_id': rec['day_id'], 'session_id': rec['session_id'], 'sample_rate_hz': rate,
                'sample_count': rec['sample_count'], 'window_origin_sample': rec['window_origin_sample'],
                'window_stride_samples': rec['window_stride_samples'], 'multiple': multiple,
                'gap_samples': gap, 'original_cases': len(rec['cases']), 'counts': dict(counts)})
    segment_coverage = []
    for sid, (item, _) in segments.items():
        rec = recordings[item['recording_id']]
        for m in MULTIPLIERS:
            segment_coverage.append({'participant': rec['participant'], 'segment_id': sid,
                'recording_id': item['recording_id'], 'day_id': rec['day_id'], 'session_id': rec['session_id'],
                'acquisition_stratum': item['acquisition_stratum'], 'sample_rate_hz': rec['sample_rate_hz'],
                'recording_start_sample': item['recording_start_sample'], 'sample_count': item['sample_count'],
                'channels': list(item['channels']), 'multiple': m,
                'core_contained_original_cases': sum(segment_counts[sid][m].values()),
                'counts': dict(segment_counts[sid][m])})
    transform_coverage = [{'multiple': m, 'supported_cases': sum(coverage[p][m]['supported'] for p in people),
                           'original_cases': total} for m in MULTIPLIERS]
    return {'schema': 'sensefog_target_free_pairing_maps_v2', 'task': TASK,
            'multipliers': list(MULTIPLIERS), 'original_case_count': total,
            'requested_transform_count': 20,
            'distinct_supported_transform_count': sum(r['supported_cases'] > 0 for r in transform_coverage),
            'transform_coverage': transform_coverage,
            'original_case_ids': [c['case_id'] for rec in recordings.values() for c in rec['cases']],
            'participants': [{'participant': p, 'transforms': [
                {'multiple': m, 'counts': dict(coverage[p][m])} for m in MULTIPLIERS]} for p in people],
            'recordings': recording_coverage, 'segments': segment_coverage, 'maps': rows,
            'primary_score': None, 'scientific_qualification': False,
            'interpretation': 'Evaluator-only descriptive lag mapping; no primary case removal, permutation p-value or causal claim.'}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--expected-input-sha256', required=True)
    p.add_argument('--max-input-bytes', required=True, type=int)
    p.add_argument('--max-output-bytes', required=True, type=int)
    p.add_argument('--max-cases', required=True, type=int)
    a = p.parse_args(argv)
    require(re.fullmatch('[0-9a-f]{64}', a.expected_input_sha256), 'input hash')
    integer(a.max_input_bytes, 1, 'input byte cap'); integer(a.max_output_bytes, 1, 'output byte cap')
    with Path(a.input).open('rb') as stream:
        raw = stream.read(a.max_input_bytes + 1)
    require(len(raw) <= a.max_input_bytes, 'input byte cap exceeded')
    require(hashlib.sha256(raw).hexdigest() == a.expected_input_sha256, 'frozen input hash mismatch')
    data = json.loads(raw, object_pairs_hook=strict_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    result = build_maps(data, max_cases=a.max_cases)
    result['input_sha256'] = a.expected_input_sha256
    encoded = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    require(len(encoded) <= a.max_output_bytes, 'complete output byte cap exceeded; no truncation')
    with Path(a.output).open('xb') as stream:
        stream.write(encoded)


if __name__ == '__main__':
    main()
