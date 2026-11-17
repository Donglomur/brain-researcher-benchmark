"""External-artifact operator route for the unchanged current NEURAL-077 worker."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
CURRENT_PIN = (2479, 'd72583caeec307b51254fd541ee5bf9e8ee0de407ef692d0dbcefcfde6ed4544')
CASES = ('development-001', 'development-002')
PUBLIC_KEYS = {'schema_version', 'candidate_id', 'public_features'}
PRIVATE_KEYS = {'private_targets', 'reference_grade', 'reference_commit'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unlinked(path):
    path = Path(path).absolute()
    require(all(not p.is_symlink() for p in (path, *path.parents)), 'Linked path rejected')
    return path


def identity(body):
    return len(body), hashlib.sha256(body).hexdigest()


def read_regular(path, cap, empty=False):
    path = unlinked(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and (0 if empty else 1) <= before.st_size <= cap, 'Bounded regular file required')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    require(fields(before) == fields(opened) == fields(after) == fields(path.stat())
            and len(body) == before.st_size and not path.is_symlink(), 'File changed during capture')
    return body


def pin(body):
    size, digest = identity(body)
    return {'bytes': size, 'sha256': digest}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key: ' + key)
        value[key] = item
    return value


def decode(body):
    return json.loads(body, object_pairs_hook=unique_object)


def save(path, value):
    body = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with Path(path).open('xb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    Path(path).chmod(0o444)
    return pin(body)


def capture_source(package, destination):
    """Check the immutable descriptor and every byte BEFORE importing source."""
    package = unlinked(package)
    body = read_regular(package / 'CURRENT_SOURCE.json', 32768)
    require(identity(body) == CURRENT_PIN, 'Unrecognized CURRENT_SOURCE.json')
    current = decode(body)
    require({p.name for p in package.iterdir()} == set(current['files']) | {'CURRENT_SOURCE.json'},
            'Missing or unexpected package source member')
    captured = {'CURRENT_SOURCE.json': body}
    for name, expected in current['files'].items():
        data = read_regular(package / name, 1000000)
        require(pin(data) == expected, 'Current package source changed: ' + name)
        captured[name] = data
    destination.mkdir(mode=0o755)
    for name, data in captured.items():
        with (destination / name).open('xb') as stream:
            stream.write(data)
        (destination / name).chmod(0o444)
    # Import only authenticated bytes from the immutable per-run snapshot.
    def module(name, filename):
        spec = importlib.util.spec_from_file_location(name, destination / filename)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    absence = module('_neural077_portable_absence', 'absence.py')
    previous = sys.modules.get('absence')
    old_path = list(sys.path)
    try:
        sys.modules['absence'] = absence
        current_score = module('_neural077_portable_current_score', 'score.py')
    finally:
        sys.path[:] = old_path
        if previous is None:
            sys.modules.pop('absence', None)
        else:
            sys.modules['absence'] = previous
    source = current_score.verify_source(destination)
    destination.chmod(0o555)
    return current_score, decode(captured['assets.json']), source


def artifact_locations(path, action):
    body = read_regular(path, 16384)
    value = decode(body)
    expected = PUBLIC_KEYS | PRIVATE_KEYS if action == 'score' else PUBLIC_KEYS
    require(isinstance(value, dict) and set(value) == expected, 'Exact artifact-location schema required')
    require(type(value['schema_version']) is int and value['schema_version'] == 1
            and value['candidate_id'] == 'NEURAL-077', 'Wrong artifact-location identity')
    for field in ('public_features', 'private_targets'):
        if field in value:
            require(isinstance(value[field], dict) and set(value[field]) == set(CASES),
                    'Exact complete case locations required')
    locations = {f'/public/{case}.npz': value['public_features'][case] for case in CASES}
    if action == 'score':
        locations.update({f'/targets/{case}.npz': value['private_targets'][case] for case in CASES})
        locations['/input/reference_grade.json'] = value['reference_grade']
        locations['/input/reference_commit.json'] = value['reference_commit']
    # Parsing path strings does not stat/open private assets before public validation.
    for location in locations.values():
        require(isinstance(location, str) and Path(location).is_absolute()
                and not any(c in location for c in (',', '\n', '\r', '\x00')),
                'Absolute safely encoded artifact location required')
    return locations, pin(body)


def runtime_options(args):
    cli = Path(args.docker_cli)
    require(cli.is_absolute(), 'Absolute Docker executable required')
    cli = cli.resolve(strict=True)
    require(cli.is_file() and os.access(cli, os.X_OK), 'Existing executable Docker CLI required')
    require(args.docker_host.startswith('unix:///'), 'Explicit local Unix Docker socket required')
    socket = unlinked(args.docker_host[len('unix://'):])
    require(stat.S_ISSOCK(socket.stat().st_mode), 'Existing local Docker socket required')
    config = unlinked(args.docker_config)
    require(config.is_dir(), 'Existing Docker config directory required')
    env = {key: value for key, value in os.environ.items() if not key.startswith('DOCKER_')}
    return [str(cli), '--config', str(config), '--host', args.docker_host], env


def create_argv(core, name, mounts, action, submission_hash):
    create = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only',
              '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
              '--memory', '4g', '--memory-swap', '4g', '--cpus', '2', '--pids-limit', '64',
              '--log-driver', 'local', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=1',
              '--log-opt', 'compress=false', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=134217728,mode=1777',
              '--workdir', '/tmp', '--ulimit', 'cpu=40:42', '--ulimit', 'nofile=1024:1024',
              '--ulimit', 'core=0:0', '--ulimit', 'fsize=35651584:35651584']
    for key in core.THREADS:
        create += ['--env', key + '=2']
    create += ['--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'EXPECTED_SUBMISSION_SHA256=' + submission_hash]
    for target, source in mounts.items():
        require(not any(c in source for c in (',', '\n', '\r', '\x00')), 'Unsafe mount encoding')
        create += ['--mount', f'type=bind,src={source},dst={target},readonly']
    return create + ['--entrypoint', 'python', core.IMAGE, '-I', '/package/worker.py', action]


def execute_stage(core, runtime, env, mounts, action, submission_hash, directory):
    """Same pinned worker/isolation contract; retain every attempted lifecycle."""
    directory.mkdir()
    started = time.monotonic()
    name = 'neural077-portable-' + uuid.uuid4().hex
    record = {'action': action, 'container_name': name, 'requested_mounts': mounts,
              'commands': [], 'attempted_create': False, 'absence_verified': False}
    result = {'status': 'operator_execution_failed', 'scientific_score_computed': False}
    code = 3

    def run(argv, cleanup=False):
        timeout = min(5 if cleanup else 40, started + (59 if cleanup else 48) - time.monotonic())
        require(timeout > 0, 'Stage deadline exceeded')
        record['commands'].append(argv)
        answer = subprocess.run([*runtime, *argv], env=env, capture_output=True, text=True, timeout=timeout)
        require(len(answer.stdout.encode()) <= 1048576 and len(answer.stderr.encode()) <= 1048576,
                'Docker response exceeds cap')
        return answer

    def response(answer):
        return {'returncode': answer.returncode, 'stdout': answer.stdout, 'stderr': answer.stderr}

    try:
        prior = run(['inspect', '--type', 'container', name])
        record['precreate_absence'] = response(prior)
        require(core.absence(prior.returncode, prior.stdout, prior.stderr, 'container', name),
                'Container absence not established')
        record['absence_verified'] = True
        create = create_argv(core, name, mounts, action, submission_hash)
        save(directory / 'ownership.json', {'owned_container': name, 'create_argv': create})
        record['attempted_create'] = True
        record['absence_verified'] = False
        made = run(create)
        require(made.returncode == 0, 'Docker create failed: ' + made.stderr)
        inspected = run(['inspect', '--type', 'container', name])
        save(directory / 'prestart_inspect.json', response(inspected))
        require(inspected.returncode == 0, 'Docker inspect failed: ' + inspected.stderr)
        rows = decode(inspected.stdout)
        require(len(rows) == 1, 'Exact inspect cardinality required')
        core.inspect_contract(rows[0], name, mounts, action)
        env_values = dict(item.split('=', 1) for item in rows[0]['Config']['Env'])
        require(env_values.get('EXPECTED_SUBMISSION_SHA256') == submission_hash, 'Submission hash environment changed')
        start = run(['start', name])
        require(start.returncode == 0, 'Docker start failed: ' + start.stderr)
        waited = run(['wait', name])
        require(waited.returncode == 0, 'Docker wait failed: ' + waited.stderr)
        worker_code = int(waited.stdout.strip())
        logs = run(['logs', name])
        record['logs'] = response(logs)
        require(logs.returncode == 0, 'Docker logs failed: ' + logs.stderr)
        result = decode(logs.stdout)
        require(isinstance(result, dict), 'Worker report must be an object')
        record['worker_exit_code'] = worker_code
        stopped = run(['inspect', '--type', 'container', name])
        require(stopped.returncode == 0, 'Stopped worker inspect failed')
        rows = decode(stopped.stdout)
        require(len(rows) == 1 and rows[0]['Name'] == '/' + name
                and rows[0]['State']['Status'] == 'exited' and not rows[0]['State']['Running']
                and not rows[0]['State']['OOMKilled'] and rows[0]['State']['ExitCode'] == worker_code,
                'Stopped worker identity/state mismatch')
        record['stopped_state'] = rows[0]['State']
        save(directory / 'worker.json', result)
        code = 0 if worker_code == 0 else (2 if result.get('status') == 'invalid_submission' else 3)
    except Exception as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        result = {'status': 'operator_execution_failed', 'error': record['error'],
                  'scientific_score_computed': False}
        code = 3
    finally:
        if record['attempted_create']:
            if 'logs' not in record:
                try:
                    recovered = run(['logs', name], cleanup=True)
                    record['recovered_logs'] = response(recovered)
                except Exception as exc:
                    record['log_recovery_error'] = repr(exc)
            try:
                removed = run(['rm', '--force', name], cleanup=True)
                record['remove'] = response(removed)
                missing = run(['inspect', '--type', 'container', name], cleanup=True)
                record['absence'] = response(missing)
                record['absence_verified'] = core.absence(missing.returncode, missing.stdout, missing.stderr, 'container', name)
            except Exception as exc:
                record['cleanup_error'] = repr(exc)
        if not record['absence_verified']:
            result = {'status': 'operator_cleanup_unverified', 'scientific_score_computed': False}
            code = 3
        record['elapsed_seconds'] = time.monotonic() - started
        record['exit_code'] = code
        record['result'] = result
        save(directory / 'execution.json', record)
    return result, code


def stage_evidence(directory):
    return {path.name: pin(read_regular(path, 4194304)) for path in directory.iterdir()}


def run(args):
    started = time.monotonic()
    output = unlinked(args.output_dir)
    # Atomic directory claim precedes all input reads. Existing evidence is never edited.
    output.mkdir(mode=0o700)
    record = {'schema_version': 1, 'candidate_id': 'NEURAL-077', 'action': args.action,
              'candidate_code_executed': False, 'new_fits': 0, 'private_stage_dispatched': False,
              'scope': 'Operator-provisioned exposed development grading; no task admission change.'}
    result = {'status': 'operator_preflight_failed', 'scientific_score_computed': False}
    code = 3
    try:
        record['wrapper'] = pin(read_regular(Path(__file__), 100000))
        core, assets, source = capture_source(args.package_dir, output / 'package')
        record['source'] = source
        record['assets_manifest'] = pin(read_regular(output / 'package' / 'assets.json', 10000))
        locations, location_pin = artifact_locations(args.artifacts, args.action)
        record['artifact_locations'] = locations
        record['artifact_descriptor'] = location_pin
        record['expected_asset_pins'] = {
            'public_features': {case: assets['public']['cases'][case]['features'] for case in CASES},
            'private': assets['private'], 'reference_freeze': assets['reference_freeze']}
        runtime, env = runtime_options(args)
        record['runtime'] = {'argv_prefix': runtime, 'image': core.IMAGE, 'pull': 'never', 'network': 'none'}
        # Missing/inaccessible/oversized host input is an operator error; malformed
        # captured NPZ content is classified by the unchanged worker as candidate-invalid.
        body = read_regular(args.submission, 1048576, empty=True)
        record['submission'] = pin(body)
        with (output / 'submission.npz').open('xb') as stream:
            stream.write(body)
        (output / 'submission.npz').chmod(0o444)
        public = {'/package': str(output / 'package'), '/input/submission.npz': str(output / 'submission.npz')}
        public.update({key: value for key, value in locations.items() if key.startswith('/public/')})
        for location in public.values():
            unlinked(location)
        result, code = execute_stage(core, runtime, env, public, 'validate', record['submission']['sha256'], output / 'validate')
        record['validation_evidence'] = stage_evidence(output / 'validate')
        if code == 0:
            require(result.get('status') == 'valid_prediction_contract'
                    and result.get('prediction_contract_valid') is True and result.get('trial_count') == 400
                    and result.get('people') == 2 and result.get('target_loader_invocations') == 0
                    and result.get('private_assets_read') is False
                    and result.get('submission_sha256') == record['submission']['sha256'],
                    'Incomplete public validation receipt')
            if args.action == 'score':
                # No private file stat, hash, read or mount is attempted above this line.
                mounts = dict(public, **locations)
                for location in locations.values():
                    unlinked(location)
                record['private_stage_dispatched'] = True
                result, code = execute_stage(core, runtime, env, mounts, 'score', record['submission']['sha256'], output / 'score')
                record['scoring_evidence'] = stage_evidence(output / 'score')
                if code == 0:
                    require(result.get('status') == 'scored' and result.get('scientific_score_computed') is True
                            and result.get('trial_count') == 400 and result.get('target_loader_invocations') == 2
                            and result.get('submission_sha256') == record['submission']['sha256']
                            and set(result.get('candidate_minus_reference', {})) == {
                                'prior', 'eeg', 'eog_site', 'gross_amplitude', 'behavioral_history', 'eeg_history'},
                            'Incomplete score receipt')
    except Exception as exc:
        result = {'status': 'operator_preflight_failed', 'error': type(exc).__name__ + ': ' + str(exc),
                  'scientific_score_computed': False}
        code = 3
    finally:
        record.update(status=result['status'], exit_code=code, elapsed_seconds=time.monotonic() - started)
        record['result'] = save(output / 'result.json', result)
        save(output / 'receipt.json', record)
    return result, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'score'))
    for name in ('package-dir', 'artifacts', 'docker-cli', 'docker-host', 'docker-config', 'submission', 'output-dir'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        result, code = run(args)
    except Exception as exc:
        result, code = {'status': 'operator_output_refused', 'error': type(exc).__name__ + ': ' + str(exc)}, 3
    print(json.dumps({'status': result['status'], 'output_dir': args.output_dir, 'exit_code': code}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
