"""Bounded artifact scoring on operator-admitted operands, not paper qualification.

No target files, source MATLAB, array fitting, networking or subprocesses are used.
The independently held operator operand bundle is trusted, not authenticated by a
candidate or established as scientifically valid merely by its content digest.
"""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from math import isfinite
from pathlib import Path


def _dependency(filename, expected_hash):
    root = Path(__file__).resolve().parent
    path = (root / filename if filename == 'metric_primitives_v2.py' else
            root.parent / 'submission-comparison' / filename)
    body = path.read_bytes()
    if sha256(body).hexdigest() != expected_hash:
        raise RuntimeError('reviewed predecessor changed: ' + filename)
    spec = importlib.util.spec_from_file_location('_find025_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    # Compile exactly the authenticated bytes, including when an unrelated
    # bytecode cache exists beside the preserved source.
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


c = _dependency('find025_contract.py',
                'adccd1362fc7f96b967467377ca834b3fbb95581252bd3c8210d79e6eb6d3ce9')
m = _dependency('metric_primitives_v2.py',
                'd90a741396ca362050697c71426b5e6fcfcd8e7eed536dfa4f028e49d34f7990')
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_ROWS = 100000
MAX_ABS_VALUE = 1e100
SUPPORTED = (c.SIGNED, c.CORR, c.PAIRED_CORR, c.ACCURACY, c.LATENCY)


class OperandError(ValueError):
    """Invalid independently supplied operator operands; abort the whole call."""


class PayloadError(ValueError):
    """Invalid candidate artifact; retain its assigned case as failed."""


def _exact(value, keys, error, where):
    if type(value) is not dict or set(value) != set(keys):
        raise error(where + ': exact fields required')


def _rows(value, error):
    if (type(value) is not list or not 0 < len(value) <= MAX_ROWS or
            any(type(x) is not str or not 0 < len(x) <= 512 or x.strip() != x for x in value) or
            len(set(value)) != len(value)):
        raise error('nonempty unique bounded ordered row IDs required')


def _numbers(value, length, error):
    if (type(value) is not list or len(value) != length or
            any(type(x) not in (int, float) or abs(x) > MAX_ABS_VALUE or
                not isfinite(x) for x in value)):
        raise error('finite bounded numeric vector matching every row required')


def _operator(plan, bundle):
    _exact(bundle, ('schema', 'plan_sha256', 'cases'), OperandError, 'operator bundle')
    if bundle['schema'] != 'find025_operands_v1' or bundle['plan_sha256'] != c.digest(plan):
        raise OperandError('operator bundle schema/plan binding differs')
    if type(bundle['cases']) is not list or len(bundle['cases']) > len(plan['cases']):
        raise OperandError('bounded operator cases required')
    assigned = {r['case_id']: r for r in plan['cases']}
    admitted = {}
    for row in bundle['cases']:
        _exact(row, ('case_id', 'identity', 'row_ids', 'target_values', 'times',
                     'delay_onset', 'representation', 'preparation_id'), OperandError, 'operand')
        key = row['case_id']
        if type(key) is not str or key not in assigned or key in admitted:
            raise OperandError('unknown or duplicate operator case')
        if row['identity'] != assigned[key]['identity'] or any(v is None for v in row['identity'].values()):
            raise OperandError('operator scientific identity incomplete or differs')
        try:
            c.text(row['preparation_id'], 'preparation_id')
        except c.ContractError as exc:
            raise OperandError(str(exc)) from exc
        metric = row['identity']['metric_id']
        if metric not in SUPPORTED:
            raise OperandError('operator operand provided for unsupported/artifact metric')
        _rows(row['row_ids'], OperandError)
        n = len(row['row_ids'])
        expected_representation = ('delay_trialmeans' if metric == c.CORR else
                                   'oriented_smoothed_prego_trace' if metric == c.LATENCY else
                                   'assigned_rows')
        if row['representation'] != expected_representation:
            raise OperandError('metric requires explicit ' + expected_representation + ' operands')
        if metric == c.LATENCY:
            if row['target_values'] is not None:
                raise OperandError('latency does not accept a target vector')
            _numbers(row['times'], n, OperandError)
            _numbers([row['delay_onset']], 1, OperandError)
            if any(a >= b for a, b in zip(row['times'], row['times'][1:])):
                raise OperandError('operator timestamps must strictly increase')
        else:
            if row['times'] is not None or row['delay_onset'] is not None:
                raise OperandError('prediction metric does not accept latency operands')
            _numbers(row['target_values'], n, OperandError)
            if metric == c.ACCURACY and any(v not in (-1, 1) for v in row['target_values']):
                raise OperandError('binary operator targets require -1/+1')
        admitted[key] = row
    # Shared prediction artifacts alone do not establish a shared evaluation
    # vector. Also check the independent target, row order and preparation.
    if plan['mode'] == 'protected_improvement':
        groups = {}
        for case in plan['cases']:
            if case['obligation'].startswith('movement_'):
                group = tuple(case[k] for k in ('obligation', 'cohort', 'animal', 'session', 'panel_id'))
                groups.setdefault(group, []).append(case['case_id'])
        for ids in groups.values():
            present = [admitted[k] for k in ids if k in admitted]
            if present and (len(present) != 2 or len(ids) != 2):
                raise OperandError('protected primary and secondary operands required together')
            if present:
                fields = ('row_ids', 'target_values', 'times', 'delay_onset', 'representation', 'preparation_id')
                if any(present[0][k] != present[1][k] for k in fields):
                    raise OperandError('protected primary/secondary operator vectors differ')
    return admitted


def payload_key(run_id, descriptor):
    """In-memory key. No candidate path is interpreted or followed."""
    return (run_id, descriptor['kind'], descriptor['logical_id'], descriptor['sha256'])


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PayloadError('duplicate JSON object key')
        result[key] = value
    return result


def _reject_constant(value):
    raise PayloadError('nonfinite JSON constant')


def _prediction(body, rows):
    try:
        decoded = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise PayloadError('invalid strict UTF-8 JSON prediction') from exc
    _exact(decoded, ('schema', 'row_ids', 'values'), PayloadError, 'prediction')
    if decoded['schema'] != 'find025_prediction_vector_v1':
        raise PayloadError('prediction schema differs')
    _rows(decoded['row_ids'], PayloadError)
    if decoded['row_ids'] != rows:
        raise PayloadError('prediction row IDs/order differ from assigned support')
    _numbers(decoded['values'], len(rows), PayloadError)
    return decoded['values']


def _payloads(submissions, payloads):
    if type(payloads) is not dict:
        raise OperandError('payloads must be an in-memory mapping')
    descriptors = {payload_key(s['run_id'], a): a for s in submissions
                   for r in s['records'] for a in r['artifacts']}
    if any(k not in descriptors for k in payloads):
        raise OperandError('unassigned payload key')
    if any(type(v) is not bytes for v in payloads.values()):
        raise OperandError('payload bodies must be bytes')
    if sum(len(v) for v in payloads.values()) > MAX_TOTAL_BYTES:
        raise OperandError('total payload byte limit exceeded; no support truncation allowed')
    authenticated, errors = {}, {}
    for key, descriptor in descriptors.items():
        body = payloads.get(key)
        if body is None:
            errors[key] = 'payload_missing'
        elif len(body) > MAX_PAYLOAD_BYTES:
            errors[key] = 'payload_byte_limit_exceeded'
        elif sha256(body).hexdigest() != descriptor['sha256']:
            errors[key] = 'payload_sha256_mismatch'
        else:
            authenticated[key] = body
    return authenticated, errors


def _evaluate(plan, submission, operands, authenticated, payload_errors, bundle_digest):
    records = {row['case_id']: row for row in submission['records']}
    run, scores, audit = submission['run_id'], [], []
    gaps = c.plan_gaps(plan)
    pair_issues = c.prediction_pair_issues(plan, records)
    submission_digest = c.digest(submission)
    preliminary = {cell['case_id']: cell for cell in c.report(plan, [submission], [])['cells']
                   if cell['run_id'] == run}
    for case in plan['cases']:
        key, metric = case['case_id'], case['identity']['metric_id']
        row = records.get(key)
        detail = {'case_id': key, 'run_id': run, 'metric_id': metric,
                  'status': 'missing', 'reason': 'submission_record_missing',
                  'authenticated_artifacts': 0, 'scored_rows': 0,
                  'ordered_rows_sha256': None, 'operator_bundle_sha256': bundle_digest}
        audit.append(detail)
        if row is None:
            continue
        if row['status'] != 'complete':
            detail.update(status=row['status'], reason=row['reason'])
            continue
        reason = None
        if gaps:
            reason = 'operator_plan_has_unresolved_obligations'
        elif row['identity'] != case['identity'] or any(v is None for v in row['identity'].values()):
            reason = 'candidate_scientific_identity_differs_or_incomplete'
        elif key in pair_issues:
            reason = pair_issues[key]
        elif preliminary[key]['status'] == 'noncomparable':
            reason = 'predecessor_admission:' + ','.join(preliminary[key]['reasons'])
        keys = [payload_key(run, a) for a in row['artifacts']]
        detail['authenticated_artifacts'] = sum(k in authenticated for k in keys)
        if reason is None:
            reason = next((payload_errors[k] for k in keys if k in payload_errors), None)
        if reason:
            detail.update(status='held', reason=reason)
            continue
        if metric == c.ARTIFACT:
            detail.update(status='artifact_authenticated', reason='no_numeric_metric')
            continue
        if metric == c.VARIANCE:
            detail.update(status='unsupported', reason='covariance_basis_denominator_contract_unresolved')
            continue
        if metric not in SUPPORTED or key not in operands:
            detail.update(status='held', reason='operator_metric_operands_missing')
            continue
        kind = c.OBLIGATIONS[case['obligation']][2]
        primaries = [a for a in row['artifacts'] if a['kind'] == kind]
        if len(primaries) != 1:
            detail.update(status='held', reason='exactly_one_primary_prediction_required')
            continue
        operand = operands[key]
        status, value = 'valid', None
        try:
            predicted = _prediction(authenticated[payload_key(run, primaries[0])], operand['row_ids'])
            if metric == c.SIGNED:
                value = m.signed_variance_explained(operand['target_values'], predicted)
            elif metric in (c.CORR, c.PAIRED_CORR):
                value = m.squared_pearson_correlation(operand['target_values'], predicted)
            elif metric == c.ACCURACY:
                value = m.binary_accuracy(operand['target_values'], predicted)
            else:
                value = m.first_strict_90pct_latency(operand['times'], predicted, operand['delay_onset'])
            detail.update(status='scored', reason=None, scored_rows=len(predicted),
                          ordered_rows_sha256=c.digest(operand['row_ids']))
        except m.UndefinedMetric as exc:
            status = 'undefined'
            detail.update(status='undefined', reason=str(exc))
        except (PayloadError, ValueError, OverflowError) as exc:
            status = 'failed'
            detail.update(status='failed', reason=str(exc))
        record_id = 'find025-artifact-evaluator-v1:' + c.digest(detail)
        scores.append({'run_id': run, 'case_id': key, 'submission_sha256': submission_digest,
                       'identity': deepcopy(case['identity']), 'status': status,
                       'value': value, 'evaluator_record_id': record_id})
        detail['evaluator_record_id'] = record_id
    return {'scores': scores, 'case_audit': audit}


def evaluate_submissions(plan, submissions, payloads, operator_operands):
    """Evaluate all supplied runs against ONE common operator target/support bundle.

    Missing assigned cases/runs are retained by the unchanged reporter. Final
    paper success is never emitted. Call this batch API for paired comparisons.
    """
    c.validate_plan(plan)
    if type(submissions) is not list:
        raise OperandError('submissions must be a list')
    runs = set()
    for submission in submissions:
        c.validate_submission(plan, submission)
        if submission['run_id'] in runs:
            raise OperandError('duplicate submitted run')
        runs.add(submission['run_id'])
    operands = _operator(plan, operator_operands)
    authenticated, errors = _payloads(submissions, payloads)
    bundle_digest = c.digest(operator_operands)
    evaluated = [_evaluate(plan, s, operands, authenticated, errors, bundle_digest) for s in submissions]
    scores = [score for result in evaluated for score in result['scores']]
    return {'schema': 'find025_artifact_evaluation_v1', 'scores': scores,
            'case_audit': [row for result in evaluated for row in result['case_audit']],
            'comparison': c.report(plan, submissions, scores),
            'support_contract': {'operator_bundle_sha256': bundle_digest,
                'plan_sha256': c.digest(plan), 'shared_between_supplied_runs': True,
                'operator_provenance_independently_verified': False,
                'paper_qualification': False, 'authentic_data_prepared': False}}


def evaluate_submission(plan, submission, payloads, operator_operands):
    """Single-run convenience; batch API is required for one-bundle pairing."""
    return evaluate_submissions(plan, [submission], payloads, operator_operands)
