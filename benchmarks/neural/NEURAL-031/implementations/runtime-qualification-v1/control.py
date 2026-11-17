"""Fixed no-change ratio control for one original NEURAL-031 public context.

NumPy is used only to decode the integer query IDs. No features or training
targets are decoded, no fit is performed, and both views use the same rule.
This participant program does not establish container or scorer isolation.
"""
import argparse
import errno
import hashlib
import io
import json
import os
import platform
import socket
import stat
import zipfile

import numpy as np


DATA_CAP, MANIFEST_CAP, OUTPUT_CAP = 262144, 16384, 131072
KEYS = ('train_x', 'train_y', 'train_mouse', 'train_rowid', 'query_x', 'query_rowid')


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate manifest key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('Nonstandard JSON constant: ' + value)


def read(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= cap,
             'Bounded regular input required')
        body = stream.read(cap + 1)
        need(len(body) == info.st_size and len(body) <= cap, 'Complete bounded input required')
    return body


def denied_open(path, flags):
    """Test opening without truncation; any successful open fails this control."""
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as error:
        need(error.errno in (errno.EROFS, errno.EACCES, errno.EPERM),
             'Expected a write-permission or read-only-filesystem denial')
        return error.errno
    else:
        os.close(fd)
        raise ValueError('Write access unexpectedly succeeded')


def runtime_probe():
    """Observed fixed-container probes only; NEVER run this on the host.

    Generated tests replace all filesystem/network operations. No result here
    proves general hostile-code containment or source preparation correctness.
    """
    uid, gid = os.getuid(), os.getgid()
    need(uid == gid == 65534, 'Declared unprivileged identity required')
    marker = '/tmp/n031-fixed-control-freshness'
    need(not os.path.lexists(marker), 'Fresh per-context temporary filesystem required')
    need(os.listdir('/output') == [], 'Empty per-context output filesystem required')
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    denials = {'root': denied_open('/n031-fixed-control-root-write',
                                  os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW)}
    for key, path in (('data', '/input/data.npz'), ('manifest', '/input/manifest.json'),
                      ('program', '/program/submission.py')):
        denials[key] = denied_open(path, os.O_WRONLY | os.O_NOFOLLOW)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.25)
        try:
            connection.connect(('192.0.2.1', 9))
        except OSError as error:
            need(error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH,
                                 errno.ENETDOWN, errno.EACCES, errno.EPERM),
                 'Expected explicit network-denial errno, not timeout/refusal')
            network_errno = error.errno
        else:
            raise ValueError('Network connection unexpectedly succeeded')
    return {'schema': 'neural031_fixed_control_runtime_probe_v1',
            'python': platform.python_version(), 'numpy': np.__version__,
            'uid': uid, 'gid': gid, 'fresh_tmp_marker_before_creation': True,
            'empty_output_before_prediction': True, 'write_denial_errnos': denials,
            'network_denial_errno': network_errno,
            'network_probe_timeout_seconds': 0.25,
            'scope': 'observed_fixed_probes_not_universal_isolation_proof'}


def query_ids(data, count):
    """Decode only the bounded, nonobject integer query_rowid member."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        need(sorted(item.filename for item in infos) == sorted(key + '.npy' for key in KEYS),
             'Exactly the six original numeric array members required')
        need(all(0 < item.file_size <= 65536 and item.compress_type in
                 (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and not item.flag_bits & 1
                 for item in infos), 'Bounded unencrypted array members required')
        selected = archive.getinfo('query_rowid.npy')
        need(selected.file_size <= 16384, 'Bounded integer query vector required')
        with archive.open(selected) as stream:
            body = stream.read(16385)
        need(len(body) == selected.file_size, 'Complete bounded query vector required')
    stream = io.BytesIO(body)
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=512)
    elif version == (2, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=512)
    else:
        raise ValueError('Expected original numeric NPY v1 or v2')
    need(shape == (count,) and fortran is False and dtype == np.dtype('<i8'),
         'Exact one-dimensional little-endian int64 query vector required')
    payload = stream.read()
    need(len(payload) == 8 * count, 'Exact declared query-vector extent required')
    rows = np.frombuffer(payload, dtype='<i8').tolist()
    need(rows == sorted(set(rows)) and all(0 <= row < 1143 for row in rows),
         'Unique sorted original query row IDs required')
    return rows


def predict(data, manifest_body):
    """Pure generated-test seam; CLI supplies only its own two public files."""
    need(type(data) is bytes and 0 < len(data) <= DATA_CAP and
         type(manifest_body) is bytes and 0 < len(manifest_body) <= MANIFEST_CAP,
         'Original input byte limits required')
    manifest = json.loads(manifest_body, object_pairs_hook=unique, parse_constant=reject_constant)
    need(type(manifest) is dict and
         manifest.get('schema') == 'neural031_ordinary_public_view_v1' and
         manifest.get('candidate_id') == 'NEURAL-031' and
         type(manifest.get('fold')) is int and 0 <= manifest['fold'] < 20 and
         manifest.get('view') in ('baseline', 'neural') and
         type(manifest.get('query_rows')) is int and 0 < manifest['query_rows'] <= 774 and
         manifest.get('query_target_or_followup_metadata') is False,
         'Original public context identity and complete request count required')
    expected = manifest.get('data')
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'} and
         type(expected['bytes']) is int and type(expected['sha256']) is str and
         expected == pin(data), 'Manifest must authenticate the exact current archive')
    rows = query_ids(data, manifest['query_rows'])
    result = {'schema': 'neural031_ordinary_prediction_v1', 'candidate_id': 'NEURAL-031',
              'fold': manifest['fold'], 'view': manifest['view'],
              'input_manifest': pin(manifest_body),
              'rows': [{'row_id': row, 'prediction': 1.0} for row in rows]}
    body = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(body) <= OUTPUT_CAP, 'Original prediction output byte cap required')
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    report = json.dumps(runtime_probe(), sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
    need(len(report.encode()) <= 4096, 'Bounded runtime-only stdout required')
    print(report, end='', flush=True)
    manifest = read(args.manifest, MANIFEST_CAP)
    data = read(args.input, DATA_CAP)
    body = predict(data, manifest)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
