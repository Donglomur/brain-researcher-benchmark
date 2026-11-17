"""Portable operator dispatch for the unchanged 5,450-epoch sleep grader."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CASES = {'development-001': 2780, 'development-002': 2670}
PUBLIC_KEYS = {'schema_version', 'candidate_id', 'comparators'}
PRIVATE_KEYS = {'private_files'}
EXECUTION_PIN = (669, 'bebeac24f28d3652bad466f620336225fc311027aa4782082340ca3b13a7999f')
HELPER_PIN = (18080, '8b0ddea888205ae58e5c1fcbef9603ce6062462622a40ea290bae05593d85319')


def helpers():
    """Reuse the published portable file/runtime primitives after byte verification."""
    path = HERE.parents[2] / 'NEURAL-077/implementations/portable-grading/score.py'
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked portable helper source rejected')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != HELPER_PIN[0]:
        raise ValueError('Portable helper must be the pinned ordinary file')
    body = path.read_bytes()
    if (len(body), hashlib.sha256(body).hexdigest()) != HELPER_PIN:
        raise ValueError('Portable helper source changed')
    spec = importlib.util.spec_from_file_location('_neural007_portable_primitives', path)
    module = importlib.util.module_from_spec(spec)
    # Execute the checked bytes, without a second path read or bytecode cache.
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


# This source contains only a public validator, not a scoring implementation.
# The scoring stage mounts the exact original grader.py unchanged.
VALIDATOR = '''import json
from pathlib import Path
import sys
sys.path.insert(0, '/source')
import candidate_adapter as adapter
plan = json.loads(Path('/source/operator_assets.json').read_text())
invocation = json.loads(Path('/source/invocation.json').read_text())
spec = adapter.Specification(tuple(adapter.Case(c['case_id'], c['epochs']) for c in plan['cases']), ('YASA', 'RF'))
report = {'id': 'NEURAL-007', 'private_loader_calls': 0, 'private_assets_read': False,
          'submission_sha256': invocation['submission']['sha256'], 'scientific_score_computed': False}
phase = 'candidate'
try:
    adapter.validate_submission(Path('/submission/predictions.npz'), invocation['submission'], spec)
    phase = 'comparators'
    for name, pin in plan['comparators'].items():
        adapter.validate_submission(Path('/comparators') / (name + '.npz'),
                                    {k: pin[k] for k in ('bytes', 'sha256')}, spec)
    report.update(status='valid_prediction_contract', prediction_contract_valid=True,
                  epoch_count=sum(c.epochs for c in spec.cases), people=len(spec.cases),
                  comparators=list(spec.comparator_names))
    code = 0
except Exception as exc:
    report.update(status='invalid_submission' if phase == 'candidate' else 'operator_error',
                  prediction_contract_valid=False, error_type=type(exc).__name__, error=str(exc)[:2000])
    code = 2 if phase == 'candidate' else 1
print(json.dumps(report, allow_nan=False, separators=(',', ':')), flush=True)
raise SystemExit(code)
'''


def capture_source(package, destination, shared):
    """Authenticate the frozen runtime and its relocated exact numerical helpers."""
    package = shared.unlinked(package)
    execution = shared.read_regular(package / 'execution_pins.json', 32768)
    shared.require(shared.identity(execution) == EXECUTION_PIN, 'Unrecognized execution_pins.json')
    frozen = shared.decode(execution)
    captured = {'execution_pins.json': execution}
    for expected in frozen['files']:
        name = Path(expected['path']).name
        data = shared.read_regular(package / name, 1000000)
        shared.require(shared.pin(data) == {k: expected[k] for k in ('bytes', 'sha256')},
                       'Registered source changed: ' + name)
        captured[name] = data
    plan = shared.decode(captured['operator_assets.json'])
    shared.require({row['case_id']: row['epochs'] for row in plan['cases']} == CASES,
                   'Complete sleep case population required')
    helper_sources = {
        'candidate_adapter.py': package.parent / 'finite-attempt-audit/vendor/candidate_adapter.py',
        'integration_helper.py': HERE / 'vendor/integration_helper.py'}
    for name, path in helper_sources.items():
        data = shared.read_regular(path, 1000000)
        shared.require(shared.pin(data) == {k: plan['source_files'][name][k] for k in ('bytes', 'sha256')},
                       'Numerical helper source changed: ' + name)
        captured[name] = data
    captured['validate.py'] = VALIDATOR.encode()
    destination.mkdir(mode=0o755)
    for name, data in captured.items():
        with (destination / name).open('xb') as stream:
            stream.write(data)
        (destination / name).chmod(0o444)
    spec = importlib.util.spec_from_file_location('_neural007_current_score', destination / 'score.py')
    core = importlib.util.module_from_spec(spec)
    exec(compile(captured['score.py'], str(destination / 'score.py'), 'exec'), core.__dict__)
    destination.chmod(0o555)
    return core, plan, {name: shared.pin(body) for name, body in captured.items()}


def artifact_locations(path, action, shared):
    body = shared.read_regular(path, 16384)
    value = shared.decode(body)
    expected = PUBLIC_KEYS | PRIVATE_KEYS if action == 'score' else PUBLIC_KEYS
    shared.require(isinstance(value, dict) and set(value) == expected, 'Exact artifact-location schema required')
    shared.require(type(value['schema_version']) is int and value['schema_version'] == 1
                   and value['candidate_id'] == 'NEURAL-007', 'Wrong artifact-location identity')
    shared.require(isinstance(value['comparators'], dict) and set(value['comparators']) == {'YASA', 'RF'},
                   'Both frozen comparator locations required')
    locations = {'/comparators/' + name + '.npz': path for name, path in value['comparators'].items()}
    if action == 'score':
        names = {'manifest.json', *(case + '_labels.npz' for case in CASES)}
        shared.require(isinstance(value['private_files'], dict) and set(value['private_files']) == names,
                       'Exact private file inventory required')
        locations.update({'/private/' + name: path for name, path in value['private_files'].items()})
    # String validation does not stat, open, or hash a target path.
    for location in locations.values():
        shared.require(isinstance(location, str) and Path(location).is_absolute()
                       and not any(c in location for c in (',', '\n', '\r', '\x00')),
                       'Absolute safely encoded artifact location required')
    canonical = [os.path.normpath(location) for location in locations.values()]
    shared.require(len(canonical) == len(set(canonical)),
                   'Artifact roles must name distinct files; public/private aliases rejected')
    return locations, shared.pin(body)


def create_argv(core, name, mounts):
    args = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--memory', str(4 * 1024**3), '--memory-swap', str(4 * 1024**3), '--cpus', '2',
            '--pids-limit', '32', '--shm-size', '1048576', '--log-driver', 'none',
            '--workdir', '/tmp', '--entrypoint', 'python', '--tmpfs', '/tmp:' + core.TMPFS['/tmp']]
    for name_, (soft, hard) in core.ULIMITS.items():
        args += ['--ulimit', f'{name_}={soft}:{hard}']
    for key in core.THREADS:
        args += ['--env', key + '=2']
    args += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
    for target, source in mounts.items():
        if not isinstance(source, str) or any(c in source for c in (',', '\n', '\r', '\x00')):
            raise ValueError('Unsafe mount encoding')
        args += ['--mount', f'type=bind,src={source},dst={target},readonly']
    return args + [core.IMAGE, '-I', '-B', '/source/grader.py']


def execute_stage(core, runtime, env, mounts, action, directory, shared):
    """Inspect the original sleep isolation contract, then dispatch one owned worker."""
    directory.mkdir()
    started = time.monotonic()
    name = 'neural007-portable-' + uuid.uuid4().hex
    record = {'action': action, 'container_name': name, 'requested_mounts': mounts,
              'commands': [], 'attempted_create': False, 'absence_verified': False}
    result = {'status': 'operator_execution_failed', 'scientific_score_computed': False}
    code = 3

    def run(argv, cleanup=False):
        timeout = min(5 if cleanup else 40, started + (59 if cleanup else 48) - time.monotonic())
        shared.require(timeout > 0, 'Stage deadline exceeded')
        record['commands'].append(argv)
        try:
            answer = subprocess.run([*runtime, *argv], env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # Docker uses attached output and disabled persistent logging. Preserve
            # captured bytes even when the CLI times out before owned-container cleanup.
            text = lambda value: value.decode(errors='replace') if isinstance(value, bytes) else value
            record['timed_out_command'] = {'argv': argv, 'stdout': text(exc.stdout), 'stderr': text(exc.stderr)}
            raise
        shared.require(len(answer.stdout.encode()) <= 1048576 and len(answer.stderr.encode()) <= 1048576,
                       'Docker response exceeds cap')
        return {'returncode': answer.returncode, 'stdout': answer.stdout, 'stderr': answer.stderr}

    try:
        prior = run(['inspect', '--type', 'container', name])
        record['precreate_absence'] = prior
        shared.require(core.absent(prior, name), 'Container absence not established')
        record['absence_verified'] = True
        image = run(['image', 'inspect', core.IMAGE])
        record['image_inspection'] = image
        shared.require(image['returncode'] == 0, 'Existing pinned Docker image required')
        rows = shared.decode(image['stdout'])
        shared.require(len(rows) == 1 and rows[0]['Id'] == core.IMAGE, 'Exact immutable image required')
        environment = dict(item.split('=', 1) for item in rows[0]['Config']['Env'])
        environment.update({key: '2' for key in core.THREADS}, PYTHONDONTWRITEBYTECODE='1')
        create = create_argv(core, name, mounts)
        shared.save(directory / 'ownership.json', {'owned_container': name, 'create_argv': create})
        record['attempted_create'] = True
        record['absence_verified'] = False
        made = run(create)
        record['create'] = made
        shared.require(made['returncode'] == 0, 'Docker create failed')
        inspected = run(['inspect', '--type', 'container', name])
        shared.save(directory / 'prestart_inspect.json', inspected)
        shared.require(inspected['returncode'] == 0, 'Docker inspect failed')
        rows = shared.decode(inspected['stdout'])
        shared.require(len(rows) == 1, 'Exact inspect cardinality required')
        core.verify(rows[0], name, mounts, environment)
        outcome = run(['start', '--attach', name])
        record['worker_output'] = outcome
        shared.require(outcome['returncode'] in (0, 1, 2) and not outcome['stderr'], 'Unexpected worker exit')
        result = shared.decode(outcome['stdout'])
        shared.require(isinstance(result, dict), 'Worker report must be an object')
        stopped = run(['inspect', '--type', 'container', name])
        shared.require(stopped['returncode'] == 0, 'Stopped worker inspect failed')
        rows = shared.decode(stopped['stdout'])
        shared.require(len(rows) == 1 and rows[0]['Name'] == '/' + name
                       and rows[0]['State']['Status'] == 'exited' and not rows[0]['State']['Running']
                       and not rows[0]['State']['OOMKilled']
                       and rows[0]['State']['ExitCode'] == outcome['returncode'], 'Stopped worker state mismatch')
        record['stopped_state'] = rows[0]['State']
        shared.save(directory / 'worker.json', result)
        success = 'valid_prediction_contract' if action == 'validate' else 'scored'
        shared.require((outcome['returncode'] == 0) == (result.get('status') == success), 'Worker exit/result mismatch')
        code = 0 if outcome['returncode'] == 0 else 2 if result.get('status') == 'invalid_submission' else 3
    except Exception as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        result = {'status': 'operator_execution_failed', 'error': record['error'], 'scientific_score_computed': False}
        code = 3
    finally:
        if record['attempted_create']:
            try:
                record['remove'] = run(['rm', '--force', name], cleanup=True)
                record['absence'] = run(['inspect', '--type', 'container', name], cleanup=True)
                record['absence_verified'] = core.absent(record['absence'], name)
            except Exception as exc:
                record['cleanup_error'] = repr(exc)
        if not record['absence_verified']:
            result = {'status': 'operator_cleanup_unverified', 'scientific_score_computed': False}
            code = 3
        record.update(elapsed_seconds=time.monotonic() - started, exit_code=code, result=result)
        shared.save(directory / 'execution.json', record)
    return result, code


def run(args):
    shared = helpers()
    output = shared.unlinked(args.output_dir)
    output.mkdir(mode=0o700)
    started = time.monotonic()
    record = {'schema_version': 1, 'candidate_id': 'NEURAL-007', 'action': args.action,
              'candidate_code_executed': False, 'new_fits': 0, 'private_stage_dispatched': False,
              'exposure': 'Both historical development people are already exposed.',
              'scope': 'Finished probability-file grading, not programme provenance or scientific qualification.'}
    result = {'status': 'operator_preflight_failed', 'scientific_score_computed': False}
    code = 3
    try:
        record['wrapper'] = shared.pin(shared.read_regular(Path(__file__), 100000))
        record['shared_helpers'] = {'bytes': HELPER_PIN[0], 'sha256': HELPER_PIN[1]}
        core, plan, source = capture_source(args.package_dir, output / 'package', shared)
        record['source'] = source
        locations, record['artifact_descriptor'] = artifact_locations(args.artifacts, args.action, shared)
        record['artifact_locations'] = locations
        record['expected_asset_pins'] = {key: plan[key] for key in ('comparators', 'private_files')}
        runtime, env = shared.runtime_options(args)
        record['runtime'] = {'argv_prefix': runtime, 'image': core.IMAGE, 'pull': 'never', 'network': 'none'}
        body = shared.read_regular(args.submission, plan['max_submission_bytes'], empty=True)
        record['submission'] = shared.pin(body)
        with (output / 'submission.npz').open('xb') as stream:
            stream.write(body)
        (output / 'submission.npz').chmod(0o444)
        shared.save(output / 'invocation.json', {'submission': record['submission'], 'producer_stopped_attested': False,
                                                'scope': record['scope']})
        public = {'/source/grader.py': str(output / 'package/validate.py'),
                  '/source/operator_assets.json': str(output / 'package/operator_assets.json'),
                  '/source/candidate_adapter.py': str(output / 'package/candidate_adapter.py'),
                  '/source/invocation.json': str(output / 'invocation.json'),
                  '/submission/predictions.npz': str(output / 'submission.npz')}
        public.update({key: value for key, value in locations.items() if key.startswith('/comparators/')})
        for location in public.values():
            shared.unlinked(location)
        result, code = execute_stage(core, runtime, env, public, 'validate', output / 'validate', shared)
        record['validation_evidence'] = shared.stage_evidence(output / 'validate')
        if code == 0:
            shared.require(result.get('status') == 'valid_prediction_contract'
                           and result.get('prediction_contract_valid') is True
                           and result.get('epoch_count') == 5450 and result.get('people') == 2
                           and result.get('comparators') == ['YASA', 'RF']
                           and result.get('private_loader_calls') == 0 and result.get('private_assets_read') is False
                           and result.get('submission_sha256') == record['submission']['sha256'],
                           'Incomplete public validation receipt')
            if args.action == 'score':
                private = dict(public)
                private['/source/grader.py'] = str(output / 'package/grader.py')
                private['/source/integration_helper.py'] = str(output / 'package/integration_helper.py')
                for target, location in locations.items():
                    if target.startswith('/private/'):
                        # First private filesystem access occurs only after complete validation.
                        path = shared.unlinked(location)
                        info = path.stat()
                        shared.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                                       'Ordinary private file required')
                        private[target] = str(path)
                record['private_stage_dispatched'] = True
                result, code = execute_stage(core, runtime, env, private, 'score', output / 'score', shared)
                record['scoring_evidence'] = shared.stage_evidence(output / 'score')
                if code == 0:
                    actual = result.get('result', {})
                    rows = actual.get('candidate', {}).get('per_person', [])
                    shared.require(result.get('status') == 'scored' and result.get('private_loader_calls') == 1
                                   and actual.get('n_people') == 2
                                   and {row.get('person_id'): row.get('full_epochs') for row in rows} == CASES
                                   and set(actual.get('comparators', {})) == {'YASA', 'RF'},
                                   'Incomplete native scoring receipt')
        shared.require(shared.pin(shared.read_regular(output / 'submission.npz', plan['max_submission_bytes'], empty=True))
                       == record['submission'], 'Captured candidate changed during grading')
    except Exception as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        result = {'status': 'operator_preflight_failed', 'error': record['error'], 'scientific_score_computed': False}
        code = 3
    record.update(elapsed_seconds=time.monotonic() - started, exit_code=code)
    record['result'] = shared.save(output / 'result.json', result)
    shared.save(output / 'receipt.json', record)
    return result, code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'score'))
    for flag in ('package-dir', 'artifacts', 'docker-cli', 'docker-host', 'docker-config', 'submission', 'output-dir'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args(argv)
    try:
        result, code = run(args)
    except Exception as exc:
        result, code = {'status': 'operator_output_refused', 'error': type(exc).__name__ + ': ' + str(exc)}, 3
    print(json.dumps(result, allow_nan=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
