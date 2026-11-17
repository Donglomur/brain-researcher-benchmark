"""Authenticate the selected public source, then test a fresh captured copy.

Caller trust starts with this verifier/interpreter and an independently reviewed
manifest pin. No dataset, Docker daemon, candidate or numerical grader runs here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile


def need(ok, message):
    if not ok:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON member')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def capture(root, name, pin):
    need(type(name) is str and name and '/' not in name and '\\' not in name
         and name not in ('.', '..') and not name.startswith('.'), 'flat source member')
    need(type(pin) is dict and set(pin) == {'bytes', 'sha256'}, 'exact source pin')
    need(type(pin['bytes']) is int and 0 < pin['bytes'] <= 1048576, 'bounded source extent')
    need(type(pin['sha256']) is str and len(pin['sha256']) == 64
         and all(c in '0123456789abcdef' for c in pin['sha256']), 'source SHA256')
    path = root / name
    for parent in (root, *root.parents):
        need(not parent.is_symlink(), 'unlinked source root')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and before.st_size == pin['bytes'], 'ordinary exact source member')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'stable opened source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(pin['bytes'] + 1)
        after = os.fstat(fd)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(fields(before) == fields(after) == fields(path.lstat()), 'stable captured source')
    finally:
        os.close(fd)
    need(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'authenticated source bytes')
    return raw


def captured_package(root, size, sha):
    need(type(size) is int and 0 < size <= 65536, 'bounded manifest')
    raw = capture(root, 'SOURCE_MANIFEST.json', {'bytes': size, 'sha256': sha})
    manifest = strict(raw)
    need(type(manifest) is dict and set(manifest) == {'schema', 'task_id', 'files',
         'scientific_qualification', 'native_qualification', 'authentic_inputs_included'}, 'manifest fields')
    need(manifest['schema'] == 'neural029-program-source-v1' and manifest['task_id'] == 'NEURAL-029'
         and all(manifest[k] is False for k in ('scientific_qualification', 'native_qualification', 'authentic_inputs_included')),
         'source-only manifest scope')
    files = manifest['files']
    need(type(files) is dict and 1 <= len(files) <= 64 and 'SOURCE_MANIFEST.json' not in files,
         'finite manifest population')
    need({'run.py', 'executor.py', 'runtime_contract.py', 'grade.py', 'core.py',
          'source_identity_join.py', 'io_utils.py', 'absence.py', 'holder.py',
          'boundary_controls.py', 'cache_regression.py', 'tests.py',
          'verify_source.py', 'check_package.py'} <= set(files), 'required source members')
    bodies = {}
    total = len(raw)
    for name, pin in files.items():
        need(type(pin) is dict and type(pin.get('bytes')) is int, 'member extent')
        total += pin['bytes']
        need(total <= 4194304, 'whole source ceiling')
        bodies[name] = capture(root, name, pin)
    entries = list(root.iterdir())
    need(all(stat.S_ISREG(p.lstat().st_mode) for p in entries)
         and {p.name for p in entries} == set(files) | {'SOURCE_MANIFEST.json'}, 'exact flat package population')
    return raw, bodies, total


def strict_result(result):
    expected = {'schema': 'neural029_public_generated_checks_v1', 'methods': 18,
                'boundary_methods': 10, 'packaging_methods': 8, 'failures': 0, 'errors': 0,
                'skipped': 0, 'expected_failures': 0, 'unexpected_successes': 0,
                'cache_regression_passed': True, 'real_Docker_calls': 0,
                'authentic_inputs_read': 0, 'model_calls': 0, 'scientific_qualification': False}
    need(type(result) is dict and set(result) == set(expected), 'exact generated result fields')
    for key, value in expected.items():
        need(type(result[key]) is type(value) and result[key] == value, 'generated disposition: ' + key)


def run_checks(directory, source):
    # Output goes to temporary files so child output cannot grow parent memory.
    # The authenticated generated script has no untrusted programme or dataset.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen([sys.executable, '-I', '-S', '-B', str(source / 'check_package.py')],
                                cwd=directory, stdout=out, stderr=err, start_new_session=True)
        try:
            code = proc.wait(timeout=120)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=10)
            raise
        out.seek(0); err.seek(0)
        stdout, stderr = out.read(65537), err.read(65537)
        need(len(stdout) + len(stderr) <= 65536, 'generated output ceiling')
        if stderr:
            sys.stderr.write(stderr.decode('utf8'))
        need(code == 0, 'generated process failed')
        strict_result(strict(stdout))


def main():
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
         and not sys.flags.optimize, 'use Python -I -S -B without optimization')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest-bytes', type=int, required=True)
    ap.add_argument('--manifest-sha256', required=True)
    ap.add_argument('--check', action='store_true', required=True)
    args = ap.parse_args()
    root = Path(__file__).absolute().parent
    manifest, bodies, total = captured_package(root, args.manifest_bytes, args.manifest_sha256)
    with tempfile.TemporaryDirectory(prefix='neural029-public-relocated-') as directory:
        directory = Path(directory).resolve()
        dest = directory / 'source'; dest.mkdir()
        for name, body in bodies.items():
            (dest / name).write_bytes(body)
        (dest / 'SOURCE_MANIFEST.json').write_bytes(manifest)
        run_checks(directory, dest)
    print(json.dumps({'schema': 'neural029_portable_source_check_v1', 'status': 'passed',
          'source_members': len(bodies) + 1, 'source_bytes': total,
          'manifest_sha256': args.manifest_sha256, 'methods': 18, 'boundary_methods': 10,
          'packaging_methods': 8, 'failures': 0, 'errors': 0, 'skipped': 0,
          'expected_failures': 0, 'unexpected_successes': 0, 'cache_regression_passed': True,
          'real_Docker_calls': 0, 'authentic_inputs_read': 0, 'model_calls': 0,
          'scientific_qualification': False, 'native_qualification': False,
          'physical_IO_and_aggregate_RSS_measured': False}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__,
                          'reason': str(error), 'scientific_qualification': False}), file=sys.stderr)
        raise SystemExit(1)
