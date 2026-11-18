"""Physically stage the two existing REVE data views; no participant execution.

Trusted operator preparation. Existing source identities and full original
support are unchanged. This copies bytes without importing scientific libraries
or interpreting arrays. It cannot confer runtime or scientific qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import ModuleType

HERE = Path(__file__).resolve().parent
VIEWS_SHA = '7de2d0f99a05b3fdd6bf813d0fcfde302ecd7abc9418228dd363b812e776dce6'
CHUNK = 65536
MANIFEST_CAP = 4 * 1024**2
MAX_IO = 64 * 1024**3


class Refusal(ValueError):
    pass


class MaterializationFailure(Refusal):
    def __init__(self, original, meter, destination):
        message = str(original)[:240] if isinstance(original, (Refusal, ValueError)) else type(original).__name__
        self.detail = {'status': 'failed', 'reason': message, 'error_type': type(original).__name__,
                       'stage': meter.stage, 'item': meter.item,
                       'errno': original.errno if isinstance(original, OSError) else None,
                       'strerror': original.strerror[:160] if isinstance(original, OSError) and
                                   isinstance(original.strerror, str) else None,
                       'output': str(destination), 'logical_read_bytes': meter.read_used,
                       'logical_write_bytes': meter.write_used,
                       'elapsed_seconds': time.monotonic() - meter.started,
                       'partial_output_must_not_be_used': True,
                       'runtime_qualified': False, 'scientific_qualification': False}
        super().__init__(message)


def need(condition, message):
    if not condition:
        raise Refusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def load_views():
    path = HERE.parent / 'development-boundary-v1/views.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == VIEWS_SHA, 'closed-view source changed')
    module = ModuleType('_reve_phase_materialization_views')
    module.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


class Meter:
    """Cumulative logical data I/O and cooperative wall checks, including failure.

    Source imports, Python/runtime I/O, directory metadata and physical filesystem
    amplification are not included. This is not an OS hard-resource boundary.
    """
    def __init__(self, read_bytes, write_bytes, wall_seconds):
        need(all(type(n) is int and 0 < n <= MAX_IO for n in (read_bytes, write_bytes)),
             'positive explicit preparation I/O allowances required')
        need(type(wall_seconds) is int and 0 < wall_seconds <= 3600,
             'explicit preparation wall allowance in 1..3600 seconds required')
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.read_used = self.write_used = 0
        self.stage, self.item = 'preflight', None
        self.started = time.monotonic()
        self.deadline = self.started + wall_seconds

    def check(self):
        need(time.monotonic() < self.deadline, 'preparation wall allowance exhausted')

    def admit(self, read_bytes=0, write_bytes=0):
        self.check()
        need(self.read_used + read_bytes <= self.read_limit and
             self.write_used + write_bytes <= self.write_limit,
             'preparation I/O allowance exhausted')

    def read(self, count):
        self.admit(read_bytes=count)
        self.read_used += count

    def write(self, count):
        self.admit(write_bytes=count)
        self.write_used += count


def directory(path):
    """Require an absolute existing directory with no symlink ancestor."""
    path = Path(path)
    need(path.is_absolute() and path.anchor == '/' and '..' not in path.parts,
         'absolute ordinary directory with one root slash required')
    for item in reversed((path, *path.parents)):
        info = item.lstat()
        need(stat.S_ISDIR(info.st_mode), 'symlink or non-directory ancestor refused')
    return path


def ordinary(path):
    directory(path.parent)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size > 0,
         'positive ordinary file without aliases required')
    return info


def state(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def disjoint_parent(source, parent):
    """Also detect source ancestry through case-insensitive directory aliases."""
    source_stat = source.stat()
    source_identity = source_stat.st_dev, source_stat.st_ino
    for ancestor in (parent, *parent.parents):
        info = ancestor.stat()
        need((info.st_dev, info.st_ino) != source_identity,
             'output parent aliases the source or its physical descendants')


def _read_document(path, meter):
    before = ordinary(path)
    need(before.st_size <= MANIFEST_CAP, 'material manifest exceeds bounded metadata limit')
    meter.admit(read_bytes=before.st_size)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        need(state(os.fstat(stream.fileno())) == state(before), 'manifest pathname changed')
        meter.read(before.st_size)
        body = stream.read(before.st_size)
        need(len(body) == before.st_size and state(os.fstat(stream.fileno())) == state(before)
             and state(path.lstat()) == state(before), 'manifest changed during read')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate manifest key')
            result[key] = value
        return result
    def constant(value):
        raise Refusal('nonfinite manifest value')
    document = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    need(type(document) is dict, 'material manifest must be an object')
    return document, pin(body)


def plan(document, expected_materials_identity, expected_panel_identity, sizes, destination):
    """Build the complete existing descriptors from a selected full manifest.

    Sizes are observed source extents, not replacement content identities. The
    selected original signal hashes and geometry pin come from the existing
    compiler. No output directory or array is opened by this function.
    """
    views = load_views()
    compiled = views.compile_views(document, expected_materials_identity, expected_panel_identity)
    all_paths = {row['signal'] for phase in ('development', 'test') for row in compiled[phase]['records']}
    need(type(sizes) is dict and set(sizes) == all_paths, 'exact full-panel signal extent roster required')
    phases = {}
    for phase in ('development', 'test'):
        view = compiled[phase]
        subset = {row['signal']: sizes[row['signal']] for row in view['records']}
        desc = views.data_mount(view, Path(destination) / phase, subset)
        views.validate_mount(view, desc)
        phases[phase] = {'view': view, 'mount': desc}
    reads = sum(item['bytes'] for item in phases['development']['mount']['files'].values())
    reads += sum(item['bytes'] for item in phases['test']['mount']['files'].values())
    view_bytes = sum(item['mount']['files']['view.json']['bytes'] for item in phases.values())
    return {'schema': 'reve-physical-phase-plan-v1',
            'materials_identity': compiled['info']['materials_identity'],
            'panel_identity': expected_panel_identity, 'phases': phases,
            'copy_source_bytes': reads - view_bytes, 'phase_output_bytes': reads,
            'runtime_qualified': False, 'scientific_qualification': False}


def _write_bytes(path, body, meter):
    meter.write(len(body))  # Debit the attempted logical write before publication.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        need(stream.write(body) == len(body), 'short output write')
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)


def _copy_verified(source, output, expected, meter):
    """Stream one exact selected body, preserving any partial failure output."""
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'} and
         type(expected['bytes']) is int and expected['bytes'] > 0 and
         type(expected['sha256']) is str and len(expected['sha256']) == 64,
         'exact positive body pin required')
    before = ordinary(source)
    need(before.st_size == expected['bytes'], 'selected source extent mismatch')
    meter.admit(read_bytes=before.st_size, write_bytes=before.st_size)
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(source_fd, 'rb') as inp:
        need(state(os.fstat(inp.fileno())) == state(before), 'source changed before copy')
        output_fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(output_fd, 'wb') as out:
            digest = hashlib.sha256()
            remaining = before.st_size
            while remaining:
                count = min(CHUNK, remaining)
                meter.read(count)
                body = inp.read(count)
                need(len(body) == count, 'selected source truncated during copy')
                digest.update(body)
                meter.write(len(body))
                need(out.write(body) == len(body), 'short copy write')
                remaining -= count
            need(state(os.fstat(inp.fileno())) == state(before) and
                 state(source.lstat()) == state(before), 'source mutated during copy')
            need(digest.hexdigest() == expected['sha256'], 'selected source hash mismatch')
            out.flush()
            os.fsync(out.fileno())
    output.chmod(0o444)


def _stage_phase(source, phase_root, phase, meter):
    """Private implementation seam: callers authenticate phase with plan()."""
    need(phase['mount']['path'] == str(phase_root) and
         pin(canonical(phase['view'])) == phase['mount']['files']['view.json'],
         'phase destination or canonical view pin changed')
    phase_root.mkdir(mode=0o700)
    (phase_root / 'signals').mkdir(mode=0o700)
    meter.stage, meter.item = 'phase:' + phase_root.name, 'view.json'
    _write_bytes(phase_root / 'view.json', canonical(phase['view']), meter)
    for name, descriptor in phase['mount']['files'].items():
        if name != 'view.json':
            meter.item = name
            _copy_verified(source / name, phase_root / name, descriptor, meter)
    observed = {str(p.relative_to(phase_root)) for p in phase_root.rglob('*') if p.is_file()}
    need(observed == set(phase['mount']['files']), 'output phase membership mismatch')
    need({p.name for p in phase_root.iterdir() if p.is_dir()} == {'signals'},
         'unexpected output phase directory')
    (phase_root / 'signals').chmod(0o555)
    phase_root.chmod(0o555)


def materialize(source, destination, *, expected_materials_identity,
                expected_panel_identity, read_bytes, write_bytes, wall_seconds):
    """Create new read-only phase directories and a private operator manifest.

    The existing private parent and this trusted operator own publication. A
    failed destination is retained, never resumed or mistaken for completion.
    Filesystem modes are not a sandbox against the trusted host owner.
    """
    meter = Meter(read_bytes, write_bytes, wall_seconds)
    try:
        return _materialize(source, destination, expected_materials_identity,
                            expected_panel_identity, meter)
    except Exception as error:
        raise MaterializationFailure(error, meter, destination) from error


def _materialize(source, destination, expected_materials_identity, expected_panel_identity, meter):
    source = directory(source)
    destination = Path(destination)
    parent = directory(destination.parent)
    need(destination.is_absolute() and destination.anchor == '/' and '..' not in destination.parts and destination != parent,
         'new absolute output directory required')
    need(not destination.exists() and not destination.is_symlink(), 'output already exists')
    need(not destination.is_relative_to(source) and not source.is_relative_to(destination),
         'source and destination must be disjoint')
    disjoint_parent(source, parent)
    parent_stat = parent.stat()
    need(parent_stat.st_uid == os.getuid() and parent_stat.st_mode & 0o077 == 0,
         'output requires an operator-owned private parent')
    meter.stage, meter.item = 'source_metadata', 'materials.json'
    document, manifest_pin = _read_document(source / 'materials.json', meter)
    views = load_views()
    compiled = views.compile_views(document, expected_materials_identity, expected_panel_identity)
    sizes = {}
    meter.stage = 'source_extents'
    for phase in ('development', 'test'):
        for row in compiled[phase]['records']:
            meter.check()
            meter.item = row['signal']
            sizes[row['signal']] = ordinary(source / row['signal']).st_size
    prepared = plan(document, expected_materials_identity, expected_panel_identity, sizes, destination)
    meter.stage, meter.item = 'planning', None
    receipt = {'schema': 'reve-materialized-phase-views-v1',
               'status': 'complete', 'source_manifest': manifest_pin,
               'materials_identity': expected_materials_identity, 'panel_identity': expected_panel_identity,
               'views': {key: {'view_identity': item['view']['view_identity'], 'mount': item['mount']}
                         for key, item in prepared['phases'].items()},
               'counts': {'people': 109, 'source_recordings': 654, 'train': 6300, 'val': 1734, 'test': 1803},
               'copy_source_bytes': prepared['copy_source_bytes'],
               'phase_output_bytes': prepared['phase_output_bytes'],
               'runtime_qualified': False, 'scientific_qualification': False,
               'array_decode_performed': False, 'participant_execution_performed': False,
               'io_accounting': 'logical requested data reads/writes; source imports, directory metadata and physical I/O excluded'}
    receipt_body = canonical(receipt)
    meter.admit(read_bytes=prepared['copy_source_bytes'],
                write_bytes=prepared['phase_output_bytes'] + len(receipt_body))
    destination.mkdir(mode=0o700)
    for key, phase in prepared['phases'].items():
        _stage_phase(source, destination / key, phase, meter)
    # Only final publication names a complete manifest, outside participant roots.
    # The newly created private destination has a single trusted writer; this
    # does not protect against that operator deliberately racing its own rename.
    # A preceding copy/fsync/deadline failure retains the pending file instead.
    temporary = destination / 'MANIFEST.pending.json'
    meter.stage, meter.item = 'completion_publication', 'MANIFEST.json'
    _write_bytes(temporary, receipt_body, meter)
    meter.check()
    need(not (destination / 'MANIFEST.json').exists() and not (destination / 'MANIFEST.json').is_symlink(),
         'completion manifest already exists')
    os.rename(temporary, destination / 'MANIFEST.json')
    return {'manifest': pin(receipt_body), 'output': str(destination),
            'logical_read_bytes': meter.read_used, 'logical_write_bytes': meter.write_used,
            'elapsed_seconds': time.monotonic() - meter.started,
            'runtime_qualified': False, 'scientific_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--materials-identity', required=True)
    parser.add_argument('--panel-identity', required=True)
    parser.add_argument('--read-bytes', type=int, required=True)
    parser.add_argument('--write-bytes', type=int, required=True)
    parser.add_argument('--wall-seconds', type=int, required=True)
    args = parser.parse_args()
    try:
        result = materialize(args.source, args.output, expected_materials_identity=args.materials_identity,
                             expected_panel_identity=args.panel_identity, read_bytes=args.read_bytes,
                             write_bytes=args.write_bytes, wall_seconds=args.wall_seconds)
    except (MaterializationFailure, Refusal) as error:
        detail = error.detail if isinstance(error, MaterializationFailure) else {'status': 'failed', 'reason': str(error)}
        print(json.dumps(detail, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
