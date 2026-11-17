"""Frozen NEURAL-029 fixed-delay-warp reference; public source calcium only.

Standalone participant ABI: reference_program.py --input /input --output FILE.
Requires the admitted NumPy 2.2.6 environment. No sibling modules or private
packet are required. This is a deterministic comparator, not a fitted model.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile


MANIFEST_CAP = 2_000_000
PACKET_CAP = 70_000_000
ARRAY_CAP = 200_000_000
SUBMISSION_CAP = 100_000_000
GRID = [i / 20 for i in range(61)]


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def opaque(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def read_regular(path, cap):
    """Capture a bounded ordinary file; never follow a private-path alias."""
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'ordinary public path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'bounded single-link public file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k)
             == getattr(linked, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
                                            'st_size', 'st_mtime_ns', 'st_ctime_ns')),
             'stable complete public capture')
    finally:
        os.close(fd)
    return raw


def manifest(root):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    raw = read_regular(Path(root) / 'public/MANIFEST.json', MANIFEST_CAP)
    doc = json.loads(raw, object_pairs_hook=unique,
                     parse_constant=lambda _: need(False, 'nonfinite JSON'))
    need(type(doc) is dict and set(doc) == {'schema', 'time_seconds', 'pairs'}
         and doc['schema'] == 'neural029-public-v1' and doc['time_seconds'] == GRID
         and type(doc['time_seconds']) is list
         and all(type(t) in (int, float) for t in doc['time_seconds'])
         and type(doc['pairs']) is list and doc['pairs'], 'exact complete public manifest')
    seen = set()
    total = 0
    for row in doc['pairs']:
        need(type(row) is dict and set(row) == {'pair_id', 'cell_ids', 'query_ids',
             'source_delay_seconds', 'target_delay_seconds', 'reward_type',
             'calibration_trials', 'validation_trials', 'file'}, 'exact public pair')
        key = row['pair_id']
        need(opaque(key) and key not in seen, 'unique opaque pair')
        seen.add(key)
        for axis in ('cell_ids', 'query_ids'):
            ids = row[axis]
            need(type(ids) is list and ids and all(opaque(v) for v in ids)
                 and len(set(ids)) == len(ids), 'complete unique opaque axes')
        need(type(row['source_delay_seconds']) in (int, float)
             and type(row['target_delay_seconds']) in (int, float)
             and row['source_delay_seconds'] == 1 and row['target_delay_seconds'] == 2
             and row['reward_type'] in ('DAT', 'MFB'), 'registered planned conditions')
        c, v = row['calibration_trials'], row['validation_trials']
        need(type(c) is int and type(v) is int and c >= 4 and v >= 1
             and c == 4 * (c + v) // 5, 'whole source-order 80 percent split')
        pin = row['file']
        need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}
             and pin['path'] == 'public/' + key + '.npz'
             and type(pin['bytes']) is int and 0 < pin['bytes'] <= PACKET_CAP
             and opaque(pin['sha256']), 'source-only file descriptor')
        total += pin['bytes']
    need(total <= PACKET_CAP, 'complete public packet byte bound; no pair omission')
    return doc


def source_mean(root, row, np):
    pin = row['file']
    raw = read_regular(Path(root) / pin['path'], pin['bytes'])
    need(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'],
         'authenticated public source array')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        need(len(entries) == 2 and {i.filename for i in entries}
             == {'calibration.npy', 'validation.npy'}
             and sum(i.file_size for i in entries) <= ARRAY_CAP, 'bounded source-only NPZ')
        for entry in entries:
            name = entry.filename[:-4]
            with archive.open(entry) as member:
                version = np.lib.format.read_magic(member)
                need(version in ((1, 0), (2, 0)), 'numeric NPY format')
                reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
                          else np.lib.format.read_array_header_2_0)
                shape, _, dtype = reader(member)
                expected = (row[name + '_trials'], len(row['cell_ids']), 61)
                need(shape == expected and dtype == np.dtype('float64')
                     and entry.file_size == member.tell() + 8 * expected[0] * expected[1] * expected[2],
                     'complete numeric NPY extent before allocation')
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        arrays = []
        for name in ('calibration', 'validation'):
            x = archive[name]
            need(x.dtype == np.dtype('float64')
                 and x.shape == (row[name + '_trials'], len(row['cell_ids']), 61)
                 and np.isfinite(x).all(), 'finite full source trial-cell-time geometry')
            arrays.append(x)
    # Preserve preparation's equal weight per source trial and reduction order.
    with np.errstate(over='raise', invalid='raise'):
        mean = np.concatenate(arrays, axis=0).mean(axis=0)
    need(np.isfinite(mean).all(), 'representable all-public-trial mean')
    return mean


def warped_mean(mean, np):
    # Both branches meet at 1 second when target time is exactly 2 seconds.
    mapped = [t / 2 if t < 2 else t - 1 for t in GRID]
    result = np.empty(mean.shape, dtype=np.float64)
    for cell in range(mean.shape[0]):
        result[cell] = np.interp(mapped, GRID, mean[cell])
    need(np.isfinite(result).all(), 'representable fixed-warp prediction')
    return result


def run(root, output, np):
    need(np.__version__ == '2.2.6', 'admitted NumPy 2.2.6')
    public = manifest(root)  # Admit all pair/axis descriptors before writing.
    output = Path(output).absolute()
    need('..' not in output.parts and not output.exists()
         and all(not p.is_symlink() for p in (output, *output.parents)), 'fresh ordinary output')
    fd, staging = tempfile.mkstemp(prefix='.neural029-', dir=output.parent)
    used = 0
    try:
        with os.fdopen(fd, 'wb') as stream:
            def emit(text):
                nonlocal used
                raw = text.encode('utf-8')
                used += len(raw)
                need(used <= SUBMISSION_CAP, 'full submission exceeds bound; no truncation')
                stream.write(raw)
            emit('{"schema":"neural029-predictions-v1","predictions":[')
            for number, row in enumerate(public['pairs']):
                prediction = warped_mean(source_mean(root, row, np), np)
                # Serialize one cell-by-time trajectory, never a trial-expanded cube.
                values = json.dumps(prediction.tolist(), allow_nan=False, separators=(',', ':'))
                emit((',' if number else '') + '{"pair_id":' + json.dumps(row['pair_id']) + ',"values":[')
                for trial in range(len(row['query_ids'])):
                    emit((',' if trial else '') + values)
                emit(']}')
            emit(']}\n')
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic no-replacement publication on the same output filesystem.
        os.link(staging, output)
    finally:
        os.unlink(staging)
    return {'pairs': len(public['pairs']), 'submission_bytes': used}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    import numpy as np
    run(args.input, args.output, np)


if __name__ == '__main__':
    main()
