#!/usr/bin/env python3
"""Fixed projection from explicit operator-normalized native recordings.

Source-field mapper exists; real MAT and external clock/animal binding remain missing. This script verifies the raw
asset identity and normalized roster declarations; it cannot certify an absent
real MAT-field/clock/animal binding.
"""
import argparse
import hashlib
import hmac
from pathlib import Path
from . import delivery_io as io
from .history import ARMS, extract, safe_key
from .scorer_core import fingerprint, public_contract

SOURCE_PIN = {'bytes': 236931813, 'sha256': '4fcf5906d95d144ed1d6741cc86f4ef4fd332dec0f52e00ee5f34e8b75fe6d45'}


def build(normalized, secret):
    io.need(type(secret) is bytes and len(secret) == 32, 'Exact private32byte generation/token key')
    io.exact(normalized, ['schema', 'source_pin', 'complete_WT_recording_roster', 'excluded_recordings', 'records', 'mapping_status'])
    io.need(normalized['schema'] == 'neural047-normalized-native-v1' and normalized['source_pin'] == SOURCE_PIN,
            'Exact original WT asset generation')
    records = normalized['records']; roster = normalized['complete_WT_recording_roster']
    excluded = normalized['excluded_recordings']
    io.need(type(excluded) is list and len(excluded) <= 256, 'Explicit bounded source exclusions')
    for row in excluded:
        io.exact(row, ['recording_id','reason'])
        io.need(type(row['recording_id']) is str and row['reason'] == 'no_exact_SAAV_identity',
                'Only documented no-SAAV recording exclusion; ambiguous identities fail')
    io.need(type(records) is list and 3 <= len(records) <= 256 and type(roster) is list and
            3 <= len(roster) <= 256 and all(type(v) is str for v in roster) and
            len(roster) == len(set(roster)) and
            sorted(roster) == sorted([r['recording_id'] for r in records] + [r['recording_id'] for r in normalized['excluded_recordings']]), 'Complete source roster with explicit SAAV-unidentified exclusions')
    units = {r['split_unit'] for r in records}
    io.need(units == {'animal'}, 'One explicit independently supported grouping unit')
    events = []; exclusions = []; lineage = []
    for record in records:
        io.need(record['source_pin'] == SOURCE_PIN, 'No unbound additional recording source')
        selected, rejected = extract(record)
        exclusions.append({'recording_id': record['recording_id'], 'source_events': len(record['events']),
                           'eligible_events': len(selected), 'excluded': rejected})
        for event in selected:
            case = safe_key(secret, record['recording_id'], event['event_id'])
            event['case_key'] = case; events.append(event)
            lineage.append({'case_key': case, 'recording_id': record['recording_id'], 'event_id': event['event_id'],
                            'landmark_index0': event['landmark_index0'], 'source_indices0': event['source_indices0']})
    io.need(0 < len(events) <= 50000 and len({e['case_key'] for e in events}) == len(events), 'Complete eligible case cap')
    groups = sorted({r['split_group'] for r in records})
    empty = [group for group in groups if not any(e['split_group'] == group for e in events)]
    # Do not quietly drop a failed/unsupported recording from the planned panel.
    if empty:
        return {'status': 'insufficient_support', 'reason': 'At least one source identity has no eligible event.',
                'empty_groups': empty, 'exclusions': exclusions}, None, None, None
    io.need(len(groups) >= 3, 'At least three animals, leaving at least two for training')
    aliases = {g: 'group_' + hashlib.sha256(secret + g.encode()).hexdigest()[:24] for g in groups}
    generation = hmac.new(secret, b'neural047-normalized-native-v1\x00' +
                          hashlib.sha256(io.canonical(normalized)).digest(), hashlib.sha256).hexdigest()
    public = {'schema': 'neural047-panel-v1', 'input_generation': generation,
              'split_unit': next(iter(units)), 'arms': list(ARMS),
              'folds': [{'fold_id': 'fold_%03d' % i, 'test_group': aliases[g],
                         'case_keys': [e['case_key'] for e in events if e['split_group'] == g]}
                        for i, g in enumerate(groups)]}
    public['packet_id'] = fingerprint(public); public_contract(public)
    folds = []
    for fold, group in zip(public['folds'], groups):
        training = [e for e in events if e['split_group'] != group]
        query = [e for e in events if e['split_group'] == group]
        if {e['label'] for e in training} != {0, 1}:
            return {'status': 'insufficient_support', 'reason': 'Outer training split lacks a direction class.',
                    'fold_id': fold['fold_id'], 'exclusions': exclusions}, None, None, None
        for arm in ARMS:
            folds.append({'schema': 'neural047-fold-v1', 'packet_id': public['packet_id'],
                'fold_id': fold['fold_id'], 'arm': arm, 'test_group': fold['test_group'],
                'training': [{'case_key': e['case_key'], 'group': aliases[e['split_group']],
                              'features': e['views'][arm], 'dorsal': e['label']} for e in training],
                'query': [{'case_key': e['case_key'], 'features': e['views'][arm]} for e in query]})
    private = {'schema': 'neural047-targets-v1', 'packet_id': public['packet_id'],
               'targets': [{'case_key': e['case_key'], 'dorsal': e['label']} for e in events]}
    audit = {'status': 'prepared_from_operator_normalized_schema', 'exclusions': exclusions, 'lineage': lineage,
             'mapping_status': normalized['mapping_status'], 'source_recording_exclusions': normalized['excluded_recordings'], 'external_clock_and_identity_mapping_certified_by_this_script': False,
             'scientific_fits': 0, 'metric_calls': 0}
    return audit, public, folds, private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-source', type=Path, required=True)
    parser.add_argument('--normalized-records', type=Path, required=True)
    parser.add_argument('--token-key', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-output-bytes', type=int, required=True)
    args = parser.parse_args()
    out = io.regular(args.output); io.need(not out.exists(), 'Fresh output before source reads')
    io.need(0 < args.max_output_bytes <= 300000000, 'Explicit bounded operator output allowance')
    io.read(args.raw_source, SOURCE_PIN['bytes'], SOURCE_PIN, retain=False)
    source = io.json_file(args.normalized_records, 300000000)
    secret = io.read(args.token_key, 32); io.need(len(secret) == 32, 'Exactly32private bytes')
    audit, public, folds, private = build(source, secret)
    planned = [('private/PREPARATION.json', audit)]
    if public is not None:
        planned += [('public/panel.json', public), ('private/targets.json', private)]
        planned += [('private/folds/' + f['fold_id'] + '/' + f['arm'] + '.json', f) for f in folds]
    bodies = [(name, value, len(io.canonical(value))) for name, value in planned]
    pins = [{'path': name, **io.pin(io.canonical(value))} for name, value in planned]
    bindings = {'schema': 'neural047-prepared-file-bindings-v1', 'source_pin': SOURCE_PIN,
                'files': pins, 'status': audit['status'], 'empirical_scoring': False}
    io.need(sum(size for _, _, size in bodies) + len(io.canonical(bindings)) <= args.max_output_bytes,
            'Complete output including file bindings exceeds selected cap; no partial panel')
    out = io.fresh(args.output)
    for name, value, size in bodies:
        path = out / name; path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        io.put(path, value, max(1, size))
    io.put(out / 'FILE_BINDINGS.json', bindings)


if __name__ == '__main__':
    main()
