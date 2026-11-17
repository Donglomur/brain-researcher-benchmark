"""Authenticate this public package; inspect, prepare offline source, or test captures.

The caller independently selects this bootstrap and manifest's reviewed pins.
No operation downloads source, data, dependencies, weights, or paper bodies.
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
import types


def require(value, reason):
    if not value:
        raise ValueError(reason)


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: require(False, 'nonfinite JSON'))


def capture(root, name, expected):
    require(type(name) is str and name and '\\' not in name, 'relative POSIX member')
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and rel.as_posix() == name and
            all(p not in ('', '.', '..') for p in rel.parts), 'canonical relative member')
    require(type(expected) is dict and set(expected) == {'bytes', 'sha256'}, 'exact pin fields')
    require(type(expected['bytes']) is int and 0 <= expected['bytes'] <= 1048576, 'bounded extent')
    digest = expected['sha256']
    require(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'SHA256 pin')
    path = root / rel
    for parent in (path.parent, *path.parent.parents):
        require(stat.S_ISDIR(parent.lstat().st_mode), 'ordinary source parent')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'], 'ordinary single-link exact member')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'stable opened member')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(expected['bytes'] + 1)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(fields(before) == fields(os.fstat(fd)) == fields(path.lstat()), 'stable captured member')
    finally:
        os.close(fd)
    require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == digest, 'authenticated member bytes')
    raw.decode('utf8')
    return raw


def authenticate(root, size, sha):
    require(type(size) is int and 0 < size <= 262144, 'bounded manifest')
    manifest_raw = capture(root, 'SOURCE_MANIFEST.json', dict(bytes=size, sha256=sha))
    manifest = parse(manifest_raw)
    require(type(manifest) is dict and set(manifest) == {'schema', 'files'} and
            manifest['schema'] == 'cbramod_public_source_manifest_v1', 'manifest schema')
    members = manifest['files']
    require(type(members) is dict and 1 <= len(members) <= 256 and
            'SOURCE_MANIFEST.json' not in members and
            {'verify_source.py', 'source_import.py', 'package_checks.py', 'executor/tests.py',
             'science/central_operator.py', 'science/SOURCE_FREEZE.json'} <= set(members), 'complete public source manifest')
    bodies = {}; total = len(manifest_raw)
    for name, pin in members.items():
        require(type(pin) is dict and type(pin.get('bytes')) is int, 'member pin')
        total += pin['bytes']; require(total <= 4194304, 'complete public source ceiling')
        bodies[name] = capture(root, name, pin)
    actual = set(); entries = 0
    for path in root.rglob('*'):
        entries += 1; require(entries <= 512, 'bounded complete source tree')
        st = path.lstat()
        require(stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode), 'ordinary source tree only')
        if stat.S_ISREG(st.st_mode): actual.add(path.relative_to(root).as_posix())
    require(actual == set(bodies) | {'SOURCE_MANIFEST.json'}, 'exact public member population')
    return bodies, manifest_raw, total


CHILD = r'''
import importlib.util, json, pathlib, sys, unittest
root = pathlib.Path(sys.argv[1])
full = sys.argv[2] == 'full'
suite = unittest.TestSuite()
for name, relative in [('packaging', 'package_checks.py')] + ([('executor_controls', 'executor/tests.py')] if full else []):
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
result = unittest.TextTestRunner(verbosity=2).run(suite)
expected = 24 if full else 8
observed = dict(methods=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                unexpected_successes=len(result.unexpectedSuccesses), packaging_methods=8,
                executor_methods=16 if full else 0, authentic_data_reads=0, native_or_model_calls=0,
                capacity_8gb_test=False, scientific_qualification=False)
if full:
    import numpy
    observed['numpy_version'] = numpy.__version__
print(json.dumps(observed, sort_keys=True))
sys.exit(0 if result.wasSuccessful() and result.testsRun == expected and not result.skipped
         and not result.expectedFailures and not result.unexpectedSuccesses else 1)
'''


def main():
    require(sys.flags.isolated and sys.dont_write_bytecode, 'use python -I -B')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation', choices=('inspect', 'prepare', 'check-package', 'check'))
    ap.add_argument('--manifest-bytes', type=int, required=True)
    ap.add_argument('--manifest-sha256', required=True)
    ap.add_argument('--official-root')
    ap.add_argument('--destination')
    args = ap.parse_args()
    needs_official = args.operation in ('prepare', 'check')
    require(bool(args.official_root) == needs_official, 'explicit external official root only for prepare/check')
    require(bool(args.destination) == (args.operation == 'prepare'), 'explicit fresh destination only for prepare')
    root = Path(__file__).resolve().parent
    bodies, manifest_raw, total = authenticate(root, args.manifest_bytes, args.manifest_sha256)
    result = dict(schema='cbramod_portable_source_v1', operation=args.operation,
                  public_source_complete=True, source_members=len(bodies) + 1, source_bytes=total,
                  bundled_scientific_roles=38, required_external_official_roles=65,
                  full_runtime_requires_external_source=True, datasets=12,
                  reproduction_candidate_files=800, reproduction_reference_slots=800,
                  improvement_candidate_cases=60, improvement_reference_slots=420,
                  authentic_data_reads=0, native_or_model_calls=0, capacity_8gb_test=False,
                  scientific_qualification=False, submission_ready=False)
    importer = types.ModuleType('authenticated_source_import')
    exec(compile(bodies['source_import.py'], '<authenticated offline source importer>', 'exec'), importer.__dict__)
    if args.operation == 'prepare':
        result['preparation'] = importer.prepare(bodies, args.official_root, args.destination, str(root))
    elif args.operation in ('check-package', 'check'):
        with tempfile.TemporaryDirectory(prefix='cbramod-portable-check-') as directory:
            dest = Path(directory).resolve() / 'package'; dest.mkdir()
            for name, raw in bodies.items():
                path = dest / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            (dest / 'SOURCE_MANIFEST.json').write_bytes(manifest_raw)
            if needs_official:
                # The prepared source is an external dependency for executor tests,
                # not a released package member or an authentic-data fixture.
                result['preparation'] = importer.prepare(bodies, args.official_root,
                    str(dest.parent / 'operator'), str(dest))
                (dest.parent / 'operator').rename(dest / 'prepared_operator')
            flags = ['-I', '-B'] if needs_official else ['-I', '-S', '-B']
            env = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR') if k in os.environ}
            env.update({k: '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')})
            child = subprocess.run([sys.executable, *flags, '-c', CHILD, str(dest), 'full' if needs_official else 'package'],
                                   cwd=directory, env=env, capture_output=True, text=True, timeout=120)
            require(len(child.stdout.encode()) + len(child.stderr.encode()) <= 65536, 'bounded generated output')
            if child.stderr: sys.stderr.write(child.stderr)
            require(child.returncode == 0, 'generated checks nonzero exit')
            observed = parse(child.stdout)
            expected = dict(methods=24 if needs_official else 8, failures=0, errors=0, skipped=0,
                            expected_failures=0, unexpected_successes=0, packaging_methods=8,
                            executor_methods=16 if needs_official else 0, authentic_data_reads=0,
                            native_or_model_calls=0, capacity_8gb_test=False, scientific_qualification=False)
            for key, value in expected.items():
                require(type(observed.get(key)) is type(value) and observed[key] == value, 'exact check result: ' + key)
            result['generated_checks'] = observed
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps(dict(status='failed', error_type=type(error).__name__, reason=str(error),
                              scientific_qualification=False)), file=sys.stderr)
        raise SystemExit(1)
