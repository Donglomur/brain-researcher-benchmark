"""Compare the two NEURAL-060 workflows on a complete protected score.

This target-free readback does not execute, qualify or replace protected grading.
It preserves the scorer's equal-mouse primary and separate authoring replications.
"""
import argparse
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import math
import os
from pathlib import Path
import stat


MODES = ('frozen_program', 'case_adaptive_equal_inputs_tools_compute')
REPLICATES = ('replicate-01', 'replicate-02', 'replicate-03')
ARMS = ('nuisance', 'joint', 'joint_test_shift10')
FAMILIES = ('linear', 'trees', 'fourier')
METRICS = ('mse', 'mae')
MAX_SCORE_BYTES = 16 * 1024 * 1024
ROSTER_PIN = {'bytes': 17391, 'sha256': 'c62ba1c5161287d1915d7dd49165be79ca93632dee686be0ea29f0929c1791cf'}
TOP_FIELDS = {'schema', 'metrics', 'descriptive_contrasts', 'primary',
              'ranking_metric', 'mice', 'sessions', 'labs',
              'qualified_neural_contribution', 'eligible_for_contribution_ranking',
              'reference_competence_qualified', 'causal_or_native_understanding_claim',
              'uncertainty', 'selected_reference_interpretation'}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def exact(value, fields, reason):
    need(type(value) is dict and set(value) == set(fields), reason)


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def number(value, *, nonnegative=False):
    """Read numbers already serialized by the 80-digit protected scorer."""
    need(type(value) in (int, float, str), 'ordinary numeric score value')
    if type(value) is float:
        need(math.isfinite(value), 'finite score value')
    if type(value) is str:
        need(0 < len(value) <= 2048 and value.strip() == value,
             'bounded decimal score string')
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('decimal score value') from error
    need(result.is_finite(), 'finite decimal score value')
    # The protected scorer starts with binary64 values, squares their differences
    # and computes finite means. This generous bound rejects exponent bombs.
    need(result.is_zero() or -1000 <= result.adjusted() <= 1000,
         'score outside finite binary64-derived metric range')
    if nonnegative:
        need(result >= 0, 'nonnegative loss')
    return result


def loss_pair(value):
    exact(value, METRICS, 'exact MSE/MAE pair')
    return {key: number(value[key], nonnegative=True) for key in METRICS}


def identity_map(value, count, reason):
    need(type(value) is dict and len(value) == count
         and all(type(key) is str and key for key in value), reason)
    return set(value)


def prefixes():
    return ([f'candidate/{mode}/{replicate}' for mode in MODES for replicate in REPLICATES]
            + [f'reference/{family}' for family in FAMILIES] + ['reference_selected'])


def roster(raw):
    need({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} == ROSTER_PIN,
         'original public roster identity')
    value = json.loads(raw, object_pairs_hook=pairs)
    result = {row['eid']: {'animal_id': row['subject'], 'lab_id': row['lab']} for row in value['assets']}
    need(len(result) == 29 and len({row['animal_id'] for row in result.values()}) == 13
         and len({row['lab_id'] for row in result.values()}) == 7, 'original roster population')
    return result


def serialization_error(value):
    """Bound the unknown pre-serialization value by binary64 rounding bins.

    Include the difference between the shortest JSON decimal and its binary64
    value. Nonzero overflow/underflow decimal strings are not float-rounded.
    """
    binary = float(value)
    if not math.isfinite(binary) or binary == 0:
        return Decimal(0)
    center = Decimal.from_float(binary)
    before, after = math.nextafter(binary, -math.inf), math.nextafter(binary, math.inf)
    # At maximum finite magnitude, extend the finite-side spacing to the
    # overflow midpoint instead of introducing an infinite error bound.
    lower = Decimal.from_float(before) if math.isfinite(before) else center - (Decimal.from_float(after) - center)
    upper = Decimal.from_float(after) if math.isfinite(after) else center + (center - Decimal.from_float(before))
    return max(abs(value - (lower + center) / 2), abs(value - (center + upper) / 2))


def consistent(actual, expected, inputs, *, mean=False):
    # Propagate representable-value rounding bins; this remains meaningful for
    # subnormal MSEs, where a relative-only tolerance is invalid. The tiny final
    # term covers the retained scorer's 80-digit decimal arithmetic rounding.
    error = sum((serialization_error(value) for value in inputs), Decimal(0))
    if mean:
        error /= len(inputs)
    magnitude = max(abs(actual), abs(expected), *(abs(value) for value in inputs))
    error += serialization_error(actual) + magnitude * Decimal('1e-78')
    need(abs(actual - expected) <= error,
         'serialized metric aggregation or contrast mismatch')


def admit(score, hierarchy):
    """Require all panels, biological identities and existing nonqualification."""
    exact(score, TOP_FIELDS, 'exact full protected score schema')
    need(score['schema'] == 'neural060_full_score_v1'
         and score['ranking_metric'] == 'joint_equal_mouse_mse_lower_is_better',
         'original task and primary metric')
    need(all(type(score[key]) is int and score[key] == count
             for key, count in (('mice', 13), ('sessions', 29), ('labs', 7))),
         'complete 29-session/13-mouse/7-lab population')
    need(score['qualified_neural_contribution'] is None
         and score['eligible_for_contribution_ranking'] is False
         and score['reference_competence_qualified'] is False
         and score['causal_or_native_understanding_claim'] is False,
         'preserve current protected scorer nonqualification')
    need(type(score['uncertainty']) is str and score['uncertainty']
         and type(score['selected_reference_interpretation']) is str
         and score['selected_reference_interpretation'], 'retain source limitations')
    expected = [prefix + '/' + arm for prefix in prefixes() for arm in ARMS]
    exact(score['metrics'], expected, 'all 30 candidate/reference metric panels')
    identities = {'sessions': set(hierarchy),
                  'animals': {row['animal_id'] for row in hierarchy.values()},
                  'labs': {row['lab_id'] for row in hierarchy.values()}}
    parsed = {}
    for key in expected:
        panel = score['metrics'][key]
        exact(panel, ('overall', 'sessions', 'animals', 'labs'), 'complete metric hierarchy')
        current = {level: identity_map(panel[level], count, 'complete ' + level + ' identities')
                   for level, count in (('sessions', 29), ('animals', 13), ('labs', 7))}
        need(current == identities, 'same original biological identities in every panel')
        parsed[key] = {'overall': loss_pair(panel['overall'])}
        for level in current:
            parsed[key][level] = {ident: loss_pair(row) for ident, row in panel[level].items()}
    with localcontext() as context:
        context.prec = 80
        def mean(values):
            return sum(values, Decimal(0)) / len(values)
        for panel in parsed.values():
            for metric in METRICS:
                for animal in identities['animals']:
                    inputs = [panel['sessions'][session][metric] for session, row in hierarchy.items()
                              if row['animal_id'] == animal]
                    consistent(panel['animals'][animal][metric], mean(inputs), inputs, mean=True)
                for lab in identities['labs']:
                    animals = {row['animal_id'] for row in hierarchy.values() if row['lab_id'] == lab}
                    inputs = [panel['animals'][animal][metric] for animal in animals]
                    consistent(panel['labs'][lab][metric], mean(inputs), inputs, mean=True)
                inputs = [row[metric] for row in panel['animals'].values()]
                consistent(panel['overall'][metric], mean(inputs), inputs, mean=True)
    exact(score['primary'], [mode + '/' + rep for mode in MODES for rep in REPLICATES],
          'all six original primary values')
    for mode in MODES:
        for rep in REPLICATES:
            key = mode + '/' + rep
            need(number(score['primary'][key], nonnegative=True)
                 == parsed['candidate/' + key + '/joint']['overall']['mse'],
                 'primary joins its original joint equal-mouse MSE')
    # These controls are not reinterpreted as workflow effects. Requiring them
    # prevents a convenient joint-only or successful-only excerpt being accepted.
    exact(score['descriptive_contrasts'], prefixes(), 'all original arm contrasts')
    for prefix, row in score['descriptive_contrasts'].items():
        fields = ('nuisance_minus_joint_mse', 'shift_minus_joint_mse')
        exact(row, (*fields, 'animal_pairs'), 'complete original arm contrast')
        for field in fields:
            number(row[field])
        exact(row['animal_pairs'], identities['animals'], 'all 13 original animal pairs')
        for pair in row['animal_pairs'].values():
            exact(pair, fields, 'original paired arm contrast fields')
            for field in fields:
                number(pair[field])
        with localcontext() as context:
            context.prec = 80
            for field, arm in zip(fields, ('nuisance', 'joint_test_shift10')):
                left, joint = parsed[prefix + '/' + arm], parsed[prefix + '/joint']
                a, b = left['overall']['mse'], joint['overall']['mse']
                consistent(number(row[field]), a - b, [a, b])
                for animal in identities['animals']:
                    a, b = left['animals'][animal]['mse'], joint['animals'][animal]['mse']
                    consistent(number(row['animal_pairs'][animal][field]), a - b, [a, b])
    return parsed


def render(value):
    if isinstance(value, Decimal):
        result = float(value)
        return result if math.isfinite(result) and (result != 0 or value == 0) else str(value)
    if type(value) is dict:
        return {key: render(item) for key, item in value.items()}
    return value


def compare(score, hierarchy):
    panels = admit(score, hierarchy)
    result = {}
    with localcontext() as context:
        context.prec = 80
        for rep in REPLICATES:
            frozen, adaptive = [panels[f'candidate/{mode}/{rep}/joint'] for mode in MODES]
            difference = lambda left, right: {metric: left[metric] - right[metric] for metric in METRICS}
            result[rep] = {
                'joint_primary_mse': {MODES[0]: frozen['overall']['mse'],
                                      MODES[1]: adaptive['overall']['mse']},
                'frozen_minus_adaptive': {
                    'overall': difference(frozen['overall'], adaptive['overall']),
                    **{level: {ident: difference(frozen[level][ident], adaptive[level][ident])
                               for ident in sorted(frozen[level])}
                       for level in ('animals', 'sessions', 'labs')},
                },
            }
    return render({
        'schema': 'neural060_workflow_comparison_v1',
        'task_id': 'NEURAL-060', 'replications': result,
        'public_roster': ROSTER_PIN,
        'aggregation_check': 'Original public hierarchy; propagated binary64 rounding bins and 80-digit decimal arithmetic bound',
        'difference_direction': 'frozen minus adaptive loss; positive favors adaptive',
        'primary_metric': 'joint_equal_mouse_mse_lower_is_better',
        'population': {'sessions': 29, 'mice': 13, 'labs': 7},
        'arithmetic': '80-digit decimal differences of serialized protected metrics; no reweighting or refitting',
        'uncertainty': 'Three separate authored replications; not 39 independent animals. No interval or inferential decision.',
        'source_uncertainty': score['uncertainty'],
        'source_reference_interpretation': score['selected_reference_interpretation'],
        'qualification': {
            'protected_grade_provenance_independently_verified': False,
            'matched_execution_budgets_independently_verified': False,
            'qualified_neural_contribution': None,
            'eligible_for_contribution_ranking': False,
            'reference_competence_qualified': False,
            'causal_or_native_understanding_claim': False,
        },
    })


def capture(path, byte_count, sha256):
    need(type(byte_count) is int and 0 < byte_count <= MAX_SCORE_BYTES, 'bounded expected score size')
    need(type(sha256) is str and len(sha256) == 64
         and all(char in '0123456789abcdef' for char in sha256), 'lowercase SHA256 identity')
    path = Path(path)
    for parent in path.absolute().parents:
        need(stat.S_ISDIR(os.lstat(parent).st_mode), 'ordinary score directory ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == byte_count, 'exact ordinary score file')
        chunks, remaining = [], byte_count
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            need(chunk, 'complete score read')
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b''.join(chunks)
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(not os.read(fd, 1) and signature(before) == signature(os.fstat(fd))
             and signature(before) == signature(os.lstat(path)), 'stable score capture')
        need(hashlib.sha256(raw).hexdigest() == sha256, 'score identity mismatch')
    finally:
        os.close(fd)
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--score', required=True)
    parser.add_argument('--roster', required=True, help='original public REQUIRED_SOURCES.json')
    parser.add_argument('--score-bytes', required=True, type=int)
    parser.add_argument('--score-sha256', required=True)
    args = parser.parse_args(argv)
    raw = capture(args.score, args.score_bytes, args.score_sha256)
    def invalid_constant(_):
        raise ValueError('nonfinite JSON constant')
    score = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    source_hierarchy = roster(capture(args.roster, ROSTER_PIN['bytes'], ROSTER_PIN['sha256']))
    result = compare(score, source_hierarchy)
    result['source_score'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return result


if __name__ == '__main__':
    main()
