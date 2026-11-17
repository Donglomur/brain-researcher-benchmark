"""Target-private binary connectivity scorer; pure arithmetic, no model fitting."""
import math
from collections import defaultdict
from contract import MAX_QUERY, PROJECTIONS, VIEWS, int64, need


def roster(rows):
    need(type(rows) is list and 0 < len(rows) <= MAX_QUERY, 'Nonempty bounded complete query roster')
    seen, pairs = set(), set()
    for r in rows:
        need(type(r) is dict and set(r) == {'edge_id', 'pre_id', 'post_id', 'projection'}, 'Exact roster fields')
        key = r['edge_id']
        need(type(key) is str and key.startswith('e') and key[1:].isascii() and key[1:].isdigit()
             and 1 < len(key) <= 20 and str(int(key[1:])) == key[1:], 'Canonical bounded edge key')
        need(int64(r['pre_id']) and int64(r['post_id']) and r['pre_id'] != r['post_id'], 'Distinct int64 endpoints')
        need(r['projection'] in PROJECTIONS, 'Known area projection')
        pair = (r['pre_id'], r['post_id'])
        need(key not in seen and pair not in pairs, 'No duplicate edge identity or directed pair')
        seen.add(key); pairs.add(pair)
    return rows


def validate_submission(rows, submission):
    need(type(submission) is dict and set(submission) == {'schema_version', 'predictions'}
         and type(submission['schema_version']) is int and submission['schema_version'] == 1,
         'Exact prediction envelope/version')
    predictions = submission['predictions']
    need(type(predictions) is list and len(predictions) == len(rows), 'Every query prediction required')
    expected = {r['edge_id'] for r in rows}; seen = {}
    for r in predictions:
        need(type(r) is dict and set(r) == {'edge_id', 'probability'}, 'Exact probability row')
        key, p = r['edge_id'], r['probability']
        need(type(key) is str and key in expected and key not in seen, 'Exact unique query keys')
        need(type(p) in (float, int) and math.isfinite(p) and 0 <= p <= 1, 'Finite nonboolean probability in [0,1]')
        seen[key] = float(p)
    need(set(seen) == expected, 'Complete query support')
    return [seen[r['edge_id']] for r in rows]


def log_loss(y, p):
    need(type(y) is int and y in (0, 1), 'Binary integer outcome')
    if (y == 1 and p == 0) or (y == 0 and p == 1):
        return math.inf
    return -math.log(p) if y else -math.log1p(-p)


def mean(values):
    need(bool(values), 'Nonempty mean')
    return math.inf if math.inf in values else math.fsum(values) / len(values)


def encoded(v):
    if v is None:
        return {'value': None, 'status': 'undefined_infinity_difference'}
    if math.isinf(v):
        return {'value': None, 'status': 'positive_infinity' if v > 0 else 'negative_infinity'}
    return {'value': v, 'status': 'finite'}


def difference(left, right):
    return None if math.isinf(left) and math.isinf(right) else left - right


def average_precision(y, p):
    """Edge-weighted step-integral AP, complete score-tie groups enter together."""
    positives = sum(y)
    if not positives:
        return {'value': None, 'status': 'undefined_no_positive_targets'}
    order = sorted(range(len(y)), key=lambda i: -p[i])
    hit = seen = 0; terms = []; j = 0
    while j < len(order):
        k = j
        while k < len(order) and p[order[k]] == p[order[j]]:
            k += 1
        new = sum(y[order[i]] for i in range(j, k))
        hit += new; seen += k - j
        terms.append((new / positives) * (hit / seen)); j = k
    return {'value': math.fsum(terms), 'status': 'finite'}


def summaries(rows, y, p):
    groups = defaultdict(list)
    losses = [log_loss(a, b) for a, b in zip(y, p, strict=True)]
    brier = [(a - b)**2 for a, b in zip(y, p, strict=True)]
    for i, r in enumerate(rows):
        groups[r['pre_id']].append(i)
    per_pre = {g: mean([losses[i] for i in ix]) for g, ix in groups.items()}
    return {
        'equal_pre_log_loss': encoded(mean(list(per_pre.values()))),
        'edge_log_loss': encoded(mean(losses)),
        'equal_pre_brier': mean([mean([brier[i] for i in ix]) for ix in groups.values()]),
        'edge_average_precision': average_precision(y, p),
        'per_pre': [{'pre_id': g, 'pairs': len(groups[g]), 'log_loss': encoded(per_pre[g])}
                    for g in sorted(groups)],
    }, per_pre


def grade(rows, submissions, private_loader):
    """Exactly one private callback, only after BOTH full public submissions pass.

    Caller binds roster/source pins and keeps private loader unreachable to candidates.
    Callback returns exactly {'schema_version':1,'targets':[{'edge_id', 'connected'}]}.
    """
    roster(rows)
    need(type(submissions) is dict and set(submissions) == set(VIEWS), 'Both prespecified views required')
    aligned = {name: validate_submission(rows, submissions[name]) for name in VIEWS}
    target = private_loader()
    need(type(target) is dict and set(target) == {'schema_version', 'targets'}
         and type(target['schema_version']) is int and target['schema_version'] == 1, 'Exact private envelope')
    yy = target['targets']; need(type(yy) is list and len(yy) == len(rows), 'Complete private support')
    y = []
    for r, t in zip(rows, yy, strict=True):
        need(type(t) is dict and set(t) == {'edge_id', 'connected'} and t['edge_id'] == r['edge_id'], 'Exact private/public ordered keys')
        need(type(t['connected']) is int and t['connected'] in (0, 1), 'Binary nonboolean target')
        y.append(t['connected'])
    scores, per = {}, {}
    for view in VIEWS:
        scores[view], per[view] = summaries(rows, y, aligned[view])
    paired = [difference(per[VIEWS[0]][key], per[VIEWS[1]][key]) for key in per[VIEWS[0]]]
    if any(x is None for x in paired) or (math.inf in paired and -math.inf in paired):
        contrast = None
    elif math.inf in paired: contrast = math.inf
    elif -math.inf in paired: contrast = -math.inf
    else: contrast = math.fsum(paired) / len(paired)
    strata = []
    for projection in PROJECTIONS:
        ix = [i for i, r in enumerate(rows) if r['projection'] == projection]
        entry = {'projection': projection, 'pairs': len(ix), 'positives': sum(y[i] for i in ix), 'views': {}}
        if ix:
            for view in VIEWS:
                entry['views'][view], _ = summaries([rows[i] for i in ix], [y[i] for i in ix], [aligned[view][i] for i in ix])
        else: entry['status'] = 'no_query_pairs_in_fixed_projection'
        strata.append(entry)
    return {'task_id': 'NEURAL-087', 'status': 'scored', 'primary_metric': 'joint_equal_presynaptic_log_loss',
            'primary': scores[VIEWS[1]]['equal_pre_log_loss'], 'direction': 'lower_is_better',
            'views': scores, 'anatomy_minus_joint_diagnostic': encoded(contrast), 'projection_strata': strata,
            'support': {'pairs': len(rows), 'presynaptic_neurons': len(per[VIEWS[0]]), 'positives': sum(y), 'zeros': len(y)-sum(y)},
            'private_loader_calls': 1, 'scientific_success': None, 'research_qualified': False}
