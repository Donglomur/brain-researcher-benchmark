"""Load only the supplied public calibration/validation observations."""
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import io_utils as safe


def load(folder, np):
    folder = Path(folder)
    manifest = safe.strict(safe.read(folder / 'MANIFEST.json', 2000000))
    safe.need(set(manifest) == {'schema', 'sessions'} and manifest['schema'] == 'neural035-public-v1'
              and len(manifest['sessions']) == 14, 'complete public cohort')
    result = []
    for row in manifest['sessions']:
        safe.need(set(row) == {'session_id', 'cell_ids', 'file', 'bytes', 'sha256',
                  'calibration_starts_seconds', 'validation_starts_seconds', 'queries'}
            and row['file'] == row['session_id'] + '.npz' and len(row['cell_ids']) >= 2
            and len(set(row['cell_ids'])) == len(row['cell_ids']), 'public phase-only schema')
        raw = safe.captured(folder, {'path': row['file'], 'bytes': row['bytes'],
                                   'sha256': row['sha256']}, 20000000)
        n = len(row['cell_ids'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            info = archive.infolist()
            safe.need(len(info) == 2 and {r.filename for r in info} == {'calibration.npy', 'validation.npy'}
                and all(not r.flag_bits & 1 for r in info)
                and sum(r.file_size for r in info) <= 1500 * n * 8 + 4096,
                'bounded exact public archive, no query arrays')
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            arrays = {k: archive[k] for k in archive.files}
        for name, blocks in [('calibration', 4), ('validation', 1)]:
            x = arrays[name]
            safe.need(x.dtype == np.dtype('float64') and x.shape == (blocks, 300, n)
                      and np.isfinite(x).all(), 'exact finite public trace geometry')
        result.append({'metadata': row, **arrays})
    safe.need(len({x['metadata']['session_id'] for x in result}) == 14
              and len({q['query_id'] for s in result for q in s['metadata']['queries']}) == 28,
              'complete unique session/query identities')
    return result
