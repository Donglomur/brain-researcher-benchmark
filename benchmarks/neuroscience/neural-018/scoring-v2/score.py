"""Operator CLI: isolated validation/scoring of arbitrary bounded candidate NPZ.

Only trusted package code runs. Candidate programs, raw NWB and network absent.
"""
from pathlib import Path
import argparse, hashlib, json, os, signal, stat, subprocess, sys, time, uuid
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
from absence import absence

IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def require(ok, message):
    if not ok: raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''): h.update(block)
    return h.hexdigest()


def regular(path, cap, empty=False):
    path = Path(path).absolute()
    for item in (path, *path.parents): require(not item.is_symlink(), 'Linked path rejected')
    s = path.stat()
    require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and (0 if empty else 1) <= s.st_size <= cap, 'Bounded regular file required')
    return path


def save(path, value):
    with Path(path).open('x') as f: json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def alias(actual, expected):
    return actual == expected or (expected.startswith('/Users/') and actual == '/host_mnt' + expected)


def inspect_contract(info, name, mounts, action):
    h, c, s = info['HostConfig'], info['Config'], info['State']
    require(info['Name'] == '/' + name and info['Image'] == c['Image'] == IMAGE, 'Wrong container/image')
    require(c['Cmd'] == ['-I', '/package/worker.py', action] and c['Entrypoint'] == ['python'] and c['WorkingDir'] == '/tmp', 'Wrong worker command')
    require(s['Status'] == 'created' and s['Running'] is False and s['Pid'] == 0, 'Must inspect before starting')
    require(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] and not h['Privileged'] and c['User'] == '65534:65534', 'Isolation mismatch')
    require(set(info.get('NetworkSettings', {}).get('Networks', {})) <= {'none'}, 'Unexpected network attachment')
    require(h.get('CapDrop') == ['ALL'] and not h.get('CapAdd') and 'no-new-privileges:true' in h.get('SecurityOpt', []), 'Capabilities mismatch')
    require(not h.get('Devices') and not h.get('DeviceRequests') and h.get('IpcMode') != 'host' and h.get('PidMode') != 'host' and not h.get('PortBindings'), 'Host/device access rejected')
    require(h['Memory'] == h['MemorySwap'] == 4 * 1024**3 and h['NanoCpus'] == 2000000000 and h['PidsLimit'] == 64, 'Resource mismatch')
    require(h['RestartPolicy']['Name'] in ('no', '') and not h['AutoRemove'], 'Lifecycle mismatch')
    require(h.get('Tmpfs') == {'/tmp': 'rw,noexec,nosuid,nodev,size=134217728,mode=1777'}, 'Scratch mismatch')
    require(h['LogConfig'] == {'Type': 'local', 'Config': {'max-size': '256k', 'max-file': '1', 'compress': 'false'}}, 'Log bounds mismatch')
    require({x['Name']: (x['Soft'], x['Hard']) for x in h['Ulimits']} == {'cpu': (40, 42), 'nofile': (1024, 1024), 'core': (0, 0), 'fsize': (35651584, 35651584)}, 'Ulimits mismatch')
    env = dict(x.split('=', 1) for x in c['Env'])
    require(all(env.get(k) == '2' for k in THREADS) and env.get('PYTHONDONTWRITEBYTECODE') == '1', 'Thread controls mismatch')
    for label, rows, target in [('daemon-request', h.get('Mounts', []), 'Target'),
                                ('effective', [x for x in info['Mounts'] if x['Type'] != 'tmpfs'], 'Destination')]:
        require(len(rows) == len(mounts) and len({x[target] for x in rows}) == len(rows) and {x[target] for x in rows} == set(mounts), 'Exact mount inventory mismatch')
        for row in rows:
            require(row['Type'] == 'bind' and alias(row['Source'], mounts[row[target]]), 'Source mount mismatch')
            require(row.get('ReadOnly') is True if label == 'daemon-request' else row['RW'] is False, 'Read-only mount required')
    require(all(x['Destination'] == '/tmp' and x['RW'] for x in info['Mounts'] if x['Type'] == 'tmpfs'), 'Extra tmpfs')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['score', 'validate'])
    p.add_argument('--submission', required=True); p.add_argument('--output', required=True)
    args = p.parse_args()
    started = time.monotonic(); work_deadline = started + 48; final_deadline = started + 59
    output = Path(args.output).absolute(); require(not output.exists(), 'Refuse output overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = output.with_name(output.name + '.execution.json')
    ownership = output.with_name(output.name + '.ownership.json')
    require(not evidence.exists() and not ownership.exists(), 'Existing execution evidence')
    assets = json.loads((HERE / 'assets.json').read_text())
    freeze = json.loads((HERE / 'SOURCE_FREEZE.json').read_text())
    for relative, pin in freeze['files'].items():
        path = regular(HERE / relative, 1000000)
        require(path.stat().st_size == pin['bytes'] and digest(path) == pin['sha256'], 'Frozen package source changed: ' + relative)
    submission = regular(args.submission, 34*1024**2, empty=True)
    submission_sha256 = digest(submission) if submission else None
    mounts = {'/package': str(HERE), '/input/public.npz': str(ROOT / assets['public']['past']['path']), '/input/manifest.json': str(ROOT / assets['public']['manifest']['path'])}
    if submission: mounts['/input/submission.npz'] = str(submission)
    if args.action != 'validate':
        mounts.update({'/input/gold.npz': str(ROOT / assets['private']['targets']['path']),
                       '/input/reference.npz': str(ROOT / assets['private']['comparator']['path']),
                       '/input/followup_grade.json': str(ROOT / assets['private']['followup_grade']['path']),
                       '/input/followup_prediction_freeze.json': str(ROOT / assets['private']['followup_prediction_freeze']['path']),
                       '/input/followup_compact.npz': str(ROOT / assets['private']['followup_compact']['path'])})
    for target, source in mounts.items():
        require(',' not in source and '\n' not in source and Path(source).is_absolute(), 'Unsafe mount encoding')
        if target != '/package': regular(source, 128000000, empty=(target == '/input/submission.npz'))
    name = 'nlb-forecast-score-v2-' + uuid.uuid4().hex
    env = dict(os.environ, DOCKER_CONFIG=str(ROOT / '.cache-build/docker-config'), DOCKER_HOST='unix:///Users/nicholas/.docker/run/docker.sock')
    docker = '/usr/local/bin/docker'; commands = []; attempted = False
    record = {'benchmark_id': 'NEURAL-018', 'action': args.action, 'container_name': name, 'new_fits': 0,
              'source_freeze_sha256': digest(HERE / 'SOURCE_FREEZE.json'), 'requested_canonical_mounts': mounts,
              'submission_sha256_before_dispatch': submission_sha256}
    def run(argv, cleanup=False):
        deadline = final_deadline if cleanup else work_deadline
        timeout = min(5 if cleanup else 40, deadline - time.monotonic())
        require(timeout > 0, 'Whole-stage deadline')
        commands.append(argv)
        result = subprocess.run([docker, *argv], env=env, capture_output=True, text=True, timeout=timeout)
        require(len(result.stdout.encode()) <= 524288 and len(result.stderr.encode()) <= 524288, 'Tool output cap')
        return result
    result = {'benchmark_id': 'NEURAL-018', 'status': 'operator_execution_failed', 'scientific_score_computed': False}
    code = 2
    try:
        prior = run(['inspect', '--type', 'container', name])
        record['precreate_absence'] = {'returncode': prior.returncode, 'stdout': prior.stdout, 'stderr': prior.stderr}
        require(absence(prior.returncode, prior.stdout, prior.stderr, 'container', name), 'Preexisting/uncertain container identity')
        create = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only', '--user', '65534:65534',
                  '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', '4g', '--memory-swap', '4g',
                  '--cpus', '2', '--pids-limit', '64', '--log-driver', 'local', '--log-opt', 'max-size=256k', '--log-opt', 'max-file=1', '--log-opt', 'compress=false',
                  '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=134217728,mode=1777', '--workdir', '/tmp',
                  '--ulimit', 'cpu=40:42', '--ulimit', 'nofile=1024:1024', '--ulimit', 'core=0:0', '--ulimit', 'fsize=35651584:35651584']
        for key in THREADS: create += ['--env', key + '=2']
        create += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
        if submission: create += ['--env', 'EXPECTED_SUBMISSION_SHA256=' + submission_sha256]
        for target, source in mounts.items(): create += ['--mount', f'type=bind,src={source},dst={target},readonly']
        create += ['--entrypoint', 'python', IMAGE, '-I', '/package/worker.py', args.action]
        save(ownership, {'owned_container': name, 'attempted_before_dispatch': True, 'canonical_create_argv': create})
        attempted = True
        made = run(create); require(made.returncode == 0, made.stderr)
        inspected = run(['inspect', '--type', 'container', name]); require(inspected.returncode == 0, inspected.stderr)
        record['created_inspect_raw'] = inspected.stdout
        rows = json.loads(inspected.stdout); require(len(rows) == 1, 'Exact inspect cardinality')
        record['created_inspect'] = rows[0]
        inspect_contract(rows[0], name, mounts, args.action)
        start = run(['start', name]); require(start.returncode == 0, start.stderr)
        waited = run(['wait', name]); require(waited.returncode == 0, waited.stderr)
        record['worker_exit_code'] = int(waited.stdout.strip())
        logs = run(['logs', name]); record['stdout'] = logs.stdout; record['stderr'] = logs.stderr
        result = json.loads(logs.stdout); code = record['worker_exit_code']
        stopped = run(['inspect', '--type', 'container', name]); rows = json.loads(stopped.stdout)
        require(stopped.returncode == 0 and len(rows) == 1 and rows[0]['Name'] == '/' + name and not rows[0]['State']['Running'] and not rows[0]['State']['OOMKilled'], 'Stopped worker identity/state')
        record['stopped_state'] = rows[0]['State']
    except Exception as exc:
        record['error'] = type(exc).__name__ + ': ' + str(exc)
        result.update(status='operator_execution_failed', error=record['error']); code = 2
    finally:
        if attempted:
            try:
                logs = run(['logs', name], cleanup=True)
                record.setdefault('stdout', logs.stdout); record.setdefault('stderr', logs.stderr)
            except Exception as exc: record['log_recovery_error'] = repr(exc)
            try:
                removed = run(['rm', '--force', name], cleanup=True)
                record['remove'] = {'returncode': removed.returncode, 'stdout': removed.stdout, 'stderr': removed.stderr}
                missing = run(['inspect', '--type', 'container', name], cleanup=True)
                record['absence'] = {'returncode': missing.returncode, 'stdout': missing.stdout, 'stderr': missing.stderr}
                record['absence_verified'] = absence(missing.returncode, missing.stdout, missing.stderr, 'container', name)
            except Exception as exc: record['cleanup_error'] = repr(exc); record['absence_verified'] = False
        else: record['absence_verified'] = bool(record.get('precreate_absence')) and absence(prior.returncode, prior.stdout, prior.stderr, 'container', name)
        if not record['absence_verified']: code = 2; result['status'] = 'operator_cleanup_unverified'
        record['commands'] = commands; record['outer_elapsed_before_receipts_seconds'] = time.monotonic() - started
        record['within60_seconds_before_receipts'] = record['outer_elapsed_before_receipts_seconds'] < 60
        result['execution_receipt'] = str(evidence)
        save(evidence, record); save(output, result)
        final = {'elapsed_through_receipts_seconds': time.monotonic() - started, 'exit_code': code,
                 'charge_seconds': None,
                 'old_cycle_not_reset': True, 'output_sha256': digest(output), 'execution_sha256': digest(evidence)}
        save(output.with_name(output.name + '.outer.json'), final)
    print(json.dumps({'status': result['status'], 'output': str(output), 'exit_code': code}))
    return code


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'status': 'preflight_rejected_no_score', 'error': type(exc).__name__ + ': ' + str(exc)}))
        raise SystemExit(2)
