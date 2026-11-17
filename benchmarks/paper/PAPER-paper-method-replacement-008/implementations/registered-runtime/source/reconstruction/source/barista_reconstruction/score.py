"""Complete masked-channel candidate admission, then private-target scoring.

No loader callback substitutes for the actual primitive NPY readers. Source
identity metadata is not an assertion of genuine provenance or native custody.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from .arrays import read_array
from .io_contract import capture, fresh, ordinary, parse, put
from .metrics import aggregate_channel_results, masked_channel_mse
from .protocol import (ARMS, MODELS, COUNTS, PEOPLE, RECORDINGS, SAMPLES,
                       TASK_ID, canonical, requests, validate_panel,
                       validate_submission_metadata, _hash)


@dataclass(frozen=True)
class Limits:
    candidate_bytes: int
    unique_target_bytes: int
    total_read_bytes: int
    live_array_bytes: int
    file_bytes: int
    metadata_bytes: int
    result_bytes: int

    def validate(self):
        for value in vars(self).values():
            if type(value) is not int or value <= 0:
                raise ValueError('All explicit resource limits must be positive integers')
        if self.file_bytes > 256_000_000 or self.metadata_bytes > 64_000_000:
            raise ValueError('Ordinary file/metadata transport bound')
        if self.result_bytes > 64_000_000:
            raise ValueError('Result transport bound')
        return self


class ReadBudget:
    """Prospective logical body charges; not measured physical OS/native I/O."""
    def __init__(self, limit):
        self.limit, self.charged = limit, 0

    def charge(self, count):
        if type(count) is not int or count < 0:
            raise ValueError('Invalid logical read charge')
        if count > self.limit - self.charged:
            raise ValueError('Cumulative logical read allowance exhausted')
        self.charged += count


def _metadata(path, limits, budget):
    # Charge the complete possible read before opening, including failed reads.
    budget.charge(limits.metadata_bytes + 1)
    return capture(path, limits.metadata_bytes)


def _descriptor(d, expected, limits):
    if not isinstance(d, dict) or set(d) != {'path', 'bytes', 'sha256', 'shape', 'dtype'}:
        raise ValueError('Exact target/candidate primitive descriptor required')
    from .protocol import FILENAME
    if (not isinstance(d['path'], str) or not FILENAME.fullmatch(d['path'])
            or not _hash(d['sha256']) or d['dtype'] not in ('<f4', '<f8')):
        raise ValueError('Safe single primitive-float NPY identity required')
    if (not isinstance(d['shape'], list) or any(type(x) is not int for x in d['shape'])
            or d['shape'] != expected):
        raise ValueError('Complete native test-segment/sample support required')
    payload = expected[0] * expected[1] * int(d['dtype'][-1])
    if type(d['bytes']) is not int or not payload < d['bytes'] <= min(payload + 4096, limits.file_bytes):
        raise ValueError('Exact primitive payload and bounded header required')
    return d


def _live_bound(shape, prediction_bytes, target_bytes=0):
    # Captured primitive bodies + known float64 error/absolute scratch + masks,
    # plus the kernel's fixed65536-sample normalized block. This does not measure
    # Python/native allocator, interpreter or report-object overhead.
    n = shape[0] * shape[1]
    return prediction_bytes + target_bytes + 18 * n + 65536 * 16


def _read(base, d, shape, limits, budget):
    budget.charge(d['bytes'] + 1)
    return read_array(base, d, shape=shape, cap=d['bytes'])


def admit_submission(panel, body, base, limits, budget):
    """Validate every descriptor first, then every actual finite candidate body."""
    sub = parse(body)
    validate_submission_metadata(sub, panel, max_declared_bytes=limits.candidate_bytes)
    expected = list(requests(panel))
    names = set()
    for row, e in zip(sub['predictions'], expected):
        d = _descriptor(row['values'], e['shape'], limits)
        if d['path'] in names:
            raise ValueError('Each complete candidate artifact must have its own filename')
        names.add(d['path'])
        if _live_bound(e['shape'], d['bytes']) > limits.live_array_bytes:
            raise ValueError('Candidate known-array memory allowance insufficient')
    for row, e in zip(sub['predictions'], expected):
        value = _read(base, row['values'], e['shape'], limits, budget)
        del value
    return sub['predictions'], expected


def _target_roster(panel):
    for session in panel['sessions']:
        for channel in session['channel_ids']:
            yield {'person': session['person'], 'recording': session['recording'],
                   'channel_id': channel,
                   'shape': [session['test_segments'], SAMPLES]}


def validate_gold(gold, panel, public_sha256, limits):
    fields = {'schema', 'task_id', 'panel_id', 'public_sha256',
              'generation_commitment', 'source_provenance', 'targets'}
    if (not isinstance(gold, dict) or set(gold) != fields
            or gold['schema'] != 'barista_reconstruction_gold_v2'
            or gold['task_id'] != TASK_ID or gold['panel_id'] != panel['panel_id']
            or gold['public_sha256'] != public_sha256
            or gold['generation_commitment'] != panel['generation_commitment']):
        raise ValueError('Exact private target/public generation binding required')
    keys = {'preparation_source_sha256', 'split_identity_sha256',
            'normalization_source_sha256', 'channel_identity_sha256',
            'rights_review_sha256', 'exposure_review_sha256', 'source_input_manifest_sha256'}
    p = gold['source_provenance']
    if (not isinstance(p, dict) or set(p) != keys | {'metadata_is_not_execution_attestation'}
            or any(not _hash(p[k]) for k in keys)
            or p['metadata_is_not_execution_attestation'] is not True):
        raise ValueError('Explicit genuine-source provenance identities remain required')
    rows = gold['targets']
    if not isinstance(rows, list) or len(rows) != sum(COUNTS[p][3] for p in PEOPLE):
        raise ValueError('Complete945 ordered private target channels required')
    total, names, bykey = 0, set(), {}
    for row, e in zip(rows, _target_roster(panel)):
        if (not isinstance(row, dict) or set(row) != {'person', 'recording', 'channel_id', 'values'}
                or type(row['person']) is not int
                or any(row[k] != e[k] for k in ('person', 'recording', 'channel_id'))):
            raise ValueError('Exact native target channel/recording identity required')
        d = _descriptor(row['values'], e['shape'], limits)
        if d['path'] in names:
            raise ValueError('Each target channel requires a distinct target artifact')
        names.add(d['path']); total += d['bytes']
        if total > limits.unique_target_bytes:
            raise ValueError('Unique target byte allowance exceeded')
        bykey[e['person'], e['channel_id']] = d
    return bykey


def _separate(candidate_root, target_root):
    a, b = ordinary(candidate_root), ordinary(target_root)
    if not a.is_dir() or not b.is_dir():
        raise ValueError('Existing ordinary candidate and private target roots required')
    a, b = a.resolve(strict=True), b.resolve(strict=True)
    if a == b or a in b.parents or b in a.parents or os.path.samefile(a, b):
        raise ValueError('Private targets and candidate trees must be separate owners')


def grade(public_path, gold_path, submission_path, limits):
    """File-backed endpoint; no candidate-supplied private-reader callbacks."""
    limits.validate()
    budget = ReadBudget(limits.total_read_bytes)
    candidate_root, target_root = Path(submission_path).parent, Path(gold_path).parent
    try:
        _separate(candidate_root, target_root)
        public_body = _metadata(public_path, limits, budget)
        panel = validate_panel(parse(public_body))
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        return {'task_id': TASK_ID, 'status': 'operator_input_error', 'reason': str(exc),
                'private_target_manifest_opened': False, 'private_numeric_inputs_opened': False,
                'logical_read_bytes_charged': budget.charged, 'scientifically_qualified': False}
    try:
        rows, expected = admit_submission(
            panel, _metadata(submission_path, limits, budget), candidate_root, limits, budget)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        return {'task_id': TASK_ID, 'status': 'invalid_submission', 'reason': str(exc),
                'private_target_manifest_opened': False, 'private_numeric_inputs_opened': False,
                'logical_read_bytes_charged': budget.charged, 'scientifically_qualified': False}
    try:
        return _score_admitted(panel, public_body, rows, expected, gold_path,
                               candidate_root, target_root, limits, budget)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        return {'task_id': TASK_ID, 'status': 'operator_or_changed_input_error',
                'reason': str(exc), 'private_target_access_attempted': True,
                'logical_read_bytes_charged': budget.charged,
                'partial_results_disclosed': False, 'scientifically_qualified': False}


def _score_admitted(panel, public_body, rows, expected, gold_path,
                    candidate_root, target_root, limits, budget):
    # This is the first private target-body read: the entire22680 candidate bank
    # passed actual byte/hash/shape/finite admission, not just metadata validation.
    gold = parse(_metadata(gold_path, limits, budget))
    targets = validate_gold(gold, panel, hashlib.sha256(public_body).hexdigest(), limits)
    # Check simultaneous memory for every target/prediction before numeric gold.
    for row, e in zip(rows, expected):
        d = targets[e['person'], e['channel_id']]
        if _live_bound(e['shape'], row['values']['bytes'], d['bytes']) > limits.live_array_bytes:
            raise ValueError('Combined target/prediction/kernel memory allowance insufficient')
    results = []
    for row, e in zip(rows, expected):
        # Recapture the exact candidate first; use only those captured bytes.
        prediction = _read(candidate_root, row['values'], e['shape'], limits, budget)
        target = _read(target_root, targets[e['person'], e['channel_id']], e['shape'], limits, budget)
        result = masked_channel_mse(target, prediction)
        results.append(dict(result, id=e['id']))
        del prediction, target
    aggregate = aggregate_channel_results(results, panel)
    report = {'task_id': TASK_ID, 'schema': 'barista_reconstruction_score_v2',
              'status': ('scored_complete_support' if all(
                  r['status'] == 'ok' for r in aggregate['model_results'])
                  else 'numeric_unavailable_complete_support'), 'panel_id': panel['panel_id'],
              'all_channel_results': results, 'summary': aggregate,
              'logical_read_bytes_charged': budget.charged,
              'logical_read_basis': 'Prospective body+1 charges; metadata charges full cap+1, including failures. Physical OS/native I/O is unmeasured.',
              'historical_r2_convention_resolved': False,
              'historical_reproduction_established': False,
              'source_provenance_or_query_isolation_qualified': False,
              'scientifically_qualified': False}
    if len(canonical(report)) + 1 > limits.result_bytes:
        raise ValueError('Complete result byte allowance exceeded; no partial report')
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('public', 'gold', 'submission', 'out'):
        parser.add_argument('--' + name, required=True)
    for name in Limits.__dataclass_fields__:
        parser.add_argument('--' + name.replace('_', '-'), required=True, type=int)
    args = parser.parse_args()
    out = fresh(args.out)
    limits = Limits(**{n: getattr(args, n) for n in Limits.__dataclass_fields__})
    report = grade(args.public, args.gold, args.submission, limits)
    if len(canonical(report)) + 1 > limits.result_bytes:
        raise ValueError('Complete result byte allowance exceeded')
    put(out, report)


if __name__ == '__main__':
    main()
