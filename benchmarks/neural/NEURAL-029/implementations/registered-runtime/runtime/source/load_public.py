"""Read source-condition calcium only; no private targets or models."""
import io
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import io_utils as safe


def load(root, np):
    root = Path(root)
    m = safe.strict(safe.read(root / 'public/MANIFEST.json', 2000000))
    safe.need(set(m) == {'schema', 'time_seconds', 'pairs'} and m['schema'] == 'neural029-public-v1'
              and m['time_seconds'] == [i / 20 for i in range(61)] and m['pairs'], 'public manifest schema')
    result = []
    for p in m['pairs']:
        safe.need(set(p) == {'pair_id', 'cell_ids', 'query_ids', 'source_delay_seconds', 'target_delay_seconds',
                  'reward_type', 'calibration_trials', 'validation_trials', 'file'}
                  and p['source_delay_seconds'] == 1 and p['target_delay_seconds'] == 2
                  and p['reward_type'] in ('DAT', 'MFB') and p['file']['path'] == 'public/' + p['pair_id'] + '.npz',
                  'exact pair context and source-only path')
        raw = safe.captured(root, p['file'], 70000000)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            items = z.infolist()
            safe.need(len(items) == 2 and {i.filename for i in items} == {'calibration.npy', 'validation.npy'}
                      and sum(i.file_size for i in items) <= 200000000, 'bounded source-condition archive')
        with np.load(io.BytesIO(raw), allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        for k in ('calibration', 'validation'):
            x = arrays[k]
            safe.need(x.dtype == np.dtype('float64') and x.shape == (p[k + '_trials'], len(p['cell_ids']), 61)
                      and np.isfinite(x).all(), 'finite complete public arrays')
        result.append({'metadata': p, **arrays})
    safe.need(len({p['pair_id'] for p in m['pairs']}) == len(result), 'unique pair identities')
    return m, result
