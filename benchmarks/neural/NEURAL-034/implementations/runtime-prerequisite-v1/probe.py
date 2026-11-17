"""Generated runtime probe only; never an authentic neural-data candidate."""
import argparse
import errno
import json
import os
from pathlib import Path
import platform
import socket
import sys

import numpy as np
import scipy
from scipy.linalg import solve

HOST_CANARIES = ()
SHAPES = {'train_windows': ((120, 300, 12), '<f8'),
          'train_behavior': ((120, 300), '<f8'), 'train_labels': ((120,), '|i1'),
          'query_windows': ((20, 300, 12), '<f8'),
          'query_behavior': ((20, 300), '<f8'), 'query_ids': ((20,), '<U24')}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def denied(action, allowed, name):
    try:
        value = action()
        if hasattr(value, 'close'):
            value.close()
    except OSError as error:
        need(error.errno in allowed, name + ': unexpected denial category')
        return {'probe': name, 'errno': error.errno}
    raise ValueError(name + ': operation unexpectedly permitted')


def packet(path):
    with np.load(path, allow_pickle=False) as data:
        need(set(data.files) == set(SHAPES), 'Exact generated six-array schema')
        values = {}
        for name, (shape, dtype) in SHAPES.items():
            value = data[name]
            need(value.shape == shape and value.dtype.str == dtype, 'Generated typed array ' + name)
            values[name] = value
    ids = values['query_ids'].tolist()
    first = int(ids[0], 16)
    need(first in (1000, 2000) and ids == [f'{first + i:024x}' for i in range(20)],
         'Active generated query identity and order')
    selected = first // 1000
    need(np.all(values['train_windows'] == 0) and np.all(values['train_behavior'] == 0) and
         np.array_equal(values['train_labels'], np.arange(120, dtype=np.int8) % 2) and
         np.all(values['query_windows'] == selected / 8) and
         np.all(values['query_behavior'] == selected - 1), 'Exact generated serialization values')
    need(np.array_equal(solve(np.eye(2), np.array([1., 2.])), np.array([1., 2.])),
         'Finite exact small SciPy arithmetic')
    return ids, selected


def main():
    p = argparse.ArgumentParser(); p.add_argument('--input', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); a = p.parse_args()
    versions = {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__}
    need(versions == {'python': '3.12.8', 'numpy': '2.2.6', 'scipy': '1.15.3'}, 'Declared installed versions')
    need(os.getuid() == os.geteuid() == 65534 and os.getgid() == 65534, 'Original nonroot identity')
    need(sorted(x.name for x in a.input.iterdir()) == ['public.npz'], 'Only active input visible')
    need(len(HOST_CANARIES) == 3, 'Three deliberately unmounted existing host canaries')
    rows = [denied(lambda: open('/neural034-write-probe', 'xb'),
                   {errno.EROFS, errno.EACCES, errno.EPERM}, 'root_write'),
            denied(lambda: open(a.input / 'public.npz', 'r+b'),
                   {errno.EROFS, errno.EACCES, errno.EPERM}, 'active_input_write')]
    for index, path in enumerate((*HOST_CANARIES, '/var/run/docker.sock', '/run/docker.sock')):
        rows.append(denied(lambda path=path: open(path, 'rb'),
                           {errno.ENOENT, errno.EACCES, errno.EPERM}, 'unmounted_' + str(index)))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
        channel.settimeout(.25)
        rows.append(denied(lambda: channel.connect(('192.0.2.1', 9)),
                           {errno.ENETUNREACH, errno.EACCES, errno.EPERM}, 'network_no_route'))
    marker = Path('/tmp/neural034-fixed-reset-marker')
    need(not marker.exists() and list(a.out.iterdir()) == [], 'Fresh scratch and output volume')
    marker.write_bytes(b'generated reset witness\n')
    ids, selected = packet(a.input / 'public.npz')
    result = {'schema_version': 1, 'probabilities': [
        {'query_id': q, 'probability': .5} for q in ids]}
    with (a.out / 'probabilities.json').open('x') as stream:
        json.dump(result, stream, separators=(',', ':'), allow_nan=False); stream.write('\n')
    print(json.dumps({'schema': 'neural034-generated-runtime-probe/v1', 'versions': versions,
          'selected_generated_unit': selected, 'queries': 20, 'denials': rows,
          'fresh_tmp_marker_before_write': True, 'fresh_output_before_write': True,
          'generated_data_only': True, 'fits': 0, 'scientific_scores': 0}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
