"""Generated NPY -> existing corpus loader -> viewer compatibility control.

No scientific execution. --programme-root must name the trusted existing
implementation-v1/program source; --scratch-parent is an explicit writable area.
"""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--programme-root', type=Path, required=True)
    parser.add_argument('--scratch-parent', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.programme_root))
    from core import Budget, encoded, pin
    from arrays import header
    from corpus import load_session
    import numpy as np
    spec = importlib.util.spec_from_file_location('viewer', Path(__file__).resolve().parents[1] / 'viewer.py')
    viewer = importlib.util.module_from_spec(spec); spec.loader.exec_module(viewer)
    start = time.monotonic(); budget = Budget(start, start + 30, 2**20, 2**20)
    generated_write_bytes = 0
    with tempfile.TemporaryDirectory(prefix='neural058-generated-', dir=args.scratch_parent) as temp:
        root = Path(temp)
        values = {'times': np.array([0., .25, .75]), 'time_offsets': np.array([0, 3], dtype='<i8'),
                  'locations': np.array([[0., 1., 2.], [3., 0., 5.]]),
                  'location_missing': np.array([[False, False, False], [False, True, False]]),
                  'spike_times': np.array([0., 0., .25, .25, .75]),
                  'spike_units': np.array([0, 0, 1, 1, 0], dtype='<i8'),
                  'spike_offsets': np.array([0, 5], dtype='<i8'),
                  'neural_domain': np.array([[0., .4], [.6, 1.]]),
                  'domain_offsets': np.array([0, 2], dtype='<i8')}
        descriptors = {}
        for name, value in values.items():
            stream = io.BytesIO(); np.save(stream, value, allow_pickle=False); raw = stream.getvalue()
            path = root / (name + '.npy'); path.write_bytes(raw); path.chmod(0o400)
            generated_write_bytes += len(raw)
            descriptors[name] = {'path': path.name, 'pin': pin(raw), 'array': header(raw, 2**20)}
        sessions, required = [], []
        for i in range(29):
            identity = {'session': f'{i + 1:032x}', 'animal': f'{100 + i % 13:032x}',
                        'session_ordinal': i, 'animal_ordinal': i % 13}
            required.append(identity)
            doc = {**identity, 'schema': 'neural058_role_session_v1', 'task': 'NEURAL-058',
                   'access': 'J', 'corpus_role': 'evaluation', 'fold': None,
                   'windows': [{'query': f'{1000 + i:032x}', 'context': [1., None, .5], 'support': [0., 1.]}],
                   'regions': ['VISp', 'MOp'], 'arrays': descriptors}
            raw = encoded(doc); path = root / f'{i}.json'; path.write_bytes(raw); path.chmod(0o400)
            generated_write_bytes += len(raw)
            sessions.append(load_session(root, {'path': path.name, 'pin': pin(raw)}, 'J', False, budget,
                                         {'metadata_bytes': 10000, 'array_bytes': 10000,
                                          'expanded_bytes': 10000, 'windows': 10}))
        x = viewer.EvaluationViewer(sessions, required, role='J', page_rows=16, max_cells=20000,
                                    max_actions=1000, max_svg_bytes=2**20)
        for item in x.catalog():
            for page in range(item['pages']):
                x.view({key: item[key] for key in ('session', 'query', 'table')} | {'page': page})
        assert x.coverage()['complete_delivery'] is True
        assert x.coverage()['timestamps'] == 87
        assert len(sessions) == 29 and len({s['animal'] for s in sessions}) == 13
        print(json.dumps({'status': 'pass', 'scope': 'generated_software_only', 'numpy': np.__version__,
                          'generated_write_bytes': generated_write_bytes,
                          'loader_read_reserved_bytes': budget.read_bytes,
                          'coverage': x.coverage()}, sort_keys=True))


if __name__ == '__main__':
    main()
