"""Complete projected inner SSE selection on other-day labels only."""
import math
from core import need, publish, encoded
from contracts import CONFIGS, FAMILIES
from array_io import load
from worker_common import start, finish, failure


def choose(scores):
    need(set(scores) == set(CONFIGS), 'all 25 configurations, no dropped failures')
    selected = {}
    for family in FAMILIES:
        options = [c for c in CONFIGS if c[0] == family]
        selected[family] = min(options, key=lambda c: (scores[c]['sse']/scores[c]['n'], CONFIGS.index(c)))
    strongest = min(FAMILIES, key=lambda f: (scores[selected[f]]['sse']/scores[selected[f]]['n'], FAMILIES.index(f)))
    return selected, strongest


def run(config):
    request, budget, limits, output = start(config)
    try:
        days = request['validation_days']; held = request['held_day']
        need(days == sorted(set(days)) and held not in days and len(days) >= 2, 'all other-day validation, never outer target')
        rows = request['rows']; expected = {(c,d) for c in CONFIGS for d in days}
        need(len(rows) == len(expected) and {(r['configuration'],r['day']) for r in rows} == expected,
             'every configuration/ordered validation consumer')
        targets = {}; support = {}; sums = {c: [] for c in CONFIGS}; counts = {c: 0 for c in CONFIGS}
        for day in days:
            target = request['targets'][str(day)]
            y = load(target['array'], ['/inputs/labels'], limits)
            need(y.dtype.str == '<f8' and y.shape == (len(target['ids']),), 'full actual permitted validation target')
            targets[day] = y; support[day] = target['ids']
        for row in rows:
            ids = support[row['day']]; need(row['ids'] == ids, 'exact full source validation order')
            pred = load(row['projected'], ['/artifacts'], limits)
            need(pred.shape == (len(ids),) and pred.dtype.str == '<f8', 'full scalar projected validation prediction')
            y = targets[row['day']]
            limits.reserve('work', len(ids)*4); limits.reserve('allocation_bytes', len(ids)*16)
            sse = math.fsum((float(a)-float(b))**2 for a,b in zip(y,pred))
            need(math.isfinite(sse), 'finite complete inner SSE')
            sums[row['configuration']].append(sse); counts[row['configuration']] += len(ids)
        scores = {c: {'sse': math.fsum(sums[c]), 'n': counts[c]} for c in CONFIGS}
        need(all(x['n'] > 0 and math.isfinite(x['sse']) for x in scores.values()), 'nonempty total inner support; empty days alone allowed')
        selected, strongest = choose(scores)
        result = {'schema': 'neural049_reference_selection_v1', 'scope': request['scope'], 'held_day': held,
                  'validation_days': days, 'scores': scores, 'selected': selected, 'strongest': strongest,
                  'consumer_rows': rows, 'targets': request['targets'], 'target_scope': 'other-days-only'}
        d = publish(output/'SELECTION.json', encoded(result), budget, readonly=True)
        return finish(output, request, budget, limits, {'SELECTION.json': d})
    except BaseException as error:
        failure(output, error, budget, limits); raise
