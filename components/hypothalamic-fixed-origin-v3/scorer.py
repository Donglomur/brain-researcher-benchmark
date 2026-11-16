"""Pure fixed-origin scorer for the registered hypothalamic drift contract.

This consumes trusted, already qualified counts/exposures. It does not derive
events, authenticate biological identities, train models, or attest blind access.
"""
import argparse
import hashlib
import json
import math
import os
import stat
from pathlib import Path

TASK_ID = 'NEURAL-SCOPE-20261114-HYPOTHALAMIC-DRIFT'
GROUPS = {'LH-Vgat': (6, 509), 'LH-Vglut2': (6, 257),
          'LH-Hcrt/OX': (6, 425), 'LH-MCH': (7, 28), 'POA-Vgat': (6, 442)}
STATES = ['wake', 'NREM', 'REM']
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024


class ContractError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ContractError(message)


def exact(obj, fields, where):
    require(type(obj) is dict and set(obj) == set(fields), where + ': exact fields')


def number(x, where):
    require(type(x) in (int, float), where + ': number, not bool')
    try:
        v = float(x)
    except (ValueError, OverflowError):
        raise ContractError(where + ': unrepresentable number') from None
    require(math.isfinite(v), where + ': finite number')
    return v


def identity(x):
    require(type(x) is str and 0 < len(x) <= 128
            and not any(ord(c) < 32 for c in x), 'nonempty bounded identity')
    return x


def pin(x):
    require(type(x) is str and len(x) == 64
            and all(c in '0123456789abcdef' for c in x), 'SHA-256 syntax')


def sequence(x, size, where):
    require(type(x) is list and len(x) == size, where + ': complete fixed length')


def decode(raw):
    require(type(raw) is bytes and len(raw) <= MAX_DOCUMENT_BYTES, 'document byte bound')

    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, 'duplicate JSON key')
            d[k] = v
        return d

    def invalid(_):
        raise ContractError('nonfinite JSON literal')

    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ContractError('invalid JSON: ' + str(exc)[:120]) from None


def admit_prediction(doc):
    """Public syntax admission; no private target/reference is read here."""
    exact(doc, ['schema', 'task_id', 'states', 'sessions', 'cells'], 'prediction')
    require(doc['schema'] == 'hypodrift-prediction-v1' and doc['task_id'] == TASK_ID,
            'prediction schema/task')
    require(doc['states'] == STATES and type(doc['sessions']) is list
            and all(type(v) is int for v in doc['sessions'])
            and doc['sessions'] == list(range(10, 22)),
            'fixed state order and all future sessions')
    sequence(doc['cells'], 1661, 'prediction cells')
    result = {}
    for cell in doc['cells']:
        exact(cell, ['mouse_id', 'neuron_id', 'log_rates'], 'prediction cell')
        key = (identity(cell['mouse_id']), identity(cell['neuron_id']))
        require(key not in result, 'duplicate predicted cell')
        sequence(cell['log_rates'], 36, 'future session-major log rates')
        result[key] = [number(v, 'predicted log rate') for v in cell['log_rates']]
        require(all(v >= 0 for v in result[key]), 'log1p of predicted nonnegative event rate')
    require(len({k[0] for k in result}) == 31, 'all 31 predicted mice')
    return result


def admit_targets(doc):
    exact(doc, ['schema', 'task_id', 'states', 'sessions', 'producer_receipt_sha256',
                'cohort_receipt_sha256', 'mice', 'cells'], 'targets')
    require(doc['schema'] == 'hypodrift-targets-v1' and doc['task_id'] == TASK_ID,
            'target schema/task')
    require(doc['states'] == STATES and type(doc['sessions']) is list
            and all(type(v) is int for v in doc['sessions'])
            and doc['sessions'] == list(range(1, 22)),
            'complete 21-session target support')
    pin(doc['producer_receipt_sha256'])
    pin(doc['cohort_receipt_sha256'])
    sequence(doc['mice'], 31, 'mouse manifest')
    mice = {}
    for m in doc['mice']:
        exact(m, ['mouse_id', 'group'], 'mouse')
        mid = identity(m['mouse_id'])
        require(mid not in mice and m['group'] in GROUPS, 'mouse uniqueness/group')
        mice[mid] = m['group']
    sequence(doc['cells'], 1661, 'target cells')
    cells = {}
    for cell in doc['cells']:
        exact(cell, ['mouse_id', 'neuron_id', 'valid_stable_seconds', 'event_counts',
                     'missing_reasons'], 'target cell')
        key = (identity(cell['mouse_id']), identity(cell['neuron_id']))
        require(key[0] in mice and key not in cells, 'target cell identity/uniqueness')
        for name in ('valid_stable_seconds', 'event_counts', 'missing_reasons'):
            sequence(cell[name], 63, name)
        for sec, count, reason in zip(cell['valid_stable_seconds'],
                                      cell['event_counts'], cell['missing_reasons']):
            if sec is None:
                require(count is None and type(reason) is str and 0 < len(reason) <= 512,
                        'unobserved slot needs null count and explicit reason')
            else:
                sec = number(sec, 'valid stable seconds')
                require(sec >= 0 and type(count) is int and count >= 0 and reason is None,
                        'observed slot requires nonnegative seconds/count and null reason')
                require(sec != 0 or count == 0, 'zero exposure cannot contain an event')
        cells[key] = cell
    require({k[0] for k in cells} == set(mice), 'every declared mouse has cells')
    for group, (nmice, ncells) in GROUPS.items():
        require(sum(g == group for g in mice.values()) == nmice, 'full group mouse count')
        require(sum(mice[k[0]] == group for k in cells) == ncells, 'full group cell count')
    return mice, cells


def mean(values):
    """Nonnegative finite losses, stable against overflow of an ordinary sum."""
    if not values:
        return None
    largest = max(values)
    return 0.0 if largest == 0 else largest * (math.fsum(v / largest for v in values) / len(values))


def target_log_rate(count, seconds):
    if count == 0:
        return 0.0
    try:
        rate = (count / seconds) * 60.0
    except OverflowError:
        rate = math.inf
    if math.isfinite(rate):
        return math.log1p(rate)
    z = math.log(count) + math.log(60.0) - math.log(seconds)
    return z + math.log1p(math.exp(-z)) if z > 0 else math.log1p(math.exp(z))


def loss(prediction, target):
    d = prediction - target
    squared = d * d
    require(math.isfinite(squared), 'squared error outside finite binary64 range')
    return squared


def aggregate(mice, by_mouse):
    mouse_results, group_results = [], []
    for mid, group in mice.items():
        a, b = mean(by_mouse[mid]['candidate']), mean(by_mouse[mid]['reference'])
        mouse_results.append({'mouse_id': mid, 'group': group,
                              'eligible_neuron_denominator': len(by_mouse[mid]['candidate']),
                              'candidate_mse': a, 'reference_mse': b,
                              'paired_loss_reduction': None if a is None else b - a})
    for group in GROUPS:
        rows = [r for r in mouse_results if r['group'] == group and r['candidate_mse'] is not None]
        a, b = mean([r['candidate_mse'] for r in rows]), mean([r['reference_mse'] for r in rows])
        group_results.append({'group': group, 'eligible_mouse_denominator': len(rows),
                              'candidate_mse': a, 'reference_mse': b,
                              'paired_loss_reduction': None if a is None else b - a})
    complete = all(r['candidate_mse'] is not None for r in group_results)
    a = mean([r['candidate_mse'] for r in group_results]) if complete else None
    b = mean([r['reference_mse'] for r in group_results]) if complete else None
    return {'primary_defined': complete,
            'undefined_reason': None if complete else 'one_or_more_groups_without_eligible_targets',
            'candidate_mse': a, 'reference_mse': b,
            'paired_loss_reduction': None if not complete else b - a,
            'groups': group_results, 'mice': mouse_results}


def score(prediction, targets, comparator):
    """Return evaluator-private numerical results; no readiness/pass threshold."""
    pred = admit_prediction(prediction)
    mice, cells = admit_targets(targets)
    exact(comparator, ['schema', 'reference_id', 'selection_receipt_sha256',
                       'prediction'], 'comparator')
    require(comparator['schema'] == 'hypodrift-comparator-v1', 'comparator schema')
    identity(comparator['reference_id'])
    pin(comparator['selection_receipt_sha256'])
    ref = admit_prediction(comparator['prediction'])
    require(set(pred) == set(cells) == set(ref), 'identical complete cell support')
    by_mouse = {m: {'candidate': [], 'reference': []} for m in mice}
    phases = {phase: {m: {'candidate': [], 'reference': []} for m in mice}
              for phase in ('acute_sessions10_12', 'chronic_sessions13_21')}
    support = []
    total_eligible = 0
    for key, cell in cells.items():
        state_losses = {'candidate': [], 'reference': []}
        phase_losses = {p: {'candidate': [], 'reference': []} for p in phases}
        state_support = []
        for state in range(3):
            a, b, eligible_sessions = [], [], []
            phase_state = {p: {'candidate': [], 'reference': []} for p in phases}
            for session in range(10, 22):
                i = (session - 1) * 3 + state
                seconds = cell['valid_stable_seconds'][i]
                if seconds is None or seconds < 20:
                    continue
                target = target_log_rate(cell['event_counts'][i], seconds)
                j = (session - 10) * 3 + state
                a.append(loss(pred[key][j], target))
                b.append(loss(ref[key][j], target))
                phase = 'acute_sessions10_12' if session <= 12 else 'chronic_sessions13_21'
                phase_state[phase]['candidate'].append(a[-1])
                phase_state[phase]['reference'].append(b[-1])
                eligible_sessions.append(session)
            total_eligible += len(a)
            state_support.append({'state': STATES[state], 'eligible_future_sessions': eligible_sessions,
                                  'denominator': len(a)})
            if a:
                state_losses['candidate'].append(mean(a))
                state_losses['reference'].append(mean(b))
            for phase in phases:
                for method in ('candidate', 'reference'):
                    if phase_state[phase][method]:
                        phase_losses[phase][method].append(mean(phase_state[phase][method]))
        for method in ('candidate', 'reference'):
            if state_losses[method]:
                by_mouse[key[0]][method].append(mean(state_losses[method]))
        for phase in phases:
            for method in ('candidate', 'reference'):
                if phase_losses[phase][method]:
                    phases[phase][key[0]][method].append(mean(phase_losses[phase][method]))
        support.append({'mouse_id': key[0], 'neuron_id': key[1],
                        'valid_stable_seconds': cell['valid_stable_seconds'],
                        'missing_reasons': cell['missing_reasons'],
                        'states': state_support,
                        'eligible_state_denominator': len(state_losses['candidate'])})
    return {'schema': 'hypodrift-score-v1', 'task_id': TASK_ID, **aggregate(mice, by_mouse),
            'phase_diagnostics': {p: aggregate(mice, data) for p, data in phases.items()},
            'loss_units': 'squared log1p(events/minute)', 'origin_after_session': 9,
            'cohort': {'groups': 5, 'mice': 31, 'neurons': 1661, 'sessions': 21,
                       'declared_state_slots': 104643, 'future_state_slots': 59796,
                       'eligible_future_state_slots': total_eligible},
            'cell_support': support,
            'reference_id': comparator['reference_id'],
            'source_receipts': {k: targets[k] for k in ('producer_receipt_sha256', 'cohort_receipt_sha256')},
            'reference_selection_receipt_sha256': comparator['selection_receipt_sha256'],
            'limits': ['Receipt hashes identify upstream evidence; this scorer does not validate that evidence.',
                       'No event extraction, identity authentication, model competence or held-target access attestation.',
                       'No bootstrap, biological/causal conclusion, task qualification or scientific pass threshold.']}


def read_document(path, expected=None):
    if expected is not None:
        pin(expected)  # Required trusted identity syntax precedes the open.
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'input must be an ordinary regular file')
        with os.fdopen(fd, 'rb') as f:
            fd = None  # The file object now owns this exact descriptor.
            raw = f.read(MAX_DOCUMENT_BYTES + 1)
    except OSError as exc:
        raise ContractError('input open/read refused: ' + str(exc)[:120]) from None
    finally:
        if fd is not None:
            os.close(fd)
    require(len(raw) <= MAX_DOCUMENT_BYTES, 'document byte bound')
    if expected is not None:
        require(hashlib.sha256(raw).hexdigest() == expected, 'trusted document hash mismatch')
    return decode(raw), hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('prediction', 'targets', 'targets-sha256', 'comparator', 'comparator-sha256', 'output'):
        parser.add_argument('--' + field, required=True)
    args = parser.parse_args(argv)
    prediction, pred_hash = read_document(args.prediction)
    admit_prediction(prediction)  # Complete public syntax admission before private opens.
    pin(args.targets_sha256)
    pin(args.comparator_sha256)  # Both required identities precede either trusted open.
    targets, target_hash = read_document(args.targets, args.targets_sha256)
    comparator, comparator_hash = read_document(args.comparator, args.comparator_sha256)
    report = score(prediction, targets, comparator)
    report['document_sha256'] = {'prediction': pred_hash, 'targets': target_hash, 'comparator': comparator_hash}
    with Path(args.output).open('x', encoding='utf-8') as f:
        json.dump(report, f, sort_keys=True, separators=(',', ':'), allow_nan=False)
        f.write('\n')


if __name__ == '__main__':
    main()
