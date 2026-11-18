"""NEURAL-002 source projection only; never acquires or authenticates raw payloads.

The fixed selected SOURCES body is the trust anchor, not a caller-supplied hash.
The existing provider remains responsible for actual raw file custody and assay
validation. All256 supplied source objects authenticate before any projection.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SOURCE_COMMIT = 'd2e09f610d267b8b3679997f8bc4e52fe6ca402a'
_SOURCE_BYTES = 80770
_SOURCE_SHA256 = '3ec6ba3dcf60c49ee381126958a617a87eadfcbabce09a5cf8bd3eb12ab0af8e'
PEOPLE = tuple(f'sub-{n:02d}' for n in range(1, 33))
TASKS = ('dotcount', 'firstlast')
ROLES = ('header', 'markers', 'events', 'signal')
SOURCE_ROLES = {'header': 'header', 'markers': 'markers', 'events': 'events', 'signal': 'eeg'}
EXTENSIONS = {'header': '_eeg.vhdr', 'markers': '_eeg.vmrk', 'events': '_events.tsv', 'signal': '_eeg.eeg'}
CAPS = {'header': 2**20, 'markers': 2**20, 'events': 2**20, 'signal': 8 * 2**30}


class PinError(ValueError):
    """No expected-pin artifact may be accepted from this invocation."""


def _need(condition, message):
    if not condition:
        raise PinError(message)


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def _selected_roster(source_body):
    _need(type(source_body) is bytes and len(source_body) == _SOURCE_BYTES
          and _sha(source_body) == _SOURCE_SHA256, 'selected SOURCES identity mismatch')
    try:
        source = json.loads(source_body, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PinError('selected source JSON') from exc
    _need(type(source) is dict and source.get('source_commit') == SOURCE_COMMIT,
          'selected source commit')
    cohort = source.get('cohort_metadata')
    _need(type(cohort) is dict and cohort.get('commit') == SOURCE_COMMIT
          and type(cohort.get('participants')) is int and cohort['participants'] == 32
          and type(cohort.get('recordings')) is int and cohort['recordings'] == 64,
          'complete selected cohort')
    rows = cohort.get('files')
    _need(type(rows) is list and len(rows) == 64, 'all64 source recordings required')
    expected = []
    paths, objects = set(), set()
    for row, (person, task) in zip(rows, ((p, t) for p in PEOPLE for t in TASKS)):
        _need(type(row) is dict and row.get('subject') == person and row.get('task') == task,
              'fixed participant/task roster and ordering')
        for role in ROLES:
            meta = row.get(SOURCE_ROLES[role])
            _need(type(meta) is dict and set(meta) == {'bytes', 'git_mode', 'git_object', 'path'},
                  'exact source asset schema')
            path = f'{person}/eeg/{person}_task-{task}' + EXTENSIONS[role]
            _need(meta['path'] == path and path not in paths, 'source participant/task/role path')
            mode = '100644' if role == 'events' else '120000'
            _need(meta['git_mode'] == mode, 'source object mode differs from selected role')
            _need(type(meta['bytes']) is int and 0 < meta['bytes'] <= (2**20 if role == 'events' else 1024),
                  'bounded source blob extent, not payload extent')
            oid = meta['git_object']
            _need(type(oid) is str and re.fullmatch('[0-9a-f]{40}', oid) is not None
                  and oid not in objects, 'unique selected source object identity')
            paths.add(path); objects.add(oid)
            expected.append({'participant': person, 'task': task, 'role': role, **meta})
    _need(len(expected) == 256, 'complete256 source support')
    return expected


def _authenticated(source_body, supplied):
    expected = _selected_roster(source_body)
    _need(type(supplied) is list and len(supplied) == 256, 'exact256 supplied source objects')
    by_path = {}
    for value in supplied:
        _need(type(value) is dict and set(value) == {'path', 'git_mode', 'git_object', 'body'},
              'exact supplied source object schema')
        path = value['path']
        _need(type(path) is str and path not in by_path, 'unique supplied source path')
        _need(type(value['body']) is bytes, 'immutable raw Git blob body required')
        by_path[path] = value
    _need(set(by_path) == {r['path'] for r in expected}, 'exact selected source path support')
    authenticated = []
    for meta in expected:
        value = by_path[meta['path']]
        _need(value['git_mode'] == meta['git_mode'] and value['git_object'] == meta['git_object'],
              'supplied source mode or object identity mismatch')
        body = value['body']
        _need(len(body) == meta['bytes'], 'source blob byte extent mismatch')
        framed = b'blob ' + str(len(body)).encode('ascii') + b'\0' + body
        _need(hashlib.sha1(framed).hexdigest() == meta['git_object'], 'source Git blob authentication failed')
        authenticated.append((meta, body))
    return authenticated


def compile_pins(source_body, supplied):
    """Return (existing intake manifest, separate source-projection receipt).

    No source-hash override, partial-cohort option, network, or payload resolver
    exists. Supplied rows can be in any order; outputs follow fixed source order.
    """
    authenticated = _authenticated(source_body, supplied)
    recordings = []
    evidence = []
    for index in range(0, 256, 4):
        group = authenticated[index:index + 4]
        selection = {'source_commit': SOURCE_COMMIT, 'participant': group[0][0]['participant'],
                     'task': group[0][0]['task'], 'files': {}}
        for meta, body in group:
            role = meta['role']
            if role == 'events':
                extent, digest = len(body), _sha(body)
                derivation = 'opaque_regular_git_blob_bytes'
            else:
                extent, digest = _pointer_pin(body, role)
                derivation = 'authenticated_source_pointer_content_key'
            selection['files'][role] = {'path': meta['path'], 'bytes': extent, 'sha256': digest}
            evidence.append({'path': meta['path'], 'role': role, 'source_git_mode': meta['git_mode'],
                             'source_git_blob_sha1': meta['git_object'], 'source_blob_bytes': len(body),
                             'source_blob_sha256': _sha(body), 'expected_payload_bytes': extent,
                             'expected_payload_sha256': digest, 'derivation': derivation})
        recordings.append(selection)
    manifest = {'schema': 'morse-pinned-cohort-v1', 'source_commit': SOURCE_COMMIT,
                'recordings': recordings}
    receipt = {'schema': 'morse-source-pin-projection-v1', 'task_id': 'NEURAL-002',
               'source_commit': SOURCE_COMMIT,
               'sources': {'bytes': len(source_body), 'sha256': _sha(source_body)},
               'source_objects_authenticated': 256, 'recordings': 64,
               'manifest_sha256': _sha(_encoded(manifest)),
               'raw_payload_custody_verified': False, 'scientific_certificate_issued': False,
               'provider_or_runtime_admission': False, 'dataset_tag_commit_equivalence_verified': False,
               'source_evidence': evidence}
    return manifest, receipt


def _read_regular(path, cap, exact=None):
    path = Path(path)
    _need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
          'absolute ordinary input path')
    # A substituted FIFO must reach fstat instead of blocking at open.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap
              and (exact is None or before.st_size == exact), 'ordinary bounded single-link input')
        body = b''
        while len(body) <= cap:
            piece = os.read(fd, min(65536, cap + 1 - len(body)))
            if not piece:
                break
            body += piece
        after = os.fstat(fd)
        _need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
              == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
              and len(body) == before.st_size, 'input changed or exceeded extent')
        return body
    finally:
        os.close(fd)


def compile_directory(sources_path, blob_directory):
    """Read supplied OID.blob files only. No Git invocation or source acquisition."""
    source_body = _read_regular(sources_path, _SOURCE_BYTES, _SOURCE_BYTES)
    expected = _selected_roster(source_body)
    root = Path(blob_directory)
    _need(root.is_absolute() and not any(p.is_symlink() for p in (root, *root.parents))
          and root.is_dir(), 'ordinary supplied source-blob directory')
    names = set()
    for child in root.iterdir():
        _need(len(names) < 256, 'extra source object directory entry')
        names.add(child.name)
    _need(names == {m['git_object'] + '.blob' for m in expected}, 'exact256 source object filenames')
    supplied = [{'path': m['path'], 'git_mode': m['git_mode'], 'git_object': m['git_object'],
                 'body': _read_regular(root / (m['git_object'] + '.blob'), m['bytes'], m['bytes'])}
                for m in expected]
    return compile_pins(source_body, supplied)


_POINTER = re.compile(
    rb'\.\./\.\./\.git/annex/objects/[A-Za-z0-9]{2}/[A-Za-z0-9]{2}/'
    rb'(?P<key>SHA256E-s(?P<size>[1-9][0-9]{0,9})--(?P<sha>[0-9a-f]{64})'
    rb'\.(?P<extension>vhdr|vmrk|eeg))/(?P=key)')
_POINTER_EXT = {'header': b'vhdr', 'markers': b'vmrk', 'signal': b'eeg'}


def _pointer_pin(body, role):
    """Parse only the observed source-key family; never open its relative path.

    A source-authenticated key states an EXPECTED payload digest/extent. It is
    not evidence that a local recording has been acquired or matches that key.
    Unobserved backend/layout variants fail closed; all192 are still required.
    """
    match = _POINTER.fullmatch(body)
    _need(match is not None, 'unsupported or malformed source pointer grammar')
    _need(match['extension'] == _POINTER_EXT[role], 'source pointer role extension mismatch')
    extent = int(match['size'])
    _need(0 < extent <= CAPS[role], 'expected payload exceeds existing provider role bound')
    return extent, match['sha'].decode('ascii')


def _output_path(value):
    path = Path(value)
    _need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents))
          and path.parent.is_dir() and not path.exists(), 'new ordinary absolute output path')
    return path


def write_outputs(manifest, receipt, manifest_path, receipt_path):
    """Exclusive files; receipt binds exact manifest bytes. Failure preserves partials.

    This does not issue a scientific certificate or write any protected runtime
    selection. Operators must check the successful return and both output pins.
    """
    manifest_path, receipt_path = _output_path(manifest_path), _output_path(receipt_path)
    _need(manifest_path != receipt_path, 'distinct output files')
    manifest_body, receipt_body = _encoded(manifest), _encoded(receipt)
    _need(len(manifest_body) <= 131072 and len(receipt_body) <= 262144
          and receipt.get('manifest_sha256') == _sha(manifest_body), 'bounded matching source projection')
    for path, body in ((manifest_path, manifest_body), (receipt_path, receipt_body)):
        with path.open('xb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return {'manifest_bytes': len(manifest_body), 'manifest_sha256': _sha(manifest_body),
            'receipt_bytes': len(receipt_body), 'receipt_sha256': _sha(receipt_body)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--blobs', type=Path, required=True)
    parser.add_argument('--manifest-output', type=Path, required=True)
    parser.add_argument('--receipt-output', type=Path, required=True)
    args = parser.parse_args(argv)
    manifest, receipt = compile_directory(args.sources, args.blobs)
    result = write_outputs(manifest, receipt, args.manifest_output, args.receipt_output)
    print(json.dumps({'status': 'complete_expected_source_pins', 'recordings': 64,
                      'entries': 256, 'actual_raw_payload_custody': False, **result}, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (PinError, OSError) as exc:
        print(json.dumps({'status': 'failed_no_accepted_projection', 'kind': type(exc).__name__,
                          'detail': str(exc)[:192]}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
