"""Run the unchanged invented reporting controls; never open authentic data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import stat
import sys
import time
import traceback
import types

PINS = {
    'published_reporting.py': (11862, '8f87075849eece5320354fb05e5f1fa37eb3f541a0b9d8e924c79f9073e35963'),
    'synthetic_controls.py': (24754, 'fcc5eb391b94fcfad5b837bf25cb8263adc68b2b4715c45e5ec9231b8165753f'),
    'EXPECTED_CONTROLS.json': (2290, '85732113033d6cd9432059edea5ab3fe6a5e415a3723882697d8c9289e19708f'),
}


def read_source(path):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 1048576
    assert not any(p.is_symlink() for p in (path, *path.parents))
    body = path.read_bytes()
    after = path.lstat()
    assert (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) == (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    return body


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def write(path, value):
    body = (json.dumps(value, indent=2) + '\n').encode()
    assert len(body) <= 1048576
    with path.open('xb') as stream:
        assert stream.write(body) == len(body)
    return pin(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    output = Path(args.out)
    assert output.is_absolute() and not any(p.is_symlink() for p in (output, *output.parents))
    output.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()

    def expired(signum, frame):
        raise TimeoutError('synthetic control deadline')

    try:
        assert sys.platform == 'linux' and sys.version_info[:3] == (3, 11, 18)
        signal.signal(signal.SIGALRM, expired)
        signal.alarm(29)
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
        source = Path(__file__).absolute().parent
        bodies = {name: read_source(source / name) for name in (
            *PINS, 'run_synthetic.py', 'README.md')}
        for name, (size, sha) in PINS.items():
            assert pin(bodies[name]) == {'bytes': size, 'sha256': sha}
        (output / 'source').mkdir()
        for name, body in bodies.items():
            with (output / 'source' / name).open('xb') as stream:
                assert stream.write(body) == len(body)
        modules = {}
        for filename, name in [('published_reporting.py', 'published_reporting'),
                               ('synthetic_controls.py', 'synthetic_controls')]:
            module = types.ModuleType(name)
            module.__file__ = str(source / filename)
            sys.modules[name] = module
            exec(compile(bodies[filename], module.__file__, 'exec'), module.__dict__)
            modules[name] = module
        result = modules['synthetic_controls'].run(modules['published_reporting'])
        result_pin = write(output / 'CONTROLS.json', result)
        expected = json.loads(bodies['EXPECTED_CONTROLS.json'])
        assert result['status'] == 'PASS' and result['harness_failure'] is None
        assert [row['name'] for row in result['controls']] == expected['names']
        assert all(row['passed'] for row in result['controls'])
        assert result['registered_controls'] == result['executed_controls'] == result['passed_controls'] == expected['controls']
        assert result['failed_controls'] == result['remaining_controls_not_attempted'] == 0
        assert result['groups_completed'] == result['groups_attempted'] == expected['groups']
        assert result['assertions'] == {'attempted': expected['assertions'], 'completed': expected['assertions'], 'failed': 0}
        assert result['executed_projection_controls'] == expected['projection_controls']
        assert result['R_or_estimator_or_model_execution'] == result['readiness_delta'] == 0
        assert result['scientific_result'] is False and result['qualified_reference'] is False
        elapsed = time.monotonic() - start
        assert elapsed < 29
        receipt = {
            'schema': 'nider_reporting_public_synthetic_receipt_v1',
            'status': 'PASS_INVENTED_CONTROLS_ONLY', 'controls': 77, 'assertions': 268,
            'groups': 5, 'projection_controls': 10, 'result': result_pin,
            'source_pins': {name: pin(body) for name, body in bodies.items()},
            'python_version': sys.version, 'python_executable': sys.executable,
            'platform': platform.platform(), 'elapsed_seconds': elapsed,
            'primary_data_reads': 0, 'scientific_fits': 0, 'model_calls': 0,
            'scientifically_qualified': False,
            'containment_scope': 'Trusted synthetic source in CI; not an arbitrary-candidate sandbox.',
        }
        receipt_pin = write(output / 'RECEIPT.json', receipt)
        signal.alarm(0)
        print(json.dumps({'status': receipt['status'], 'receipt': receipt_pin}))
        return 0
    except BaseException as error:
        signal.alarm(0)
        write(output / 'FAILURE.json', {
            'status': 'FAILED_PRESERVED', 'type': type(error).__name__,
            'message': str(error), 'traceback': traceback.format_exc(),
            'elapsed_seconds': time.monotonic() - start, 'retry': False,
        })
        raise


if __name__ == '__main__':
    raise SystemExit(main())
