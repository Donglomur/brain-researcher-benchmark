"""Authenticate the portable NEURAL-061 source and run relocated generated checks.

No dataset, target, fitted model, Docker operation or API call is selected here.
Use Python 3.11+ with -I -S -B and an independently selected manifest byte/hash pin.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import stat
import sys
import tempfile
import types
import unittest

MAX_MEMBER = 1048576
MAX_TOTAL = 4194304
MAX_MEMBERS = 128
AUTHOR_METHODS = 21
PACKAGE_METHODS = 5
ROLES = ('wire', 'enclosure', 'supervisor', 'adapter', 'loader')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def parse(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'duplicate JSON member'); out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'nonfinite JSON token'))


def relative(name):
    require(type(name) is str and name and '\\' not in name and '\x00' not in name,
            'literal relative POSIX member')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and
            all(part not in ('', '.', '..') for part in name.split('/')) and len(path.parts) <= 6,
            'canonical package member path')
    return path


def pin(value):
    require(type(value) is dict and set(value) == {'bytes', 'sha256'} and
            type(value['bytes']) is int and 0 < value['bytes'] <= MAX_MEMBER and
            type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
            'exact bounded source pin')
    return value


def capture(root, name, expected):
    parts = relative(name).parts; pin(expected)
    path = root
    for part in parts[:-1]:
        path /= part
        require(stat.S_ISDIR(path.lstat().st_mode), 'ordinary source parent, no links')
    path /= parts[-1]
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            before.st_size == expected['bytes'], 'ordinary exact single-link source')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'same opened source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(expected['bytes'] + 1)
        after = os.fstat(fd)
        fields = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink,
                              row.st_size, row.st_mtime_ns, row.st_ctime_ns)
        require(fields(before) == fields(after) == fields(path.lstat()), 'stable complete source capture')
    finally:
        os.close(fd)
    require(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
            'source content identity')
    body.decode('utf8')
    return body


def inner_joins(bodies):
    """All inner factory/science references terminate inside this package."""
    producer = parse(bodies['producer/SOURCE_MANIFEST.json'])
    require(producer['schema'] == 'N061_NATIVE_STATE_SOURCE_V1' and producer['task'] == 'NEURAL-061',
            'accepted participant schema')
    wanted = {name + '.py' for name in (*ROLES, 'child', 'run')} | {'INHERITED.json'}
    require(set(producer['files']) == wanted, 'complete exact participant source roles')
    require({name.removeprefix('producer/') for name in bodies if name.startswith('producer/')} ==
            wanted | {'SOURCE_MANIFEST.json'}, 'no unbound participant members')
    for name, expected in producer['files'].items():
        pin(expected); body = bodies['producer/' + name]
        require(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
                'inner participant source binding')
    science = parse(bodies['science/SOURCE_MANIFEST.json'])
    require(science['schema'] == 'N061_PORTABLE_SCIENCE_MANIFEST_V1' and science['task'] == 'NEURAL-061'
            and science['scientific_changes'] is False, 'portable exact scientific source manifest')
    require(len(science['files']) == 35 and
            {name.removeprefix('science/') for name in bodies if name.startswith('science/')} ==
            set(science['files']) | {'SOURCE_MANIFEST.json'}, 'complete scientific source and contract population')
    for name, expected in science['files'].items():
        relative(name); pin(expected); body = bodies['science/' + name]
        require(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
                'inner scientific source binding')
    inherited = parse(bodies['producer/INHERITED.json'])
    raw = bodies['science/SOURCE_MANIFEST.json']; expected = pin(inherited['installed_manifest'])
    require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
            'factory uses this same bundled science manifest')
    runtime = {name: value for name, value in science['files'].items() if name.startswith('runtime/n061/')}
    require(len(runtime) == 22 and inherited['runtime'] == runtime and inherited['scientific_changes'] is False,
            'complete original 22-module scientific runtime; no external source dependency')


def authenticate(root, expected_bytes, expected_sha256):
    root = Path(root).absolute()
    require(all(not path.is_symlink() for path in (root, *root.parents)) and root.is_dir(),
            'ordinary package root and ancestors')
    expected = pin({'bytes': expected_bytes, 'sha256': expected_sha256})
    require(expected_bytes <= 65536, 'bounded package manifest')
    raw = capture(root, 'SOURCE_MANIFEST.json', expected); manifest = parse(raw)
    require(type(manifest) is dict and set(manifest) == {'schema', 'task', 'files'} and
            manifest['schema'] == 'N061_PORTABLE_PUBLIC_PACKAGE_V1' and manifest['task'] == 'NEURAL-061',
            'closed public package manifest')
    members = manifest['files']
    require(type(members) is dict and 1 <= len(members) <= MAX_MEMBERS and 'SOURCE_MANIFEST.json' not in members,
            'finite nonrecursive package membership')
    require({'README.md', 'LICENSE', 'PROVENANCE.json', 'verify_source.py', 'tests.py', 'test_package.py',
             'producer/SOURCE_MANIFEST.json', 'science/SOURCE_MANIFEST.json'} <= set(members),
            'complete portable entrypoint and dependency roots')
    total = len(raw)
    # Validate all selectors before reading any selected member.
    for name, expected in members.items():
        relative(name); pin(expected); total += expected['bytes']
        require(total <= MAX_TOTAL, 'whole source byte ceiling')
    actual = set(); directories = [root]; directory_count = 1
    while directories:
        directory = directories.pop()
        for path in directory.iterdir():
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                require(len(path.relative_to(root).parts) <= 6, 'bounded source depth')
                directory_count += 1
                require(directory_count <= MAX_MEMBERS, 'bounded source directory population')
                directories.append(path)
            else:
                require(stat.S_ISREG(mode), 'no links or special package members')
                actual.add(path.relative_to(root).as_posix())
                require(len(actual) <= MAX_MEMBERS + 1, 'bounded source member population')
    require(actual == set(members) | {'SOURCE_MANIFEST.json'}, 'exact source population; no unlisted bytecode')
    bodies = {name: capture(root, name, expected) for name, expected in members.items()}
    bodies['SOURCE_MANIFEST.json'] = raw
    inner_joins(bodies)
    return bodies


def load_producer(bodies):
    """Compile the unchanged accepted bootstrap and role bodies from captured bytes."""
    inner_joins(bodies)
    bootstrap = types.ModuleType('n061_verified_producer_bootstrap')
    bootstrap.__file__ = '<captured-public-source>/producer/run.py'
    exec(compile(bodies['producer/run.py'], bootstrap.__file__, 'exec'), bootstrap.__dict__)
    selected = {name.removeprefix('producer/'): body for name, body in bodies.items()
                if name.startswith('producer/') and '/' not in name.removeprefix('producer/')}
    return bootstrap.compile_modules(selected)


def completed(result, expected):
    return (result.wasSuccessful() and result.testsRun == expected and not result.failures and not result.errors
            and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses)


def run_generated(bodies):
    """One source-only process, executing a relocated copy of authenticated bytes."""
    with tempfile.TemporaryDirectory(prefix='neural061-generated-public-') as directory:
        destination = Path(directory).resolve() / 'package'; destination.mkdir()
        for name, body in bodies.items():
            path = destination / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        before_cwd = Path.cwd(); os.chdir(Path(directory).resolve())
        try:
            suites = []
            for name, module_name in (('tests.py', 'n061_public_author_controls'),
                                      ('test_package.py', 'n061_public_package_controls')):
                module = types.ModuleType(module_name); module.__file__ = str(destination / name)
                module.__verified_package__ = {'root': destination, 'bodies': bodies}
                sys.modules[module_name] = module
                exec(compile(bodies[name], module.__file__, 'exec'), module.__dict__)
                suites.append(unittest.defaultTestLoader.loadTestsFromModule(module))
            require(suites[0].countTestCases() == AUTHOR_METHODS and suites[1].countTestCases() == PACKAGE_METHODS,
                    'exact generated control population')
            result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
            require(completed(result, AUTHOR_METHODS + PACKAGE_METHODS),
                    'every generated method must pass; failure, error, skip and expected failure all refuse')
            return result.testsRun
        finally:
            os.chdir(before_cwd)


def main(argv=None):
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'use Python -I -S -B')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-bytes', type=int, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    bodies = authenticate(Path(__file__).absolute().parent, args.manifest_bytes, args.manifest_sha256)
    # CI may execute captured bytes with exec(..., fresh_globals), so __main__
    # in sys.modules can still be the bootstrap. Publish this actual namespace,
    # never a different entrypoint module or a filesystem import.
    exported = types.ModuleType('n061_public_verifier')
    exported.__dict__.update(globals())
    sys.modules['n061_public_verifier'] = exported
    methods = run_generated(bodies) if args.check else 0
    if args.inspect:
        load_producer(bodies)
    used = resource.getrusage(resource.RUSAGE_SELF)
    peak = used.ru_maxrss if sys.platform == 'darwin' else used.ru_maxrss * 1024
    require(peak <= 134217728, 'observed generated-verifier RSS exceeds source lane')
    print(json.dumps({'schema': 'N061_PORTABLE_PUBLIC_CHECK_V1', 'status': 'passed',
          'operation': 'generated-check' if args.check else 'inspect', 'source_members': len(bodies),
          'source_bytes': sum(map(len, bodies.values())), 'manifest_sha256': args.manifest_sha256,
          'generated_methods': methods, 'author_methods': AUTHOR_METHODS if args.check else 0,
          'package_methods': PACKAGE_METHODS if args.check else 0, 'failures': 0, 'errors': 0,
          'skipped': 0, 'expected_failures': 0, 'unexpected_successes': 0,
          'source_sessions': 423, 'source_animals': 126, 'evaluation_sessions': 29,
          'evaluation_animals': 13, 'reference_arms': 6, 'candidate_arms': ['BR', 'BC'],
          'matching_seeds': 10, 'regions': 'all original R; two generated regions only in controls',
          'authentic_inputs_read': 0, 'native_or_model_calls': 0, 'scientific_qualification': False,
          'runtime_qualification': False, 'ready_delta': 0, 'observed_max_rss_bytes': peak,
          'user_cpu_seconds': used.ru_utime, 'system_cpu_seconds': used.ru_stime}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'reason': str(error),
                          'scientific_qualification': False}), file=sys.stderr)
        raise SystemExit(1)
