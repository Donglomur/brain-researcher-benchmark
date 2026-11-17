"""DoSEI descriptive matched-support RPS; no transform construction or p-value.

Frozen evaluator mapping receipts are operands, not source authenticity proofs.
The unchanged primary scorer supplies category, eligibility, RPS and full scope.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import stat
import types

PRIMARY_BYTES = 15749
PRIMARY_SHA = '09560538d472f0b99c65532bf371c8e9af56635e1ec437f68dd2f83b5f7bde77'
CAPS = {'policy': 4 * 1024**2, 'maps': 32 * 1024**2,
        'predictions': 64 * 1024**2, 'targets': 1024**2}
OUTPUT_CAP = 32 * 1024**2
MAX_ARMS, MAX_TRANSFORMS = 8, 32


def primary_module(path):
    # Only exact accepted ordinary software may execute. No arbitrary plugin.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != PRIMARY_BYTES:
            raise ValueError('exact ordinary primary software file required')
        raw = stream.read(PRIMARY_BYTES + 1)
    if len(raw) != PRIMARY_BYTES or hashlib.sha256(raw).hexdigest() != PRIMARY_SHA:
        raise ValueError('exact accepted primary source required')
    module = types.ModuleType('dosei_primary_dependency')
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def decode(m, raw, expected, kind):
    m.digest(expected)
    m.require(type(raw) is bytes and len(raw) <= CAPS[kind], 'paired input cap: ' + kind)
    m.require(hashlib.sha256(raw).hexdigest() == expected, 'paired input hash: ' + kind)
    return json.loads(raw, object_pairs_hook=m.strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def admit_maps(m, maps, policy, policy_sha):
    people, recordings, assessments, transitions, person_fold = policy
    m.fields(maps, 'schema task policy_sha256 arms freeze_receipts case_metadata transforms', 'maps')
    m.require(maps['schema'] == 'dosei_frozen_pairing_manifest_v1' and maps['task'] == m.TASK, 'maps schema/task')
    m.require(maps['policy_sha256'] == policy_sha, 'map-to-policy binding')
    arms = m.ids(maps['arms']); m.require(1 <= len(arms) <= MAX_ARMS, 'finite complete arm roster required')
    m.fields(maps['freeze_receipts'], 'target_free_rules original_packet_set admissibility before_outcomes', 'freeze receipts')
    for value in maps['freeze_receipts'].values(): m.digest(value)
    metadata = m.by_id(maps['case_metadata'], 'assessment_id')
    m.require(set(metadata) == set(assessments), 'complete original case metadata required')
    recording_session = {}
    for aid, row in metadata.items():
        m.fields(row, 'assessment_id session_id nuisance_stratum original_packet_sha256', 'case metadata')
        session = m.identity(row['session_id']); m.identity(row['nuisance_stratum'])
        rid = assessments[aid]['recording_id']
        # Session identity is supplied, never inferred from filename/person.
        if rid in recording_session:
            m.require(recording_session[rid] == session, 'one recording has inconsistent session mapping')
        recording_session[rid] = session
        if row['original_packet_sha256'] is not None: m.digest(row['original_packet_sha256'])
        m.require(not m.eligible(assessments[aid]) or row['original_packet_sha256'] is not None,
                  'evaluable original packet receipt required')
    transforms = m.by_id(maps['transforms'], 'transform_id')
    m.require(1 <= len(transforms) <= MAX_TRANSFORMS, 'finite complete transform roster required')
    distinct = set(); entries = {}
    for tid, transform in transforms.items():
        m.fields(transform, 'transform_id kind coordinate_map_sha256 nonidentity_receipt_sha256 rows', 'transform')
        m.require(transform['kind'] in ('channel_shuffle', 'temporal_shuffle', 'channel_and_temporal_shuffle'),
                  'only registered channel/temporal diagnostic family')
        fingerprint = m.digest(transform['coordinate_map_sha256'])
        m.require(fingerprint not in distinct, 'duplicate declared coordinate map cannot inflate transform count')
        distinct.add(fingerprint); m.digest(transform['nonidentity_receipt_sha256'])
        rows = m.by_id(transform['rows'], 'assessment_id')
        m.require(set(rows) == set(assessments), 'every transform retains every original slot')
        for aid, row in rows.items():
            m.fields(row, 'assessment_id disposition reason transformed_packet_sha256', 'map row')
            m.require(row['disposition'] in ('supported', 'invalid', 'unsupported'), 'map disposition')
            m.identity(row['reason'])
            if row['disposition'] == 'supported':
                m.require(row['reason'] == 'supported', 'supported reason must be explicit')
                m.digest(row['transformed_packet_sha256'])
                m.require(metadata[aid]['original_packet_sha256'] is not None, 'supported map lacks original packet')
            else:
                m.require(row['reason'] != 'supported' and row['transformed_packet_sha256'] is None,
                          'unavailable map cannot silently substitute original input')
        entries[tid] = (transform, rows)
    return arms, metadata, entries


def paired_ids(m, assessments, rows):
    return {aid for aid, row in rows.items() if row['disposition'] == 'supported' and m.eligible(assessments[aid])}


def admit_predictions(m, submitted, policy, map_parts, maps):
    people, recordings, assessments, transitions, person_fold = policy
    arms, metadata, entries = map_parts
    m.fields(submitted, 'schema task arms', 'paired predictions')
    m.require(submitted['schema'] == 'dosei_paired_predictions_v1' and submitted['task'] == m.TASK, 'prediction schema/task')
    arm_rows = m.by_id(submitted['arms'], 'arm_id')
    m.require(set(arm_rows) == set(arms), 'exact frozen arm roster required')
    admitted = {}
    for arm in arms:
        item = arm_rows[arm]
        m.fields(item, 'arm_id original_packet_set_sha256 original transforms', 'arm')
        m.require(item['original_packet_set_sha256'] == maps['freeze_receipts']['original_packet_set'],
                  'all arms must bind identical original packet set')
        original = m.admit_predictions(item['original'], policy)
        transformed = m.by_id(item['transforms'], 'transform_id')
        m.require(set(transformed) == set(entries), 'all frozen transforms required for every arm')
        outputs = {}
        for tid, (definition, mapping) in entries.items():
            transformed_item = transformed[tid]
            m.fields(transformed_item, 'transform_id coordinate_map_sha256 assessments', 'transformed prediction')
            m.require(transformed_item['coordinate_map_sha256'] == definition['coordinate_map_sha256'],
                      'same frozen map required across arms')
            rows = m.by_id(transformed_item['assessments'], 'assessment_id')
            m.require(set(rows) == set(assessments), 'transformed output must retain every original slot')
            support = paired_ids(m, assessments, mapping); probabilities = {}
            for aid, row in rows.items():
                m.fields(row, 'assessment_id outer_fold status packet_sha256 probabilities', 'transformed assessment')
                expected_fold = person_fold[recordings[assessments[aid]['recording_id']]['person_id']]
                m.require(row['outer_fold'] == expected_fold, 'transformed person/fold mismatch')
                m.require(row['packet_sha256'] == mapping[aid]['transformed_packet_sha256'],
                          'identical transformed packet hash/support required across arms')
                if aid in support:
                    m.require(row['status'] == 'ok', 'failed supported output refuses complete paired submission')
                    probabilities[aid] = m.probability_vector(row['probabilities'])
                else:
                    m.require(row['status'] == 'not_paired' and row['probabilities'] is None,
                              'unavailable/ineligible case must remain explicit not_paired')
            m.require(set(probabilities) == support, 'exact identical paired support required')
            outputs[tid] = probabilities
        admitted[arm] = (original, outputs)
    return admitted


def mean(values):
    return sum(values, Fraction(0)) / len(values) if values else None


def grade(m, targets, policy, map_parts, predictions):
    people, recordings, assessments, transitions, person_fold = policy
    arms, metadata, entries = map_parts
    # Unchanged complete primary target validation and original full score.
    originals = {arm: m.score_admitted(targets, policy, predictions[arm][0]) for arm in arms}
    labels = {row['assessment_id']: row['category'] for row in targets['assessments']}
    original_losses = {arm: {row['assessment_id']: Fraction(int(row['normalized_rps']['numerator']),
                              int(row['normalized_rps']['denominator']))
                             for row in report['assessments'] if row['evaluable']}
                       for arm, report in originals.items()}
    reports = []; transform_differences = {arm: [] for arm in arms}
    for tid, (definition, mapping) in entries.items():
        support = paired_ids(m, assessments, mapping)
        by_person = {person: [] for person in people}; strata = {}; retained = []
        for aid, row in mapping.items():
            rid = assessments[aid]['recording_id']; person = recordings[rid]['person_id']
            meta = metadata[aid]; paired = aid in support
            if paired: by_person[person].append(aid)
            key = (person, rid, meta['session_id'], meta['nuisance_stratum'])
            if key not in strata:
                strata[key] = {'mapping_dispositions': Counter(), 'reasons': Counter(),
                               'paired_target_categories': Counter(), 'original_cases': 0, 'paired_cases': 0}
            group = strata[key]; group['original_cases'] += 1; group['paired_cases'] += int(paired)
            group['mapping_dispositions'][row['disposition']] += 1; group['reasons'][row['reason']] += 1
            if paired: group['paired_target_categories'][str(labels[aid])] += 1
            retained.append({'assessment_id': aid, 'mapping_disposition': row['disposition'],
                             'reason': row['reason'], 'paired': paired})
        arm_reports = []
        for arm in arms:
            persons = []; person_means = []
            for person in people:
                cases = by_person[person]
                original = [original_losses[arm][aid] for aid in cases]
                transformed = [m.normalized_rps(predictions[arm][1][tid][aid], labels[aid]) for aid in cases]
                difference = mean([t - o for o, t in zip(original, transformed)])
                if difference is not None: person_means.append(difference)
                persons.append({'person_id': person, 'paired_cases': len(cases),
                                'original_matched_rps': m.exact(mean(original)),
                                'transformed_matched_rps': m.exact(mean(transformed)),
                                'transformed_minus_original': m.exact(difference)})
            overall = mean(person_means)
            if overall is not None: transform_differences[arm].append(overall)
            arm_reports.append({'arm_id': arm, 'people': persons,
                                'supported_person_macro_difference': m.exact(overall)})
        reports.append({'transform_id': tid, 'coordinate_map_sha256': definition['coordinate_map_sha256'],
                        'status': 'available_on_declared_support' if support else 'unavailable_no_paired_support',
                        'all_original_cases': retained,
                        'paired_case_ids_by_person': by_person,
                        'people_without_support': [person for person in people if not by_person[person]],
                        'coverage_by_person_recording_session_stratum': [
                            {'person_id': k[0], 'recording_id': k[1], 'session_id': k[2], 'nuisance_stratum': k[3], **v}
                            for k, v in strata.items()], 'arms': arm_reports})
    return {'schema': 'dosei_descriptive_paired_rps_v1', 'task': m.TASK,
            'complete_original_scores': originals, 'transforms': reports,
            'declared_distinct_mapping_count': len(entries),
            'available_transform_count': sum(bool(paired_ids(m, assessments, rows)) for _, rows in entries.values()),
            'equal_valid_transform_means': [{'arm_id': arm,
                'transformed_minus_original': m.exact(mean(transform_differences[arm]))} for arm in arms],
            'support_proof': 'Every arm admitted exactly the frozen paired case set, original person/fold and transformed packet hash for every transform.',
            'actual_physical_transform_distinctness_verified': False,
            'native_mapping_admissibility_verified': False,
            'scientifically_qualified': False, 'new_benchmark_count': 0,
            'interpretation': 'Support-limited descriptive dependence diagnostic; no permutation p-value, exchangeability, causal or consciousness claim. Full original score is separate.'}


def score_artifacts(policy_raw, maps_raw, predictions_raw, targets_raw, *, primary_source,
                    expected_policy_sha256, expected_maps_sha256,
                    expected_predictions_sha256, expected_targets_sha256):
    m = primary_module(primary_source)
    policy = m.admit_policy(decode(m, policy_raw, expected_policy_sha256, 'policy'))
    maps = decode(m, maps_raw, expected_maps_sha256, 'maps')
    map_parts = admit_maps(m, maps, policy, expected_policy_sha256)
    predictions = admit_predictions(m, decode(m, predictions_raw, expected_predictions_sha256, 'predictions'),
                                    policy, map_parts, maps)
    result = grade(m, decode(m, targets_raw, expected_targets_sha256, 'targets'), policy, map_parts, predictions)
    result['input_sha256'] = dict(policy=expected_policy_sha256, maps=expected_maps_sha256,
                                 predictions=expected_predictions_sha256, targets=expected_targets_sha256)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--primary-source', required=True)
    for name in CAPS:
        p.add_argument('--' + name, required=True); p.add_argument('--expected-' + name + '-sha256', required=True)
    p.add_argument('--output', required=True); a = p.parse_args(argv)
    m = primary_module(a.primary_source)
    pins = {kind: m.digest(getattr(a, 'expected_' + kind + '_sha256')) for kind in CAPS}
    read = lambda kind: decode(m, m.read_regular(getattr(a, kind), CAPS[kind]), pins[kind], kind)
    policy = m.admit_policy(read('policy')); maps = read('maps')
    map_parts = admit_maps(m, maps, policy, pins['policy'])
    predictions = admit_predictions(m, read('predictions'), policy, map_parts, maps)
    result = grade(m, read('targets'), policy, map_parts, predictions)
    result['input_sha256'] = pins
    raw = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    m.require(len(raw) <= OUTPUT_CAP, 'complete output cap; no truncation')
    with Path(a.output).open('xb') as stream: stream.write(raw)


if __name__ == '__main__':
    main()
