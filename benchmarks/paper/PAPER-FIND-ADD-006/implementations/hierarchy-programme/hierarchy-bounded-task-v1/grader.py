"""Bounded trusted hierarchy grader; private bodies open only in the lazy callback."""
import time
START = time.monotonic()
import argparse
import hashlib
import os
from pathlib import Path
import signal
import stat
import sys
import types

sys.path.insert(0, '/source')
import scorer_core as core
import generated_checks

REFERENCE_CORE_PIN = {'bytes': 18828, 'sha256': 'f419be9d6a55b34bd271b015937216243e4e37b584446e2b2c98da60508de08d'}


def captured(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        core.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
                  'Bounded ordinary captured file')
        parts = []; remaining = before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            core.need(bool(part), 'Complete captured descriptor')
            parts.append(part); remaining -= len(part)
        core.need(not os.read(fd, 1), 'No growth during capture')
        after = os.fstat(fd)
        core.need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                  (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                  'Stable captured descriptor')
        return b''.join(parts)
    finally:
        os.close(fd)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pinned(body, expected):
    core.need(type(expected) is dict and set(expected) == {'bytes', 'sha256'} and
              type(expected['bytes']) is int and expected['bytes'] > 0 and
              type(expected['sha256']) is str and len(expected['sha256']) == 64 and
              pin(body) == expected, 'Captured input matches exact invocation pin')


def save_score(path, result):
    body = core.json_bytes(result)
    core.need(len(body) <= core.SCORE_CAP, 'Bounded complete score report')
    final = Path(path); temporary = final.with_name(final.name + '.next')
    core.need(not final.exists() and not final.is_symlink(), 'Fresh final score')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            count = os.write(fd, view)
            core.need(count > 0, 'Complete score write'); view = view[count:]
        os.fsync(fd); os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    os.replace(temporary, final)
    return pin(body)


def main():
    def expire(*unused):
        raise TimeoutError('Forty-second grader work deadline')
    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, max(.001, START + 40 - time.monotonic()))
    parser = argparse.ArgumentParser()
    for field in ('submission', 'schema', 'references', 'output'):
        parser.add_argument('--' + field, required=True)
    args = parser.parse_args()
    reads = attempts = callbacks = 0
    checks = {'status': 'not_completed', 'cases': 0, 'count': 0}
    try:
        core.need((args.submission, args.schema, args.references, args.output) ==
                  ('/submission/submission.json', '/source/OUTPUT_SCHEMA.json',
                   '/source/REFERENCES.json', '/grade/score.json'), 'Exact trusted grader aliases')
        invocation = core.strict_json(captured('/source/invocation.json', 16384))
        core.need(type(invocation) is dict and set(invocation) ==
                  {'schema_version', 'candidate_id', 'submission', 'output_schema', 'references'} and
                  type(invocation['schema_version']) is int and invocation['schema_version'] == 1 and
                  invocation['candidate_id'] == core.CANDIDATE_ID, 'Exact grader invocation')
        schema_body = captured(args.schema, 200000); reference_body = captured(args.references, 16384)
        pinned(schema_body, invocation['output_schema']); pinned(reference_body, invocation['references'])
        spec = core.strict_json(schema_body); core.validate_schema(spec)
        refs = core.strict_json(reference_body)
        core.need(type(refs) is dict and set(refs) == {'schema_version', 'candidate_id', 'files'} and
                  type(refs['schema_version']) is int and refs['schema_version'] == 1 and
                  refs['candidate_id'] == core.CANDIDATE_ID and type(refs['files']) is dict and
                  set(refs['files']) == set(core.MEMBER_CAPS), 'Exact protected reference descriptors')
        for name, row in refs['files'].items():
            core.need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and
                      row['path'] == '/reference/' + name and type(row['bytes']) is int and
                      0 < row['bytes'] <= core.MEMBER_CAPS[name] and type(row['sha256']) is str and
                      len(row['sha256']) == 64, 'Fixed bounded private alias')
        # Verified captured implementation, not an import that reopens its path.
        source = captured('/source/reference_core.py', 100000); pinned(source, REFERENCE_CORE_PIN)
        reference_core = types.ModuleType('hierarchy_held_reference_core')
        reference_core.__file__ = '/source/reference_core.py'
        exec(compile(source, reference_core.__file__, 'exec'), reference_core.__dict__)
        import numpy as np
        core.need(np.__version__ == '2.2.6', 'Held NumPy API; no Ward optimization in grader')
        checks = generated_checks.run(np, reference_core, core, spec)
        core.need(checks['status'] == 'central_generated_checks_passed' and
                  checks['cases'] == checks['count'] == 8, 'Eight invented scoring guard groups')
        def loader():
            nonlocal reads, attempts, callbacks
            callbacks += 1; bodies = {}
            for name in ('linkages.npz', 'report.json'):
                row = refs['files'][name]; attempts += 1
                body = captured(row['path'], core.MEMBER_CAPS[name]); reads += 1
                pinned(body, {k: row[k] for k in ('bytes', 'sha256')}); bodies[name] = body
            return core.decode_reference(np, bodies)
        try:
            candidate = captured(args.submission, core.SUBMISSION_CAP)
        except TimeoutError:
            raise
        except (OSError, ValueError) as error:
            result = core.invalid_submission('Candidate capture: ' + type(error).__name__ + ': ' + str(error))
        else:
            pinned(candidate, invocation['submission'])
            result = core.grade(candidate, spec, loader, np, reference_core)
        core.need(result['private_loader_calls'] == callbacks and result['private_reference_reads'] == reads,
                  'Private callback/read counts match actual captures')
        code = 0 if result['status'] == 'scored' else 2
    except Exception as error:
        result = {'status': 'operator_error', 'submission_valid': None,
                  'reason': type(error).__name__ + ': ' + str(error)[:512],
                  'private_loader_calls': callbacks, 'private_reference_reads': reads,
                  'performance_floor': None, 'scientific_success': None}
        code = 1
    signal.signal(signal.SIGALRM, lambda *unused: os._exit(124))
    signal.setitimer(signal.ITIMER_REAL, min(5.0, max(.001, START + 45 - time.monotonic())))
    result.update(generated_checks=checks, model_fits=0, ward_optimizations=0,
                  private_reference_read_attempts=attempts, wall_seconds_before_output=time.monotonic() - START)
    score_pin = save_score(args.output, result)
    terminal = core.json_bytes({'status': result['status'], 'score_file': 'score.json',
                                'score_pin': score_pin, 'private_reference_reads': reads,
                                'generated_checks': checks})
    core.need(len(terminal) <= 16384, 'Terminal summary cap')
    sys.stdout.write(terminal.decode()); sys.stdout.flush()
    core.need(time.monotonic() < START + 45, 'Finalization within grader wall deadline')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
