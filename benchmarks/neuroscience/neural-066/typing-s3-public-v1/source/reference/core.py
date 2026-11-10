"""Independent, standard-library support/selection/metric primitives."""
import hashlib, json, math, statistics
from collections import Counter, defaultdict
CLASSES = 29
GRID = (5e-05, 0.0001)
CELLS = tuple(((p, t) for p in range(3) for t in range(3)))

def need(ok, message):
    if not ok:
        raise ValueError(message)

def finite(v):
    return type(v) in (int, float) and math.isfinite(v)

def layout(rows, n_rows, training=True):
    need(type(rows) is list and rows and (type(n_rows) is int) and (n_rows > 0), 'nonempty complete sentence layout')
    fields = {'id', 'begin', 'n_keys'} | ({'person', 'session', 'template'} if training else set())
    end = 0
    ids = set()
    for row in rows:
        need(type(row) is dict and set(row) == fields, 'exact sentence fields')
        for key in fields - {'begin', 'n_keys'}:
            need(type(row[key]) is str and row[key], 'nonempty opaque group')
        need(row['id'] not in ids, 'unique sentence ID')
        ids.add(row['id'])
        need(type(row['begin']) is int and row['begin'] == end and (type(row['n_keys']) is int) and (1 <= row['n_keys'] <= 256), 'complete contiguous sentence support')
        end += row['n_keys']
    need(end == n_rows, 'complete exact row extent')
    return rows

def subset(rows, ids):
    need(type(ids) is list and ids and (len(ids) == len(set(ids))), 'nonempty unique sentence subset')
    wanted = set(ids)
    out = [r for r in rows if r['id'] in wanted]
    need([r['id'] for r in out] == ids, 'subset retains exact admitted sentence order')
    return out

def row_indices(rows):
    return [i for r in rows for i in range(r['begin'], r['begin'] + r['n_keys'])]

def weights(rows):
    """One normalized weight per real key; recomputed for this fit only."""
    need(rows, 'nonempty fitting sentences')
    counts = Counter((r['person'] for r in rows))
    persons = len(counts)
    out = [1.0 / (persons * counts[r['person']] * r['n_keys']) for r in rows for _ in range(r['n_keys'])]
    total = math.fsum(out)
    need(math.isfinite(total) and total > 0, 'finite fitting weights')
    return [w / total for w in out]

def derive_buckets(modality, outer_person, outer_fold, kind, groups):
    """Private preparation only: return source-private groups, never export hashes."""
    need(modality in ('MEG', 'EEG') and type(outer_person) is str and outer_person and (type(outer_fold) is int) and (outer_fold in (0, 1)), 'private outer identity')
    need(kind in ('person', 'template') and type(groups) is list and groups and (len(groups) == len(set(groups))) and all((type(g) is str and g for g in groups)), 'private group identities')

    def key(group):
        raw = json.dumps(['NEURAL065-inner-v1', modality, outer_person, outer_fold, kind, group], ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
        return (hashlib.sha256(raw).hexdigest(), group)
    return {g: i % 3 for i, g in enumerate(sorted(groups, key=key))}

def cells(rows, plan, context):
    need(type(plan) is dict and set(plan) == {'schema', 'case', 'modality', 'condition', 'person_buckets', 'template_buckets', 'assignment_provenance'}, 'exact private reference plan')
    need(plan['schema'] == 'neural066_reference_plan_v1' and all((plan[k] == context[k] for k in ('case', 'modality', 'condition'))), 'plan context')
    for name, field in [('person_buckets', 'person'), ('template_buckets', 'template')]:
        m = plan[name]
        need(type(m) is dict and set(m) == {r[field] for r in rows} and all((type(v) is int and v in range(3) for v in m.values())), 'complete exact bucket grouping')
    need(type(plan['assignment_provenance']) is dict and plan['assignment_provenance'], 'operator-authenticated bucket provenance required')
    out = {}
    for p, t in CELLS:
        fit = [r['id'] for r in rows if plan['person_buckets'][r['person']] != p and plan['template_buckets'][r['template']] != t]
        val = [r['id'] for r in rows if plan['person_buckets'][r['person']] == p and plan['template_buckets'][r['template']] == t]
        out[p, t] = {'fit': fit, 'validation': val, 'status': 'complete' if fit and val else 'incomplete_empty_support'}
    coverage = Counter((s for c in out.values() for s in c['validation']))
    need(coverage == Counter({r['id']: 1 for r in rows}), 'every outer training sentence validates exactly once')
    return out

def probabilities(rows, n):
    need(type(rows) is list and len(rows) == n, 'complete probability row count')
    for row in rows:
        need(type(row) is list and len(row) == CLASSES and all((finite(x) and 0 <= x <= 1 for x in row)) and (abs(math.fsum(row) - 1) <= 1e-06), 'finite exact29 probability simplex; no repair')
    return rows

def classes(values):
    need(type(values) is list and values and all((type(v) is int and 0 <= v < CLASSES for v in values)), 'observed mapped29-class labels')
    return values

def greedy(rows):
    probabilities(rows, len(rows))
    return [max(range(CLASSES), key=lambda j: r[j]) for r in rows]

def edit_distance(predicted, truth):
    """Independent column recurrence, not the captured scorer's row routine."""
    classes(truth)
    need(type(predicted) is list and all((type(v) is int and 0 <= v < 29 for v in predicted)), 'possibly empty mapped prediction')
    column = list(range(len(predicted) + 1))
    for j, truth_symbol in enumerate(truth, 1):
        diagonal = column[0]
        column[0] = j
        for i, pred_symbol in enumerate(predicted, 1):
            above = column[i]
            column[i] = min(column[i - 1] + 1, above + 1, diagonal + (pred_symbol != truth_symbol))
            diagonal = above
    return column[-1]

def sentence_cer(predicted, truth):
    return edit_distance(predicted, truth) / len(truth)

def person_cer(rows, truth, predicted):
    need(set(truth) == set(predicted) == {r['id'] for r in rows}, 'exact sentence assessment support')
    values = defaultdict(list)
    for r in rows:
        need(len(truth[r['id']]) == len(predicted[r['id']]) == r['n_keys'], 'full sentence key support')
        values[r['person']].append(sentence_cer(predicted[r['id']], truth[r['id']]))
    by = {p: math.fsum(v) / len(v) for p, v in sorted(values.items())}
    need(by and all((math.isfinite(v) for v in by.values())), 'finite full person CER')
    return {'mean_person_CER': math.fsum(by.values()) / len(by), 'by_person': by, 'sentences': len(rows)}

def split_predictions(rows, flat):
    probabilities(flat, sum((r['n_keys'] for r in rows)))
    out = {}
    start = 0
    for r in rows:
        out[r['id']] = greedy(flat[start:start + r['n_keys']])
        start += r['n_keys']
    return out

def truth_by_sentence(rows, labels):
    out = {}
    for r in rows:
        values = []
        for i in range(r['begin'], r['begin'] + r['n_keys']):
            value = labels[i]
            integer = int(value)
            need(value == integer and 0 <= integer < 29, 'exact mapped integer truth; no rounding')
            values.append(integer)
        out[r['id']] = classes(values)
    return out

def choose_oof(rows, labels, plan, context, results):
    """Every one of 18 cells is required; score complete OOF support per grid."""
    membership = cells(rows, plan, context)
    need(type(results) is list and len(results) == 18, 'all18 inner results required')
    indexed = {}
    for item in results:
        need(type(item) is dict and set(item) == {'result', 'probabilities'}, 'exact selection operand')
        r = item['result']
        need(type(r['cell']) is list and len(r['cell']) == 2 and all((type(v) is int and v in range(3) for v in r['cell'])), 'typed exact cell coordinates')
        key = (r['grid_index'], tuple(r['cell']))
        need(type(r['grid_index']) is int and r['grid_index'] in (0, 1) and (key[1] in CELLS) and (key not in indexed), 'unique exact grid/cell')
        need(r['status'] == 'complete' and r['action'] == 'r2_inner' and (r['context'] == context), 'complete independent inner result')
        expected = membership[key[1]]
        need(expected['status'] == 'complete', 'empty required selection cell')
        need(r['fit_sentences'] == expected['fit'] and r['validation_sentences'] == expected['validation'], 'exact fit/validation membership')
        need(type(r['best_epoch']) is int and 1 <= r['best_epoch'] <= 300, 'admitted best epoch')
        history = r['history']
        need(type(history) is list and 1 <= len(history) <= 300, 'complete epoch history')
        for epoch, h in enumerate(history, 1):
            need(type(h) is dict and type(h['epoch']) is int and (h['epoch'] == epoch) and finite(h['validation_person_CER']) and (0 <= h['validation_person_CER'] <= 1), 'complete finite fixed-length epoch metric')
        best = 1
        stale = 0
        for i, h in enumerate(history, 1):
            if i == 1 or h['validation_person_CER'] < history[best - 1]['validation_person_CER']:
                best = i
                stale = 0
            else:
                stale += 1
            need(stale < 30 or i == len(history), 'no epochs after original patience cutoff')
        need(best == r['best_epoch'], 'earliest strictly lowest epoch retained')
        need(len(history) == 300 or stale == 30, 'selected fit stops only maxepochs or exact patience')
        val = subset(rows, expected['validation'])
        pred = split_predictions(val, item['probabilities'])
        score = person_cer(val, truth_by_sentence(val, labels), pred)
        need(score['mean_person_CER'] == history[best - 1]['validation_person_CER'], 'best checkpoint predictions reproduce selection metric')
        indexed[key] = (r, pred)
    summaries = []
    for grid in (0, 1):
        combined = {}
        epochs = []
        for cell in CELLS:
            r, pred = indexed[grid, cell]
            need(not set(combined) & set(pred), 'disjoint OOF validation sentences')
            combined.update(pred)
            epochs.append(r['best_epoch'])
        score = person_cer(rows, truth_by_sentence(rows, labels), combined)
        summaries.append({'grid_index': grid, 'max_lr': GRID[grid], 'score': score, 'best_epochs': epochs, 'final_epochs': sorted(epochs)[4]})
    selected = min(range(2), key=lambda i: summaries[i]['score']['mean_person_CER'])
    return {'schema': 'neural066_complete_oof_selection_v1', 'context': context, 'selected_grid': selected, 'selected_lr': GRID[selected], 'final_epochs': summaries[selected]['final_epochs'], 'configurations': summaries, 'query_used': False, 'all18_required': True}

def bigram_count(sentences):
    need(type(sentences) is list and sentences, 'complete nonempty training sentences')
    starts = [1] * CLASSES
    transition = [[1] * CLASSES for _ in range(CLASSES)]
    for s in sentences:
        classes(s)
        starts[s[0]] += 1
        for a, b in zip(s, s[1:]):
            transition[a][b] += 1
    return {'starts': starts, 'transition': transition}

def viterbi_length(n, counts):
    """Literal original uniform-emission, weight-one tie/order semantics."""
    need(type(n) is int and 1 <= n <= 256 and (set(counts) == {'starts', 'transition'}), 'known complete sequence length/table')
    starts = counts['starts']
    trans = counts['transition']
    need(len(starts) == 29 and len(trans) == 29 and all((len(r) == 29 for r in trans)) and all((type(v) is int and v >= 1 for v in starts + sum(trans, []))), 'positive Laplace counts')
    logstart = [math.log(v / sum(starts)) for v in starts]
    logs = [[math.log(v / sum(row)) for v in row] for row in trans]
    uniform = math.log(1 / 29)
    scores = [uniform + v for v in logstart]
    back = []
    for _ in range(1, n):
        prev = []
        new = []
        for j in range(29):
            k = max(range(29), key=lambda i: scores[i] + logs[i][j])
            prev.append(k)
            new.append(scores[k] + logs[k][j] + uniform)
        back.append(prev)
        scores = new
    out = [max(range(29), key=lambda j: scores[j])]
    for b in reversed(back):
        out.append(b[out[-1]])
    return list(reversed(out))
