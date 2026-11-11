"""Frozen comparator construction and inert task-specific paired grading.

The selected comparator hash is an operator input, never read from a candidate.
Hash custody does not prove native algorithm identity or chronology.
"""
import argparse
import json
from pathlib import Path
import re

from parent_sources import BASE, load

P = load()
A, B, IO, M = (P[n] for n in ('artifact_io', 'bindings', 'program_io', 'metrics'))
Invalid = A.Invalid
TASK = 'PAPER-paper-method-replacement-009'
CAP = 1_000_000_000
SELECTION_CAP = 16384
PRODUCER_CAP = 1_000_000


def need(ok, message):
    if not ok:
        raise Invalid(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def descriptor(path, body):
    return {'path': path, 'bytes': len(body), 'sha256': B.sha(body)}


def panel_at(path):
    body = A.capture(Path(path), 10_000_000)
    panel = A.strict_json(body)
    protocol = A.capture(BASE / 'public/common/PROTOCOL.json', 100000)
    IO.validate_panel(panel, protocol)
    return panel, body


def admit_parts(meta_body, pred_body, panel, panel_body):
    """Same four-column parent ABI, admitted from one immutable byte capture."""
    meta = A.strict_json(meta_body)
    need(type(meta) is dict and set(meta) == {'schema', 'panel_sha256', 'methods', 'method_provenance'}, 'exact submission fields')
    need(meta['schema'] == 'trial_session_submission_v1' and meta['panel_sha256'] == B.sha(panel_body) and meta['methods'] == panel['methods'], 'exact panel and method binding')
    provenance = meta['method_provenance']
    need(type(provenance) is dict and set(provenance) == set(panel['methods']) and all(type(v) is str and 1 <= len(v) <= 2000 for v in provenance.values()), 'bounded declared method provenance')
    pred = A.read_predictions(pred_body, (panel['prediction_rows'], len(panel['methods'])))
    for case in panel['cases']:
        if case['target'] == 'choice':
            values = pred[slice(*case['offset'])]
            need(not ((values < 0) | (values > 1)).any(), 'choice probabilities in [0,1]')
    return pred


def capture_bundle(path, panel, panel_body):
    root = Path(path)
    need(not root.is_symlink() and root.is_dir(), 'ordinary submission directory')
    need({p.name for p in root.iterdir()} == {'submission.json', 'predictions.npy'}, 'exact two-file submission')
    meta = A.capture(root / 'submission.json', 16384)
    cap = min(CAP, panel['prediction_rows'] * len(panel['methods']) * 8 + 2048)
    predictions = A.capture(root / 'predictions.npy', cap)
    return admit_parts(meta, predictions, panel, panel_body), meta, predictions


def freeze(baseline, panel_path, producer_record, output, max_bytes):
    """Copy an independently produced operator artifact before candidate access.

    The producer record is retained as declared provenance, not executable proof.
    No candidate artifact participates in this operation.
    """
    out = Path(output)
    B.fresh(out)
    panel, panel_body = panel_at(panel_path)
    _, meta, predictions = capture_bundle(baseline, panel, panel_body)
    producer = A.capture(Path(producer_record), PRODUCER_CAP)
    need(type(A.strict_json(producer)) is dict, 'operator producer record must be a JSON object')
    selection = {
        'schema': 'trial_session_fixed_comparator_selection_v1',
        'task_id': TASK,
        'panel_sha256': B.sha(panel_body),
        'protocol_sha256': panel['protocol_sha256'],
        'comparator_method': 'multi_rrr',
        'baseline': {'metadata': descriptor('baseline/submission.json', meta),
                     'predictions': descriptor('baseline/predictions.npy', predictions)},
        'producer_record': descriptor('producer_record.json', producer),
    }
    selection_body = encode(selection)
    need(len(selection_body) <= SELECTION_CAP, 'selection size')
    total = len(meta) + len(predictions) + len(producer) + len(selection_body)
    need(type(max_bytes) is int and 0 < max_bytes <= CAP + PRODUCER_CAP + 32768 and total <= max_bytes, 'complete freeze output cap')
    need(out.parent.is_dir(), 'existing output parent')
    out.mkdir(mode=0o700)
    (out / 'baseline').mkdir()
    for name, body in [('baseline/submission.json', meta), ('baseline/predictions.npy', predictions), ('producer_record.json', producer)]:
        with (out / name).open('xb') as stream:
            stream.write(body)
        (out / name).chmod(0o400)
    # Completion marker last. Failed/incomplete directories are not selections.
    with (out / 'SELECTION.json').open('xb') as stream:
        stream.write(selection_body)
    (out / 'SELECTION.json').chmod(0o400)
    return {'selection_sha256': B.sha(selection_body), 'bytes': total,
            'algorithm_identity_verified': False, 'candidate_execution': False}


def selected_comparator(selection_path, selected_sha256, panel, panel_body):
    need(type(selected_sha256) is str and re.fullmatch('[0-9a-f]{64}', selected_sha256) is not None, 'external operator selection hash required')
    path = Path(selection_path)
    raw = A.capture(path, SELECTION_CAP)
    need(B.sha(raw) == selected_sha256, 'operator-selected comparator hash mismatch')
    selection = A.strict_json(raw)
    fields = {'schema', 'task_id', 'panel_sha256', 'protocol_sha256', 'comparator_method', 'baseline', 'producer_record'}
    need(type(selection) is dict and set(selection) == fields, 'exact selection fields')
    need(selection['schema'] == 'trial_session_fixed_comparator_selection_v1' and selection['task_id'] == TASK and selection['comparator_method'] == 'multi_rrr', 'fixed comparator identity')
    need(selection['panel_sha256'] == B.sha(panel_body) and selection['protocol_sha256'] == panel['protocol_sha256'], 'comparator on same full panel and protocol')
    files = selection['baseline']
    need(type(files) is dict and set(files) == {'metadata', 'predictions'}, 'exact frozen baseline descriptors')
    for row, expected in [(files['metadata'], 'baseline/submission.json'), (files['predictions'], 'baseline/predictions.npy'), (selection['producer_record'], 'producer_record.json')]:
        need(type(row) is dict and row.get('path') == expected, 'fixed private comparator member')
    meta = B.bound(path.parent, files['metadata'], 16384)
    cap = min(CAP, panel['prediction_rows'] * len(panel['methods']) * 8 + 2048)
    predictions = B.bound(path.parent, files['predictions'], cap)
    producer = B.bound(path.parent, selection['producer_record'], PRODUCER_CAP)
    need(type(A.strict_json(producer)) is dict, 'operator producer record JSON object')
    pred = admit_parts(meta, predictions, panel, panel_body)
    return pred[:, panel['methods'].index('multi_rrr')], selection


def contrast(panel, truth, candidate, fixed):
    """Only improved candidate column versus independent fixed predictions."""
    rows = []
    col = panel['methods'].index('improved')
    for case in panel['cases']:
        sl = slice(*case['offset'])
        target = case['target']
        key, fn = ('auc', M.auc) if target == 'choice' else ('pearson', M.pearson) if target == 'prior' else ('r2', M.r2)
        a = M.metric(fn, truth[sl], candidate[sl, col])
        b = M.metric(fn, truth[sl], fixed[sl])
        gain = ({'value': None, 'status': 'undefined_paired_support'} if a['value'] is None or b['value'] is None
                else M.metric(lambda x, y: M.finite(x - y), a['value'], b['value']))
        rows.append({k: case[k] for k in ['case_id', 'eid', 'animal_id', 'target', 'query_trials']} | {
            'primary_metric': key, 'candidate_improved': a, 'fixed_multi_rrr': b,
            'candidate_minus_fixed': gain})
    aggregate = {}
    for target in sorted({r['target'] for r in rows}):
        subset = [r for r in rows if r['target'] == target]
        animals = sorted({r['animal_id'] for r in subset})
        endpoints = {}
        for endpoint in ['candidate_improved', 'fixed_multi_rrr', 'candidate_minus_fixed']:
            av = [M.summary([r[endpoint]['value'] for r in subset if r['animal_id'] == animal])['mean_all'] for animal in animals]
            endpoints[endpoint] = {'session_macro': M.summary([r[endpoint]['value'] for r in subset]),
                                   'animal_macro': M.summary(av)}
        aggregate[target] = {'primary_metric': subset[0]['primary_metric'], 'animal_ids': animals, **endpoints}
    return {'per_session': rows, 'aggregate': aggregate, 'success_threshold': None,
            'direction': 'positive candidate_minus_fixed means higher predictive metric on identical support'}


def read_reference(reference_path, panel, panel_body):
    path = Path(reference_path)
    ref = A.strict_json(A.capture(path, 1_000_000))
    need(ref.get('schema') == 'trial_session_reference_v1' and ref.get('panel_sha256') == B.sha(panel_body), 'private reference matches panel')
    y = A.read_predictions(B.bound(path.parent, ref['truth']), (panel['prediction_rows'],))
    template = A.read_predictions(B.bound(path.parent, ref['template']), (panel['prediction_rows'],))
    groups = A.read_predictions(B.bound(path.parent, ref['groups']), (panel['group_rows'], 3))
    for case in panel['cases']:
        if case['target'] == 'choice':
            values = y[slice(*case['offset'])]
            need(((values == 0) | (values == 1)).all(), 'private binary truth')
    return y, template, groups


def grade(candidate_path, panel_path, reference_path, selection_path, selection_sha256):
    panel, panel_body = panel_at(panel_path)
    # Fully admit candidate and fixed comparator before private target reads.
    pred, meta, raw_pred = capture_bundle(candidate_path, panel, panel_body)
    fixed, selection = selected_comparator(selection_path, selection_sha256, panel, panel_body)
    truth, template, groups = read_reference(reference_path, panel, panel_body)
    return {'schema': 'trial_session_fixed_comparator_grade_v1', 'status': 'scored',
            'task_id': TASK, 'panel_sha256': B.sha(panel_body),
            'operator_selection_sha256': selection_sha256,
            'candidate_captured_sha256': {'metadata': B.sha(meta), 'predictions': B.sha(raw_pred)},
            'fixed_comparator': selection,
            'fixed_comparator_comparison': contrast(panel, truth, pred, fixed),
            'candidate_supplied_method_diagnostics': M.evaluate(panel, truth, template, groups, pred),
            'candidate_supplied_contrasts_are_not_fixed_comparator_evidence': True,
            'algorithm_identity_verified': False, 'candidate_execution_verified': False,
            'selection_chronology_verified': False, 'scientific_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze_parser = commands.add_parser('freeze')
    for flag in ['baseline', 'panel', 'producer-record', 'output']:
        freeze_parser.add_argument('--' + flag, required=True, type=Path)
    freeze_parser.add_argument('--max-output-bytes', required=True, type=int)
    grade_parser = commands.add_parser('grade')
    for flag in ['candidate', 'panel', 'reference', 'selection', 'output']:
        grade_parser.add_argument('--' + flag, required=True, type=Path)
    grade_parser.add_argument('--selection-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'freeze':
        result = freeze(args.baseline, args.panel, args.producer_record, args.output, args.max_output_bytes)
        print(json.dumps(result, allow_nan=False))
    else:
        B.fresh(args.output)
        result = grade(args.candidate, args.panel, args.reference, args.selection, args.selection_sha256)
        B.write_json(args.output, result)


if __name__ == '__main__':
    main()
