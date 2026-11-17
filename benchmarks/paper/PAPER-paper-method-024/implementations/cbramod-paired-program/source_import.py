"""Offline, exact-role preparation; external official source is never bundled here."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat


def require(value, reason):
    if not value:
        raise ValueError(reason)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON member')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'nonfinite JSON'))


def relative(name):
    require(type(name) is str and name and '\\' not in name, 'relative POSIX member')
    p = PurePosixPath(name)
    require(not p.is_absolute() and p.as_posix() == name and
            all(x not in ('', '.', '..') for x in p.parts), 'canonical relative member')
    return p


def absolute(value):
    require(type(value) is str and value.startswith('/') and not value.startswith('//'), 'canonical single-root path')
    p = Path(value)
    require(p.as_posix() == value and all(x not in ('.', '..') for x in p.parts), 'canonical absolute path')
    return p


def ordinary_parents(path):
    for p in reversed((path, *path.parents)):
        require(stat.S_ISDIR(p.lstat().st_mode), 'ordinary source directory; no symlink')


def capture(root, name, pin):
    rel = relative(name)
    require(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'exact pin fields')
    require(type(pin['bytes']) is int and 0 <= pin['bytes'] <= 1048576, 'bounded member extent')
    sha = pin['sha256']
    require(type(sha) is str and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha), 'SHA256 pin')
    path = root / rel
    ordinary_parents(path.parent)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin['bytes'], 'ordinary single-link exact member')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        require((os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (before.st_dev, before.st_ino), 'stable opened member')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(pin['bytes'] + 1)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(fields(before) == fields(os.fstat(fd)) == fields(path.lstat()), 'stable complete source capture')
    finally:
        os.close(fd)
    require(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == sha, 'authenticated exact source bytes')
    raw.decode('utf8')
    return raw


def prepare(bodies, official_root, destination, package_root):
    """Authenticate all65 external roles before creating any runtime destination.

    Caller supplies the already authenticated package bodies. This trusted API
    does not independently authorize those bodies; the public verifier does.
    """
    external = absolute(official_root)
    dest = absolute(destination)
    package = absolute(package_root)
    for other in (external, package):
        require(dest != other and dest not in other.parents and other not in dest.parents,
                'disjoint destination and source owners')
    ordinary_parents(external)
    ordinary_parents(dest.parent)
    require(not os.path.lexists(dest), 'fresh destination only')
    freeze = parse(bodies['science/SOURCE_FREEZE.json'])
    require(freeze['task_id'] == 'PAPER-paper-method-024' and freeze['role_count'] == 103,
            'complete original103-role source freeze')
    rows = freeze['roles']
    require(type(rows) is list and len(rows) == 103, 'all103 source roles')
    seen = set()
    captured = {}
    external_count = 0
    for row in rows:
        require(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'exact role fields')
        name = row['path']; relative(name)
        require(name.startswith('runtime/source/') and name not in seen, 'unique source-only role')
        seen.add(name)
        pin = {k: row[k] for k in ('bytes', 'sha256')}
        if name.startswith('runtime/source/official/'):
            raw = capture(external, name.removeprefix('runtime/source/official/'), pin)
            external_count += 1
        else:
            raw = bodies['science/' + name]
            require(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'bundled authored-role continuity')
        captured[name] = raw
    require(external_count == 65 and len(captured) - external_count == 38, 'full65 external and38 bundled roles')
    require(sum(map(len, captured.values())) == freeze['bytes'], 'full source byte population')
    captured['central_operator.py'] = bodies['science/central_operator.py']
    captured['SOURCE_FREEZE.json'] = bodies['science/SOURCE_FREEZE.json']
    # No checked-out file is executed or imported. No network is consulted.
    dest.mkdir(mode=0o700)
    try:
        for name, raw in captured.items():
            path = dest / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
    except BaseException:
        shutil.rmtree(dest)
        raise
    return dict(schema='cbramod_offline_source_preparation_v1', source_members=105,
                scientific_roles=103, external_roles=65, bundled_roles=38,
                source_bytes=sum(map(len, captured.values())), network_calls=0,
                source_code_executed=False, scientific_qualification=False)
