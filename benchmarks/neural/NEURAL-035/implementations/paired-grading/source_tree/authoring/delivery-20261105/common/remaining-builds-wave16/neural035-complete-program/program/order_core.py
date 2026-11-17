"""NEURAL035 peak-order metrics. Pure scalar operations, no files or model fits."""
import math


def need(ok, why):
    if not ok:
        raise ValueError(why)


def ranks(values):
    """Average zero-based ranks, normalized by n-1; one/all-tied value is0.5."""
    n = len(values)
    need(n >= 1 and all(type(x) in (int, float) and math.isfinite(x) for x in values),
         'finite scalar rank vector')
    if n == 1:
        return [0.5]
    ordered = sorted(range(n), key=lambda i: values[i])
    result = [0.0] * n
    start = 0
    while start < n:
        stop = start + 1
        while stop < n and values[ordered[stop]] == values[ordered[start]]:
            stop += 1
        mid = (start + stop - 1) / (2.0 * (n - 1))
        for i in ordered[start:stop]:
            result[i] = mid
        start = stop
    return result


def error(scores, peaks, active):
    need(len(scores) == len(peaks) == len(active), 'complete same-cell vector')
    chosen = [i for i, yes in enumerate(active) if yes]
    if len(chosen) < 2:
        return None
    # Reranking on target-active cells prevents a query-flat cell from changing
    # any scored cell's rank. Every cell is nevertheless required in submission.
    predicted = ranks([scores[i] for i in chosen])
    target = ranks([peaks[i] for i in chosen])
    return math.fsum(abs(a - b) for a, b in zip(predicted, target)) / len(chosen)


def baseline(calibration_peaks, calibration_active):
    need(len(calibration_peaks) == len(calibration_active) == 5, 'all5public blocks')
    n = len(calibration_peaks[0]); total = [0.0] * n
    for values, active in zip(calibration_peaks, calibration_active):
        need(len(values) == len(active) == n, 'same calibration cell inventory')
        chosen = [i for i, yes in enumerate(active) if yes]
        block = [0.5] * n
        if len(chosen) >= 2:
            for i, value in zip(chosen, ranks([values[i] for i in chosen])):
                block[i] = value
        for i, value in enumerate(block):
            total[i] += value / 5.0
    return total


def validate_submission(doc, public):
    need(type(doc) is dict and set(doc) == {'schema', 'predictions'}
         and doc['schema'] == 'neural035-order-predictions-v1', 'exact output schema')
    expected = {q['query_id']: len(s['cell_ids']) for s in public['sessions'] for q in s['queries']}
    need(len(expected) == 28 and type(doc['predictions']) is list
         and len(doc['predictions']) == 28, 'all28 original queryblocks')
    answer = {}
    for row in doc['predictions']:
        need(type(row) is dict and set(row) == {'query_id', 'ordering_scores'}, 'exact query record')
        key = row['query_id']
        need(type(key) is str and key in expected and key not in answer, 'known unique query')
        values = row['ordering_scores']
        need(type(values) is list and len(values) == expected[key]
             and all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in values),
             'finite nonboolean score for every public cell')
        answer[key] = values
    return answer


def validate_targets(target, public):
    need(type(target) is dict and set(target) == {'schema', 'sessions'}
         and target['schema'] == 'neural035-private-targets-v1'
         and type(target['sessions']) is list and len(target['sessions']) == 14,
         'complete private cohort')
    for row, manifest in zip(target['sessions'], public['sessions'], strict=True):
        need(set(row) == {'session_id', 'mouse', 'context', 'calibration_peaks',
                         'calibration_active', 'queries'}
             and row['session_id'] == manifest['session_id']
             and type(row['mouse']) is str and row['context'] in ('cxta', 'cxtb'), 'exact private session')
        n = len(manifest['cell_ids'])
        def vector(values, mask=False):
            need(type(values) is list and len(values) == n and all(
                type(x) is bool if mask else type(x) is int and 0 <= x < 300 for x in values),
                'exact peak or activity vector')
        need(len(row['calibration_peaks']) == len(row['calibration_active']) == 5, '5public calibration targets')
        for x in row['calibration_peaks']:
            vector(x)
        for x in row['calibration_active']:
            vector(x, True)
        need(type(row['queries']) is list and len(row['queries']) == 2, 'all2query blocks')
        for q, expected in zip(row['queries'], manifest['queries'], strict=True):
            need(set(q) == {'query_id', 'peaks', 'active', 'surrogate_peaks'}
                 and q['query_id'] == expected['query_id'], 'exact private query identity')
            vector(q['peaks']); vector(q['active'], True)
            need(type(q['surrogate_peaks']) is list and len(q['surrogate_peaks']) == 99, 'all99phase draws')
            for x in q['surrogate_peaks']:
                vector(x)
    mice = sorted({s['mouse'] for s in target['sessions']})
    need(len(mice) == 7 and all(sorted(s['context'] for s in target['sessions'] if s['mouse'] == m)
                              == ['cxta', 'cxtb'] for m in mice), '7paired mice, no subset')


def average(values):
    return None if any(x is None for x in values) else math.fsum(values) / len(values)


def grade(doc, public, private_loader):
    answer = validate_submission(doc, public)
    target = private_loader()  # All28 complete outputs validate first.
    validate_targets(target, public)
    sessions = []
    for row in target['sessions']:
        fixed = baseline(row['calibration_peaks'], row['calibration_active'])
        records = []
        for q in row['queries']:
            values = answer[q['query_id']]
            observed = error(values, q['peaks'], q['active'])
            control = average([error(values, peaks, q['active']) for peaks in q['surrogate_peaks']])
            base = error(fixed, q['peaks'], q['active'])
            records.append({'query_id': q['query_id'], 'rank_mae': observed, 'baseline_rank_mae': base,
                'active_cells': sum(q['active']), 'flat_cells': len(q['active']) - sum(q['active']),
                'distinct_active_peak_times': len({v for v, a in zip(q['peaks'], q['active']) if a}),
                'surrogate_mean_rank_mae': control,
                'surrogate_mean_minus_observed': None if observed is None else control - observed,
                'candidate_minus_baseline': None if observed is None else observed - base})
        sessions.append({'session_id': row['session_id'], 'mouse': row['mouse'], 'context': row['context'],
            'queries': records, 'rank_mae': average([r['rank_mae'] for r in records]),
            'baseline_rank_mae': average([r['baseline_rank_mae'] for r in records]),
            'surrogate_mean_minus_observed': average([r['surrogate_mean_minus_observed'] for r in records])})
    mice = []
    for mouse in sorted({s['mouse'] for s in sessions}):
        by_context = {s['context']: s for s in sessions if s['mouse'] == mouse}
        a, b = (by_context[k]['rank_mae'] for k in ('cxta', 'cxtb'))
        mice.append({'mouse': mouse, 'rank_mae': average([a, b]),
            'baseline_rank_mae': average([s['baseline_rank_mae'] for s in by_context.values()]),
            'context_A_minus_B': None if a is None or b is None else a - b,
            'surrogate_mean_minus_observed': average([s['surrogate_mean_minus_observed'] for s in by_context.values()])})
    return {'schema': 'neural035-grade-v1', 'primary_rank_mae': average([m['rank_mae'] for m in mice]),
        'baseline_rank_mae': average([m['baseline_rank_mae'] for m in mice]),
        'paired_context_A_minus_B': average([m['context_A_minus_B'] for m in mice]),
        'surrogate_mean_minus_observed': average([m['surrogate_mean_minus_observed'] for m in mice]),
        'sessions': sessions, 'mice': mice, 'required_sessions': 14, 'required_mice': 7,
        'required_queryblocks': 28, 'no_undefined_unit_dropped': True,
        'scientific_success_threshold': None, 'p_value_computed': False,
        'causal_claim': False, 'source_selected_event_claim': False}
