"""Project a complete trusted Filio raw interchange; no fits or empirical scores."""
import argparse
import hashlib
import hmac
import io
import json
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import io_utils as safe
from source_identity_join import validate_source_index, bind_public_identity
from timing import fixed_warp_mean


def interpolate(x, t, np):
    grid = np.arange(61, dtype=np.float64) / 20
    safe.need(t.ndim == 1 and len(t) == x.shape[2] and np.isfinite(t).all()
              and (np.diff(t) > 0).all() and t[0] <= 0 and t[-1] >= 3, 'full native clock support')
    y = np.empty((x.shape[0], x.shape[1], 61), dtype=np.float64)
    for trial in range(x.shape[0]):
        for cell in range(x.shape[1]):
            y[trial, cell] = np.interp(grid, t, x[trial, cell])
    return y


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--index-sha256', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    import numpy as np
    safe.need(np.__version__ == '2.2.6', 'NumPy2.2.6')
    src, out = Path(a.source_root), Path(a.output)
    raw = safe.read(src / 'INDEX.json', 2000000)
    safe.need(hashlib.sha256(raw).hexdigest() == a.index_sha256, 'root-selected complete source index')
    index = safe.strict(raw)
    validate_source_index(index)  # Before raw array reads, key creation or output effects.
    safe.need(set(index) == {'schema', 'source_record', 'complete_selected_cohort', 'source_part_count',
              'source_session_count', 'selected_target_session_indices1', 'cohort_dispositions', 'pairs', 'scientific_fits',
              'scientific_scores'} and index['schema'] == 'neural029-raw-projection-v2'
              and index['source_record'] == '21645651' and index['complete_selected_cohort'] is True
              and index['source_part_count'] == 2 and index['scientific_fits'] == index['scientific_scores'] == 0,
              'exact complete unscored two-part projection')
    pairs = index['pairs']; selected = index['selected_target_session_indices1']
    safe.need(type(pairs) is list and pairs and type(selected) is list and
              len(set(selected)) == len(selected) == len(pairs)
              and [r['target_session_index1'] for r in pairs] == selected, 'complete source cohort join')
    safe.need(sum(r[k]['bytes'] for r in pairs for k in ('source_file', 'target_file')) <= 150000000,
              'complete raw projection bound')
    safe.need(not out.exists(), 'fresh output directory')
    out.mkdir(); (out / 'public').mkdir(); (out / 'private').mkdir()
    salt = secrets.token_bytes(32)
    (out / 'private/ID_KEY.bin').write_bytes(salt); (out / 'private/ID_KEY.bin').chmod(0o400)
    def token(kind, value):
        return hmac.new(salt, (kind + '|' + str(value)).encode(), hashlib.sha256).hexdigest()
    used = 32
    def write_npz(path, **arrays):
        nonlocal used
        buffer = io.BytesIO(); np.savez_compressed(buffer, **arrays); raw = buffer.getvalue()
        safe.need(used + len(raw) <= 70000000, 'whole packet bound; no cohort shrinking')
        with path.open('xb') as f:
            f.write(raw)
        path.chmod(0o444); used += len(raw)
        return {'path': str(path.relative_to(out)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    public = {'schema': 'neural029-public-v1', 'time_seconds': [i / 20 for i in range(61)], 'pairs': []}
    targets = {'schema': 'neural029-targets-v2', 'pairs': []}
    for r in pairs:
        safe.need(set(r) == {'pair_index1', 'source_session_index1', 'target_session_index1', 'mouse_id',
                  'reward_type', 'source_cells_index1', 'target_cells_index1', 'source_shape', 'target_shape',
                  'source_time_seconds', 'target_time_seconds', 'source_file', 'target_file',
                  'registration_rows_source_target'}, 'exact raw pair')
        safe.need(r['reward_type'] in ('DAT', 'MFB') and type(r['mouse_id']) is str and r['mouse_id'], 'planned reward context')
        arrays = []
        for side in ('source', 'target'):
            shape = r[side + '_shape']; cells = np.atleast_1d(r[side + '_cells_index1'])
            safe.need(type(shape) is list and len(shape) == 3 and all(type(v) is int and v > 0 for v in shape)
                      and cells.dtype.kind in 'iu' and len(np.unique(cells)) == len(cells) == shape[1]
                      and (cells > 0).all() and shape[2] >= 2, 'complete registered trial-cell-time geometry')
            body = safe.captured(src, r[side + '_file'], 150000000)
            safe.need(len(body) == 8 * int(np.prod(shape)), 'exact binary size')
            x = np.frombuffer(body, dtype='<f8').reshape(shape)
            safe.need(np.isfinite(x).all(), 'nonfinite required values are a preparation blocker')
            arrays.append(interpolate(x, np.asarray(r[side + '_time_seconds'], dtype=np.float64), np))
        train, query = arrays
        safe.need(train.shape[1:] == query.shape[1:] and len(train) >= 5 and len(query) > 0, 'full paired data')
        pair_id = token('pair', r['pair_index1']); nc = train.shape[1]; split = 4 * len(train) // 5
        train_pin = write_npz(out / 'public' / (pair_id + '.npz'), calibration=train[:split], validation=train[split:])
        with np.errstate(over='raise', invalid='raise'):
            baseline = train.mean(axis=0)
            scale = float(np.mean((train - train.mean(axis=(0, 2), keepdims=True)) ** 2))
        safe.need(np.isfinite(baseline).all() and np.isfinite(scale), 'representable train-only normalization')
        fixed_warp = fixed_warp_mean(baseline, public['time_seconds'], public['time_seconds'], np)
        target_pin = write_npz(out / 'private' / (pair_id + '.npz'), target=query, baseline=baseline, fixed_warp_baseline=fixed_warp)
        public['pairs'].append({'pair_id': pair_id, 'cell_ids': [token('cell', pair_id + str(c)) for c in range(nc)],
            'query_ids': [token('query', pair_id + str(t)) for t in range(len(query))],
            'source_delay_seconds': 1, 'target_delay_seconds': 2, 'reward_type': r['reward_type'],
            'calibration_trials': split, 'validation_trials': len(train) - split, 'file': train_pin})
        targets['pairs'].append({'pair_id': pair_id, 'mouse_id': r['mouse_id'],
            'file': target_pin, 'training_scale_squared': scale})
    identity_pin = safe.write_new(out / 'private/IDENTITY_MAP.json',
        bind_public_identity(index, public, a.index_sha256), 2000000)
    pub_pin = safe.write_new(out / 'public/MANIFEST.json', public, 2000000)
    private_pin = safe.write_new(out / 'private/TARGETS.json', targets, 2000000)
    safe.write_new(out / 'private/BINDING.json', {'schema': 'neural029-binding-v2',
        'public': {'path': 'public/MANIFEST.json', **pub_pin},
        'private': {'path': 'private/TARGETS.json', **private_pin},
        'identity': {'path': 'private/IDENTITY_MAP.json', **identity_pin}}, 4096)
    safe.write_new(out / 'PREPARATION_RECEIPT.json', {'schema': 'neural029-preparation-v2',
        'source_index_sha256': a.index_sha256, 'pairs': len(pairs), 'complete_cohort': True,
        'source_record': '21645651', 'model_fits': 0, 'empirical_scores': 0,
        'public_manifest': pub_pin, 'private_metadata': private_pin,
        'scientific_execution_qualified': False, 'submission_ready': False,
        'private_identity_inverse': {'path': 'private/IDENTITY_MAP.json', **identity_pin}}, 8192)


if __name__ == '__main__':
    main()
