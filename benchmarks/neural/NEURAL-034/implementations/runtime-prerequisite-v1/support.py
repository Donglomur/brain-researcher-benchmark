"""Bounded operator metadata and original captured runtime, no data/scorer calls."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

LOCAL = 'authoring/glial-context-v1/ordinary-completion-v1/'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate metadata key'); result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite metadata'))


def literal(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         all(not x.is_symlink() for x in (path, *path.parents)), 'Literal unlinked path')
    return path


def read(path, cap=262144):
    path = literal(path); fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link ordinary metadata/source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(linked, k)
             for k in keys), 'Stable complete file')
        return body
    finally:
        os.close(fd)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def checked(root, entry, cap=262144):
    name = entry['path']; rel = Path(name)
    need(not rel.is_absolute() and '..' not in rel.parts and rel.as_posix() == name, 'Relative descriptor')
    body = read(Path(root) / name, cap)
    need(pin(body) == {k: entry[k] for k in ('bytes', 'sha256')}, 'Exact descriptor bytes')
    return body


def publish(path, body, mode=0o400):
    path = literal(path)
    need(type(body) is bytes and len(body) <= 1048576 and mode in (0o400, 0o444), 'Bounded explicit publication')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(body); stream.flush(); os.fchmod(fd, mode); os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    publish(path, encode(value))


def module(name, path, body):
    result = types.ModuleType(name); result.__file__ = str(path)
    sys.modules[name] = result
    exec(compile(body, str(path), 'exec'), result.__dict__)
    return result


def runtime(root, source_freeze):
    """Only the exact source gate and module constructors; never authentic profile.load."""
    root = literal(root)
    body = read(root / source_freeze['path'])
    need(pin(body) == {k: source_freeze[k] for k in ('bytes', 'sha256')}, 'Configured exact source freeze')
    roster = decode(body)['files']
    admission_name = LOCAL + 'admission.py'
    admission_body = checked(root, {'path': admission_name, **roster[admission_name]})
    admission = module('admission', root / admission_name, admission_body)
    _, bodies = admission.source_gate(source_freeze)
    name = LOCAL + 'runtime.py'
    value = module('_neural034_prerequisite_runtime', root / name, bodies[name])
    return value.load(bodies), value.recover_unit


def validate_probe(record, expected_unit):
    need(record['status'] == 'unit_committed' and record['all_owned_absent'] is True,
         'Closed generated unit only')
    logs = record['candidate_logs']
    need(logs['returncode'] == 0 and logs['stderr'] == '' and logs['capture_truncated'] is False,
         'Complete generated probe logs')
    body = logs['stdout'].encode()
    need(0 < len(body) <= 8192 and logs['captured_stdout_bytes'] == len(body), 'Bounded exact probe log')
    value = decode(body)
    need(value.get('schema') == 'neural034-generated-runtime-probe/v1' and
         value.get('versions') == {'python': '3.12.8', 'numpy': '2.2.6', 'scipy': '1.15.3'} and
         value.get('selected_generated_unit') == expected_unit and value.get('queries') == 20 and
         value.get('fresh_tmp_marker_before_write') is True and value.get('fresh_output_before_write') is True and
         value.get('generated_data_only') is True and value.get('fits') == value.get('scientific_scores') == 0,
         'Exact generated probe result')
    names = ['root_write', 'active_input_write', *['unmounted_' + str(i) for i in range(5)], 'network_no_route']
    need([row['probe'] for row in value['denials']] == names and
         all(type(row['errno']) is int and row['errno'] > 0 for row in value['denials']), 'All denial observations')
    # The selected container is Linux, even when the trusted operator is macOS.
    allowed = [{1, 13, 30}, {1, 13, 30}, *[{1, 2, 13} for _ in range(5)], {1, 13, 101}]
    need(all(set(row) == {'probe', 'errno'} and row['errno'] in codes
             for row, codes in zip(value['denials'], allowed)), 'Actual Linux denial categories; no timeout/refusal shortcut')
    return value
