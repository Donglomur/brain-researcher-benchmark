"""Authenticate the complete NIDER public component before any test import."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

NAMES = frozenset(["ENGINE_MANIFEST.json","LOCATIONS.template.json","OPERATIONS.md","PROVISIONING.md","README.md","RIGHTS.md","RUNTIME_REQUIREMENTS.json","engine/ASSET_MANIFEST.template.json","engine/FULL120_OWNER.template.json","engine/comparator/compare_local.py","engine/comparator/custody.py","engine/comparator/extended_score.py","engine/comparator/reporting_core.py","engine/comparator/reporting_resolution.py","engine/configuration/LOCK.json","engine/configuration/authoring_gateway.py","engine/configuration/configuration.py","engine/owner/PACKAGE_LOCK.json","engine/owner/admit_runtime.py","engine/owner/owner_package.py","engine/participant/AUTHOR_LABELS.json","engine/participant/DATA_SCHEMA.md","engine/participant/FIELD_SCHEMA.json","engine/participant/METHODS.md","engine/participant/OUTPUT_INTERFACE.json","engine/participant/TASK.md","engine/runtime/DEPENDENCIES.json","engine/runtime/FULL120_CONTRACT.json","engine/runtime/build_spec.py","engine/runtime/custody.py","engine/runtime/extended_score.py","engine/runtime/full120_output.py","engine/runtime/full120_portable.py","engine/runtime/observe_protected_runner.py","engine/runtime/owner_binding.py","engine/runtime/protected_runner.py","engine/runtime/reporting_core.py","engine/runtime/runtime_policy.py","engine/runtime/scientific_score.py","instruction.md","run_public_checks.py","setup.py","test_setup.py","test_v3_projection.py"])
MANIFEST_NAME = 'SOURCE_MANIFEST.json'
SCHEMA = 'nider120-owner-public-source-v1'


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_exact(path, extent, digest):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != extent:
        raise ValueError('ordinary exact public member required: ' + path.name)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError('public member changed before read')
        body = stream.read(extent + 1)
        after = os.fstat(stream.fileno())
    if identity(before) != identity(after) or identity(after) != identity(path.lstat()):
        raise ValueError('public member changed during read')
    if len(body) != extent or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('public member digest differs: ' + path.name)
    return body


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate manifest key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite manifest')))


def verify_public(root, manifest_bytes, manifest_sha256):
    root = Path(root).absolute()
    if '..' in root.parts or any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError('ordinary component ancestry required')
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError('ordinary component directory required')
    if type(manifest_bytes) is not int or not 0 < manifest_bytes <= 65536:
        raise ValueError('manifest extent out of bounds')
    if type(manifest_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', manifest_sha256):
        raise ValueError('manifest digest shape differs')
    raw = read_exact(root / MANIFEST_NAME, manifest_bytes, manifest_sha256)
    manifest = strict_json(raw)
    if type(manifest) is not dict or set(manifest) != {'schema', 'members'} or manifest['schema'] != SCHEMA:
        raise ValueError('public manifest schema differs')
    rows = manifest['members']
    if type(rows) is not list or len(rows) != len(NAMES):
        raise ValueError('complete public member count required')
    seen = set()
    total = 0
    for row in rows:
        if type(row) is not dict or set(row) != {'path', 'bytes', 'sha256'}:
            raise ValueError('public member schema differs')
        name = row['path']
        if type(name) is not str or name not in NAMES or name in seen:
            raise ValueError('complete unique public member names required')
        if type(row['bytes']) is not int or not 0 < row['bytes'] <= 262144:
            raise ValueError('public member extent out of bounds')
        if type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('public member digest shape differs')
        seen.add(name)
        total += row['bytes']
    if seen != NAMES or total > 2097152:
        raise ValueError('complete bounded source selection required')
    allowed_dirs = {str(parent) for name in NAMES for parent in PurePosixPath(name).parents
                    if str(parent) != '.'}
    found_files, found_dirs, pending = set(), set(), [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                rel = str(path.relative_to(root))
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    if rel not in allowed_dirs:
                        raise ValueError('unexpected source directory')
                    found_dirs.add(rel)
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    found_files.add(rel)
                else:
                    raise ValueError('ordinary single-link source required')
    if found_files != NAMES | {MANIFEST_NAME} or found_dirs != allowed_dirs:
        raise ValueError('exact recursive component inventory required')
    bodies = {row['path']: read_exact(root / row['path'], row['bytes'], row['sha256']) for row in rows}
    return bodies


def run_generated_checks(root, bodies):
    """Run the existing public-safe metadata controls from authenticated source bytes."""
    import sys
    import tempfile
    import types
    import unittest
    module_names = ('setup', 'nider_public_setup_controls', 'nider_public_projection_controls')
    if any(name in sys.modules for name in module_names):
        raise ValueError('clean public control module namespace required')
    previous_test_root = os.environ.get('NIDER_TEST_ROOT')
    try:
        with tempfile.TemporaryDirectory(prefix='nider-public-metadata-') as temporary:
            os.environ['NIDER_TEST_ROOT'] = str(Path(temporary).resolve())
            loaded = {}
            for name, source in (('setup', 'setup.py'),
                                 ('nider_public_setup_controls', 'test_setup.py'),
                                 ('nider_public_projection_controls', 'test_v3_projection.py')):
                module = types.ModuleType(name)
                module.__file__ = str(root / source)
                sys.modules[name] = module
                exec(compile(bodies[source], module.__file__, 'exec'), module.__dict__)
                loaded[name] = module
            suite = unittest.TestSuite((
                unittest.defaultTestLoader.loadTestsFromTestCase(loaded['nider_public_setup_controls'].SetupControls),
                unittest.defaultTestLoader.loadTestsFromTestCase(loaded['nider_public_projection_controls'].ProjectionControls),
            ))
            if suite.countTestCases() != 16:
                raise ValueError('13 setup plus3 projection methods required')
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            if not result.wasSuccessful():
                raise SystemExit(1)
            print(json.dumps({'schema': 'nider-public-source-controls-v1',
                              'tests': result.testsRun,
                              'public_source_members_authenticated': len(bodies),
                              'scientific_execution': False,
                              'runtime_admitted': False,
                              'new_benchmark_ids': 0}, sort_keys=True))
    finally:
        for name in module_names:
            sys.modules.pop(name, None)
        if previous_test_root is None:
            os.environ.pop('NIDER_TEST_ROOT', None)
        else:
            os.environ['NIDER_TEST_ROOT'] = previous_test_root


def main():
    import argparse
    import sys
    if sys.flags.optimize:
        raise ValueError('public controls require assertions enabled')
    root = Path(__file__).absolute().parent
    if '_PUBLIC_SOURCE_BODIES' in globals():
        bodies = globals()['_PUBLIC_SOURCE_BODIES']
        if set(bodies) != NAMES:
            raise ValueError('complete trusted CI source cache required')
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--manifest-bytes', required=True, type=int)
        parser.add_argument('--manifest-sha256', required=True)
        args = parser.parse_args()
        bodies = verify_public(root, args.manifest_bytes, args.manifest_sha256)
    run_generated_checks(root, bodies)


if __name__ == '__main__':
    main()
