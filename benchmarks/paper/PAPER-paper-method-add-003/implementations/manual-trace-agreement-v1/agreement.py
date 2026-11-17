"""Original human motion-trace agreement kernel; alignment is an operator input.

This module does not recover the paper's still-unresolved trace alignment,
execute DREDge, or establish a paper win. It never chooses a lag, rescales a
trace, drops samples, interpolates, averages patients, or computes an IID p-value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

TASK_ID = 'PAPER-paper-method-add-003'
PATIENTS = ('Pt01', 'Pt02', 'Pt03')
REFERENCE_SCHEMA = 'dredge-manual-reference/v1'
CANDIDATE_SCHEMA = 'dredge-manual-candidate/v1'


def _digest(value, name):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError(f'{name} must be a lowercase SHA256 digest')
    return value


def _vector(value, name):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError(f'{name} must contain at least two samples')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(f'{name} must contain finite real numbers')
    return tuple(float(v) for v in value)


def pearson_r(x, y):
    """Pearson r with no deletion, fitting, alignment or IID inference.

    Remove an overflow-safe midpoint before positive rescaling, preserving
    representable variation around large offsets while avoiding large products.
    A constant trace has undefined correlation, returned as
    None rather than being dropped or assigned perfect agreement.
    """
    x = _vector(x, 'first trace')
    y = _vector(y, 'second trace')
    if len(x) != len(y):
        raise ValueError('Trace lengths differ')

    def center(values):
        origin = min(values) / 2 + max(values) / 2
        residuals = tuple(v - origin for v in values)
        scale = max(abs(v) for v in residuals)
        if scale == 0:
            return None
        scaled = tuple(v / scale for v in residuals)
        mean = math.fsum(scaled) / len(scaled)
        centered = tuple(v - mean for v in scaled)
        norm = math.sqrt(math.fsum(v * v for v in centered))
        return None if norm == 0 else tuple(v / norm for v in centered)

    a, b = center(x), center(y)
    if a is None or b is None:
        return None
    return max(-1.0, min(1.0, math.fsum(u * v for u, v in zip(a, b))))


def _records(packet, schema):
    if not isinstance(packet, dict) or packet.get('schema') != schema or packet.get('task_id') != TASK_ID:
        raise ValueError('Wrong packet schema or task identity')
    records = packet.get('records')
    if not isinstance(records, list) or len(records) != len(PATIENTS):
        raise ValueError('Full original Pt01-Pt03 cohort required')
    result = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('Each patient record must be an object')
        patient = record.get('patient')
        if patient not in PATIENTS or patient in result:
            raise ValueError('Unknown or duplicate patient identity')
        _digest(record.get('recording_sha256'), 'recording_sha256')
        times = _vector(record.get('times_s'), 'times_s')
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError('Times must be strictly increasing')
        result[patient] = record
    return result


def public_support(reference):
    """Return the exact prescribed support, excluding manual/author values.

    Operators must first recover and independently authenticate the original
    support and freeze its recipe. Presence of a digest is not authentication.
    """
    records = _records(reference, REFERENCE_SCHEMA)
    _digest(reference.get('alignment_recipe_sha256'), 'alignment_recipe_sha256')
    _digest(reference.get('author_execution_sha256'), 'author_execution_sha256')
    return {
        'schema': 'dredge-manual-support/v1', 'task_id': TASK_ID,
        'alignment_recipe_sha256': reference['alignment_recipe_sha256'],
        'records': [{
            'patient': patient,
            'recording_sha256': records[patient]['recording_sha256'],
            'times_s': list(_vector(records[patient]['times_s'], 'times_s')),
        } for patient in PATIENTS],
    }


def support_sha256(reference):
    payload = json.dumps(public_support(reference), sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def score_packets(reference, candidate):
    """Return the ordered paired vector; there is no invented cohort scalar."""
    operator = _records(reference, REFERENCE_SCHEMA)
    submitted = _records(candidate, CANDIDATE_SCHEMA)
    support_digest = support_sha256(reference)
    if candidate.get('support_sha256') != support_digest:
        raise ValueError('Candidate is not bound to this frozen support')
    results = []
    for patient in PATIENTS:
        source, estimate = operator[patient], submitted[patient]
        if source['recording_sha256'] != estimate['recording_sha256']:
            raise ValueError(f'{patient}: recording identity differs')
        times = _vector(source['times_s'], 'times_s')
        if times != _vector(estimate['times_s'], 'times_s'):
            raise ValueError(f'{patient}: exact time support differs; automatic matching is prohibited')
        manual = _vector(source.get('manual_displacement_um'), 'manual trace')
        author = _vector(source.get('author_displacement_um'), 'author trace')
        proposed = _vector(estimate.get('displacement_um'), 'candidate trace')
        if not len(times) == len(manual) == len(author) == len(proposed):
            raise ValueError(f'{patient}: trace/time shape mismatch')
        author_r = pearson_r(manual, author)
        candidate_r = pearson_r(manual, proposed)
        results.append({
            'patient': patient, 'sample_count': len(times),
            'author_r': author_r, 'candidate_r': candidate_r,
            'delta_r': None if author_r is None or candidate_r is None else candidate_r - author_r,
        })
    return {
        'task_id': TASK_ID, 'metric': 'per_patient_manual_LFP_trace_Pearson_r',
        'support_sha256': support_digest,
        'alignment_recipe_sha256': reference['alignment_recipe_sha256'],
        'author_execution_sha256': reference['author_execution_sha256'],
        'patient_order': list(PATIENTS), 'patients': results,
        'interpretation': 'Conditional trace agreement on supplied operator alignment; no superiority decision.',
    }


def _unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _load(path):
    data = Path(path).read_bytes()
    return data, json.loads(data, object_pairs_hook=_unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--reference-sha256', required=True,
                        help='Externally frozen hash of the complete operator reference packet')
    args = parser.parse_args()
    if args.output.resolve() in {args.reference.resolve(), args.candidate.resolve()}:
        raise ValueError('Output must not overwrite an input packet')
    raw_reference, reference = _load(args.reference)
    expected = _digest(args.reference_sha256, 'reference-sha256')
    if hashlib.sha256(raw_reference).hexdigest() != expected:
        raise ValueError('Frozen operator reference packet hash mismatch')
    raw_candidate, candidate = _load(args.candidate)
    output = score_packets(reference, candidate)
    output['reference_packet_sha256'] = expected
    output['candidate_packet_sha256'] = hashlib.sha256(raw_candidate).hexdigest()
    with args.output.open('x') as handle:
        handle.write(json.dumps(output, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
