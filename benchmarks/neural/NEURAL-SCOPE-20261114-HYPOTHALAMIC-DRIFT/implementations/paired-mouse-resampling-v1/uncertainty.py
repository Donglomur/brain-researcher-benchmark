"""Paired mouse-resampling diagnostic conditional on frozen scored forecasts.

This is not a confidence procedure for the fitted learning algorithm. It does
not refit overlapping cross-validation folds or establish source qualification.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random


SCORER_SHA256 = 'd593735fec77f50e826636e988d8e0ec19253d1807a629f25ff7549a7a8257d8'
SCORER_PATH = Path(__file__).resolve().parent.parent / 'fixed-origin-forecast' / 'scorer.py'
_scorer_source = SCORER_PATH.read_bytes()
if hashlib.sha256(_scorer_source).hexdigest() != SCORER_SHA256:
    raise RuntimeError('fixed-origin scorer source mismatch')
_spec = importlib.util.spec_from_file_location('hypodrift_uncertainty_scorer', SCORER_PATH)
s = importlib.util.module_from_spec(_spec)
# Execute the authenticated snapshot, without reopening the path or using bytecode.
exec(compile(_scorer_source, str(SCORER_PATH), 'exec'), s.__dict__)

SUMMARY_FIELDS = ['primary_defined', 'undefined_reason', 'candidate_mse',
                  'reference_mse', 'paired_loss_reduction', 'groups', 'mice']
MOUSE_FIELDS = ['mouse_id', 'group', 'eligible_neuron_denominator',
                'candidate_mse', 'reference_mse', 'paired_loss_reduction']
GROUP_FIELDS = ['group', 'eligible_mouse_denominator', 'candidate_mse',
                'reference_mse', 'paired_loss_reduction']


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def _loss_pair(row, count, where):
    fields = ['candidate_mse', 'reference_mse', 'paired_loss_reduction']
    if count == 0:
        s.require(all(row[k] is None for k in fields), where + ': absent loss is null')
        return None
    candidate, reference, delta = [s.number(row[k], where + ' ' + k) for k in fields]
    s.require(candidate >= 0 and reference >= 0, where + ': nonnegative losses')
    s.require(delta == reference - candidate, where + ': exact paired loss reduction')
    return candidate, reference


def admit_summary(report):
    """Check the required numerical projection; not all cell/source evidence.

    An operator must supply an authenticated report from the pinned scorer. This
    check independently recomputes the aggregation from its mouse summaries.
    """
    s.require(type(report) is dict and report.get('schema') == 'hypodrift-score-v1'
              and report.get('task_id') == s.TASK_ID, 'score report schema/task')
    s.require(all(k in report for k in SUMMARY_FIELDS), 'complete score summary')
    s.require(type(report.get('origin_after_session')) is int
              and report['origin_after_session'] == 9, 'fixed origin nine')
    s.require(report.get('loss_units') == 'squared log1p(events/minute)', 'loss units')
    s.require(type(report['primary_defined']) is bool, 'primary_defined is Boolean')
    s.sequence(report['mice'], 31, 'all 31 mouse summaries')
    mice, by_mouse, grouped, ineligible = {}, {}, {g: [] for g in s.GROUPS}, []
    neuron_totals = {g: 0 for g in s.GROUPS}
    for row in report['mice']:
        s.exact(row, MOUSE_FIELDS, 'mouse summary')
        mid = s.identity(row['mouse_id'])
        group = row['group']
        s.require(type(group) is str and group in s.GROUPS, 'declared biological group')
        s.require(mid not in mice, 'unique mouse identity')
        count = row['eligible_neuron_denominator']
        s.require(type(count) is int and 0 <= count <= s.GROUPS[group][1],
                  'bounded eligible-neuron denominator')
        pair = _loss_pair(row, count, 'mouse summary')
        mice[mid] = group
        by_mouse[mid] = {'candidate': [] if pair is None else [pair[0]],
                        'reference': [] if pair is None else [pair[1]]}
        grouped[group].append((mid, pair))
        neuron_totals[group] += count
        if pair is None:
            ineligible.append(mid)
    for group, (nmice, ncells) in s.GROUPS.items():
        s.require(len(grouped[group]) == nmice, 'complete declared group mouse support')
        s.require(neuron_totals[group] <= ncells, 'group eligible neurons exceed cohort')
        grouped[group].sort(key=lambda item: item[0])
    recomputed = s.aggregate(mice, by_mouse)
    for key in SUMMARY_FIELDS[:5]:
        value = report[key]
        if key in ['candidate_mse', 'reference_mse', 'paired_loss_reduction'] and value is not None:
            s.number(value, 'overall ' + key)
        s.require(value == recomputed[key], 'overall aggregation mismatch: ' + key)
    s.sequence(report['groups'], 5, 'all five group summaries')
    observed_groups = {}
    for row in report['groups']:
        s.exact(row, GROUP_FIELDS, 'group summary')
        group = row['group']
        s.require(type(group) is str and group in s.GROUPS
                  and group not in observed_groups, 'group summary identity')
        n = row['eligible_mouse_denominator']
        s.require(type(n) is int and 0 <= n <= s.GROUPS[group][0], 'eligible-mouse count')
        _loss_pair(row, n, 'group summary')
        observed_groups[group] = row
    for row in recomputed['groups']:
        s.require(observed_groups[row['group']] == row, 'group aggregation mismatch')
    projection = {'task_id': s.TASK_ID, 'scorer_sha256': SCORER_SHA256,
                  'mice': sorted(report['mice'], key=lambda row: row['mouse_id']),
                  'groups': [observed_groups[g] for g in s.GROUPS],
                  **{k: report[k] for k in SUMMARY_FIELDS[:5]}}
    return grouped, sorted(ineligible), projection


def nearest_rank(sorted_values, probability):
    """Empirical inverse CDF: order statistic ceil(n*p), with bounded endpoints."""
    return sorted_values[max(0, min(len(sorted_values) - 1,
                                    math.ceil(len(sorted_values) * probability) - 1))]


def _draw_paired_effect(grouped, rng):
    candidate_groups, reference_groups = [], []
    for group in s.GROUPS:
        rows = grouped[group]
        # One index selects BOTH losses; never resample the methods separately.
        pairs = [rows[rng.randrange(len(rows))][1] for _ in range(len(rows))]
        candidate_groups.append(s.mean([pair[0] for pair in pairs]))
        reference_groups.append(s.mean([pair[1] for pair in pairs]))
    return s.mean(reference_groups) - s.mean(candidate_groups)


def resample(report, *, seed, replicates=10000, interval_mass=0.95):
    """Return a descriptive percentile interval; never an improvement decision."""
    s.require(type(seed) is int and 0 <= seed < 2 ** 64, 'unsigned 64-bit seed')
    s.require(type(replicates) is int and 100 <= replicates <= 100000,
              'replicates must be an integer from 100 through 100000')
    interval_mass = s.number(interval_mass, 'interval mass')
    s.require(0 < interval_mass < 1, 'interval mass strictly between zero and one')
    grouped, ineligible, projection = admit_summary(report)
    out = {
        'schema': 'hypodrift-paired-mouse-resampling-v1', 'task_id': s.TASK_ID,
        'method': 'stratified_paired_mouse_percentile_diagnostic',
        'inference_scope': 'conditional_on_frozen_scored_forecasts_and_observed_masks',
        'interval_defined': not ineligible, 'unavailable_reason': None if not ineligible else
        'one_or_more_declared_mice_without_eligible_neural_targets',
        'ineligible_mouse_ids': ineligible, 'seed': seed,
        'replicates_requested': replicates, 'replicates_completed': 0,
        'interval_mass': interval_mass, 'interval': None,
        'quantile_rule': 'empirical_inverse_CDF_nearest_rank',
        'random_generator': 'Python random.Random MT19937 with randrange; same-interpreter reproducibility',
        'point_paired_loss_reduction': report['paired_loss_reduction'],
        'loss_units': 'squared log1p(events/minute)',
        'strata': [{'group': g, 'mice': n[0]} for g, n in s.GROUPS.items()],
        'mouse_summary_sha256': hashlib.sha256(canonical_bytes(projection)).hexdigest(),
        'scorer_sha256': SCORER_SHA256,
        'scientific_improvement_decision': None,
        'limits': [
            'Resamples already scored paired mouse losses within fixed biological groups; no cell or session pseudoreplication.',
            'No model refitting or propagation of training, selection, event extraction, registration or mask uncertainty.',
            'Overlapping leave-one-mouse-out training folds induce dependence this diagnostic does not model; nominal generalization coverage is not established.',
            'No missing mouse is dropped and no undefined replicate is retried; the interval is unavailable if any declared mouse has no eligible targets.',
            'A trusted report hash and numerical consistency are not biological/source authentication, blind access, model competence or benchmark qualification.',
            'Interval exclusion of zero is not by itself an improvement, causal, reproducibility or SOTA claim.'
        ]}
    if ineligible:
        return out
    rng = random.Random(seed)
    effects = sorted(_draw_paired_effect(grouped, rng) for _ in range(replicates))
    alpha = (1.0 - interval_mass) / 2.0
    out.update(replicates_completed=replicates,
               interval={'lower': nearest_rank(effects, alpha),
                         'upper': nearest_rank(effects, 1.0 - alpha)})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('score-report', 'score-report-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--seed', required=True, type=int)
    parser.add_argument('--replicates', type=int, default=10000)
    parser.add_argument('--interval-mass', type=float, default=0.95)
    args = parser.parse_args(argv)
    s.pin(args.score_report_sha256)
    report, report_hash = s.read_document(args.score_report, args.score_report_sha256)
    result = resample(report, seed=args.seed, replicates=args.replicates,
                      interval_mass=args.interval_mass)
    result['score_report_sha256'] = report_hash
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical_bytes(result))


if __name__ == '__main__':
    main()
