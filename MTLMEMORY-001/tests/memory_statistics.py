"""Public rank/selection arithmetic, using direct paired wins and math.erfc.

This does not import the oracle or impose any scientific outcome direction.
"""
import hashlib
import json
import math
import numpy as np

METHOD_SHA256 = '7e2ed03d8887a62206db229e52024793852a55c1b34202965d4f4fec3038e37d'
SOURCE_SHA256 = '3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9'
ARRAY_FIELDS = ('unit_key response_unit_index source_trial_row trial_id source_label '
                'spike_count rate_hz repeat_id train_membership').split()
POPULATIONS = ('full_data_selected_same_trials', 'crossfit_selected_at_least_five_splits')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def doubled_u(old, new):
    x, y = np.asarray(old), np.asarray(new)
    require(x.ndim == y.ndim == 1 and x.dtype.kind in 'iu' and y.dtype.kind in 'iu', 'Integer counts required')
    require(np.all(x >= 0) and np.all(y >= 0), 'Negative released count')
    if not len(x) or not len(y):
        return None
    return int(2*np.count_nonzero(x[:, None] > y)+np.count_nonzero(x[:, None] == y))


def rank_measure(count, label):
    x, y = np.asarray(count), np.asarray(label)
    require(x.ndim == y.ndim == 1 and x.shape == y.shape and y.dtype.kind in 'iu', 'Bad rank support')
    require(np.isin(y, [0, 1]).all(), 'Unknown source label')
    old, new = x[y == 1], x[y == 0]
    n1, n0 = len(old), len(new)
    u2 = doubled_u(old, new)
    if u2 is None:
        return dict(status='insufficient_class_support', u_old_twice=None, auc_old=None,
                    p=None, preferred_sign=None, same_trial_auc=None, selected=False)
    auc = u2/(2*n0*n1)
    _, multiplicities = np.unique(x, return_counts=True)
    tie_sum = sum(int(t)**3-int(t) for t in multiplicities)
    n = n0+n1
    if len(multiplicities) == 1:
        p = 1.
    else:
        variance = n0*n1*((n+1)*n*(n-1)-tie_sum)/(12*n*(n-1))
        require(variance > 0 and math.isfinite(variance), 'Invalid tie variance')
        z = (max(u2/2, n0*n1-u2/2)-n0*n1/2-.5)/math.sqrt(variance)
        p = min(1., math.erfc(z/math.sqrt(2.)))
    require(math.isfinite(p) and 0 <= p <= 1, 'Invalid probability')
    return dict(status='ok', u_old_twice=u2, auc_old=auc, p=p,
        preferred_sign=1 if u2 >= n0*n1 else -1, same_trial_auc=max(auc, 1-auc), selected=p < .05)


def generate_masks(arrays):
    """Canonical source-order arrays, one global PCG64 stream."""
    unit, labels = arrays['response_unit_index'], arrays['source_label']
    groups = [np.flatnonzero(unit == i) for i in range(len(arrays['unit_key']))]
    rng = np.random.Generator(np.random.PCG64(0))
    masks = np.zeros((60, len(unit)), dtype=bool)
    for repeat in range(60):
        for indices in groups:
            i0, i1 = indices[labels[indices] == 0], indices[labels[indices] == 1]
            if min(len(i0), len(i1)) < 4:
                continue
            masks[repeat, rng.choice(i0, len(i0)//2, replace=False, shuffle=True)] = True
            masks[repeat, rng.choice(i1, len(i1)//2, replace=False, shuffle=True)] = True
    return masks


def primitive_fingerprint(arrays):
    digest = hashlib.sha256(METHOD_SHA256.encode())
    for name in ARRAY_FIELDS:
        if name == 'rate_hz':
            continue
        value = np.ascontiguousarray(arrays[name])
        digest.update(name.encode()); digest.update(value.dtype.str.encode())
        digest.update(str(value.shape).encode()); digest.update(value.tobytes())
    for name in ('sessions', 'units'):
        if name in arrays:
            digest.update(json.dumps(arrays[name], sort_keys=True, allow_nan=False).encode())
    return digest.hexdigest()


def analyze(ref):
    """Cached by complete exact scientific primitives, never reported summaries."""
    fingerprint = primitive_fingerprint(ref)
    cache = ref.get('_analysis_cache')
    if cache is not None and cache[0] == fingerprint:
        return cache[1]
    units = {r['unit_key']: r for r in ref['units']}
    sessions = {r['asset_path']: r for r in ref['sessions']}
    events, neurons = [], []
    for index, key in enumerate(ref['unit_key'].tolist()):
        source = units[key]; positions = np.flatnonzero(ref['response_unit_index'] == index)
        count, labels = ref['spike_count'][positions], ref['source_label'][positions]
        full = rank_measure(count, labels)
        n0, n1 = int(np.sum(labels == 0)), int(np.sum(labels == 1)); held = []
        for repeat in range(60):
            row = dict(unit_key=key, repeat=repeat)
            if min(n0, n1) < 4:
                row.update(status='insufficient_class_support', n_train_new=None, n_train_old=None,
                    n_test_new=None, n_test_old=None, train_u_old_twice=None, train_auc_old=None,
                    train_p=None, train_selected=False, train_preferred_sign=None, test_u_old_twice=None,
                    test_auc_old=None, test_directed_auc=None, included_in_conditional_summary=False)
            else:
                train = ref['train_membership'][repeat, positions]; test = ~train
                a = rank_measure(count[train], labels[train])
                test_u2 = doubled_u(count[test & (labels == 1)], count[test & (labels == 0)])
                nt0, nt1 = int(np.sum(labels[test] == 0)), int(np.sum(labels[test] == 1))
                require(test_u2 is not None, 'Missing class in held-out partition')
                test_auc = test_u2/(2*nt0*nt1)
                directed = test_auc if a['preferred_sign'] == 1 else 1-test_auc
                row.update(status='ok', n_train_new=int(np.sum(labels[train] == 0)),
                    n_train_old=int(np.sum(labels[train] == 1)), n_test_new=nt0, n_test_old=nt1,
                    train_u_old_twice=a['u_old_twice'], train_auc_old=a['auc_old'], train_p=a['p'],
                    train_selected=a['selected'], train_preferred_sign=a['preferred_sign'],
                    test_u_old_twice=test_u2, test_auc_old=test_auc, test_directed_auc=directed,
                    included_in_conditional_summary=a['selected'])
                if a['selected']:
                    held.append(directed)
            events.append(row)
        neurons.append(dict(unit_key=key, asset_path=source['asset_path'],
            subject_id=sessions[source['asset_path']]['subject_id'], unit_id=source['unit_id'],
            region=source['region'], n_trials=n0+n1, n_new=n0, n_old=n1, full_status=full['status'],
            u_old_twice=full['u_old_twice'], auc_old=full['auc_old'], full_p=full['p'],
            preferred_sign=full['preferred_sign'], same_trial_auc=full['same_trial_auc'],
            memory_selective=full['selected'], n_usable_splits=60 if min(n0, n1) >= 4 else 0,
            n_selected_splits=len(held), conditional_auc=math.fsum(held)/len(held) if held else None,
            conditional_status='defined' if held else 'no_selected_splits', heldout_eligible=len(held) >= 5))
    calculated = dict(neurons=neurons, split_events=events)
    ref['_analysis_cache'] = (fingerprint, calculated)
    return calculated


def summarize(ref, neurons, headline):
    require(headline in POPULATIONS, 'Unknown headline population')
    populations = {}
    same = [r['same_trial_auc'] for r in neurons if r['memory_selective']]
    conditional = [r['conditional_auc'] for r in neurons if r['heldout_eligible']]
    for name, values in zip(POPULATIONS, (same, conditional)):
        require(all(v is not None and math.isfinite(v) and 0 <= v <= 1 for v in values), 'Invalid included AUC')
        populations[name] = dict(n_units=len(values), mean_auc=math.fsum(values)/len(values) if values else None,
                                 status='defined' if values else 'empty_population')
    overlap = dict(full_only=0, conditional_only=0, both=0, neither=0)
    for row in neurons:
        key = ('both' if row['heldout_eligible'] else 'full_only') if row['memory_selective'] else (
            'conditional_only' if row['heldout_eligible'] else 'neither')
        overlap[key] += 1
    return dict(status='complete', task_id='MTLMEMORY-001', headline_population=headline,
        headline_status=populations[headline]['status'], memory_selective_new_old_auc=populations[headline]['mean_auc'],
        n_sessions=len(ref['sessions']), n_patients=len({r['subject_id'] for r in ref['sessions']}),
        n_source_units=len(ref['units']), n_mtl_units=len(neurons),
        n_full_test_defined=sum(r['full_status'] == 'ok' for r in neurons),
        n_full_test_undefined=sum(r['full_status'] != 'ok' for r in neurons),
        n_memory_selective=len(same), proportion_memory_selective=len(same)/len(neurons) if neurons else None,
        n_crossfit_eligible=len(conditional), n_response_rows=len(ref['spike_count']), n_split_events=60*len(neurons),
        populations=populations, population_overlap=overlap)
