"""Numerical consumer for the registered nine-experiment LEP report assay.

Trusted target production and protocol execution are separate prerequisites.
All candidate parsing finishes before the trusted-loader callback is invoked.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

TASK_ID = 'NEURAL-SCOPE-20261114-LASER-EEG-REPORT'
COUNTS = (26, 29, 39, 30, 65, 95, 142, 223, 29)
DEVICES = ('BioSemi', 'ANT', 'BrainProducts', 'ANT', 'ANT', 'BrainProducts',
           'BioSemi', 'BrainProducts', 'BrainProducts')
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024
PENALTY = 10.0


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact(obj, keys, name):
    require(type(obj) is dict and set(obj) == set(keys), name + ': exact fields')


def pin(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'required external SHA-256 identity')


def identity(value):
    require(type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', value) is not None,
            'opaque identifier; paths and source metadata are not permitted')
    return value


def rating(value):
    require(type(value) in (int, float), 'rating must be numeric, not Boolean')
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ContractError('rating representation') from None
    require(math.isfinite(value) and 0 <= value <= 10, 'finite rating in [0,10]')
    return value


def decode(raw):
    require(type(raw) is bytes and len(raw) <= MAX_DOCUMENT_BYTES, 'bounded UTF-8 document')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise ContractError('nonfinite JSON literal')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError('invalid JSON: ' + str(exc)[:100]) from None


def parse_submission(raw, protocol_sha256, representation_sha256):
    """Classify the entire public output without accessing a trusted body.

Invalid whole envelopes yield no usable predictions (every required ID will
receive penalty10). Invalid individual records remain represented by ID.
"""
    pin(protocol_sha256)
    pin(representation_sha256)
    indexed, diagnostics = {}, {'envelope_valid': False, 'unassignable_records': 0,
                                'record_count': 0, 'envelope_error': None}
    try:
        doc = decode(raw)
        exact(doc, ('schema', 'task_id', 'protocol_sha256', 'representation_sha256',
                    'predictions'), 'submission')
        require(doc['schema'] == 'lep-predictions-v1' and doc['task_id'] == TASK_ID,
                'submission schema/task')
        require(doc['protocol_sha256'] == protocol_sha256
                and doc['representation_sha256'] == representation_sha256,
                'incompatible protocol or representation')
        require(type(doc['predictions']) is list, 'prediction records list')
    except ContractError as exc:
        diagnostics['envelope_error'] = str(exc)
        return indexed, diagnostics
    diagnostics['envelope_valid'] = True
    diagnostics['record_count'] = len(doc['predictions'])
    for row in doc['predictions']:
        try:
            require(type(row) is dict and 'query_id' in row, 'record has query ID')
            qid = identity(row['query_id'])
        except ContractError:
            diagnostics['unassignable_records'] += 1
            continue
        try:
            require(set(row) in ({'query_id', 'median'}, {'query_id', 'median', 'q10', 'q90'}),
                    'prediction fields')
            median = rating(row['median'])
            interval = None
            if 'q10' in row:
                lo, hi = rating(row['q10']), rating(row['q90'])
                require(lo <= median <= hi, 'ordered optional quantiles')
                interval = (lo, hi)
            item = {'median': median, 'interval': interval, 'error': None}
        except ContractError as exc:
            item = {'median': None, 'interval': None, 'error': str(exc)}
        indexed.setdefault(qid, []).append(item)
    return indexed, diagnostics


def validate_targets(doc, protocol_sha256, representation_sha256):
    exact(doc, ('schema', 'task_id', 'protocol_sha256', 'representation_sha256',
                'inventory_receipt_sha256', 'producer_receipt_sha256', 'people'), 'targets')
    require(doc['schema'] == 'lep-targets-v1' and doc['task_id'] == TASK_ID,
            'target schema/task')
    require(doc['protocol_sha256'] == protocol_sha256
            and doc['representation_sha256'] == representation_sha256,
            'trusted policy mismatch')
    pin(doc['inventory_receipt_sha256'])
    pin(doc['producer_receipt_sha256'])
    require(type(doc['people']) is list and len(doc['people']) == 678,
            'all 678 nominal participant-within-experiment records required')
    people, required, seen_trials = {}, {}, set()
    excluded_total = 0
    for person in doc['people']:
        exact(person, ('experiment', 'person_id', 'trials'), 'person')
        exp = person['experiment']
        require(type(exp) is int and 1 <= exp <= 9, 'exact integer experiment1..9')
        key = (exp, identity(person['person_id']))
        require(key not in people, 'duplicate person-within-experiment')
        require(type(person['trials']) is list and person['trials'], 'complete trial ledger')
        eligible, excluded = [], []
        previous = -1
        for trial in person['trials']:
            exact(trial, ('query_id', 'chronology', 'eligible', 'rating', 'exclusion_reason'), 'trial')
            qid = identity(trial['query_id'])
            require(qid not in seen_trials, 'duplicate source query ID')
            seen_trials.add(qid)
            order = trial['chronology']
            require(type(order) is int and order > previous, 'strict nonnegative chronological order')
            previous = order
            require(type(trial['eligible']) is bool, 'explicit eligibility Boolean')
            if trial['eligible']:
                require(trial['exclusion_reason'] is None, 'eligible trial has no exclusion reason')
                eligible.append((qid, rating(trial['rating'])))
            else:
                reason = trial['exclusion_reason']
                require(trial['rating'] is None and type(reason) is str and 0 < len(reason) <= 512,
                        'excluded trial has null target and explicit source reason')
                excluded.append({'query_id': qid, 'reason': reason})
        require(len(eligible) >= 3, 'fewer than three eligible trials holds the complete assay')
        scored = eligible[2:]
        for qid, target in scored:
            required[qid] = target
        people[key] = {'calibration_ids': [r[0] for r in eligible[:2]],
                       'scored': scored, 'excluded': excluded, 'source_trial_count': len(person['trials'])}
        excluded_total += len(excluded)
    for exp, count in enumerate(COUNTS, 1):
        require(sum(key[0] == exp for key in people) == count, 'complete nine-experiment counts')
    return people, required, excluded_total, len(seen_trials)


def mean(values):
    return None if not values else math.fsum(values) / len(values)


def ranks(values):
    """Average ranks for ties; only finite complete vectors enter here."""
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        value = (i + 1 + j) / 2
        for k in order[i:j]:
            result[k] = value
        i = j
    return result


def rank_correlation(predicted, targets):
    if len(predicted) < 2:
        return None, 'fewer_than_two_scored_trials'
    a, b = ranks(predicted), ranks(targets)
    ma, mb = mean(a), mean(b)
    da, db = [v - ma for v in a], [v - mb for v in b]
    va, vb = math.fsum(v * v for v in da), math.fsum(v * v for v in db)
    if va == 0 or vb == 0:
        return None, 'constant_prediction_or_target'
    corr = math.fsum(x * y for x, y in zip(da, db)) / math.sqrt(va * vb)
    return min(1.0, max(-1.0, corr)), None


def resolved_record(index, qid):
    rows = index.get(qid, [])
    if not rows:
        return None, 'missing'
    if len(rows) != 1:
        return None, 'duplicate'
    if rows[0]['error'] is not None:
        return None, 'malformed'
    return rows[0], None


def grade(submission_raw, trusted_loader, *, protocol_sha256, representation_sha256):
    """Public validation first, then trusted complete targets and fixed reference.

The callback returns (targets_dict, comparator_dict). Failed public predictions
are scored with the declared penalty; a defective trusted input refuses instead.
"""
    index, admission = parse_submission(submission_raw, protocol_sha256, representation_sha256)
    targets, comparator = trusted_loader()
    people, required, excluded_total, total_trials = validate_targets(
        targets, protocol_sha256, representation_sha256)
    exact(comparator, ('schema', 'reference_id', 'information', 'selection_receipt_sha256',
                       'prediction'), 'comparator')
    require(comparator['schema'] == 'lep-comparator-v1'
            and comparator['information'] == 'energy_context_only', 'fixed context-only comparator')
    identity(comparator['reference_id'])
    pin(comparator['selection_receipt_sha256'])
    baseline_raw = json.dumps(comparator['prediction'], allow_nan=False, separators=(',', ':')).encode()
    baseline, baseline_admission = parse_submission(baseline_raw, protocol_sha256, representation_sha256)
    require(baseline_admission['envelope_valid'] and baseline_admission['unassignable_records'] == 0
            and set(baseline) == set(required), 'trusted reference exact required support')
    for qid in required:
        require(resolved_record(baseline, qid)[1] is None, 'trusted reference malformed/missing/duplicate')
    person_results = []
    penalties = {'missing': 0, 'duplicate': 0, 'malformed': 0}
    for (exp, pid), person in people.items():
        errors, ref_errors, predicted, actual, covered, widths = [], [], [], [], [], []
        person_penalties = {k: 0 for k in penalties}
        for qid, target in person['scored']:
            row, invalid = resolved_record(index, qid)
            if invalid:
                errors.append(PENALTY)
                penalties[invalid] += 1
                person_penalties[invalid] += 1
            else:
                errors.append(abs(row['median'] - target))
                predicted.append(row['median'])
                actual.append(target)
                if row['interval'] is not None:
                    lo, hi = row['interval']
                    covered.append(int(lo <= target <= hi))
                    widths.append(hi - lo)
            ref_errors.append(abs(baseline[qid][0]['median'] - target))
        if sum(person_penalties.values()):
            rho, rho_reason = None, 'invalid_predictions_full_trial_support_required'
        else:
            rho, rho_reason = rank_correlation(predicted, actual)
        a, b = mean(errors), mean(ref_errors)
        person_results.append({'experiment': exp, 'person_id': pid, 'device': DEVICES[exp - 1],
                               'source_trial_count': person['source_trial_count'],
                               'calibration_ids': person['calibration_ids'],
                               'excluded_trials': person['excluded'], 'scored_denominator': len(errors),
                               'valid_prediction_count': len(predicted), 'penalties': person_penalties,
                               'candidate_mae': a, 'reference_mae': b, 'paired_mae_reduction': b - a,
                               'rank_correlation': rho, 'rank_undefined_reason': rho_reason,
                               'interval_diagnostic': {'nominal_coverage': 0.8,
                                                       'supplied_valid_count': len(widths),
                                                       'required_denominator': len(errors),
                                                       'conditional_coverage': mean(covered),
                                                       'conditional_mean_width': mean(widths),
                                                       'complete_interval_support': len(widths) == len(errors)}})
    experiment_results = []
    for exp in range(1, 10):
        rows = [p for p in person_results if p['experiment'] == exp]
        a, b = mean([p['candidate_mae'] for p in rows]), mean([p['reference_mae'] for p in rows])
        experiment_results.append({'experiment': exp, 'person_denominator': len(rows),
                                   'scored_trial_denominator': sum(p['scored_denominator'] for p in rows),
                                   'candidate_mae': a, 'reference_mae': b, 'paired_mae_reduction': b - a})
    candidate_mae = mean([r['candidate_mae'] for r in experiment_results])
    reference_mae = mean([r['reference_mae'] for r in experiment_results])
    unknown = sorted(set(index) - set(required))
    complete = (admission['envelope_valid'] and not admission['unassignable_records']
                and not unknown and not sum(penalties.values()))
    device_results = []
    for device in dict.fromkeys(DEVICES):
        rows = [p for p in person_results if p['device'] == device]
        device_results.append({'device': device, 'person_denominator': len(rows),
                               'candidate_person_macro_mae': mean([p['candidate_mae'] for p in rows]),
                               'reference_person_macro_mae': mean([p['reference_mae'] for p in rows])})
    return {'schema': 'lep-score-v1', 'task_id': TASK_ID,
            'candidate_mae': candidate_mae, 'reference_mae': reference_mae,
            'paired_mae_reduction': reference_mae - candidate_mae,
            'primary_units': 'recorded intensity scale points [0,10]',
            'candidate_person_macro_mae': mean([p['candidate_mae'] for p in person_results]),
            'reference_person_macro_mae': mean([p['reference_mae'] for p in person_results]),
            'output_contract_passed': complete, 'admission': admission,
            'unknown_prediction_ids': unknown, 'penalty_counts': penalties,
            'population': {'experiments': 9, 'nominal_people': 678,
                           'source_trial_count': total_trials, 'excluded_trial_count': excluded_total,
                           'calibration_trial_count': 1356, 'scored_trial_denominator': len(required)},
            'experiments': experiment_results, 'people': person_results,
            'device_strata_person_weighted': device_results,
            'reference_id': comparator['reference_id'],
            'receipt_identities': {k: targets[k] for k in ('inventory_receipt_sha256', 'producer_receipt_sha256')},
            'reference_selection_receipt_sha256': comparator['selection_receipt_sha256'],
            'protocol_sha256': protocol_sha256, 'representation_sha256': representation_sha256,
            'limits': ['Nominal participant-within-experiment counts are not authenticated distinct biological people.',
                       'Receipt identities and owner targets/reference require separate scientific qualification.',
                       'Unknown/unassignable extras fail the output contract and cannot earn score; every required ID retains its specified loss.',
                       'Interval coverage is conditional on valid supplied intervals; availability is explicit, not full-assay uncertainty.',
                       'Bootstrap, training-normalized loss, model competence, protected execution and causal/neural-specific inference are not established.']}


def read_bytes(path, expected=None, *, public_submission=False):
    # Public output gets one extra byte solely to classify an over-bound whole
    # envelope. Trusted bodies remain strict, including their complete hashes.
    require(not public_submission or expected is None,
            'trusted hashes cannot apply to a bounded submission prefix')
    if expected is not None:
        pin(expected)
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'ordinary regular input file required')
        with os.fdopen(fd, 'rb') as f:
            fd = None
            raw = f.read(MAX_DOCUMENT_BYTES + 1)
    except OSError as exc:
        raise ContractError('input open/read refused: ' + str(exc)[:100]) from None
    finally:
        if fd is not None:
            os.close(fd)
    require(public_submission or len(raw) <= MAX_DOCUMENT_BYTES, 'input byte bound')
    if expected is not None:
        require(hashlib.sha256(raw).hexdigest() == expected, 'trusted input hash mismatch')
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('submission', 'protocol-sha256', 'representation-sha256', 'targets',
                  'targets-sha256', 'comparator', 'comparator-sha256', 'output'):
        parser.add_argument('--' + field, required=True)
    args = parser.parse_args(argv)
    for value in (args.protocol_sha256, args.representation_sha256,
                  args.targets_sha256, args.comparator_sha256):
        pin(value)  # All external identities are required before any input open.
    raw = read_bytes(args.submission, public_submission=True)
    oversized = len(raw) > MAX_DOCUMENT_BYTES
    # An over-bound prefix is never decoded or represented as a complete body.
    # grade() classifies it as an invalid envelope and keeps every required case.
    hashes = {'submission': None if oversized else hashlib.sha256(raw).hexdigest()}
    def load():
        target_raw = read_bytes(args.targets, args.targets_sha256)
        reference_raw = read_bytes(args.comparator, args.comparator_sha256)
        hashes['targets'] = hashlib.sha256(target_raw).hexdigest()
        hashes['comparator'] = hashlib.sha256(reference_raw).hexdigest()
        return decode(target_raw), decode(reference_raw)
    report = grade(raw, load, protocol_sha256=args.protocol_sha256,
                   representation_sha256=args.representation_sha256)
    report['document_sha256'] = hashes
    report['submission_read'] = {'byte_limit': MAX_DOCUMENT_BYTES, 'bytes_read': len(raw),
                                 'complete_body': not oversized, 'limit_exceeded': oversized}
    with Path(args.output).open('x', encoding='utf-8') as f:
        json.dump(report, f, separators=(',', ':'), sort_keys=True, allow_nan=False)
        f.write('\n')


if __name__ == '__main__':
    main()
