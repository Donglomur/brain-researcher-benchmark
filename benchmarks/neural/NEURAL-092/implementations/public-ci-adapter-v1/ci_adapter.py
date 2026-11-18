"""Preserve actual NEURAL-092 public-boundary evidence for the shared CI runner.

This trusted task adapter runs only the pinned six inactive source/CLI controls.
The enclosing runner owns the process group and final descendant cleanup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import time

RUNTIME = 'benchmarks/neural/NEURAL-092/implementations/registered-runtime-stable-deviance-v1'
PINS_SHA256 = '65bb6b18feb624cbb3b06e6f26be26eb8ef27b3942e424085bd26b741c6147d8'
CONTROL_IDS = ('inert_import', 'cli_inspection', 'cli_no_selection',
               'cli_exclusive_modes', 'unissued_selection_shadow_precedence',
               'unselected_import_cleanup')
MAX_REPORT = 8192
MAX_CAPTURE = 16384
CHILD_SECONDS = 120
FIXED = {
    'schema': 'neural092_public_boundary_controls_v1',
    'scope': 'POSIX stdlib source/import/CLI refusals only',
    'controls': [{'id': name, 'status': 'passed'} for name in CONTROL_IDS],
    'scientific_execution': False, 'selection_issued': False,
    'authentic_data': False, 'readiness_promoted': False, 'numerical_calls': 0,
    'fixture_bytes': 59,
    'fixture_sha256': '054cea2fadbcc6d79eaa271848478a120eaeca687fd4cac69d3b6440e816479c',
    'status': 'passed',
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError('nonfinite JSON constant')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=bad_constant)


def ordinary(path, directory=False):
    for parent in (path, *path.parents):
        need(not parent.is_symlink(), 'symlink in selected path')
    info = path.stat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
         'ordinary selected path required')
    return info


def bounded(path, limit):
    before = ordinary(path)
    need(before.st_size <= limit, 'selected file byte bound')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    after = path.stat()
    need(len(raw) == before.st_size and
         (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
         'selected file changed during read')
    return raw


def source_guard(repository, pins_path):
    raw = bounded(pins_path, 32768)
    need(hashlib.sha256(raw).hexdigest() == PINS_SHA256, 'source pin descriptor mismatch')
    descriptor = decode(raw)
    rows = descriptor['files']
    need(descriptor['runtime_root'] == RUNTIME and len(rows) == 69, 'exact source graph required')
    seen = set()
    total = 0
    for row in rows:
        name = row['path']
        need(name.startswith(RUNTIME + '/') and '..' not in Path(name).parts and name not in seen,
             'source path membership mismatch')
        seen.add(name)
        path = repository / name
        before = ordinary(path)
        need(row['mode'] == '100644' and not before.st_mode & 0o111, 'source executable mode changed')
        body = bounded(path, row['bytes'])
        need(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'],
             'selected source identity mismatch: ' + name)
        total += len(body)
    need(total == 429930, 'complete source byte extent required')
    return {'files': 69, 'bytes': total, 'descriptor_sha256': PINS_SHA256}


def allocate(repository, artifact):
    artifact = artifact.absolute()
    need(not artifact.exists() and not artifact.is_symlink(), 'fresh artifact directory required')
    ordinary(artifact.parent, directory=True)
    need(not artifact.resolve().is_relative_to(repository.resolve()), 'artifacts must stay outside checkout')
    artifact.mkdir(mode=0o700)
    return artifact


def capture(argv, repository, artifact, receipt):
    """Bound retained pipe bytes; the outer job owns the inherited process group."""
    process = None
    consumed = 0
    deadline = time.monotonic() + CHILD_SECONDS
    with (artifact / 'STDOUT.json').open('xb') as stdout, (artifact / 'STDERR.txt').open('xb') as stderr:
        try:
            process = subprocess.Popen(argv, cwd=repository, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, close_fds=True)
            receipt['child_pid'] = process.pid
            with selectors.DefaultSelector() as selector:
                for pipe, target in ((process.stdout, stdout), (process.stderr, stderr)):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, target)
                while selector.get_map():
                    need(time.monotonic() < deadline, 'public control child wall timeout')
                    for key, unused in selector.select(min(0.05, max(0, deadline-time.monotonic()))):
                        chunk = os.read(key.fileobj.fileno(), min(4096, MAX_CAPTURE-consumed+1))
                        if not chunk:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                            continue
                        retained = chunk[:MAX_CAPTURE-consumed]
                        key.data.write(retained)
                        consumed += len(retained)
                        receipt['retained_capture_bytes'] = consumed
                        need(len(retained) == len(chunk), 'public control combined capture limit')
                receipt['child_exit_code'] = process.wait(timeout=max(0.01, deadline-time.monotonic()))
        except BaseException as error:
            receipt['capture_error'] = {'type': type(error).__name__, 'message': str(error)[:768]}
            raise
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                receipt['child_exit_code'] = process.returncode
                for pipe in (process.stdout, process.stderr):
                    if pipe is not None:
                        pipe.close()


def validate_report(raw, stdout, stderr, exit_code, provenance):
    need(type(exit_code) is int and exit_code == 0, 'public control child did not succeed')
    need(not stderr and raw == stdout and len(raw) <= MAX_REPORT, 'raw report/capture mismatch')
    report = decode(raw)
    need(type(report) is dict and set(report) == set(FIXED) | set(provenance), 'public report fields changed')
    need(all(type(report[key]) is str and report[key] == value for key, value in provenance.items()),
         'actual interpreter provenance mismatch')
    projection = {key: report[key] for key in FIXED}
    need(json.dumps(projection, sort_keys=True, allow_nan=False) ==
         json.dumps(FIXED, sort_keys=True, allow_nan=False), 'public control statuses or scope changed')
    return projection


def run(repository, artifact):
    need(os.name == 'posix' and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
         'existing isolated POSIX interpreter required (-I -S -B)')
    repository = repository.resolve()
    ordinary(repository, directory=True)
    artifact = allocate(repository, artifact)
    provenance = {'interpreter': sys.executable, 'python_version': sys.version, 'platform': sys.platform}
    receipt = {'schema': 'neural092-public-ci-adapter-receipt/v1', 'status': 'failed',
               'provenance': provenance, 'child_exit_code': None, 'retained_capture_bytes': 0,
               'scientific_qualification': False,
               'descendant_cleanup': 'owned by enclosing job process group; not attested by this receipt'}
    pins_path = Path(__file__).with_name('SOURCE_PINS.json')
    try:
        receipt['source_before'] = source_guard(repository, pins_path)
        argv = [sys.executable, '-I', '-S', '-B',
                str(repository / RUNTIME / 'checks/test_public_contract.py'),
                '--work-root', str(artifact / 'generated-work'),
                '--report', str(artifact / 'RAW_REPORT.json')]
        receipt['argv'] = argv
        try:
            capture(argv, repository, artifact, receipt)
        finally:
            receipt['source_after'] = source_guard(repository, pins_path)
        raw = bounded(artifact / 'RAW_REPORT.json', MAX_REPORT)
        stdout = bounded(artifact / 'STDOUT.json', MAX_CAPTURE)
        stderr = bounded(artifact / 'STDERR.txt', MAX_CAPTURE)
        projection = validate_report(raw, stdout, stderr, receipt['child_exit_code'], provenance)
        receipt['raw_report'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        receipt['status'] = 'passed'
        return projection
    except BaseException as error:
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)[:768]}
        raise
    finally:
        body = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
        need(len(body) <= MAX_REPORT, 'adapter receipt byte bound')
        with (artifact / 'ADAPTER_RECEIPT.json').open('xb') as stream:
            stream.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-root', type=Path, required=True)
    args = parser.parse_args()
    try:
        projection = run(Path(__file__).resolve().parents[5], args.artifact_root)
    except Exception as error:
        print('NEURAL-092 public CI adapter refused: ' + type(error).__name__ + ': ' + str(error)[:768],
              file=sys.stderr)
        return 1
    print(json.dumps(projection, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
