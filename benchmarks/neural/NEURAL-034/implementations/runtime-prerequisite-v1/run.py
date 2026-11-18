"""Root-leased150-second two-unit runtime prerequisite; never authentic input work."""
import argparse
import hashlib
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import configure
import support as s

INITIAL = time.monotonic()
OWNER = 'complete_neural034'
RUN_ID = 'neural034-scoped-runtime-prerequisite-01'
APPROVAL_ID = 'neural034-scoped-runtime-prerequisite-protocol-01'
ARTIFACT_ID = 'neural034-scoped-runtime-prerequisite-artifacts-01'
LIMITS = {'hard_wall_seconds': 150, 'controller_work_seconds': 105,
          'declared_max_working_ram_bytes': 4 * 1024**3, 'operator_threads': 1,
          'artifact_bytes': 16 * 1024**2, 'minimum_free_disk_bytes': 60 * 1024**3,
          'generated_units': 2, 'candidate_seconds_each': 20}
THREADS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
           'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS',
           'POLARS_MAX_THREADS', 'RAYON_NUM_THREADS')
EXECUTION_FILES = {'run.py', 'controller.py', 'support.py', 'probe.py', 'configure.py'}


def lease(plan, plan_path, body, ledger_path):
    expected = {'path': str(s.literal(plan_path)), 'sha256': s.pin(body)['sha256']}
    command = [plan['operator']['invocation_path'], '-I', '-B', str(HERE / 'run.py'),
               '--plan', expected['path'], '--ledger', str(s.literal(ledger_path))]
    for _ in range(50):
        ledger = s.decode(s.read(ledger_path, 16 * 1024**2))
        approvals = [r for r in ledger.get('approved_native_protocols', []) if r['id'] == APPROVAL_ID]
        s.need(len(approvals) == 1 and approvals[0]['owner'] == OWNER and
               approvals[0]['approved_by'] == '/root' and approvals[0]['protocol'] == expected,
               'Exact independent root protocol approval')
        rows = [r for r in ledger['native_runs'] if r['id'] == RUN_ID]
        s.need(len(rows) == 1, 'Unique root-owned native lease')
        row = rows[0]
        s.need(row['owner'] == OWNER and row['status'] == 'running' and row['protocol'] == expected and
               row['approval_id'] == APPROVAL_ID and row['coordinator_pid'] == os.getppid() and
               row['command'] == command and row['requested_threads'] == 1 and
               row['declared_max_working_ram_bytes'] == LIMITS['declared_max_working_ram_bytes'],
               'Exact native lease identity and resource declaration')
        reservations = [r for r in ledger['reservations'] if r['id'] == ARTIFACT_ID]
        s.need(len(reservations) == 1 and reservations[0]['owner'] == OWNER and
               reservations[0]['status'] == 'active' and reservations[0]['kind'] == 'artifact' and
               reservations[0]['destination'] == plan['output_root'] and
               reservations[0]['reserved_bytes'] >= LIMITS['artifact_bytes'], 'Active exact artifact reservation')
        s.need(ledger['minimum_free_disk_bytes'] >= LIMITS['minimum_free_disk_bytes'], 'Preserved disk floor')
        if 'child_pid' in row:
            s.need(row['child_pid'] == os.getpid(), 'Exact owned child process')
            return
        time.sleep(.1)
    raise ValueError('Native coordinator did not bind child')


def stream_pin(path, expected):
    """Runtime binary may have package-manager links; bound complete stream by size."""
    path = Path(path).resolve(strict=True)
    info = path.stat(); s.need(path.is_file() and info.st_size == expected['bytes'] <= 64 * 1024**2,
                              'Bounded fixed runtime extent')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for body in iter(lambda: stream.read(65536), b''):
            digest.update(body)
    after = path.stat()
    s.need((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
           (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) and
           digest.hexdigest() == expected['sha256'], 'Runtime bytes changed')


def preflight(plan):
    s.need(plan['schema'] == 'neural034-scoped-runtime-prerequisite/v1' and
           plan['owner'] == OWNER and plan['run_id'] == RUN_ID and
           plan['approval_id'] == APPROVAL_ID and plan['artifact_id'] == ARTIFACT_ID and plan['limits'] == LIMITS,
           'Exact fixed prerequisite protocol')
    s.need(plan['authentic_inputs'] == plan['model_calls'] == plan['scientific_scores'] == plan['downloads'] == 0,
           'Generated-only scope')
    s.need(all(os.environ.get(key) == '1' for key in THREADS), 'One operator thread')
    s.need(Path(sys.executable).absolute() == Path(plan['operator']['invocation_path']).absolute(),
           'Selected operator environment')
    for entry in plan['operator']['files']:
        stream_pin(entry['path'], entry)
    import numpy as np
    s.need({'python': sys.version.split()[0], 'numpy': np.__version__, 'byte_order': sys.byteorder} ==
           plan['operator']['versions'], 'Selected operator runtime versions')
    s.need(set(plan['source_files']) == EXECUTION_FILES, 'Complete fixed prerequisite execution closure')
    for name, pin in plan['source_files'].items():
        s.need(s.pin(s.read(HERE / name)) == pin, 'Frozen prerequisite source ' + name)
    source_root = s.literal(plan['source_root'])
    observed = subprocess.run(['git', 'show', '-s', '--format=%H%n%T%n%P', 'HEAD'], cwd=source_root,
                              capture_output=True, text=True, timeout=5)
    identities = observed.stdout.strip().splitlines()
    s.need(observed.returncode == 0 and not observed.stderr and len(identities) == 3 and
           identities[1] == plan['source_tree'] and identities[2] == plan['predecessor_commit'],
           'Exact committed source tree and reviewed predecessor')
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=source_root,
                           capture_output=True, text=True, timeout=5)
    s.need(dirty.returncode == 0 and not dirty.stdout and not dirty.stderr, 'Clean selected source')
    configure.source_pin(source_root)
    output = s.literal(plan['output_root'])
    s.need(not output.exists() and output.parent.is_dir(), 'Fresh allocated output')
    fs = os.statvfs(output.parent)
    s.need(fs.f_bavail * fs.f_frsize >= LIMITS['minimum_free_disk_bytes'], 'Actual preserved free disk')
    s.need(not any(value for key, value in os.environ.items() if key.startswith('DOCKER_')),
           'No inherited Docker context override')
    docker = s.literal(plan['docker_binary'])
    s.need(docker.is_file() and os.access(docker, os.X_OK) and
           sum(row['path'] == str(docker) for row in plan['operator']['files']) == 1,
           'Exactly pinned canonical Docker binary')
    host = plan['docker_host']
    s.need(type(host) is str and host.startswith('unix:///') and
           not any(c in host for c in '\0\r\n?#'), 'Explicit Unix Engine host')
    s.need(stat.S_ISSOCK(s.literal(host[7:]).stat().st_mode), 'Existing exact local Engine socket')
    return source_root, output, identities[0]


def fixtures(root, configured):
    import numpy as np
    generated = root / 'generated'; generated.mkdir(mode=0o700)
    private = generated / 'operator-private.txt'
    s.publish(private, b'generated private canary\n')
    inactive = generated / 'inactive-secret.txt'
    s.publish(inactive, b'generated inactive-fold canary\n')
    socket_canary = generated / 'operator-daemon-canary.txt'
    s.publish(socket_canary, b'generated daemon-location canary\n')
    source = s.read(HERE / 'probe.py', 65536).decode()
    s.need(source.count('HOST_CANARIES = ()') == 1, 'Exact probe rendering seam')
    source = source.replace('HOST_CANARIES = ()', 'HOST_CANARIES = ' + repr(tuple(map(str,
        (private, inactive, socket_canary)))))
    candidate = root / 'candidates/generated-probe.py'
    candidate.parent.mkdir(mode=0o700, exist_ok=True)
    s.publish(candidate, source.encode(), 0o444)
    units = []
    for index in range(2):
        ids = [f'{1000 * (index + 1) + i:024x}' for i in range(20)]
        target = generated / f'active-{index:02d}.npz'
        # Complete original typed dimensions, compressed constants, no original data.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            np.savez_compressed(stream, train_windows=np.zeros((120, 300, 12), '<f8'),
                train_behavior=np.zeros((120, 300), '<f8'), train_labels=np.arange(120, dtype='i1') % 2,
                query_windows=np.full((20, 300, 12), (index + 1) / 8, '<f8'),
                query_behavior=np.full((20, 300), index, '<f8'), query_ids=np.asarray(ids, dtype='<U24'))
            stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())
        body = s.read(target, 32768)
        units.append({'unit_id': f'fixture-{index:02d}', 'expected_ids': ids,
            'expected_query_count': 20, 'output_filename': 'probabilities.json', 'max_output_bytes': 100000,
            'public_inputs': [{'path': target.relative_to(root).as_posix(), **s.pin(body),
                              'mount_destination': '/input/public.npz', 'read_only': True}]})
    return {'schema': 'neural034-two-generated-units/v1', 'source_freeze': configured['source_freeze'],
            'program': {'path': candidate.relative_to(root).as_posix(), **s.pin(source.encode())},
            'units': units, 'unmounted_canaries': [str(p) for p in (private, inactive, socket_canary)]}


def publish_terminal(output, result):
    """Publication/cap failure can never retain a successful terminal status."""
    try:
        result['elapsed_before_receipt_seconds'] = time.monotonic() - INITIAL
        retained = sum(p.lstat().st_size for p in output.rglob('*') if p.is_file())
        result['retained_before_receipt_bytes'] = retained
        body = s.encode(result)
        s.need(retained + len(body) <= LIMITS['artifact_bytes'], 'Retained artifact ceiling')
        s.publish(output / 'RESULT.json', body)
    except BaseException as error:
        result.update(status='failed_finalization_preserved', finalization_error=repr(error))
        if not (output / 'FAILURE.json').exists():
            body = s.encode(result)
            retained = sum(p.lstat().st_size for p in output.rglob('*') if p.is_file())
            if retained + len(body) <= LIMITS['artifact_bytes']:
                s.publish(output / 'FAILURE.json', body)
        return False
    return True


def close_owned(api, recover, out, proc, fixture, root, budget):
    group = api.owner.stop(out, min(INITIAL + 120, time.monotonic() + 5), proc)
    s.need(group['absence_verified'], 'Group absent before resource recovery')
    reaped = proc is None or proc.returncode is not None
    rows = []
    if fixture is not None:
        program = root / fixture['program']['path']
        for unit in reversed(fixture['units']):
            rows.extend(recover(api, out / unit['unit_id'], INITIAL + 146, budget, program, fixture['units']))
    return {'controller_group': group, 'controller_reaped': reaped,
            'resource_recovery': rows, 'all_owned_absent': all(row['absence_verified'] for row in rows) and reaped}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--plan', required=True)
    parser.add_argument('--ledger', required=True); args = parser.parse_args()
    proc = None; api = None; recover = None; output = None; fixture = None; out = None
    result = {'schema': 'neural034-runtime-prerequisite-result/v1', 'status': 'failed_preserved',
              'runtime_qualified': False, 'authentic_inputs': 0, 'scientific_scores': 0,
              'model_calls': 0, 'all_owned_absent': False, 'charged_wall_allowance_seconds': 150,
              'cost_family_id': 'astrocyte_source_family', 'historical_lifetime_complete': False,
              'prior_costs_reset': False, 'cumulative_family_seconds': None}
    def hard(*unused):
        if proc is not None and proc.poll() is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        os._exit(124)
    def interrupted(number, *unused):
        raise InterruptedError('Owned prerequisite signal ' + str(number))
    s.need(signal.getitimer(signal.ITIMER_REAL) == (0., 0.), 'No conflicting process timer')
    signal.signal(signal.SIGALRM, hard); signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    signal.setitimer(signal.ITIMER_REAL, max(.001, INITIAL + 150 - time.monotonic()))
    try:
        raw = s.read(args.plan); plan = s.decode(raw)
        lease(plan, args.plan, raw, args.ledger)
        source_root, output, source_commit = preflight(plan)
        result['source_commit'] = source_commit
        output.mkdir(mode=0o700)
        s.save(output / 'admitted_plan.json', plan)
        root = output / 'workspace'
        configured = configure.configure(source_root, root)
        s.need(configure.load(root) == configured and
               {key: configured[key] for key in ('source_freeze', 'manifest')} == plan['configured_source'],
               'Exact independently frozen publication successor')
        config = root / '.cache-build/docker-config'; config.mkdir(mode=0o700, parents=True)
        s.publish(config / 'config.json', b'{}\n')
        fixture = fixtures(root, configured)
        local = root / 'authoring/neural034-runtime-prerequisite'; local.mkdir(mode=0o700)
        for name in ('controller.py', 'support.py'):
            s.publish(local / name, s.read(HERE / name), 0o444)
        fixture_path = root / 'generated/fixture.json'; s.save(fixture_path, fixture)
        for key in list(os.environ):
            if key.startswith('DOCKER_'): del os.environ[key]
        os.environ['NEURAL034_DOCKER'] = plan['docker_binary']
        os.environ['NEURAL034_DOCKER_HOST'] = plan['docker_host']
        api, recover = s.runtime(root, configured['source_freeze'])
        out = root / 'artifacts-build/runtime-prerequisite'; out.mkdir(mode=0o700, parents=True)
        budget = api.HostBudget(out, limit=12 * 1024**2, reserve=2 * 1024**2)
        controller = local / 'controller.py'
        descriptor = {'path': controller.relative_to(root).as_posix(), **s.pin(s.read(controller))}
        argv = [sys.executable, str(controller), '--fixture', str(fixture_path), '--fixture-sha256',
                s.pin(s.read(fixture_path))['sha256'], '--work-end', str(INITIAL + 105),
                '--whole-end', str(INITIAL + 115)]
        s.need(time.monotonic() < INITIAL + 15, 'Full generated lifecycle allowance before launch')
        proc = api.owner.launch(argv, out, 120, descriptor)
        while not (out / 'process_completion.json').exists():
            s.need(time.monotonic() < INITIAL + 110 and proc.poll() is None, 'Owned controller work deadline')
            time.sleep(.02)
        complete = api.owner.read(out / 'process_completion.json'); owner = api.owner.read(out / 'process_owner.json')
        s.need(complete['token'] == owner['token'] and complete['group_leader_waits_for_owner_stop'] is True,
               'Exact completed controller identity')
        result['controller_returncode'] = complete['returncode']
    except BaseException as error:
        result['error'] = repr(error)
    finally:
        if output is not None and output.exists():
            try:
                if api is not None and out is not None and out.exists():
                    result.update(close_owned(api, recover, out, proc, fixture, output / 'workspace', budget))
                    if result.get('controller_returncode') == 0 and result['all_owned_absent']:
                        body = s.read(out / 'controller_result.json')
                        complete = s.decode(body)
                        s.need(complete['status'] == 'two_generated_units_closed' and len(complete['units']) == 2,
                               'Complete two-unit closed result')
                        result.update(status='two_generated_units_closed_pending_independent_review',
                                      controller_result=s.pin(body), units=complete['units'])
            except BaseException as error:
                result.update(status='failed_cleanup_preserved', recovery_error=repr(error))
            publish_terminal(output, result)
        signal.setitimer(signal.ITIMER_REAL, 0)
    print(s.encode({key: result[key] for key in ('status', 'runtime_qualified',
          'prior_costs_reset', 'cumulative_family_seconds')} |
          {'output': str(output) if output is not None else None, 'error': result.get('error')}).decode(), flush=True)
    return 0 if result['status'] == 'two_generated_units_closed_pending_independent_review' else 2


if __name__ == '__main__':
    raise SystemExit(main())
