"""Fixed-origin count/exposure delivery and fold collection; no model execution.

Only tool-assisted or frozen-program event-history conditions are represented.
The operator must authenticate event production, identities and context upstream.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path


SCORER_SHA256 = 'd593735fec77f50e826636e988d8e0ec19253d1807a629f25ff7549a7a8257d8'
SCORER_PATH = Path(__file__).resolve().parent.parent / 'fixed-origin-forecast' / 'scorer.py'
_scorer_source = SCORER_PATH.read_bytes()
if hashlib.sha256(_scorer_source).hexdigest() != SCORER_SHA256:
    raise RuntimeError('fixed-origin scorer source mismatch')
_spec = importlib.util.spec_from_file_location('hypodrift_pinned_scorer', SCORER_PATH)
s = importlib.util.module_from_spec(_spec)
# Execute the authenticated snapshot, without reopening the path or using bytecode.
exec(compile(_scorer_source, str(SCORER_PATH), 'exec'), s.__dict__)


def canonical_bytes(doc):
    return (json.dumps(doc, sort_keys=True, separators=(',', ':'), allow_nan=False)
            + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def admit_context(doc, mice):
    """Allowlist actual time context; accept explicit unknowns without imputation."""
    s.exact(doc, ['schema', 'task_id', 'source_receipt_sha256', 'mice'], 'context')
    s.require(doc['schema'] == 'hypodrift-context-v1' and doc['task_id'] == s.TASK_ID,
              'context schema/task')
    s.pin(doc['source_receipt_sha256'])
    s.sequence(doc['mice'], 31, 'complete mouse context')
    contexts = {}
    for row in doc['mice']:
        s.exact(row, ['mouse_id', 'sessions'], 'mouse context')
        mid = s.identity(row['mouse_id'])
        s.require(mid in mice and mid not in contexts, 'context mouse identity')
        s.sequence(row['sessions'], 21, 'all session contexts including unknowns')
        clean, last_time = [], None
        for session, entry in enumerate(row['sessions'], 1):
            s.exact(entry, ['session', 'acquisition_seconds_relative_to_session9',
                            'zeitgeber_hours'], 'session context')
            s.require(type(entry['session']) is int and entry['session'] == session,
                      'chronological integer context session')
            relative = entry['acquisition_seconds_relative_to_session9']
            zt = entry['zeitgeber_hours']
            if relative is not None:
                relative = s.number(relative, 'actual relative acquisition seconds')
                s.require((relative < 0 if session < 9 else
                           relative == 0 if session == 9 else relative > 0),
                          'time relative to session9 acquisition')
                s.require(last_time is None or relative > last_time,
                          'known acquisitions strictly chronological')
                last_time = relative
            if zt is not None:
                zt = s.number(zt, 'actual Zeitgeber hours')
                s.require(0 <= zt < 24, 'Zeitgeber hours in [0,24)')
            clean.append({'session': session,
                          'acquisition_seconds_relative_to_session9': relative,
                          'zeitgeber_hours': zt,
                          'condition': ('baseline' if session <= 9 else
                                        'acute_recovery' if session <= 12 else
                                        'chronic_recovery')})
        contexts[mid] = clean
    s.require(set(contexts) == set(mice), 'complete context cohort')
    return contexts


def build_packet(targets, context, held_mouse_id):
    """Project one complete, operator-trusted cohort into one isolated episode.

    This function must stay in the operator process: targets contain future
    observations. It returns fresh allowlisted objects, never source dictionaries.
    """
    mice, cells = s.admit_targets(targets)
    s.require(held_mouse_id in mice, 'held mouse belongs to complete cohort')
    contexts = admit_context(context, mice)
    held_group = mice[held_mouse_id]
    calibration, training = [], []
    for (mid, nid), cell in sorted(cells.items()):
        if mice[mid] != held_group:
            continue
        stop = 27 if mid == held_mouse_id else 63
        row = {'mouse_id': mid, 'neuron_id': nid,
               'valid_stable_seconds': cell['valid_stable_seconds'][:stop],
               'event_counts': cell['event_counts'][:stop]}
        (calibration if mid == held_mouse_id else training).append(row)
    # No full-target hash, source receipt, missing-reason string, future exposure,
    # target eligibility or all-session normalization is put in the packet.
    return {
        'schema': 'hypodrift-event-history-packet-v1', 'task_id': s.TASK_ID,
        'representation': 'qualified_event_counts_and_stable_exposure',
        'training_scope': 'other_mice_in_held_biological_group',
        'origin_after_session': 9, 'states': s.STATES[:],
        'held_mouse': {'mouse_id': held_mouse_id, 'group': mice[held_mouse_id]},
        'training': {
            'sessions': list(range(1, 22)),
            'mice': [{'mouse_id': mid, 'group': mice[mid], 'context': contexts[mid]}
                     for mid in sorted(mice)
                     if mid != held_mouse_id and mice[mid] == held_group],
            'cells': training,
        },
        'calibration': {'sessions': list(range(1, 10)),
                        'context': contexts[held_mouse_id][:9], 'cells': calibration},
        'forecast_request': {'sessions': list(range(10, 22)),
                             'context': contexts[held_mouse_id][9:],
                             'values_per_cell': 36,
                             'value_units': 'log1p(events/minute)',
                             'order': 'session-major; wake,NREM,REM'},
    }


def make_binding(packet, targets, context, target_hash, context_hash):
    """Evaluator-private receipt: authenticate this file independently at join."""
    s.pin(target_hash)
    s.pin(context_hash)
    return {'schema': 'hypodrift-fold-binding-v1', 'task_id': s.TASK_ID,
            'held_mouse': dict(packet['held_mouse']),
            'training_mouse_ids': [m['mouse_id'] for m in packet['training']['mice']],
            'neuron_ids': [c['neuron_id'] for c in packet['calibration']['cells']],
            'packet_sha256': digest(canonical_bytes(packet)),
            'targets_document_sha256': target_hash,
            'context_document_sha256': context_hash,
            'producer_receipt_sha256': targets['producer_receipt_sha256'],
            'cohort_receipt_sha256': targets['cohort_receipt_sha256'],
            'context_receipt_sha256': context['source_receipt_sha256'],
            'scorer_sha256': SCORER_SHA256}


def admit_forecasts(forecasts):
    """Public output syntax admission, before opening private bindings."""
    s.sequence(forecasts, 31, 'one forecast per held mouse')
    result = {}
    cell_count = 0
    for doc in forecasts:
        s.exact(doc, ['schema', 'task_id', 'mouse_id', 'packet_sha256',
                      'sessions', 'states', 'cells'], 'held forecast')
        s.require(doc['schema'] == 'hypodrift-held-forecast-v1'
                  and doc['task_id'] == s.TASK_ID, 'held forecast schema/task')
        mid = s.identity(doc['mouse_id'])
        s.require(mid not in result, 'one forecast per held mouse')
        s.pin(doc['packet_sha256'])
        s.require(type(doc['sessions']) is list and
                  all(type(v) is int for v in doc['sessions']) and
                  doc['sessions'] == list(range(10, 22)) and doc['states'] == s.STATES,
                  'all 12 future sessions and ordered states')
        s.require(type(doc['cells']) is list and 0 < len(doc['cells']) <= 1661,
                  'nonempty bounded held cell list')
        cells = {}
        for cell in doc['cells']:
            s.exact(cell, ['neuron_id', 'log_rates'], 'held forecast cell')
            nid = s.identity(cell['neuron_id'])
            s.require(nid not in cells, 'unique held neuron')
            s.sequence(cell['log_rates'], 36, 'full future vectors even if unobserved')
            values = [s.number(v, 'predicted log rate') for v in cell['log_rates']]
            s.require(all(v >= 0 for v in values), 'nonnegative log rates')
            cells[nid] = values
        result[mid] = (doc['packet_sha256'], cells)
        cell_count += len(cells)
    s.require(cell_count == 1661, 'complete 1661-cell forecast collection')
    return result


def join_forecasts(forecasts, bindings):
    """Join all 31 independently isolated held-mouse outputs for the V3 scorer.

    Bindings are operator-trusted; no participant gets the collection of packets
    or another fold's training data. This does not attest execution or isolation.
    """
    predicted = admit_forecasts(forecasts)
    s.sequence(bindings, 31, 'complete private fold binding collection')
    expected, group_mice, group_cells, rosters, mouse_groups = {}, {}, {}, {}, {}
    common = None
    pins = ['targets_document_sha256', 'context_document_sha256',
            'producer_receipt_sha256', 'cohort_receipt_sha256',
            'context_receipt_sha256', 'scorer_sha256']
    for binding in bindings:
        s.exact(binding, ['schema', 'task_id', 'held_mouse', 'training_mouse_ids', 'neuron_ids',
                          'packet_sha256'] + pins, 'private fold binding')
        s.require(binding['schema'] == 'hypodrift-fold-binding-v1'
                  and binding['task_id'] == s.TASK_ID, 'binding schema/task')
        for key in ['packet_sha256'] + pins:
            s.pin(binding[key])
        s.require(binding['scorer_sha256'] == SCORER_SHA256, 'binding scorer identity')
        this_common = tuple(binding[k] for k in pins)
        s.require(common is None or this_common == common, 'one cohort/context/producer across folds')
        common = this_common
        s.exact(binding['held_mouse'], ['mouse_id', 'group'], 'binding mouse')
        mid = s.identity(binding['held_mouse']['mouse_id'])
        group = binding['held_mouse']['group']
        s.require(type(group) is str and group in s.GROUPS, 'binding group')
        s.require(mid in predicted and mid not in expected, 'binding mouse identity/uniqueness')
        s.require(type(binding['training_mouse_ids']) is list, 'binding training roster')
        roster = [s.identity(other) for other in binding['training_mouse_ids']]
        s.require(len(roster) == len(set(roster)), 'unique training mice')
        rosters[mid], mouse_groups[mid] = set(roster), group
        s.require(type(binding['neuron_ids']) is list and len(binding['neuron_ids']) > 0,
                  'binding neuron identities')
        ids = [s.identity(nid) for nid in binding['neuron_ids']]
        s.require(len(ids) == len(set(ids)), 'unique binding neuron identities')
        packet_hash, cells = predicted[mid]
        s.require(packet_hash == binding['packet_sha256'], 'forecast issued for bound packet')
        s.require(set(ids) == set(cells), 'all held cells match bound identities')
        expected[mid] = cells
        group_mice[group] = group_mice.get(group, 0) + 1
        group_cells[group] = group_cells.get(group, 0) + len(cells)
    for group, (nmice, ncells) in s.GROUPS.items():
        s.require((group_mice.get(group), group_cells.get(group)) == (nmice, ncells),
                  'full declared group cohort in fold collection')
    for mid, group in mouse_groups.items():
        s.require(rosters[mid] == {other for other, other_group in mouse_groups.items()
                                  if other != mid and other_group == group},
                  'exact other-mouse training roster within held biological group')
    prediction = {'schema': 'hypodrift-prediction-v1', 'task_id': s.TASK_ID,
                  'sessions': list(range(10, 22)), 'states': s.STATES[:],
                  'cells': [{'mouse_id': mid, 'neuron_id': nid, 'log_rates': values}
                            for mid, cells in sorted(expected.items())
                            for nid, values in sorted(cells.items())]}
    s.admit_prediction(prediction)
    return prediction


def write_new(path, raw):
    """Create-only, 0600 even under a permissive caller umask."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    for flag in ('targets', 'targets-sha256', 'context', 'context-sha256',
                 'held-mouse', 'packet-output', 'binding-output'):
        export.add_argument('--' + flag, required=True)
    join = commands.add_parser('join')
    for flag in ('forecasts', 'bindings', 'bindings-sha256', 'output'):
        join.add_argument('--' + flag, required=True)
    args = parser.parse_args(argv)
    if args.command == 'export':
        s.pin(args.targets_sha256)
        s.pin(args.context_sha256)
        s.require(Path(args.packet_output).resolve() != Path(args.binding_output).resolve(),
                  'packet and private binding must be separate files')
        targets, target_hash = s.read_document(args.targets, args.targets_sha256)
        context, context_hash = s.read_document(args.context, args.context_sha256)
        packet = build_packet(targets, context, args.held_mouse)
        binding = make_binding(packet, targets, context, target_hash, context_hash)
        # Keep any partial create-only delivery for inspection if the second
        # write fails. A partial pair is not a completed operator delivery.
        write_new(args.binding_output, canonical_bytes(binding))
        write_new(args.packet_output, canonical_bytes(packet))
    else:
        forecasts, _ = s.read_document(args.forecasts)
        admit_forecasts(forecasts)
        bindings, _ = s.read_document(args.bindings, args.bindings_sha256)
        prediction = join_forecasts(forecasts, bindings)
        write_new(args.output, canonical_bytes(prediction))


if __name__ == '__main__':
    main()
