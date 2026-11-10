"""Protected source-owned scoring and report algebra. Never imports participant source.
Not executed on real or invented scientific targets in current build-only controls.
"""
import math
from .common import need, load, number, probabilities
from .spec import PEOPLE, LABELS, WINDOWS, FAMILIES, CORE, SUMMARY, REFS


def average(xs):
    need(bool(xs), 'Nonempty mean')
    return math.fsum(xs) / len(xs)


def descriptive(xs):
    need(len(xs) == 4, 'All four person effects')
    m = average(xs); se = math.sqrt(math.fsum((x - m) ** 2 for x in xs) / 3 / 4)
    return {'mean': m, 'se': se, 'interval': [m - 3.182446 * se, m + 3.182446 * se],
            'people': dict(zip(PEOPLE, xs)), 'qualification': 'DESCRIPTIVE_ONLY_DEPENDENT_FINITE_N'}


def accumulator():
    return [[[0, 0, 0., 0, 0, 0] for _ in (0, 1)] for _ in LABELS]


def add(acc, truth, values):
    need(type(truth) is list and len(truth) == 27 and all(type(t) is int and t in (0, 1) for t in truth), 'Binary truth')
    probabilities(values)
    for j, (t, q) in enumerate(zip(truth, values)):
        a = acc[j][t]; v = q if t else 1 - q
        a[0] += 1; a[1] += int((q >= .5) == bool(t)); a[2] += -math.log(max(1e-15, v))
        a[3] += int(q == 0); a[4] += int(q == 1); a[5] += int(v < 1e-15)


def finish(acc):
    rows = []
    for name, pair in zip(LABELS, acc):
        need(all(x[0] > 0 for x in pair), 'Missing class invalidates metric; never drop label/session')
        total = pair[0][0] + pair[1][0]
        rows.append({'label': name, 'counts': [x[0] for x in pair],
                     'balanced_logloss': average([x[2] / x[0] for x in pair]),
                     'balanced_accuracy': average([x[1] / x[0] for x in pair]),
                     'unweighted_logloss': sum(x[2] for x in pair) / total,
                     'exact_zero': sum(x[3] for x in pair), 'exact_one': sum(x[4] for x in pair),
                     'clipped': sum(x[5] for x in pair)})
    return {'labels': rows, **{m: average([r[m] for r in rows]) for m in
                              ('balanced_logloss', 'balanced_accuracy', 'unweighted_logloss')}}


def complete_metrics(controller, targets):
    records = [('candidate', key, list(controller.items(artifacts))) for key, artifacts in controller.candidates.items()]
    records += [(kind, family, [a for a in controller.items(bank['artifacts']) if a['owner'] == family])
                for kind, bank in controller.banks.items() for family in REFS[kind]]
    slots = {s['id']: s for s in controller.panel['slots']}
    need(set(targets) == set(slots), 'Full exact target slot set')
    metrics = {}
    for kind, owner, artifacts in records:
        acc = {(p, session, w, a): accumulator() for p in PEOPLE for session in range(1, 13)
               for w in WINDOWS for a in FAMILIES}
        need(len(artifacts) == 6000, 'Full scientific artifact count')
        for descriptor in artifacts:
            artifact = load(descriptor['path'], 128 << 20, {k: descriptor[k] for k in ('bytes', 'sha256')})
            s = slots[artifact['slot']]; c = s['logical']['case']
            need(artifact['label_order'] == list(LABELS) and artifact['status'] == 'complete', 'Complete frozen output')
            rows = {r['id']: r for r in artifact['rows']}
            need(set(rows) == set(targets[s['id']]) == set(s['query_ids']), 'Exact target/candidate/reference support')
            current = acc[(c['person'], c['session'], s['logical']['window'], s['logical']['arm'])]
            # Pool all five concept folds first; do not average differently sized fold metrics.
            for qid, truth in targets[s['id']].items(): add(current, truth, rows[qid]['probabilities'])
        sessions = {key: finish(value) for key, value in acc.items()}
        people = {}
        for p in PEOPLE:
            people[p] = {w: {a: {m: average([sessions[(p, session, w, a)][m] for session in range(1, 13)])
                                for m in ('balanced_logloss', 'balanced_accuracy', 'unweighted_logloss')}
                             for a in FAMILIES} for w in WINDOWS}
        metrics[(kind, owner)] = {'people': people,
            'sessions': [{'person': p, 'session': s, 'window': w, 'arm': a, **v}
                         for (p, s, w, a), v in sessions.items()],
            'mean': {w: {a: {m: average([people[p][w][a][m] for p in PEOPLE])
                              for m in ('balanced_logloss', 'balanced_accuracy', 'unweighted_logloss')}
                         for a in FAMILIES} for w in WINDOWS}}
    return metrics


def score(controller, targets):
    metrics = complete_metrics(controller, targets); points = {}; sections = {}; estimates = {}
    for (kind, owner), result in metrics.items():
        for w in WINDOWS:
            for a in FAMILIES:
                for metric, value in result['mean'][w][a].items():
                    points[f'{kind}/{owner}/{w}/{a}/{metric}'] = value
    for condition in controller.manifest['conditions']:
        if condition['mode'] not in 'PID': continue
        key = condition['id']; candidate = metrics[('candidate', key)]
        section = {'mode': condition['mode'], 'tool': condition['tool'], 'replicate': condition['replicate'],
                   'profile': condition['profile'], 'completion_status': 'complete', 'raw': candidate,
                   'costs': controller._budget(), 'exposure': controller.manifest['exposure'], 'contrasts': {}}
        if condition['mode'] in 'PI':
            section['bank_kind'] = CORE; section['bank_seal'] = controller.banks[CORE]['seal']
            r1 = metrics[(CORE, 'R1')]
            for w in WINDOWS:
                for e, arm in [('E01', 'NUISANCE'), ('E02', 'JOINT')]:
                    values = [r1['people'][p][w][arm]['balanced_logloss'] -
                              candidate['people'][p][w]['JOINT']['balanced_logloss'] for p in PEOPLE]
                    section['contrasts'][e + '/' + w] = descriptive(values)
                    points[key + '/' + e + '/' + w] = average(values)
            section['primary'] = {'estimand': 'E01/EARLY', 'value': points[key + '/E01/EARLY'],
                                  'meaning': 'Fixed R1 nuisance minus candidate joint; method and information differ'}
            section['E04'] = {}
            # Positive means improved loss/accuracy in the second (right) condition.
            for metric in ('balanced_logloss', 'balanced_accuracy'):
                sign = 1 if metric == 'balanced_logloss' else -1
                comparisons = [('NEURAL_AUGMENTATION/' + w, w, 'NUISANCE', w, 'JOINT') for w in WINDOWS]
                comparisons += [(f'TEMPORAL/{a}/EARLY_VS_{other}', other, a, 'EARLY', a)
                                for a in FAMILIES for other in ('PRE', 'LATE')]
                for name, lw, la, rw, ra in comparisons:
                    values = [sign * (candidate['people'][p][lw][la][metric] - candidate['people'][p][rw][ra][metric]) for p in PEOPLE]
                    evidence = f'{key}/E04/{name}/{metric}'
                    section['E04'][name + '/' + metric] = {
                        **descriptive(values), 'metric': metric, 'left': {'window': lw, 'arm': la},
                        'right': {'window': rw, 'arm': ra}, 'sign': 'positive_is_right_better',
                        'support': 'same full 4 people/12 sessions/27 labels; paired immutable query/target bank',
                        'evidence_id': evidence, 'descriptive_only': True}
                    points[evidence] = average(values)
        else:
            section['bank_kind'] = SUMMARY; section['bank_seal'] = controller.banks[SUMMARY]['seal']
            for family in REFS[SUMMARY]:
                reference = metrics[(SUMMARY, family)]
                for w in WINDOWS:
                    for a in FAMILIES:
                        for metric in ('balanced_logloss', 'balanced_accuracy'):
                            sign = 1 if metric == 'balanced_logloss' else -1
                            values = [sign * (reference['people'][p][w][a][metric] -
                                             candidate['people'][p][w][a][metric]) for p in PEOPLE]
                            name = f'E06/{family}/{w}/{a}/{metric}'
                            section['contrasts'][name] = descriptive(values)
                            points[key + '/' + name] = average(values)
            section['primary'] = None  # Separate compressed-information diagnostic, no E01 pool.
        sections[key] = section
    if CORE in controller.banks:
        estimates['E03'] = {}
        for family in ('R0', 'R1', 'R2'):
            r = metrics[(CORE, family)]
            for w in WINDOWS:
                values = [r['people'][p][w]['NUISANCE']['balanced_logloss'] -
                          r['people'][p][w]['JOINT']['balanced_logloss'] for p in PEOPLE]
                estimates['E03'][family + '/' + w] = descriptive(values)
                points['E03/' + family + '/' + w] = average(values)
    else: estimates['E03'] = {'status': 'NOT_SELECTED', 'value': None}
    estimates['E05'] = {}
    conditions = {c['id']: c for c in controller.manifest['conditions']}
    for pair in controller.manifest['comparisons']:
        need(set(pair) == {'id', 'left', 'right'}, 'Predeclared matched contrast')
        left, right = conditions[pair['left']], conditions[pair['right']]
        need(left['mode'] in 'PI' and right['mode'] in 'PI' and left['profile'] == right['profile'] and
             left['replicate'] == right['replicate'], 'Matched full-core profile/replicate only')
        # Same full support and common phase resource classes are controller-enforced.
        l = metrics[('candidate', left['id'])]; r = metrics[('candidate', right['id'])]
        estimates['E05'][pair['id']] = {w: {a: descriptive([
            l['people'][p][w][a]['balanced_logloss'] - r['people'][p][w][a]['balanced_logloss'] for p in PEOPLE])
            for a in FAMILIES} for w in WINDOWS}
        for w in WINDOWS:
            for a in FAMILIES:
                evidence = f'E05/{pair["id"]}/{w}/{a}/balanced_logloss'
                effect = estimates['E05'][pair['id']][w][a]
                effect.update({'evidence_id': evidence, 'left_condition': left['id'], 'right_condition': right['id'],
                               'metric': 'balanced_logloss', 'sign': 'left_minus_right_positive_is_right_better',
                               'support': 'identical full-core profile/replicate/query/target bank'})
                points[evidence] = effect['mean']
    if not estimates['E05']: estimates['E05'] = {'status': 'NOT_SELECTED', 'value': None}
    return {'schema': 'n054_report_v1', 'status': 'COMPLETE_UNQUALIFIED', 'conditions': sections,
            'references': {kind + '/' + owner: v for (kind, owner), v in metrics.items() if kind != 'candidate'},
            'estimands': estimates, 'points': points, 'citations': ['eLife.82580v4', 'N054_ACCEPTED_S3'],
            'inactive': {m: 'NOT_SELECTED' for m in 'PIDR' if m not in controller.requirements['modes']},
            'reasoning_rubric_score': None,
            'limits': ['27 deterministic image/concept labels; predictive gain relative to finite controls',
                       'No irreducible conditional-image information, causal onset, or online claim',
                       '103 fixed visual features and linear controls do not exhaust nuisance explanations',
                       'All four people share images; descriptive intervals are not population-calibrated',
                       'Balanced probabilities target a pseudo-population; prevalence loss reported separately',
                       'P/I and D information profiles cannot share a ranking composite',
                       'Null, negative and inconclusive effects are valid; no preferred-sign reward']}


def check_claims(response, report):
    need(set(response) == {'status', 'claims'} and response['status'] == 'interpreted' and type(response['claims']) is list,
         'Typed R output')
    results = []
    for claim in response['claims']:
        need(set(claim) == {'estimand', 'evidence_ids', 'value', 'units', 'uncertainty', 'comparison',
                            'alternative_explanations', 'limitations', 'falsification_needed', 'citations'}, 'Complete scientific claim schema')
        need(type(claim['evidence_ids']) is list and claim['evidence_ids'], 'Evidence required')
        need(all(e in report.get('points', {}) for e in claim['evidence_ids']), 'Evidence ID absent from frozen report')
        need(all(c in report.get('citations', []) for c in claim['citations']), 'Unsupported source citation')
        # A scalar claim cites one frozen point; compound reasoning stays independently reviewed.
        need(len(claim['evidence_ids']) == 1, 'One independently checkable scalar per claim')
        expected = report['points'][claim['evidence_ids'][0]]
        correct = (claim['value'] is None and expected is None) or (number(claim['value']) and number(expected) and
                                                                                abs(claim['value'] - expected) <= 1e-8)
        results.append({'estimand': claim['estimand'], 'arithmetic_correct': correct,
                        'scientific_reasoning_review': 'UNQUALIFIED'})
    return results
