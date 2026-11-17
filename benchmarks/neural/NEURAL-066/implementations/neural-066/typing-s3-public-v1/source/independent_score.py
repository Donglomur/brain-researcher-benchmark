"""Separate decoder, full-matrix edit distance and complete aggregation.

No primary numerical function is imported. Inputs are reread independently from
original sealed prediction and private count captures after the same barrier.
"""
import math
from collections import defaultdict
from core import COUNTS, MODES, need

def sequence(vectors, counts, use_lm):
    if not use_lm:
        return [next((j for j, x in enumerate(v) if x == max(v))) for v in vectors]
    starts = counts['starts']
    transition = counts['transition']
    need(type(starts) is list and len(starts) == 29 and (type(transition) is list) and (len(transition) == 29) and all((type(r) is list and len(r) == 29 for r in transition)) and all((type(v) is int and v >= 1 for v in starts + sum(transition, []))), 'Independent exact positive count table')
    scores = [[math.log(max(vectors[0][j], 1e-12)) + 0.5 * math.log(starts[j] / sum(starts)) for j in range(29)]]
    paths = []
    for t in range(1, len(vectors)):
        row = []
        ancestors = []
        for j in range(29):
            candidates = [scores[-1][k] + 0.5 * math.log(transition[k][j] / sum(transition[k])) for k in range(29)]
            best = max(candidates)
            k = next((i for i, v in enumerate(candidates) if v == best))
            ancestors.append(k)
            row.append(best + math.log(max(vectors[t][j], 1e-12)))
        scores.append(row)
        paths.append(ancestors)
    best = max(scores[-1])
    state = next((i for i, v in enumerate(scores[-1]) if v == best))
    out = [state]
    for row in paths[::-1]:
        state = row[state]
        out.insert(0, state)
    return out

def edit_distance(a, b):
    need(len(a) <= 256 and 0 < len(b) <= 256, 'Complete original support')
    matrix = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        matrix[i][0] = i
    for j in range(len(b) + 1):
        matrix[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + (0 if a[i - 1] == b[j - 1] else 1))
    return matrix[-1][-1]

def stats(values):
    average = sum(values) / len(values)
    return (average, math.sqrt(sum(((v - average) ** 2 for v in values)) / (len(values) - 1) / len(values)) if len(values) > 1 else None)

def locate(term, spec):
    parts = term.split('/')
    decoder = parts[1] if len(parts) == 2 else spec['decoder']
    label = parts[0]
    mode = spec['mode']
    if label == 'R1':
        return '|'.join(['r1', 'reference', 'LANGUAGE_ONLY', 'raw', spec['modality']])
    role, arm = label.split(':')
    if role == 'frozen':
        role = 'candidate'
        mode = MODES[0]
    elif role == 'adaptive':
        role = 'candidate'
        mode = MODES[1]
    elif role in ('R0', 'R2'):
        role = role.lower()
        mode = 'reference'
    need(decoder in ('raw', 'LM0.5'), 'Independent explicit decoder')
    return '|'.join([role, mode, arm, decoder, spec['modality']])

def verify_stream(predictions, expected, gold, primary, ws, languages, contrast_rows):
    need(set(predictions) == set(expected) and len(expected) == 1794 and (len(contrast_rows) == 164), 'Independent complete1794/164 support')
    sums = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    seen = set()
    folds = defaultdict(set)
    audit = {}
    for context, meta in expected.items():
        entry = predictions[context]
        d = ws.from_capture(entry['capture'], 'PREDICTIONS.json')
        body = ws.read(d['source_path'], d)
        view = entry['public']['view']
        lookup = {r['id']: r for r in meta['private_queries']}
        need(type(body) is dict and set(body) == {'format', 'task', 'generation', 'case', 'arm', 'sentences'} and (body['format'] == 'typing_predictions_v1') and (body['task'] == 'NEURAL-066') and (body['case'] == view['case']) and (body['generation'] == view['generation']) and (body['arm'] == view['condition']), 'Independent exact prediction envelope')
        need(type(body['sentences']) is list and len(body['sentences']) == len(lookup), 'Independent complete rows')
        row_seen = set()
        for row in body['sentences']:
            need(type(row) is dict and set(row) == {'id', 'p'} and (row['id'] in lookup) and (row['id'] not in row_seen), 'Independent unique sentence')
            row_seen.add(row['id'])
            source = lookup[row['id']]['source_key']
            truth = gold[meta['slot']][source]
            need(type(row['p']) is list and len(row['p']) == len(truth) and (0 < len(truth) <= 256) and all((type(v) is int and 0 <= v < 29 for v in truth)), 'Independent full key support')
            for vector in row['p']:
                need(type(vector) is list and len(vector) == 29 and all((type(v) in (int, float) and math.isfinite(v) and (0 <= v <= 1) for v in vector)) and (abs(sum(vector) - 1) <= 1e-06), 'Independent simplex, no repair')
            for decoder in ['raw'] if meta['role'] == 'r1' else ['raw', 'LM0.5']:
                group = '|'.join([meta['role'], meta['mode'], meta['condition'], decoder, meta['modality']])
                person = meta['person_slot']
                ident = (group, person, source)
                need(ident not in seen, 'Independent unique original observation')
                seen.add(ident)
                folds[group, person].add(meta['fold'])
                seq = sequence(row['p'], languages[meta['slot']], decoder == 'LM0.5')
                error = edit_distance(seq, truth)
                sums[group][person][0] += error / len(truth)
                sums[group][person][1] += 1
                audit[context + '|' + decoder + '|' + row['id']] = [error, len(truth)]
        need(row_seen == set(lookup), 'Independent full query union')
        ws.budget.tick()
    metrics = {}
    for group, people in sums.items():
        need(set(people) == set(range(COUNTS[group.split('|')[-1]]['people'])) and all((folds[group, p] == {0, 1} for p in people)), 'Independent all people/both folds')
        by = {str(p): total / count for p, (total, count) in sorted(people.items())}
        average, se = stats(list(by.values()))
        metrics[group] = {'by_person': by, 'person_macro_sentence_CER': average, 'descriptive_person_SE': se, 'people': len(by), 'sentences': sum((v[1] for v in people.values()))}
    contrasts = {}
    for spec in contrast_rows:
        left = metrics[locate(spec['left'], spec)]['by_person']
        right = metrics[locate(spec['right'], spec)]['by_person']
        need(set(left) == set(right), 'Independent exact paired support')
        by = {p: left[p] - right[p] for p in left}
        average, se = stats(list(by.values()))
        contrasts[spec['id']] = {'specification': spec, 'by_person': by, 'mean': average, 'descriptive_person_SE': se}
    need(audit == primary['integer_sentence_audit'], 'Independent exact integer edit/support audit')

    def compare(a, b):
        if type(a) is dict:
            need(type(b) is dict and set(a) == set(b), 'Independent exact fields')
            [compare(a[k], b[k]) for k in a]
        elif type(a) is list:
            need(type(b) is list and len(a) == len(b), 'Independent exact list')
            [compare(x, y) for x, y in zip(a, b)]
        elif type(a) is float:
            need(type(b) in (int, float) and math.isfinite(b) and (abs(a - b) <= 1e-12), 'Independent1e-12 agreement')
        else:
            need(type(a) is type(b) and a == b, 'Independent exact identity')
    legacy={}
    for modality in ('MEG','EEG'):
        for mode in MODES:
            item={arm:'|'.join(['candidate',mode,arm,'raw',modality])for arm in ('TIMING','EOG','NEURAL_PRE','NEURAL','NEURAL_POST','SHUFFLE')}
            item['LANGUAGE_ONLY']='|'.join(['r1','reference','LANGUAGE_ONLY','raw',modality])
            item['NEURAL_PLUS_FIXED_LM']='|'.join(['candidate',mode,'NEURAL','LM0.5',modality]);legacy[mode+'|'+modality]=item
    compare(legacy,primary['legacy_output_bindings']);need(len(metrics)==90,'Independent complete90 groups')
    compare(metrics, primary['metrics'])
    compare(contrasts, primary['contrasts'])
    return {'schema': 'neural066_independent_metric_join_v2', 'matched': True, 'groups': len(metrics), 'contrasts': 164, 'sentence_audit_rows': len(audit), 'scientific_qualification': False, 'reference_competence': False}
