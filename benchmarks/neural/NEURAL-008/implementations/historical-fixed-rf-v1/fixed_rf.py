"""One fixed training-only RF fit; identical program in both physical views."""
import io
import hashlib
import json
from pathlib import Path
import time
import zipfile
import numpy as np

PARAMETERS = dict(n_estimators=100, criterion='gini', max_depth=None,
    min_samples_split=2, min_samples_leaf=5, min_weight_fraction_leaf=0.,
    max_features=1.0, max_leaf_nodes=None, min_impurity_decrease=0.,
    bootstrap=True, oob_score=False, n_jobs=2, random_state=241, verbose=0,
    warm_start=False, class_weight='balanced', ccp_alpha=0., max_samples=None,
    monotonic_cst=None)
CLASSES = ('W', 'N1', 'N2', 'N3', 'R')
TRAIN = tuple('train-%03d' % i for i in range(1, 7))
DEV = ('development-001', 'development-002')
COUNTS = (2630, 2740, 2690, 2740, 2740, 2750, 2780, 2670)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def arrays(path, keys, cap=1_000_000):
    body = path.read_bytes()
    need(0 < len(body) <= cap, 'Bounded pinned ordinary input')
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = archive.infolist()
        need(len(rows) == len(keys) and {r.filename for r in rows} == {k+'.npy' for k in keys} and
             all(r.compress_type == zipfile.ZIP_STORED and r.file_size <= cap and not r.flag_bits & 1 for r in rows),
             'Exact stored arrays, no hidden members')
    with np.load(io.BytesIO(body), allow_pickle=False, max_header_size=4096) as source:
        return {k: source[k] for k in keys}


def checked_view(case, n, width, a):
    ids, x = a['epoch_id'], a['X']
    expected = np.asarray([f'{case}/{i:05d}' for i in range(n)])
    need(set(a) == {'epoch_id', 'X'} and ids.shape == (n,) and ids.dtype.kind == 'U' and
         np.array_equal(ids, expected) and x.dtype == np.dtype('float64') and x.shape == (n, width) and
         x.flags.c_contiguous and np.isfinite(x).all(), 'Complete exact physical feature view')
    return ids, x


def fit_one(factory, x, y, mask):
    need(x.ndim == 2 and x.shape[1] in (15, 21) and x.shape[0] == len(y) and
         np.isfinite(x).all() and y.dtype.kind in 'iu' and mask.dtype.kind == 'b' and
         mask.shape == y.shape and np.isin(y, [-1, 0, 1, 2, 3, 4]).all() and
         np.array_equal(mask, y >= 0) and len(np.unique(y[mask])) >= 2,
         'Same finite pooled training rows and declared unknown mask')
    model = factory(**PARAMETERS)
    model.fit(x[mask], y[mask])
    return model


def probabilities(model, x):
    native = model.predict_proba(x); classes = np.asarray(model.classes_)
    need(classes.ndim == 1 and classes.dtype.kind in 'iu' and len(np.unique(classes)) == len(classes) and
         np.isin(classes, np.arange(5)).all() and native.shape == (len(x), len(classes)) and
         np.isfinite(native).all() and np.all((native >= 0) & (native <= 1)) and
         np.allclose(native.sum(1), 1, rtol=0, atol=1e-10), 'Fixed five-class probability mapping')
    answer = np.zeros((len(x), 5), dtype=np.float64); answer[:, classes] = native
    return answer


def main():
    from sklearn.ensemble import RandomForestClassifier
    import sklearn
    started = time.monotonic(); cpu = time.process_time()
    root = Path('/input'); manifest = json.loads((root/'manifest.json').read_text())
    width = manifest['feature_count']
    need(width in (15, 21) and manifest['classes'] == list(CLASSES), 'Frozen physical representation')
    need(manifest['training'] == [{'case_id': c, 'epochs': n} for c,n in zip(TRAIN, COUNTS[:6])] and
         manifest['development'] == [{'case_id': c, 'epochs': n} for c,n in zip(DEV, COUNTS[6:])], 'Fixed people and source order')
    allowed = {'manifest.json'} | {c+'_features.npz' for c in TRAIN+DEV} | {c+'_labels.npz' for c in TRAIN}
    need({p.name for p in root.iterdir()} == allowed, 'Only physical view and six training labels')
    files = manifest['files']
    need(len(files)==14 and {r['filename'] for r in files}==allowed-{'manifest.json'}, 'Exact view file identity roster')
    for row in files:
        body=(root/row['filename']).read_bytes()
        need(0<len(body)<=1_000_000 and len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],
             'Candidate consumes the exact physically released input bytes')
    xs, ys, masks = [], [], []
    query = {}
    for case, n in zip(TRAIN+DEV, COUNTS):
        ids, x = checked_view(case, n, width, arrays(root/(case+'_features.npz'), ('epoch_id','X')))
        if case in TRAIN:
            target = arrays(root/(case+'_labels.npz'), ('epoch_id','stage','score_mask'))
            need(np.array_equal(target['epoch_id'], ids) and target['stage'].shape == (n,) and
                 target['score_mask'].shape == (n,) and target['score_mask'].any(), 'Whole-person label identity')
            xs.append(x); ys.append(target['stage']); masks.append(target['score_mask'])
        else:
            query[case] = (ids, x)
    x = np.concatenate(xs); y = np.concatenate(ys); mask = np.concatenate(masks)
    before = time.monotonic(); before_cpu = time.process_time()
    model = fit_one(RandomForestClassifier, x, y, mask)
    fit_wall = time.monotonic()-before; fit_cpu = time.process_time()-before_cpu
    values = {'class_order': np.asarray(CLASSES)}
    for case, (ids, features) in query.items():
        values[case+'__epoch_id'] = ids
        values[case+'__probabilities'] = probabilities(model, features)
    np.savez('/output/predictions.npz', **values)
    print(json.dumps({'status':'one_fixed_rf_fit_complete', 'fit_count':1, 'hyperparameter_trials':0,
        'feature_count':width, 'training_rows':len(y), 'scored_rows':int(mask.sum()),
        'masked_rows':int((~mask).sum()), 'stage_counts':np.bincount(y[mask],minlength=5).tolist(),
        'parameters':PARAMETERS, 'fit_wall_seconds':fit_wall, 'fit_cpu_seconds':fit_cpu,
        'wall_seconds':time.monotonic()-started, 'cpu_seconds':time.process_time()-cpu,
        'numpy':np.__version__, 'sklearn':sklearn.__version__}, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
