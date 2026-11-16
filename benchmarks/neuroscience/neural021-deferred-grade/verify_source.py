"""Authenticate this entire source package, then test a fresh captured copy.

This is a generated-source CI entrypoint, never a native/data qualification.
The caller selects the manifest's independently reviewed exact byte/hash pin.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile


def require(value, reason):
    if not value:
        raise ValueError(reason)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def capture(root, name, expected):
    require(type(name) is str and name and '\\' not in name, 'relative POSIX member')
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and all(p not in ('', '.', '..') for p in rel.parts)
            and rel.as_posix() == name, 'canonical relative member')
    require(type(expected) is dict and set(expected) == {'bytes', 'sha256'}, 'exact pin fields')
    require(type(expected['bytes']) is int and 0 < expected['bytes'] <= 1048576, 'bounded extent')
    digest = expected['sha256']
    require(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'SHA256 pin')
    path = root
    for part in rel.parts[:-1]:
        path /= part
        require(stat.S_ISDIR(path.lstat().st_mode), 'ordinary member parent')
    path /= rel.name
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'ordinary single-link exact member')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'stable opened member')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(expected['bytes'] + 1)
        after = os.fstat(fd)
        fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
        require(fields(before) == fields(after) == fields(path.lstat()), 'stable captured member')
    finally:
        os.close(fd)
    require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == digest, 'authenticated member bytes')
    return raw


def main():
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'use python -I -S -B')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest-bytes', type=int, required=True)
    ap.add_argument('--manifest-sha256', required=True)
    ap.add_argument('--check', action='store_true', required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    require(0 < args.manifest_bytes <= 65536, 'bounded manifest')
    manifest_raw = capture(root, 'SOURCE_MANIFEST.json', dict(bytes=args.manifest_bytes, sha256=args.manifest_sha256))
    manifest = parse(manifest_raw)
    require(type(manifest) is dict and set(manifest) == {'schema', 'files'}
            and manifest['schema'] == 'neural021_public_source_manifest_v1', 'manifest schema')
    members = manifest['files']
    require(type(members) is dict and 1 <= len(members) <= 64
            and 'SOURCE_MANIFEST.json' not in members
            and {'verify_source.py', 'peer_checks.py', 'test_grade_completed.py', 'grade_completed.py'} <= set(members), 'complete source manifest')
    bodies = {}
    total = len(manifest_raw)
    for name, pin in members.items():
        require(type(pin) is dict and type(pin.get('bytes')) is int, 'member pin')
        total += pin['bytes']
        require(total <= 4194304, 'whole source ceiling')
        bodies[name] = capture(root, name, pin)
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'no package symlinks')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        else:
            require(path.is_dir(), 'ordinary source tree')
    require(actual == set(bodies) | {'SOURCE_MANIFEST.json'}, 'exact source member population')
    with tempfile.TemporaryDirectory(prefix='neural021-relocated-generated-') as directory:
        dest = Path(directory).resolve() / 'source'
        dest.mkdir()
        for name, raw in bodies.items():
            path = dest / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (dest / 'SOURCE_MANIFEST.json').write_bytes(manifest_raw)
        # The tested source is the authenticated captured copy. cwd is outside it.
        result = subprocess.run([sys.executable, '-I', '-S', '-B', str(dest / 'peer_checks.py')],
                                cwd=directory, capture_output=True, text=True, timeout=120)
        require(len(result.stdout.encode()) + len(result.stderr.encode()) <= 65536, 'generated output ceiling')
        if result.stderr:
            sys.stderr.write(result.stderr)
        require(result.returncode == 0, 'generated checks nonzero exit')
        observed = parse(result.stdout)
        for key, expected in {'methods': 11, 'author_methods': 5, 'independent_methods': 6,
                              'failures': 0, 'errors': 0, 'skipped': 0,
                              'expected_failures': 0, 'unexpected_successes': 0,
                              'authentic_inputs_read': 0, 'native_or_model_calls': 0,
                              'scientific_qualification': False}.items():
            require(type(observed.get(key)) is type(expected) and observed[key] == expected, 'exact generated result: ' + key)
    print(json.dumps(dict(schema='neural021_relocated_source_check_v1', status='passed',
        source_members=len(bodies) + 1, source_bytes=total, manifest_sha256=args.manifest_sha256,
        relocated_generated_methods=11, skipped=0, failures=0, errors=0,
        expected_failures=0, unexpected_successes=0,
        complete_query_population=92, active_queries=52, perturbation_queries=40,
        authentic_inputs_read=0, native_or_model_calls=0, scientific_qualification=False,
        physical_IO_and_aggregate_peak_RSS_measured=False), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps(dict(status='failed', reason=str(error), error_type=type(error).__name__,
                              scientific_qualification=False)), file=sys.stderr)
        raise SystemExit(1)
