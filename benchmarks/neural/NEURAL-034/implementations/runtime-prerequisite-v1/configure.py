"""Explicit source-only publication successor; no input bodies or runtime launch.

The caller must supply a private parent without concurrent hostile writers.
Original repository members are never changed. The configured manifest is a new
primary release, not an expansion of the old three-member current-source gate.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat

PACKAGE = Path('benchmarks/neural/NEURAL-034/implementations')
PORTABLE = PACKAGE / 'neural034-portable'
CURRENT = PACKAGE / 'combined-workflow-v1/CURRENT_SOURCE.json'
LOCAL = 'authoring/glial-context-v1/ordinary-completion-v1/'
FREEZE = LOCAL + 'SOURCE_FREEZE.json'
ADMISSION = LOCAL + 'admission.py'
GRADER = LOCAL + 'grader/grader_runtime.py'
BRIDGE = LOCAL + 'grader/grade_bridge.py'
ARCHIVE = 'predecessor-publication-v1/'
CHANGED = ('provision.py', ADMISSION, GRADER, BRIDGE, FREEZE)
CURRENT_PIN = {'bytes': 6799, 'sha256': '2fc0406d021d9b74c43f15808c34f6ec32f7daa4ef3d88e0666315c8cc7ba267'}
MANIFEST_PIN = {'bytes': 6598, 'sha256': 'fe66143cda6de7f54c4e63b8751262aa6d892f0ae9074c8cbc86665795c9e4f3'}
FREEZE_PIN = {'bytes': 5437, 'sha256': 'e3d361b05de3d89a556a84ac1bbbcfb1e3780b357f185de555221475cb247818'}
HISTORICAL = {'path': FREEZE, 'bytes': 5621, 'sha256': '37d5797c474fa2f64e2bb7a1d27832b3fc94146e0ef3c8d95bfe16cef86cd84c'}
COPY_CAP = 300 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON member')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def plain(path):
    path = Path(path).absolute()
    need('..' not in path.parts and not any(c in str(path) for c in ('\0', '\r', '\n', ',')), 'Literal path')
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked path and ancestry')
    return path


def member(name):
    need(type(name) is str and name and not Path(name).is_absolute()
         and Path(name).as_posix() == name and '..' not in Path(name).parts
         and not any(c in name for c in ('\0', '\r', '\n', ',')), 'Canonical relative member')
    return name


def read(path, expected=None, cap=65536):
    path = plain(path)
    if expected is not None:
        need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
             and type(expected['bytes']) is int and 0 < expected['bytes'] <= cap
             and type(expected['sha256']) is str and re.fullmatch('[a-f0-9]{64}', expected['sha256']), 'Exact bounded pin')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded ordinary member')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        need(len(body) == before.st_size and stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'Stable source identity')
        need(expected is None or pin(body) == expected, 'Exact source checksum')
        return body
    finally:
        os.close(fd)


def _metadata(current_body, manifest_body):
    need(pin(current_body) == CURRENT_PIN and pin(manifest_body) == MANIFEST_PIN, 'Pinned predecessor descriptors')
    current = decode(current_body)
    manifest = decode(manifest_body)
    need(current['schema'] == 'neural034-current-source/v1' and current['task_id'] == 'NEURAL-034'
         and current['execution_authority'] is False and current['native_qualification'] is False, 'Non-authorizing predecessor')
    need(current['historical_manifest'] == {'path': 'SOURCE_MANIFEST.json', **MANIFEST_PIN}, 'Exact release lineage')
    need(current['changed_members'] == ['check_result.py', 'provision.py', 'tests/test_relocation.py'], 'Exact predecessor repairs')
    files = current['files']
    need(type(files) is dict and 1 <= len(files) <= 64 and set(files) == set(manifest['files']), 'Complete predecessor roster')
    need(sorted(name for name in files if files[name] != manifest['files'][name]) == current['changed_members'], 'Exact predecessor delta')
    for name in files:
        member(name)
    return current


def _capture(source_root):
    root = plain(source_root)
    current_body = read(root / CURRENT, CURRENT_PIN)
    manifest_body = read(root / PORTABLE / 'SOURCE_MANIFEST.json', MANIFEST_PIN)
    current = _metadata(current_body, manifest_body)
    bodies = {name: read(root / PORTABLE / name, expected) for name, expected in current['files'].items()}
    _closure(bodies)
    return bodies, current_body, manifest_body


def _closure(bodies):
    need(pin(bodies[FREEZE]) == FREEZE_PIN, 'Exact predecessor source freeze')
    freeze = decode(bodies[FREEZE])
    need(freeze['schema'] == 'neural034_ordinary_source_v1' and freeze['candidate_id'] == 'NEURAL-034'
         and freeze['execution_authority'] is False and freeze['historical_source_freeze'] == HISTORICAL, 'Original freeze lineage')
    need(all(name in bodies and pin(bodies[name]) == expected for name, expected in freeze['files'].items()), 'Complete held execution closure')
    need(freeze['entrypoint'] == {'path': LOCAL + 'run.py', **pin(bodies[LOCAL + 'run.py'])}, 'Original entrypoint pin')


def source_pin(source_root):
    """Authenticate every predecessor source body, never the INPUTS data bodies."""
    bodies, _, _ = _capture(source_root)
    return {'schema': 'neural034-publication-predecessor/v1', 'current_source': dict(CURRENT_PIN),
            'manifest': dict(MANIFEST_PIN), 'source_freeze': {'path': FREEZE, **FREEZE_PIN},
            'source_members': len(bodies), 'source_bytes': sum(map(len, bodies.values()))}


def replace_once(body, old, new):
    old, new = old.encode(), new.encode()
    need(body.count(old) == 1, 'Exactly one authenticated source replacement')
    return body.replace(old, new)


def _render(bodies, current_body, manifest_body):
    """Deterministic narrow successor; unchanged core bodies keep exact bytes."""
    files = dict(bodies)
    files['provision.py'] = replace_once(files['provision.py'],
        'if out is not None:os.fsync(out)',
        'if out is not None:os.fchmod(out,0o444);os.fsync(out)')
    files[GRADER] = replace_once(files[GRADER],
        'stream.write(body); stream.flush(); os.fsync(fd)',
        'stream.write(body); stream.flush(); os.fchmod(fd, 0o644); os.fsync(fd)')
    files[BRIDGE] = replace_once(files[BRIDGE], 'RUNTIME_PIN = ' + repr(pin(bodies[GRADER])),
                                'RUNTIME_PIN = ' + repr(pin(files[GRADER])))
    predecessor = {'path': FREEZE, **FREEZE_PIN}
    files[ADMISSION] = replace_once(files[ADMISSION],
        "IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'",
        'PREDECESSOR_SOURCE_FREEZE=' + repr(predecessor) + '\n' +
        "IMAGE='sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'")
    files[ADMISSION] = replace_once(files[ADMISSION],
        "prior.get('source_freeze') in (source_pin,HISTORICAL_SOURCE_FREEZE)",
        "prior.get('source_freeze') in (source_pin,HISTORICAL_SOURCE_FREEZE,PREDECESSOR_SOURCE_FREEZE)")
    freeze = decode(bodies[FREEZE])
    freeze['predecessor_source_freeze'] = predecessor
    freeze['publication_successor'] = 'neural034-owned-fd-publication/v1'
    freeze['files'] = {name: pin(files[name]) for name in freeze['files']}
    files[FREEZE] = encoded(freeze)
    for name in CHANGED:
        files[ARCHIVE + name] = bodies[name]
    files[ARCHIVE + 'CURRENT_SOURCE.json'] = current_body
    files[ARCHIVE + 'SOURCE_MANIFEST.json'] = manifest_body
    need(1 <= len(files) <= 64 and set(name for name in bodies if files[name] != bodies[name]) == set(CHANGED), 'Exact successor changes and bounded roster')
    manifest = {'schema': 'neural034-owned-fd-publication-source/v1', 'task_id': 'NEURAL-034',
                'execution_authority': False, 'native_qualification': False,
                'predecessor_current_source': {'path': ARCHIVE + 'CURRENT_SOURCE.json', **CURRENT_PIN},
                'predecessor_manifest': {'path': ARCHIVE + 'SOURCE_MANIFEST.json', **MANIFEST_PIN},
                'predecessor_source_freeze': predecessor,
                'historical_source_freeze': HISTORICAL, 'changed_members': sorted(CHANGED),
                'files': {name: pin(body) for name, body in sorted(files.items())}}
    files['SOURCE_MANIFEST.json'] = encoded(manifest)
    need(sum(map(len, files.values())) <= COPY_CAP, 'Bounded complete source copy')
    return files


def publish(path, body, mode=0o444):
    """Write exclusively and restore only the declared mode on the owned fd."""
    path = plain(path)
    need(type(body) is bytes and 0 < len(body) <= 65536 and mode in (0o444, 0o644), 'Bounded declared publication')
    need(path.parent.is_dir(), 'Existing private parent')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fchmod(fd, mode)
            os.fsync(fd)
    finally:
        os.close(fd)


def _receipt(files):
    return {'schema': 'neural034-owned-fd-publication-configuration/v1',
            'execution_authority': False, 'native_qualification': False,
            'source_freeze': {'path': FREEZE, **pin(files[FREEZE])},
            'manifest': {'path': 'SOURCE_MANIFEST.json', **pin(files['SOURCE_MANIFEST.json'])},
            'source_members': len(files), 'source_bytes': sum(map(len, files.values())),
            'changed_members': sorted(CHANGED), 'historical_source_freeze': HISTORICAL,
            'predecessor_source_freeze': {'path': FREEZE, **FREEZE_PIN}}


def configure(source_root, destination):
    """Create one absent private source workspace from repository root W."""
    root, destination = plain(source_root), plain(destination)
    need(root.is_dir() and destination.parent.is_dir() and not destination.exists()
         and root != destination and root not in destination.parents and destination not in root.parents,
         'Fresh separate private source destination')
    bodies, current, manifest = _capture(root)
    files = _render(bodies, current, manifest)
    destination.mkdir(mode=0o700)
    # A partial source copy remains for inspection if publication fails.
    for name, body in sorted(files.items()):
        target = destination / member(name)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        publish(target, body)
    return _receipt(files)


def load(destination):
    """Verify deterministic source closure; additional operator artifacts are unselected."""
    destination = plain(destination)
    need(destination.is_dir() and stat.S_IMODE(destination.stat().st_mode) == 0o700, 'Private source workspace')
    current_body = read(destination / ARCHIVE / 'CURRENT_SOURCE.json', CURRENT_PIN)
    manifest_body = read(destination / ARCHIVE / 'SOURCE_MANIFEST.json', MANIFEST_PIN)
    current = _metadata(current_body, manifest_body)
    bodies = {name: read(destination / (ARCHIVE + name if name in CHANGED else name), expected)
              for name, expected in current['files'].items()}
    _closure(bodies)
    files = _render(bodies, current_body, manifest_body)
    for name, body in files.items():
        path = destination / name
        read(path, pin(body))
        need(stat.S_IMODE(path.stat().st_mode) == 0o444, 'Exact configured source publication mode')
    return _receipt(files)
