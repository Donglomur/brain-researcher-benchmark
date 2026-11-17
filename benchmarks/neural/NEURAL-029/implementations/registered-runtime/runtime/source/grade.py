"""Operator-only scorer for the prepared NEURAL029 interchange packet."""
import argparse
import io
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
import io_utils as safe


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'binding', 'submission', 'output'):
        ap.add_argument('--' + name, required=True)
    a = ap.parse_args()
    import numpy as np
    binding = safe.strict(safe.read(a.binding, 2000000))
    safe.need(set(binding) == {'schema', 'public', 'private', 'identity'} and binding['schema'] == 'neural029-binding-v2',
              'trusted operator binding')
    public = safe.strict(safe.captured(a.root, binding['public'], 2000000))
    submission = safe.strict(safe.read(a.submission, 100000000))
    def private():
        meta = safe.strict(safe.captured(a.root, binding['private'], 2000000))
        safe.need(set(meta) == {'schema', 'pairs'} and meta['schema'] == 'neural029-targets-v2', 'private schema')
        identity = safe.strict(safe.captured(a.root, binding['identity'], 2000000))
        rows = []
        for t in meta['pairs']:
            safe.need(set(t) == {'pair_id', 'mouse_id', 'file', 'training_scale_squared'}, 'private record')
            raw = safe.captured(a.root, t['file'], 100000000)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                infos = z.infolist()
                safe.need({x.filename for x in infos} == {'target.npy', 'baseline.npy', 'fixed_warp_baseline.npy'} and len(infos) == 3
                          and sum(x.file_size for x in infos) <= 200000000, 'bounded target archive')
            with np.load(io.BytesIO(raw), allow_pickle=False) as z:
                y, base, warp = z['target'], z['baseline'], z['fixed_warp_baseline']
            safe.need(y.dtype == base.dtype == warp.dtype == np.dtype('float64'), 'exact float64 labels')
            rows.append({k: v for k, v in t.items() if k != 'file'} | {'target': y, 'baseline': base, 'fixed_warp_baseline': warp})
        return {'pairs': rows, 'identity': identity}
    safe.write_new(a.output, core.grade(submission, public, private, np), 2000000)


if __name__ == '__main__':
    main()
