"""Trusted full-cohort grader; all public pairs precede one lazy private read."""
import time
START = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import types

CANDIDATE_ID = 'PAPER-FIND-REP-009'
SOURCE_NAMES = {'grader.py', 'scorer_core.py', 'generated_checks.py', 'paired_diagnostics.R',
                'SESSION_MANIFEST.json', 'REFERENCE_EXPECTATIONS.json'}
PAIR_NAMES = ['pair%03d.json' % i for i in range(1, 18)]
R_SCRIPT = '/opt/thalamus/R-4.3.1/bin/Rscript'
SCORE_CAP = 1_000_000


def need(ok, message):
    if not ok:
        raise ValueError(message)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def metadata(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'No duplicate trusted metadata keys')
            result[k] = v
        return result
    return json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'No nonfinite trusted metadata'))


def captured(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link ordinary captured file')
        parts = []; remaining = before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            need(bool(part), 'Complete captured file'); parts.append(part); remaining -= len(part)
        need(not os.read(fd, 1), 'No file growth')
        after = os.fstat(fd)
        need(all(getattr(before, k) == getattr(after, k) for k in
                 ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'Stable captured file')
        return b''.join(parts)
    finally:
        os.close(fd)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pinned(body, expected):
    need(type(expected) is dict and set(expected) == {'bytes', 'sha256'}
         and type(expected['bytes']) is int and expected['bytes'] > 0
         and type(expected['sha256']) is str and re.fullmatch('[0-9a-f]{64}', expected['sha256'])
         and pin(body) == expected, 'Exact captured invocation descriptor')


def module(name, filename, body):
    result = types.ModuleType(name)
    result.__file__ = filename
    exec(compile(body, filename, 'exec'), result.__dict__)
    return result


def save_score(path, result):
    body = json_bytes(result)
    need(len(body) <= SCORE_CAP, 'Complete score within one-million-byte cap')
    final = Path(path); temporary = final.with_name(final.name + '.next')
    need(not final.exists() and not final.is_symlink(), 'Fresh final score')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            written = os.write(fd, view); need(written > 0, 'Complete score write'); view = view[written:]
        os.fsync(fd); os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    os.replace(temporary, final)
    return pin(body)


def group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def r_diagnostics(value, script_body, core, state):
    """Only complete computed candidate/reference scalar diagnostics reach R."""
    body = json_bytes(value)
    need(len(body) <= 1_000_000 and time.monotonic() < START + 39, 'R input/time budget')
    with tempfile.TemporaryDirectory(prefix='thalamus-grader-', dir='/tmp') as directory:
        base = Path(directory)
        input_path = base/'input.json'; output_path = base/'output.json'; script = base/'paired_diagnostics.R'
        input_path.write_bytes(body); script.write_bytes(script_body)
        process = None; normal_closed = False; diagnostics_admitted = False
        state.update(started=False, direct_child_reaped=False, process_group_absent=False,
                     native_model_fits=0, input_pin=pin(body), script_pin=pin(script_body))
        with (base/'stdout').open('w+b') as stdout, (base/'stderr').open('w+b') as stderr:
            try:
                process = subprocess.Popen([R_SCRIPT, '--vanilla', str(script), str(input_path),
                    hashlib.sha256(body).hexdigest(), str(output_path)],
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True,
                    env={'PATH': '/opt/thalamus/R-4.3.1/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
                         'LC_ALL': 'C.UTF-8', 'HOME': '/tmp', 'TMPDIR': '/tmp',
                         'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
                state.update(started=True, pid=process.pid, pgid=process.pid)
                while process.poll() is None:
                    need(os.fstat(stdout.fileno()).st_size <= 16384 and os.fstat(stderr.fileno()).st_size <= 32768,
                         'Bounded R terminal/stderr capture')
                    need(not output_path.exists() or output_path.stat().st_size <= 1_000_000,
                         'Bounded R diagnostic output')
                    need(time.monotonic() < START + 40, 'R completes inside work deadline')
                    time.sleep(.01)
                process.wait(timeout=max(.001, min(1., START + 40 - time.monotonic())))
                need(not group_exists(process.pid), 'No surviving R process-group members')
                normal_closed = True
                state.update(returncode=process.returncode, direct_child_reaped=True,
                             process_group_absent=True)
                need(process.returncode == 0, 'Exact R diagnostic process succeeded')
                stdout.seek(0); stderr.seek(0)
                terminal_body = stdout.read(16385); stderr_body = stderr.read(32769)
                need(len(terminal_body) <= 16384 and len(stderr_body) <= 32768, 'Bounded final R captures')
                terminal = core.strict_json(terminal_body)
                result_body = captured(output_path, 1_000_000)
                need(type(terminal) is dict and set(terminal) == {'status', 'bytes', 'sha256'}
                     and terminal['status'] == 'thalamus_paired_diagnostics_completed',
                     'Exact R terminal schema/status')
                pinned(result_body, {k: terminal[k] for k in ('bytes', 'sha256')})
                result = core.strict_json(result_body)
                need(result['schema'] == 'thalamus_candidate_and_reference_paired_diagnostics_v1'
                     and result['status'] == 'thalamus_paired_diagnostics_completed'
                     and result['input_sha256'] == hashlib.sha256(body).hexdigest()
                     and result['session_order'] == value['session_order']
                     and result['native_model_fits'] == 0,
                     'Exact complete R diagnostic output identity')
                state.update({'returncode': 0, 'direct_child_reaped': True,
                    'process_group_absent': True, 'input_pin': pin(body), 'output_pin': pin(result_body),
                    'stdout_pin': pin(terminal_body), 'stderr_pin': pin(stderr_body),
                    'script_pin': pin(script_body), 'native_model_fits': 0})
                diagnostics_admitted = True
                return result
            finally:
                if process is not None and not normal_closed:
                    if group_exists(process.pid):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=max(.001, min(2., START + 45 - time.monotonic())))
                    need(not group_exists(process.pid), 'R failure group absence')
                    state.update(returncode=process.returncode, direct_child_reaped=True,
                                 process_group_absent=True)
                if not diagnostics_admitted:
                    stdout.seek(0); stderr.seek(0)
                    for name, stream, cap in [('stdout', stdout, 16384), ('stderr', stderr, 32768)]:
                        retained = stream.read(cap + 1)
                        state[name + '_failure_capture'] = {
                            'file_bytes': os.fstat(stream.fileno()).st_size,
                            'retained_utf8': retained[:cap].decode('utf-8', errors='replace'),
                            'retained_raw_pin': pin(retained[:cap]), 'truncated': len(retained) > cap}


def main():
    def expire(*unused):
        raise TimeoutError('Forty-second grader work deadline')
    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, max(.001, START + 40 - time.monotonic()))
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    reads = attempts = callbacks = 0
    checks = {'status': 'not_completed', 'cases': 0, 'count': 0}
    guard_report = None; r_state = {'started': False}
    try:
        need(args.output == '/grade/score.json', 'Exact trusted score alias')
        invocation = metadata(captured('/source/invocation.json', 32768))
        need(type(invocation) is dict and set(invocation) ==
             {'schema_version', 'candidate_id', 'submissions', 'fixed_reference', 'sources'}
             and type(invocation['schema_version']) is int and invocation['schema_version'] == 1
             and invocation['candidate_id'] == CANDIDATE_ID
             and type(invocation['submissions']) is dict and set(invocation['submissions']) == set(PAIR_NAMES)
             and type(invocation['sources']) is dict and set(invocation['sources']) == SOURCE_NAMES,
             'Exact full-cohort invocation metadata')
        sources = {}
        for name in sorted(SOURCE_NAMES):
            sources[name] = captured('/source/' + name, 1_000_000)
            pinned(sources[name], invocation['sources'][name])
        # Only these verified bytes become modules; no sibling path reopening.
        core = module('thalamus_captured_score_core', '/source/scorer_core.py', sources['scorer_core.py'])
        guards = module('thalamus_captured_generated_checks', '/source/generated_checks.py', sources['generated_checks.py'])
        manifest = core.strict_json(sources['SESSION_MANIFEST.json'])
        expected = core.strict_json(sources['REFERENCE_EXPECTATIONS.json'])
        core.validate_manifest(manifest)
        guard_report = guards.run(core)
        checks = {k: guard_report[k] for k in ('status', 'cases', 'count', 'names', 'invented_only',
                  'empirical_inputs_opened', 'model_fits', 'scope', 'assertions')}
        need(checks['status'] == 'thalamus_generated_checks_passed' and checks['cases'] == checks['count'] == 8
             and checks['names'] == guards.NAMES and checks['invented_only'] is True
             and checks['empirical_inputs_opened'] == checks['model_fits'] == 0,
             'All eight invented guards before empirical input')
        def loader():
            nonlocal reads, attempts, callbacks
            callbacks += 1; attempts += 1
            body = captured('/reference/fixed_reference.json', core.REFERENCE_CAP)
            reads += 1; pinned(body, invocation['fixed_reference'])
            return core.strict_json(body)
        try:
            core.public(set(p.name for p in Path('/submission').iterdir()) == set(PAIR_NAMES),
                        'Exactly seventeen committed candidate files')
            candidate = []
            for name in PAIR_NAMES:
                try:
                    body = captured('/submission/' + name, core.PAIR_CAP)
                except TimeoutError:
                    raise
                except (OSError, ValueError) as error:
                    raise core.InvalidSubmission('Candidate capture: ' + type(error).__name__) from error
                # Hash mismatch is trusted commitment failure, never candidate invalidity.
                pinned(body, invocation['submissions'][name])
                candidate.append(body)
        except TimeoutError:
            raise
        except (OSError, core.InvalidSubmission) as error:
            result = {'schema': 'thalamus_figure3C_score_v1', 'status': 'invalid_submission',
                      'reason': 'Candidate capture: ' + type(error).__name__, 'primary_metric': None,
                      'private_loader_calls': 0, 'private_reference_reads': 0,
                      'private_reference_read_attempts': 0, 'scientific_success': None,
                      'research_qualified': False, 'full_paper_complete': False}
        else:
            result = core.score(candidate, manifest, expected, loader)
        need(result['private_loader_calls'] == callbacks and result['private_reference_reads'] == reads,
             'Actual private callback/read count equality')
        if result['status'] == 'scored' and '_statistics_input' in result:
            statistics_input = result.pop('_statistics_input')
            diagnostics = r_diagnostics(statistics_input, sources['paired_diagnostics.R'], core, r_state)
            result['statistics'] = diagnostics
            result['R_diagnostic_process'] = r_state
            result['whole17_statistics_status'] = 'computed_R431_full17_candidate_and_reference'
        code = 0 if result['status'] == 'scored' else 2
    except Exception as error:
        result = {'schema': 'thalamus_figure3C_score_v1', 'status': 'operator_error',
                  'reason': type(error).__name__ + ': ' + str(error)[:512],
                  'primary_metric': None, 'private_loader_calls': callbacks,
                  'private_reference_reads': reads, 'scientific_success': None,
                  'research_qualified': False, 'full_paper_complete': False,
                  'R_diagnostic_process': r_state}
        code = 1
    signal.signal(signal.SIGALRM, lambda *unused: os._exit(124))
    signal.setitimer(signal.ITIMER_REAL, min(5., max(.001, START + 45 - time.monotonic())))
    result.update(generated_checks=checks, model_fits=0, private_reference_read_attempts=attempts,
                  wall_seconds_before_output=time.monotonic() - START)
    if guard_report is not None:
        result.update(generated_check_records=guard_report['records'],
                      generated_fixture_score_sha256=guard_report['exact_fixture_score_sha256'],
                      synthetic_private_loader_calls=guard_report['synthetic_loader_calls'])
    score_pin = save_score('/grade/score.json', result)
    terminal = json_bytes({'status': result['status'], 'score_file': 'score.json', 'score_pin': score_pin,
                           'private_reference_reads': reads, 'generated_checks': checks})
    need(len(terminal) <= 16384, 'Bounded terminal summary')
    sys.stdout.write(terminal.decode('utf-8')); sys.stdout.flush()
    need(time.monotonic() < START + 45, 'Bounded final return')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
