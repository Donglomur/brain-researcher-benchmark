"""Stable paired finite-panel loss arithmetic; no candidate execution."""
import math
import numpy as np


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pair_difference(cue, neural, truth, conditions, contexts):
    # Independently derive paired losses; do not infer increment from a report.
    rows = [abs(float(a) - float(y)) - abs(float(b) - float(y))
            for a, b, y in zip(cue, neural, truth, strict=True)]
    need(all(math.isfinite(v) for v in rows), 'Finite derived paired losses')
    def mean(values):
        values = list(values); value = math.fsum(x / len(values) for x in values)
        need(math.isfinite(value), 'Finite paired mean; no clipping'); return value
    result = {'cue_minus_neural_mae_ms': mean(rows),
            'by_condition': {str(k): {'n': int(np.sum(conditions == k)),
                'cue_minus_neural_mae_ms': mean(v for v, g in zip(rows, conditions) if g == k)} for k in range(40)},
            'by_context': {str(k): {'n': int(np.sum(contexts == k)),
                'cue_minus_neural_mae_ms': mean(v for v, g in zip(rows, contexts) if g == k)} for k in range(8)},
            'sign': 'positive means neural arm lower absolute error on this finite panel',
            'scientific_pass_floor': None, 'matched_method_proven': False,
            'RL_or_neural_understanding_reward': False}
    result['cue_minus_neural_eight_context_macro_mae_ms'] = mean(
        row['cue_minus_neural_mae_ms'] for row in result['by_context'].values())
    return result


def verify_paired_arithmetic(paired, cue_score, neural_score):
    """Check aggregate consistency without destroying a small paired increment.

    A subtraction of separately rounded large MAEs can lose a representable
    per-trial increment. The stable paired mean remains the reported metric.
    The 64-ULP envelope is a conservative arithmetic guard at the absolute-arm
    scale, not a scientific success threshold; no prediction/value is changed.
    """
    checks = []
    def compare(name, paired_value, cue_value, neural_value):
        direct = cue_value - neural_value
        need(all(math.isfinite(v) for v in (paired_value, cue_value, neural_value, direct)),
             'Finite derived arithmetic before consistency check')
        bound = 1e-10 + 64 * max(math.ulp(v) for v in (paired_value, cue_value, neural_value, direct))
        need(abs(paired_value - direct) <= bound, 'Independent paired arithmetic outside roundoff envelope')
        checks.append({'metric': name, 'aggregate_subtraction_ms': direct,
                       'absolute_difference_ms': abs(paired_value - direct), 'roundoff_bound_ms': bound})
    compare('mae_ms', paired['cue_minus_neural_mae_ms'], cue_score['mae_ms'], neural_score['mae_ms'])
    for group in ('by_condition', 'by_context'):
        for key, row in paired[group].items():
            cue, neural = cue_score[group][key], neural_score[group][key]
            need(row['n'] == cue['n'] == neural['n'], 'Same group support for paired arithmetic')
            compare(group + '/' + key, row['cue_minus_neural_mae_ms'], cue['mae_ms'], neural['mae_ms'])
    compare('eight_context_macro_mae_ms', paired['cue_minus_neural_eight_context_macro_mae_ms'],
            cue_score['eight_context_macro_mae_ms'], neural_score['eight_context_macro_mae_ms'])
    return checks
