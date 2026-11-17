"""Offline, pin-first BaRISTA source admission. This module never executes source.

The two operator-supplied bodies remain subject to their original access terms.
Assembly is a source-identity check, not a redistribution grant or model run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

COMMIT = '83b27375eba60e9eba9da4e7dd8fb283baace376'
PROTOCOL_SHA256 = '4efa128d8dc7d81c5cb560f0b422e4aecef18fe2d3db442e18bbf431c2ff60a2'
MEMBER_CAP = 1024 * 1024
BATCH_CAP = 16 * 1024 * 1024
MAX_MEMBERS = 2048
MANIFEST = 'ADMISSION_MANIFEST.json'
EXTERNAL = {
    'barista/data/braintreebank_data_helpers.py': {
        'bytes': 27196,
        'sha256': 'a2a979207759e249d8ee03ba4f35f3b72e2f4c5edb26d2a3d6c2ccbec09bac07',
        'git_blob': '7c7d0e076a0ffb070f380498a481727af7134525',
        'git_mode': '100644',
    },
    'barista/data/braintreebank_wrapper.py': {
        'bytes': 48287,
        'sha256': 'ad42d64469f9af9426cf6fc5b9e8b10d81bbcc97ac4966caeaa9b6ce7a31743a',
        'git_blob': 'a21aa7f754571384fad16123ce5edf3bd3b2faa1',
        'git_mode': '100644',
    },
}
PIN_KEYS = {'bytes', 'sha256', 'git_blob', 'git_mode'}
ROW_KEYS = PIN_KEYS | {'role', 'origin', 'path', 'destination'}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'git_blob': hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest(),
            'git_mode': '100644'}


def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Ordinary relative path required')
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in ('.', '..', '.git') for p in path.parts):
        raise ValueError('Canonical non-traversing relative path required')
    return path.parts


def _check_pin(value):
    if not isinstance(value, dict) or not PIN_KEYS <= value.keys():
        raise ValueError('Complete ordinary identity required')
    if type(value['bytes']) is not int or not 0 <= value['bytes'] <= MEMBER_CAP:
        raise ValueError('Exact bounded ordinary length required')
    if value['git_mode'] != '100644':
        raise ValueError('Only ordinary mode 100644 is admitted')
    for key, length in (('sha256', 64), ('git_blob', 40)):
        if not isinstance(value[key], str) or re.fullmatch('[0-9a-f]{%d}' % length, value[key]) is None:
            raise ValueError('Exact lowercase digest required')


def _root_fd(root):
    """Open each directory without following symlinks, including root ancestors."""
    if root is None:
        raise ValueError('Explicit source root required')
    raw = os.fspath(root)
    path = Path(raw) if Path(raw).is_absolute() else Path.cwd() / raw
    if '..' in path.parts:
        raise ValueError('Source-root traversal is not admitted')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _read(root, relative, cap, expected_size=None):
    """Capture one bounded UTF-8 ordinary file, retaining a stable descriptor."""
    parts = _relative(relative)
    parent = _root_fd(root)
    file_fd = None
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o644 or before.st_nlink != 1:
            raise ValueError('Source must be a single-link ordinary file with mode 0644')
        if before.st_size > cap or (expected_size is not None and before.st_size != expected_size):
            raise ValueError('Exact bounded source length mismatch')
        chunks = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(file_fd, min(65536, remaining))
            if not chunk:
                raise ValueError('Short source capture')
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(file_fd, 1):
            raise ValueError('Source grew during capture')
        after = os.fstat(file_fd)
        named = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        if _identity(before) != _identity(after) or _identity(after) != _identity(named):
            raise ValueError('Source identity changed during capture')
        body = b''.join(chunks)
        body.decode('utf-8')
        if b'\0' in body:
            raise ValueError('NUL source payload is not ordinary text')
        return body
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(parent)


def capture(root, relative, expected):
    _check_pin(expected)
    body = _read(root, relative, MEMBER_CAP, expected['bytes'])
    if pin(body) != {key: expected[key] for key in PIN_KEYS}:
        raise ValueError('Complete source hash/blob/mode identity mismatch')
    return body


def _parse(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(body.decode('utf-8'), object_pairs_hook=unique)


def load_descriptor(path, expected_sha256):
    """The caller must bind expected_sha256 to the published package identity."""
    path = Path(path)
    body = _read(path.parent, path.name, MEMBER_CAP)
    if not isinstance(expected_sha256, str) or hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError('Published source descriptor identity mismatch')
    return body


def _descriptor(body, expected_sha256):
    if not isinstance(body, bytes) or len(body) > MEMBER_CAP or hashlib.sha256(body).hexdigest() != expected_sha256:
        raise ValueError('Published source descriptor identity mismatch')
    doc = _parse(body)
    if set(doc) != {'schema', 'upstream_commit', 'roles', 'notices'} or doc['schema'] != 'barista_offline_source_access_v1' or doc['upstream_commit'] != COMMIT:
        raise ValueError('Pinned BaRISTA source descriptor schema/commit required')
    if not isinstance(doc['roles'], list) or len(doc['roles']) != 32:
        raise ValueError('All 32 original source roles are required')
    if not isinstance(doc['notices'], list) or len(doc['notices']) < 1:
        raise ValueError('Required source-specific notices are missing')
    rows = doc['roles'] + doc['notices']
    if len(rows) + 1 > MAX_MEMBERS or sum(r.get('bytes', BATCH_CAP + 1) for r in rows if isinstance(r, dict) and type(r.get('bytes')) is int) > BATCH_CAP:
        raise ValueError('Bounded source batch required')
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise ValueError('Exact source row schema required')
        _check_pin(row)
        _relative(row['path']); _relative(row['destination']); _relative(row['role'])
        if row['origin'] not in ('bundled', 'operator') or row['destination'] == MANIFEST:
            raise ValueError('Source origin or destination invalid')
    for key in ('role', 'destination'):
        names = [r[key] for r in rows]
        if len(names) != len(set(names)) or len(names) != len({n.casefold() for n in names}):
            raise ValueError('Duplicate or case-colliding source name')
    names = {r['destination'] for r in rows}
    if any('/'.join(PurePosixPath(n).parts[:i]) in names for n in names for i in range(1, len(PurePosixPath(n).parts))):
        raise ValueError('File/directory destination collision')
    for row in doc['notices']:
        if row['origin'] != 'bundled' or not row['destination'].startswith('notices/'):
            raise ValueError('Notices must be bundled and retained under notices/')
    external = [r for r in doc['roles'] if r['origin'] == 'operator']
    if {r['role'] for r in external} != set(EXTERNAL) or len(external) != 2:
        raise ValueError('Exactly the two pinned external source roles are required')
    for row in external:
        if row['path'] != row['role'] or row['destination'] != row['role'] or {k: row[k] for k in PIN_KEYS} != EXTERNAL[row['role']]:
            raise ValueError('External source role pin substitution refused')
    return doc


def authenticate_official(bundled_source_root, operator_root, descriptor_body, expected_sha256):
    """Capture the complete 32-role package and every required notice, without import."""
    doc = _descriptor(descriptor_body, expected_sha256)
    if operator_root is None:
        raise ValueError('B requires an explicit operator source root for both external bodies')
    protocol_body = _read(bundled_source_root, 'PROTOCOL.json', MEMBER_CAP)
    if hashlib.sha256(protocol_body).hexdigest() != PROTOCOL_SHA256:
        raise ValueError('Original source protocol identity mismatch')
    originals = _parse(protocol_body)['source_files']
    if {r['role'] for r in doc['roles']} != set(originals):
        raise ValueError('Complete original source-role coverage required')
    for row in doc['roles']:
        original = originals[row['role']]
        is_notebook = row['role'].endswith('.ipynb')
        destination = 'chronological_notebook_source.json' if is_notebook else row['role']
        if row['destination'] != destination or row['bytes'] != original['retained_bytes'] or row['sha256'] != original['retained_sha256']:
            raise ValueError('Source-role body/placement differs from pinned protocol')
        if not is_notebook and row['git_blob'] != original['git_blob']:
            raise ValueError('Original Git-blob identity required')
        if row['origin'] == 'bundled':
            expected_path = destination if is_notebook else 'author/' + row['role']
            if row['path'] != expected_path:
                raise ValueError('Bundled source placement differs from complete package')
    captured = []
    for row in doc['roles'] + doc['notices']:
        root = operator_root if row['origin'] == 'operator' else bundled_source_root
        body = capture(root, row['path'], row)
        if row['role'].endswith('.ipynb'):
            notebook = _parse(body)
            if notebook.get('source_git_blob') != originals[row['role']]['git_blob']:
                raise ValueError('Notebook projection must identify the original Git blob')
        captured.append((row['destination'], body))
    return captured


def official_sources_for_arm(arm, *, bundled_source_root=None, operator_root=None, descriptor_path=None, expected_sha256=None):
    """A performs no official descriptor/root access. B requires all source plus notices."""
    if arm == 'paper_and_data':
        return []
    if arm != 'paper_data_official_code':
        raise ValueError('Unknown source-access arm')
    if operator_root is None:
        raise ValueError('B requires an explicit operator source root for both external bodies')
    body = load_descriptor(descriptor_path, expected_sha256)
    return authenticate_official(bundled_source_root, operator_root, body, expected_sha256)


def _write_at(root_fd, relative, body):
    parts = _relative(relative)
    parent = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o755, dir_fd=parent)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent); parent = child
        fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        try:
            os.fchmod(fd, 0o644)
            view = memoryview(body)
            while view:
                n = os.write(fd, view)
                if n <= 0:
                    raise OSError('Short source assembly write')
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def provision(bundled_source_root, operator_root, descriptor_path, expected_sha256, out_path):
    """Write a fresh offline assembly; return admission only after all writes.

An output failure may retain partial files or an uncertain finalization outcome.
Quarantine that destination; do not infer admission from a path existing or retry
in place. The admission manifest is the last written body on successful return.
"""
    body = load_descriptor(descriptor_path, expected_sha256)
    captured = authenticate_official(bundled_source_root, operator_root, body, expected_sha256)
    result = {'schema': 'barista_offline_source_admission_v1', 'upstream_commit': COMMIT,
              'descriptor_sha256': expected_sha256, 'original_source_roles': 32,
              'external_source_roles': 2, 'native_execution': False, 'redistribution_grant': False,
              'files': [{'path': n, **pin(b)} for n, b in captured]}
    manifest_body = canonical(result)
    if len(manifest_body) > MEMBER_CAP or sum(len(b) for _, b in captured) + len(manifest_body) > BATCH_CAP:
        raise ValueError('Assembly and manifest exceed finite source limits')
    out = Path(out_path)
    _relative(out.name)
    parent_fd = _root_fd(out.parent)
    out_fd = None
    try:
        os.mkdir(out.name, 0o755, dir_fd=parent_fd)
        out_fd = os.open(out.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        for name, data in captured:
            _write_at(out_fd, name, data)
        _write_at(out_fd, MANIFEST, manifest_body)
        os.fsync(out_fd)
        return result
    finally:
        if out_fd is not None:
            os.close(out_fd)
        os.close(parent_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundled-source-root', required=True)
    parser.add_argument('--operator-source-root', required=True)
    parser.add_argument('--descriptor', required=True)
    parser.add_argument('--expected-descriptor-sha256', required=True,
                        help='The descriptor digest published with this benchmark package')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = provision(args.bundled_source_root, args.operator_source_root, args.descriptor,
                       args.expected_descriptor_sha256, args.out)
    print(json.dumps({'status': 'source_identity_admitted', 'files': len(result['files']),
                      'native_execution': False, 'redistribution_grant': False}, sort_keys=True))


if __name__ == '__main__':
    main()
