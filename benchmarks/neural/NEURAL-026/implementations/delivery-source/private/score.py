"""Arbitrary-artifact scorer for the predeclared controlled reconstruction.

All 50 candidate files are admitted before any private target/reference read.
This is not proof of execution, input dependence, or access-arm compliance.
No real-data score has been calculated during package construction.
"""
import argparse
import itertools
from pathlib import Path
import re
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'public'))
import protocol as p
from common import need, save_json
from array_io import capture, identity, arrays, fresh_output, metadata

KEYS = {'trial_id', *p.ARMS}
FILE_CAP = 128 * 1024**2
TOTAL_CAP = 2 * 1024**3


def regular_path(root, name):
    need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_-]+\.npz', name) is not None,
         'Fixed flat NPZ basename')
    path = Path(root) / name
    need(all(not x.is_symlink() for x in (path, *path.parents)), 'No linked files or ancestors')
    return path


def file_identity(path):
    return identity(capture(path, FILE_CAP))


def predictions(v, expected):
    need(set(v) == KEYS, 'Exactly IDs and all three prediction arms')
    ids = v['trial_id']
    need(ids.dtype.kind in 'iu' and ids.ndim == 1 and np.array_equal(ids, expected),
         'Complete frozen query ID order')
    for arm in p.ARMS:
        a = v[arm]
        need(a.dtype.kind == 'f' and a.dtype.itemsize in (4, 8)
             and a.shape == (len(ids), 51, 24) and np.isfinite(a).all(),
             'Complete finite 24-joint trajectories for every arm')
    return {'trial_id': ids, **{a: v[a].astype(np.float64, copy=False) for a in p.ARMS}}


def admit_submission(folder, design):
    p.validate_design(design)
    m = metadata(folder / 'submission.json')
    need(type(m) is dict and set(m) == {'schema', 'cases'} and m['schema'] == 'neural026_submission_v1'
         and type(m['cases']) is list and len(m['cases']) == 50, 'Exact submission schema')
    need({f.name for f in folder.iterdir()} == {'submission.json', *[c + '.npz' for c in p.case_ids()]},
         'No missing/extra artifacts')
    admitted, total = {}, 0
    for row, case in zip(m['cases'], design['cases']):
        cid = case['case_id']
        need(type(row) is dict and set(row) == {'case_id', 'file', 'bytes', 'sha256'}
             and row['case_id'] == cid and row['file'] == cid + '.npz'
             and type(row['bytes']) is int and 0 < row['bytes'] <= FILE_CAP
             and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
             'Exact case/file identity and typed byte/hash descriptor')
        path = regular_path(folder, row['file'])
        raw = capture(path, FILE_CAP); ident = identity(raw)
        need(ident == {k: row[k] for k in ('bytes', 'sha256')}, 'Candidate bytes authenticate')
        total += ident['bytes']; need(total <= TOTAL_CAP, 'Aggregate submission cap')
        predictions(arrays(raw, KEYS, FILE_CAP), case['query_id'])
        admitted[cid] = ident
    return admitted


def moments_add(state, y):
    """Stable pooled query variance, across all folds once, never per-fold pseudo-replicates."""
    a = np.asarray(y, dtype=np.float64).reshape(-1, 24)
    with np.errstate(over='raise', invalid='raise'):
        n = len(a); mean = a.mean(axis=0); m2 = ((a - mean)**2).sum(axis=0)
    if state is None:
        return n, mean, m2
    old, mu, s = state
    with np.errstate(over='raise', invalid='raise'):
        delta = mean - mu
        return old + n, mu + delta * (n / (old + n)), s + m2 + delta**2 * old * n / (old + n)


def effect(sse, sst):
    need(np.isfinite(sst).all() and (sst > 0).all(),
         'Every prespecified joint has positive pooled query variance; do not drop targets')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        result = (sse['nuisance'] - sse['neural']) / sst
    need(np.isfinite(result).all(), 'Finite dimensionless effect')
    return result


def paired_summary(values):
    x = np.asarray(values, dtype=float)
    need(x.shape == (5,) and np.isfinite(x).all(), 'Five biological paired units')
    with np.errstate(over='raise', invalid='raise'):
        mean = float(x.mean())
        half = float(2.7764451051977987 * x.std(ddof=1) / np.sqrt(5.))
        observed = abs(float(x.sum()))
        permutations = [abs(float((x * signs).sum())) for signs in itertools.product((-1, 1), repeat=5)]
    # Exact finite sign-flip descriptive p. Exchangeability is an assumption, not established.
    exact_p = sum(v >= observed for v in permutations) / 32.
    need(np.isfinite([mean-half, mean+half]).all(), 'Representable interval endpoints')
    return dict(mouse_values=x.tolist(), mean=mean, descriptive_t95=[mean-half, mean+half],
                exact_two_sided_signflip_p=exact_p, independent_units=5)


def holm(values):
    v = np.asarray(values, dtype=float)
    need(v.shape == (24,) and np.isfinite(v).all() and ((0 <= v) & (v <= 1)).all(), '24 p values')
    order = np.argsort(v, kind='stable'); result = np.empty(24); running = 0.
    for rank, index in enumerate(order):
        running = max(running, (24-rank) * v[index])
        result[index] = min(1., running)
    return result.tolist()


@np.errstate(over='raise', invalid='raise', divide='raise')
def evaluate(folder, design, private_loader):
    admitted = admit_submission(folder, design)  # no private callback before complete admission
    cells = {}
    for case in design['cases']:
        cid = case['case_id']; path = regular_path(folder, cid + '.npz')
        raw = capture(path, FILE_CAP)
        need(identity(raw) == admitted[cid], 'Candidate unchanged after complete admission')
        c = predictions(arrays(raw, KEYS, FILE_CAP), case['query_id'])
        target, reference = private_loader(cid)
        need(set(target) == {'trial_id', 'y'} and target['trial_id'].dtype.kind in 'iu'
             and np.array_equal(target['trial_id'], case['query_id'])
             and target['y'].dtype.kind == 'f' and target['y'].dtype.itemsize in (4, 8)
             and target['y'].shape == (len(case['query_id']), 51, 24)
             and np.isfinite(target['y']).all(), 'Exact complete private joint targets')
        r = predictions(reference, case['query_id'])
        key = (case['mouse'], case['area'])
        cell = cells.setdefault(key, dict(moments=None, candidate={a: np.zeros(24) for a in p.ARMS},
                      reference={a: np.zeros(24) for a in p.ARMS}, parity={a: np.zeros(24) for a in p.ARMS}))
        y = target['y'].astype(np.float64, copy=False)
        cell['moments'] = moments_add(cell['moments'], y)
        with np.errstate(over='raise', invalid='raise'):
            for arm in p.ARMS:
                cell['candidate'][arm] += ((c[arm]-y)**2).sum(axis=(0, 1))
                cell['reference'][arm] += ((r[arm]-y)**2).sum(axis=(0, 1))
                cell['parity'][arm] += ((c[arm]-r[arm])**2).sum(axis=(0, 1))
    effects, reference_effects, detail, errors = {}, {}, [], []
    for mouse in p.MICE:
        for area in p.AREAS:
            cell = cells[mouse, area]; n, _, sst = cell['moments']
            ce, re = effect(cell['candidate'], sst), effect(cell['reference'], sst)
            effects[mouse, area], reference_effects[mouse, area] = ce, re
            errors.extend(np.abs(ce-re).tolist())
            detail.append(dict(mouse=mouse, area=area, query_samples=n,
                incremental_explained_variance_by_joint=ce.tolist(),
                reference_incremental_by_joint=re.tolist(),
                reconstruction_absolute_error_by_joint=np.abs(ce-re).tolist(),
                neural_vs_shifted_increment_by_joint=((cell['candidate']['shifted']-cell['candidate']['neural'])/sst).tolist(),
                r2_by_arm={a: (1-cell['candidate'][a]/sst).tolist() for a in p.ARMS},
                prediction_rmse_to_reference_by_arm={a: np.sqrt(cell['parity'][a]/n).tolist() for a in p.ARMS}))
    area_difference = np.stack([effects[m, 'S1']-effects[m, 'M1'] for m in p.MICE])
    reference_difference = np.stack([reference_effects[m, 'S1']-reference_effects[m, 'M1'] for m in p.MICE])
    joints = [paired_summary(area_difference[:, j]) for j in range(24)]
    adjusted = holm([x['exact_two_sided_signflip_p'] for x in joints])
    for x, adj in zip(joints, adjusted): x['holm24_p'] = adj
    return dict(schema='neural026_grade_v1', complete_cases=50, independent_mice=5,
        primary_metric='equal_mouse_area_joint_incremental_EV_reconstruction_MAE',
        primary_value=float(np.mean(errors)), direction='lower', binary_pass=None,
        biological_effects=detail,
        paired_area_difference=paired_summary(area_difference.mean(axis=1)),
        paired_area_by_joint=joints,
        paired_area_reconstruction_MAE=float(np.abs(area_difference-reference_difference).mean()),
        runtime_verified=False, execution_proven=False, causal_claim=False,
        historical_fig5_reproduction=False, research_qualified=False)


def main():
    q = argparse.ArgumentParser(description=__doc__)
    q.add_argument('--submission', type=Path, required=True)
    q.add_argument('--design', type=Path, required=True)
    q.add_argument('--private-root', type=Path, required=True)
    q.add_argument('--binding', type=Path, required=True)
    q.add_argument('--output', type=Path, required=True)
    a = q.parse_args(); fresh_output(a.output)
    design = metadata(a.design); binding = metadata(a.binding)
    need(binding['schema'] == 'neural026_private_binding_v1'
         and set(binding['cases']) == set(p.case_ids()), 'All sealed targets and reference predictions')
    def loader(cid):
        out = []
        for role, keys in (('target', {'trial_id', 'y'}), ('reference', KEYS)):
            row = binding['cases'][cid][role]
            path = regular_path(a.private_root, row['file'])
            raw = capture(path, FILE_CAP)
            need(identity(raw) == {k: row[k] for k in ('bytes', 'sha256')}, 'Trusted private identity')
            out.append(arrays(raw, keys, FILE_CAP))
        return out
    save_json(a.output, evaluate(a.submission, design, loader))


if __name__ == '__main__':
    main()
