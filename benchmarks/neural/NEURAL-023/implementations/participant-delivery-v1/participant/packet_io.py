"""Exact bounded stored-NPZ input checks, before any NumPy allocation."""
from pathlib import Path
import hashlib, io, json, os, stat
import numpy as np
from bundle import npz_headers

ARMS = ('zero_velocity', 'source_mean_velocity', 'calibration_mean_velocity',
        'source_only_ridge', 'source_only_ridge_plus_calibration_mean_residual',
        'calibration_only_ridge', 'balanced_pooled_ridge')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path, pin, schemas):
    path = Path(path)
    before = path.lstat()
    require(not path.is_symlink() and stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            before.st_size == pin['bytes'] <= 10_000_000, 'Exact bounded ordinary packet')
    body = path.read_bytes()
    after = path.stat()
    require(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'] and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Unchanged packet identity')
    npz_headers(body, schemas)
    with np.load(io.BytesIO(body), allow_pickle=False, max_header_size=4096) as archive:
        values = {key: archive[key] for key in schemas}
    require(all(np.isfinite(x).all() for x in values.values()), 'All required packet values finite')
    return values


def observed_packet(path, pin, kind):
    specifications = {
        'source': (18700, 18691, 0, 10, 18700),
        'calibration': (3000, 2991, 0, 10, 3000),
        'assessment': (22100, 22091, 3000, 3010, 25100)}
    bins, rows, origin, first, last = specifications[kind]
    schemas = {'counts': ('<u4', (bins, 96)), 'bin_edges_seconds': ('<f8', (bins + 1,)),
               'endpoint_bin': ('<u4', (rows,))}
    if kind != 'assessment':
        schemas['velocity_m_s'] = ('<f8', (rows, 2))
    value = load(path, pin, schemas)
    require(np.array_equal(value['endpoint_bin'], np.arange(first, last + 1, dtype=np.uint32)),
            'Exact full endpoint identity and source order')
    edges = value['bin_edges_seconds']
    require(np.all(np.diff(edges) > 0) and np.all(np.abs(np.diff(edges) - .02) <= 5e-7),
            'Fixed physical clock inherited from five qualified native intervals')
    value['count_bin_origin'] = origin
    return value


def prediction_schemas():
    return {'case_id': ('<u4', (22091,))} | {arm: ('<f8', (22091, 2)) for arm in ARMS}


def predictions(path, pin):
    value = load(path, pin, prediction_schemas())
    require(np.array_equal(value['case_id'], np.arange(3010, 25101, dtype=np.uint32)),
            'Complete assessment identities; no missing/reordered case')
    return value


def write_json(path, value, cap):
    body = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(body) <= cap, 'Bounded JSON output')
    with Path(path).open('xb') as stream:
        stream.write(body)
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def file_pin(path):
    body = Path(path).read_bytes()
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
