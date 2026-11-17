"""Protected complete-support score: target access belongs to the final barrier."""
import math
import statistics
from collections import defaultdict
from core import COUNTS, MODES, exact, need, no_science_promotion

def admit_predictions(body, view):
    exact(body, ('format', 'task', 'generation', 'case', 'arm', 'sentences'))
    need(body['format'] == 'typing_predictions_v1' and body['task'] == 'NEURAL-066' and (body['generation'] == view['generation']) and (body['case'] == view['case']) and (body['arm'] == view['condition']), 'Exact original prediction context')
    wanted = {r['id']: r['n_keys'] for r in view['queries']}
    result = {}
    need(len(wanted) == len(view['queries']) and type(body['sentences']) is list and (len(body['sentences']) == len(wanted)), 'Full query sentence union')
    for row in body['sentences']:
        exact(row, ('id', 'p'))
        need(row['id'] in wanted and row['id'] not in result and (type(row['p']) is list) and (len(row['p']) == wanted[row['id']]), 'Full exact unique query keys')
        for v in row['p']:
            need(type(v) is list and len(v) == 29 and all((type(x) in (int, float) and math.isfinite(x) and (0 <= x <= 1) for x in v)) and (abs(sum(v) - 1) <= 1e-06), 'Finite29 simplex without repair')
        result[row['id']] = row['p']
    return result

def counts_admit(value):
    exact(value, ('starts', 'transition'))
    s = value['starts']
    t = value['transition']
    need(type(s) is list and len(s) == 29 and (type(t) is list) and (len(t) == 29) and all((type(r) is list and len(r) == 29 for r in t)) and all((type(v) is int and v >= 1 for v in s + sum(t, []))), 'Original positive Laplace1 training counts')
    return value

def decode(prob, counts, weight):
    need(0 < len(prob) <= 256 and weight in (0.0, 0.5), 'Complete known-key support and predeclared decoder')
    if weight == 0:
        return [max(range(29), key=lambda j: v[j]) for v in prob]
    counts_admit(counts)
    s = counts['starts']
    t = counts['transition']
    starts = [math.log(v / sum(s)) for v in s]
    trans = [[math.log(v / sum(row)) for v in row] for row in t]
    score = [math.log(max(prob[0][j], 1e-12)) + weight * starts[j] for j in range(29)]
    back = []
    for vector in prob[1:]:
        previous = [max(range(29), key=lambda k: score[k] + weight * trans[k][j]) for j in range(29)]
        score = [score[previous[j]] + weight * trans[previous[j]][j] + math.log(max(vector[j], 1e-12)) for j in range(29)]
        back.append(previous)
    last = max(range(29), key=lambda j: score[j])
    out = [last]
    for previous in reversed(back):
        last = previous[last]
        out.append(last)
    return list(reversed(out))

def distance(pred, truth):
    previous = list(range(len(truth) + 1))
    for i, a in enumerate(pred, 1):
        current = [i]
        for j, b in enumerate(truth, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + int(a != b)))
        previous = current
    return previous[-1]

def summary(values):
    need(len(values) > 0, 'No available-case metric')
    return {'mean': sum(values) / len(values), 'descriptive_person_SE': statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None}

def metric_key(role, mode, arm, decoder, modality):
    return '|'.join((role, mode, arm, decoder, modality))

def resolve(term, row):
    decoder = row['decoder']
    mode = row['mode']
    if '/' in term:
        term, decoder = term.split('/')
    if term == 'R1':
        return metric_key('r1', 'reference', 'LANGUAGE_ONLY', 'raw', row['modality'])
    producer, arm = term.split(':')
    if producer in ('frozen', 'adaptive'):
        mode = MODES[0 if producer == 'frozen' else 1]
        producer = 'candidate'
    if producer in ('R0', 'R2'):
        producer = producer.lower()
        mode = 'reference'
    need(decoder in ('raw', 'LM0.5'), 'Explicit contrast decoder')
    return metric_key(producer, mode, arm, decoder, row['modality'])

def grade_stream(items, expected, gold, languages, contrast_rows):
    need(len(expected) == 1794 and len(contrast_rows) == 164, 'Full precommitted contexts and contrasts')
    groups = defaultdict(lambda: defaultdict(list))
    seen = set()
    folds = defaultdict(set)
    audits = {}
    contexts = set()
    for context, predictions in items:
        need(context in expected and context not in contexts, 'Original unique prediction context')
        contexts.add(context)
        meta = expected[context]
        rows = meta['private_queries']
        need(set(predictions) == {r['id'] for r in rows}, 'Exact target/source query bijection')
        for decoder, weight in [('raw', 0.0)] if meta['role'] == 'r1' else [('raw', 0.0), ('LM0.5', 0.5)]:
            group = metric_key(meta['role'], meta['mode'], meta['condition'], decoder, meta['modality'])
            person = meta['person_slot']
            folds[group, person].add(meta['fold'])
            for row in rows:
                source = row['source_key']
                truth = gold[meta['slot']][source]
                ident = (group, person, source)
                need(ident not in seen and 0 < len(truth) <= 256 and all((type(v) is int and 0 <= v < 29 for v in truth)), 'Original unique nonempty mapped targets')
                seen.add(ident)
                need(len(predictions[row['id']]) == len(truth), 'Complete known key count')
                sequence = decode(predictions[row['id']], languages[meta['slot']], weight)
                error = distance(sequence, truth)
                groups[group][person].append(error / len(truth))
                audits[context + '|' + decoder + '|' + row['id']] = [error, len(truth)]
    need(contexts == set(expected), 'No omitted context or favorable partial campaign')
    output = {}
    for group, people in groups.items():
        modality = group.split('|')[-1]
        need(set(people) == set(range(COUNTS[modality]['people'])) and all((folds[group, p] == {0, 1} for p in people)), 'All modality-local people and both folds before mean')
        by = {str(p): sum(v) / len(v) for p, v in sorted(people.items())}
        ss = summary(list(by.values()))
        output[group] = {'by_person': by, 'person_macro_sentence_CER': ss['mean'], 'descriptive_person_SE': ss['descriptive_person_SE'], 'people': len(by), 'sentences': sum(map(len, people.values()))}
    contrasts = {}
    for row in contrast_rows:
        left = output[resolve(row['left'], row)]['by_person']
        right = output[resolve(row['right'], row)]['by_person']
        need(set(left) == set(right), 'Complete matched contrast support')
        by = {p: left[p] - right[p] for p in left}
        contrasts[row['id']] = {'specification': row, 'by_person': by, **summary(list(by.values()))}
    need(len(contrasts) == 164, 'Exact unique164 contrasts')
    need(len(output)==90,'All complete candidate/reference decoder metric groups')
    legacy={}
    for modality in COUNTS:
        for mode in MODES:
            legacy[mode+'|'+modality]={arm:metric_key('candidate',mode,arm,'raw',modality)for arm in ('TIMING','EOG','NEURAL_PRE','NEURAL','NEURAL_POST','SHUFFLE')}
            legacy[mode+'|'+modality].update(LANGUAGE_ONLY=metric_key('r1','reference','LANGUAGE_ONLY','raw',modality),NEURAL_PLUS_FIXED_LM=metric_key('candidate',mode,'NEURAL','LM0.5',modality))
    return {'schema': 'neural066_complete_score_v2', 'status': 'complete_support_metric_computed', 'metrics': output, 'legacy_output_bindings':legacy, 'contrasts': contrasts, 'integer_sentence_audit': audits, 'primary_scalar': None, 'modalities_pooled': False, 'unique_recruits_total': None, 'uncertainty': 'descriptive person SE only; no p-values or success threshold', **no_science_promotion()}

def incomplete(expected, dispositions):
    return {'schema': 'neural066_complete_score_v2', 'status': 'incomplete', 'expected_contexts': len(expected), 'primary_scalar': None, 'dispositions': dispositions, 'complete_primary_defined': False, **no_science_promotion()}
