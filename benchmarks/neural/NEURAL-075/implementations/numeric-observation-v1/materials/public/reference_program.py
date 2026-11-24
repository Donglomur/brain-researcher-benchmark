"""Prospective fixed ridge reference SOURCE. Not historical sparse regression.

No fitting occurs on import. Generated tests do not call fit_predict/main.
"""
import argparse
from pathlib import Path
import numpy as np
from delivery_io import need, read, decode, pin, put
from array_io import arrays, fresh_output
from protocol import VERSION


def correlations(pred, bank):
    pred = np.asarray(pred, dtype=np.float64); bank = np.asarray(bank, dtype=np.float64)
    a = pred - pred.mean(axis=1, keepdims=True)
    b = bank - bank.mean(axis=1, keepdims=True)
    den = np.linalg.norm(a, axis=1)[:, None] * np.linalg.norm(b, axis=1)[None, :]
    out = np.zeros((len(a), len(b)), dtype=np.float64)
    np.divide(a @ b.T, den, out=out, where=den > 0)
    need(np.all(np.isfinite(out)), 'Finite Pearson similarities; constant vector maps0')
    return np.clip(out, -1, 1)


def fit_predict(x, y, query):
    # All transforms/voxel selection use perception support only, refit for
    # each permuted control. No perception-test/imagery response selection.
    x, y, query = [np.asarray(a, dtype=np.float64) for a in (x, y, query)]
    need(all(np.all(np.isfinite(a)) for a in (x, y, query)), 'Finite fixed reference inputs')
    xm, xs = x.mean(0), x.std(0, ddof=1)
    ym, ys = y.mean(0), y.std(0, ddof=1)
    xs[xs == 0] = 1; ys[ys == 0] = 1
    xx, yy = (x - xm) / xs, (y - ym) / ys
    relevance = np.mean((xx.T @ yy / (len(x) - 1)) ** 2, axis=1)
    # Shared top1000, not the paper's separately selected voxels per unit.
    cols = np.argsort(-relevance, kind='stable')[:min(1000, x.shape[1])]
    z = xx[:, cols]
    coefficient = np.linalg.solve(z.T @ z + np.eye(len(cols)), z.T @ yy)
    return (((query - xm) / xs)[:, cols] @ coefficient) * ys + ym


def main():
    p = argparse.ArgumentParser(); p.add_argument('--input', required=True)
    p.add_argument('--output', required=True); a = p.parse_args()
    fresh_output(a.output); root = Path(a.input)
    raw = read(root / 'case.json', 2**20); case = decode(raw)
    need(case['protocol'] == VERSION, 'Fixed protocol')
    keys = ['train_y', 'bank', 'groups', 'runs']
    if case['arm'] != 'no_neural': keys += ['train_x', 'query_x']
    data = arrays(read(root / case['inputs']['path'], 512 * 2**20,
                       {k: case['inputs'][k] for k in ('bytes', 'sha256')}), keys, 512 * 2**20)
    if case['arm'] == 'no_neural':
        decoded = np.tile(data['train_y'].mean(0), (len(case['trial_ids']), 1))
    else:
        decoded = fit_predict(data['train_x'], data['train_y'], data['query_x'])
    scores = correlations(decoded, data['bank'])
    put(a.output, {'protocol': VERSION, 'case_id': case['case_id'], 'context_sha256': pin(raw)['sha256'],
                   'categories': case['categories'], 'trial_ids': case['trial_ids'], 'scores': scores.tolist()}, 4 * 2**20)


if __name__ == '__main__': main()
