"""NEURAL-088 current count endpoint. Operator-only; no fitting or source I/O.

Near-saturated deviance uses the reviewed historical precision successor's
series. This version implements the current, explicitly revised endpoint;
it must never replace historical numerical results or historical grading.
"""
import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

VIEWS = ('anatomy', 'anatomy_plus_in_vivo')
MAX_ROWS = 232985


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite_number(value, *, positive=False):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        return False


def label(value):
    return (type(value) is str and 0 < len(value) <= 128 and value.isascii()
            and all(32 < ord(c) < 127 for c in value))


def validate_roster(rows):
    """Operator-only identities; endpoint IDs must never be predictors."""
    require(type(rows) is list and 0 < len(rows) <= MAX_ROWS, 'Nonempty bounded frozen roster required')
    identities, pairs = set(), set()
    for row in rows:
        require(type(row) is dict and set(row) == {
            'edge_id', 'pre_id', 'post_id', 'projection', 'sampling_weight'}, 'Exact roster fields required')
        require(label(row['edge_id']) and label(row['projection']), 'Invalid roster labels')
        require(all(type(row[k]) is int and -(2**63) <= row[k] < 2**63
                    for k in ('pre_id', 'post_id')), 'Signed-int64 endpoint identities required')
        pair = row['pre_id'], row['post_id']
        require(pair[0] != pair[1] and pair not in pairs and row['edge_id'] not in identities,
                'Self-pairs, duplicate edges and duplicate directed pairs are forbidden')
        require(finite_number(row['sampling_weight'], positive=True), 'Positive finite frozen sampling weights required')
        identities.add(row['edge_id'])
        pairs.add(pair)
    return rows


def align_views(rows, views):
    require(type(views) is dict and set(views) == set(VIEWS), 'Both and only the frozen paired views required')
    required = {r['edge_id'] for r in rows}
    aligned = {}
    for view in VIEWS:
        values = views[view]
        require(type(values) is list and len(values) == len(rows), 'Complete paired prediction support required')
        mapped = {}
        for item in values:
            require(type(item) is dict and set(item) == {'edge_id', 'mean'}, 'Exact prediction fields required')
            key = item['edge_id']
            require(label(key) and key in required and key not in mapped, 'Unique exact query edge IDs required')
            require(finite_number(item['mean']), 'Finite nonnegative predicted counts required')
            mapped[key] = float(item['mean'])
        aligned[view] = [mapped[r['edge_id']] for r in rows]
    return aligned


def align_counts(rows, counts):
    require(type(counts) is list and len(counts) == len(rows), 'Complete private target support required')
    mapped = {}
    for item in counts:
        require(type(item) is dict and set(item) == {'edge_id', 'count'}, 'Exact private target fields required')
        key, count = item['edge_id'], item['count']
        require(label(key) and key not in mapped, 'Unique private target edge IDs required')
        require(type(count) is int and 0 <= count <= 2**53, 'Exactly represented integer counts required')
        mapped[key] = count
    require(set(mapped) == {r['edge_id'] for r in rows}, 'Exact private/public identity equality required')
    return [mapped[r['edge_id']] for r in rows]


def poisson_deviance(count, mean, rate_floor):
    """D(y, max(mu, floor)); floor is frozen by the operator, never a candidate."""
    require(type(count) is int and 0 <= count <= 2**53, 'Invalid count')
    require(finite_number(mean) and finite_number(rate_floor, positive=True), 'Invalid count mean or frozen floor')
    mean = max(float(mean), float(rate_floor))
    if count == 0:
        return 2.0 * mean
    if mean == count:
        return 0.0
    relative = (mean - count) / count
    if abs(relative) < .125:
        # Historical precision repair: avoid cancellation in r - log1p(r).
        value = 2.0 * count * math.fsum((-relative)**n / n for n in range(2, 33))
    else:
        value = 2.0 * (mean - count + count * (math.log(count) - math.log(mean)))
    require(not math.isnan(value) and value >= 0, 'Unsupported deviance arithmetic')
    return value


def weighted_mean(values, weights):
    """Positive-weight reduction without binary64 intermediate overflow.

    Decimal accumulation also avoids losing a small weight before multiplying
    by a large value. Nonfinite per-edge losses remain explicitly unscorable.
    """
    require(len(values) == len(weights) and len(values) > 0, 'Invalid reduction support')
    if not all(math.isfinite(v) for v in values):
        return None
    with localcontext() as ctx:
        ctx.prec = 80
        ws = [Decimal(w) for w in weights]
        result = sum((Decimal(v) * w for v, w in zip(values, ws)), Decimal(0)) / sum(ws)
        value = float(result)
    return value if math.isfinite(value) else None


def _arm(rows, counts, means, rate_floor):
    groups = {}
    for i, row in enumerate(rows):
        groups.setdefault(row['pre_id'], []).append(i)
    losses = [poisson_deviance(y, mu, rate_floor) for y, mu in zip(counts, means)]
    errors = [abs(y - mu) for y, mu in zip(counts, means)]
    per_pre = []
    for pre_id, indices in sorted(groups.items()):
        weights = [rows[i]['sampling_weight'] for i in indices]
        per_pre.append({'pre_id': pre_id, 'edge_n': len(indices),
                        'deviance': weighted_mean([losses[i] for i in indices], weights),
                        'mean_absolute_count_error': weighted_mean([errors[i] for i in indices], weights)})
    def equal_mean(key):
        values = [p[key] for p in per_pre]
        return None if None in values else weighted_mean(values, [1] * len(values))
    return {'equal_presynaptic_deviance': equal_mean('deviance'),
            'equal_presynaptic_mean_absolute_count_error': equal_mean('mean_absolute_count_error'),
            'floored_predictions': sum(mu < rate_floor for mu in means),
            'unsupported_arithmetic_edges': sum(not math.isfinite(v) for v in losses),
            'per_presynaptic': per_pre}


def _contrast(left, right):
    # Both arms always have identical sorted presynaptic membership.
    gains = [a['deviance'] - b['deviance'] if a['deviance'] is not None and b['deviance'] is not None else None
             for a, b in zip(left['per_presynaptic'], right['per_presynaptic'])]
    # Signed contrasts can cancel across neurons. A fixed-precision Decimal sum
    # can discard a small gain before a later large opposite gain cancels.
    # Sum the already-computed binary64 gains exactly, then round only the mean.
    mean = None if None in gains else float(sum((Fraction(gain) for gain in gains), Fraction()) / len(gains))
    return {'equal_presynaptic_loss_difference': mean,
            'per_presynaptic': [{'pre_id': row['pre_id'], 'loss_difference': gain}
                                for row, gain in zip(left['per_presynaptic'], gains)]}


def grade(rows, candidate_views, fixed_reference_views, load_private_counts, *, rate_floor):
    """Validate complete candidates before invoking the operator's private loader.

    Independent reference predictions are supplied separately by the operator.
    Their independence, freeze timing, source eligibility and empirical mapping
    require provenance review; arithmetic cannot establish these facts.
    """
    validate_roster(rows)
    require(finite_number(rate_floor, positive=True), 'Freeze a positive finite rate floor')
    references = align_views(rows, fixed_reference_views)  # Operator errors raise.
    try:
        candidate = align_views(rows, candidate_views)
    except (ValueError, TypeError, OverflowError) as exc:
        return {'status': 'invalid_submission', 'reason': str(exc), 'private_callback_invocations': 0, 'primary': None}
    counts = align_counts(rows, load_private_counts())
    arms = {role: {view: _arm(rows, counts, values, rate_floor) for view, values in paired.items()}
            for role, paired in (('candidate', candidate), ('fixed_reference', references))}
    joint = arms['candidate']['anatomy_plus_in_vivo']['equal_presynaptic_deviance']
    unsupported = any(arm['unsupported_arithmetic_edges'] for paired in arms.values() for arm in paired.values())
    return {
        'status': 'valid_unscorable_arithmetic' if unsupported else 'scored',
        'endpoint_version': 'NEURAL-088/count-endpoint-v2', 'private_callback_invocations': 1,
        'rate_floor': float(rate_floor), 'edge_n': len(rows),
        'unique_presynaptic_n': len({r['pre_id'] for r in rows}),
        'primary': {'name': 'equal_presynaptic_joint_view_poisson_deviance', 'direction': 'lower', 'value': None if unsupported else joint},
        'fixed_reference_anatomy_minus_joint': _contrast(arms['fixed_reference']['anatomy'], arms['fixed_reference']['anatomy_plus_in_vivo']),
        'fixed_reference_joint_minus_candidate_joint': _contrast(arms['fixed_reference']['anatomy_plus_in_vivo'], arms['candidate']['anatomy_plus_in_vivo']),
        'candidate_self_contrast_descriptive_only': _contrast(arms['candidate']['anatomy'], arms['candidate']['anatomy_plus_in_vivo']),
        'arms': arms,
        'scope': 'Unqualified arithmetic on supplied roster; one-mouse descriptive endpoint, no animal-population or causal inference.'}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result


def read_json(path):
    require(Path(path).stat().st_size <= 64 * 1024 * 1024, 'JSON input exceeds bounded interface')
    def invalid_constant(_):
        raise ValueError('Nonfinite JSON constants forbidden')
    return json.loads(Path(path).read_text(), object_pairs_hook=_pairs, parse_constant=invalid_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', required=True, help='Operator JSON: rows, rate_floor, fixed_reference_views')
    parser.add_argument('--candidate', required=True, help='Paired candidate views, opaque edge IDs only')
    parser.add_argument('--targets', required=True, help='Operator-only target JSON; read after candidate validation')
    parser.add_argument('--output', required=True, help='Operator-only report path outside public delivery')
    args = parser.parse_args()
    protocol = read_json(args.protocol)
    require(type(protocol) is dict and set(protocol) == {'rows', 'rate_floor', 'fixed_reference_views'}, 'Exact protocol fields required')
    report = grade(protocol['rows'], read_json(args.candidate), protocol['fixed_reference_views'],
                   lambda: read_json(args.targets), rate_floor=protocol['rate_floor'])
    report['protocol_sha256'] = hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    return 0 if report['status'] == 'scored' else 2


if __name__ == '__main__':
    raise SystemExit(main())
