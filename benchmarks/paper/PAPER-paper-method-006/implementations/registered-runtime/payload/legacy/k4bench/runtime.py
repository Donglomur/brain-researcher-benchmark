"""Concrete source-bound launch with acyclic identities and terminal custody."""
import hashlib
import os
from pathlib import Path
import selectors
import subprocess
import time
from .protocol import require, validate_pin, identifier, digest, write_new, Rejected
from .admission import resource_contract
from .identity import plan_digest, manifest_digest, job_digest, profile_digest, bind_profile
from .snapshot import verify_snapshot
from .custody import cleanup, terminal


def namespace(profile, job, request):
    """Exact readonly/writable namespace, including literal constructor paths."""
    kind = profile['worker_kind']
    readonly = {'/input', '/run', '/candidate', '/provider', '/opt/author', '/common'}
    writable = {'main': '/output'}
    if kind == 'preparation':
        readonly = {'/run', '/sources/kilosort-v4.0.2', '/inputs', '/home/carsen/.kilosort/probes'}
        require(request['source_root'] == '/sources/kilosort-v4.0.2'
                and request['output_root'] == '/work/constructor-output',
                'preparation-namespace', job['id'])
        writable['constructor'] = '/work/constructor-output'
        if request['operation'] == 'hybrid_source':
            name = request['parameters']['sim_name']
            require(isinstance(name, str) and 1 <= len(name) <= 64
                    and all(c.isalnum() or c in '-_' for c in name), 'hybrid-output-name', job['id'])
            writable['historical-hybrid'] = '/media/carsen/ssd1/spikesorting/sim_' + name
    selected = {x['root_id']: x['target'] for x in profile['writable_outputs']}
    require(selected == writable and len(selected) == len(profile['writable_outputs']),
            'writable-namespace-mismatch', job['id'])
    require(sum(x['quota_bytes'] for x in profile['writable_outputs']) <= job['resources']['disk_bytes']
            and all(type(x['quota_bytes']) is int and x['quota_bytes'] > 0 for x in profile['writable_outputs']),
            'writable-namespace-quota', job['id'])
    return readonly, writable


def command(profile, job, writable_roots, container_name, verified):
    caps = resource_contract(job['resources'])
    require(verified['schema'] == 'kilosort4_verified_mounts_v2'
            and verified['producer_profile_digest'] == profile_digest(profile)
            and verified['job_digest'] == job_digest(job), 'unbound-effective-mounts', job['id'])
    require(profile['backend'] == 'docker-linux', 'unsupported-backend', job['id'])
    image = profile['image']
    require(image.startswith('sha256:') and len(image) == 71 and all(c in '0123456789abcdef' for c in image[7:]),
            'mutable-image', image)
    require(type(profile['uid']) is int and profile['uid'] > 0 and type(profile['gid']) is int
            and profile['gid'] > 0 and profile['cpu_count'] > 0, 'invalid-worker-identity', job['id'])
    readonly, required_writable = namespace(profile, job, verified['request'])
    require(set(writable_roots) == set(required_writable), 'missing-writable-root', job['id'])
    args = [profile['docker_executable'], 'run', '--name', container_name, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit', str(caps['max_processes']),
            '--memory', str(caps['memory_bytes']), '--memory-swap', str(caps['memory_bytes']),
            '--cpus', str(profile['cpu_count']), '--user', f"{profile['uid']}:{profile['gid']}",
            '--ulimit', f"cpu={caps['cpu_seconds']}:{caps['cpu_seconds']}",
            '--ulimit', f"fsize={caps['output_bytes']}:{caps['output_bytes']}",
            '--tmpfs', f"/tmp:rw,noexec,nosuid,nodev,size={caps['tmp_bytes']}",
            '--workdir', '/output', '--env', 'HOME=/tmp/worker-home', '--env', 'PYTHONNOUSERSITE=1',
            '--env', 'PYTHONDONTWRITEBYTECODE=1']
    for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        args += ['--env', f"{key}={caps['threads']}"]
    if profile['gpu_device_ids']:
        require(caps['gpu_memory_bytes'] > 0 and profile.get('gpu_partition_receipt_pin'), 'GPU-partition-unqualified', job['id'])
        validate_pin(profile['gpu_partition_receipt_pin'])
        require(all(isinstance(x, str) and x and all(c.isalnum() or c in '-_' for c in x)
                    for x in profile['gpu_device_ids']), 'invalid-GPU-id', job['id'])
        args += ['--gpus', 'device=' + ','.join(profile['gpu_device_ids'])]
    seen = set()
    for mount in verified['mounts']:
        target = mount['target']
        require(target in readonly and target not in seen and mount['read_only'] is True, 'unsafe-readonly-mount', target)
        seen.add(target)
        require(',' not in mount['source'] and '\n' not in mount['source'], 'unsafe-mount-source', target)
        args += ['--mount', f"type=bind,src={mount['source']},dst={target},readonly"]
    require('/run' in seen, 'request-mount-missing', job['id'])
    for root_id, target in required_writable.items():
        source = Path(writable_roots[root_id])
        require(source.is_absolute() and source == source.resolve(strict=True) and source.is_dir()
                and not source.is_symlink() and ',' not in str(source), 'unsafe-writable-mount', root_id)
        require(source.stat().st_uid == profile['uid'] and source.stat().st_gid == profile['gid'],
                'writable-output-ownership', root_id)
        args += ['--mount', f'type=bind,src={source},dst={target}']
    entry = {
        'kilosort4': ['python', '-I', '/opt/k4bench/native_worker.py', '/run/request.json'],
        'preparation': ['/environment/python3', '-I', '/opt/k4bench/preparation/native_bridge.py', '/run/request.json'],
        'candidate': ['python', '-I', '/candidate/program.py', '/run/request.json', '/output'],
        'provider': ['python', '-I', '/opt/k4bench/provider_worker.py', '/run/request.json'],
        'scientific': ['python', '-I', '/opt/k4bench/scientific_worker.py', '/run/request.json'],
    }[profile['worker_kind']]
    require(profile['entrypoint'] == entry, 'entrypoint-mismatch', job['id'])
    return args + [image, *entry]


def inventories(writable_roots, caps, max_files):
    rows, failures, total = [], [], 0
    for root_id, root in writable_roots.items():
        for folder, dirs, names in os.walk(root, followlinks=False):
            for name in dirs + names:
                p = Path(folder) / name
                if p.is_symlink():
                    failures.append({'root_id': root_id, 'path': str(p.relative_to(root)), 'reason': 'symlink'})
            for name in names:
                p = Path(folder) / name
                if p.is_file() and not p.is_symlink():
                    require(len(rows) < max_files, 'output-file-count-limit', root_id)
                    size = p.stat().st_size
                    total += size
                    rows.append({'root_id': root_id, 'path': str(p.relative_to(root)), 'bytes': size})
    require(total <= caps['output_bytes'], 'output-byte-limit', str(total))
    return {'files': rows, 'bytes': total, 'unsafe': failures}


def finish_attempt(path, record, meter, processes, streams, selector, stop_container,
                   writable_roots, max_files, original_failure, exit_code, log_bytes,
                   started, killpg=None):
    """Used by the actual worker and inert failure controls; never raises on cleanup."""
    termination = cleanup(processes, streams, selector, stop_container, killpg)
    failure = original_failure
    auxiliary = []
    if termination['errors']:
        auxiliary.append({'code': 'cleanup-failed', 'details': termination['errors']})
        if failure is None:
            failure = {'code': 'cleanup-failed', 'detail': 'termination or stream custody incomplete'}
    try:
        inventory = inventories(writable_roots, record['resource_caps'], max_files)
        if inventory['unsafe']:
            auxiliary.append({'code': 'unsafe-output-inventory', 'details': inventory['unsafe']})
            if failure is None:
                failure = {'code': 'output-contract', 'detail': 'symlink output'}
    except BaseException as error:
        inventory = None
        auxiliary.append({'code': 'inventory-failed', 'type': type(error).__name__, 'detail': str(error)})
        if failure is None:
            failure = {'code': 'inventory-failed', 'detail': str(error)}
    result = {**record, 'status': 'failed' if failure else 'native-exited', 'failure': failure,
              'original_failure': original_failure, 'auxiliary_failures': auxiliary,
              'exit_code': exit_code, 'wall_seconds': time.monotonic() - started, 'log_bytes': log_bytes,
              'output_inventory': inventory, 'termination': termination,
              'physical_io': None, 'cpu_seconds': None, 'peak_RSS': None,
              'scientific_pass': None, 'whole_benchmark_complete': False, 'no_retry': True}
    custody = terminal(path / 'END.json', result, meter)
    if not custody['written']:
        result = {**result, 'status': 'failed', 'terminal_custody_error': custody['error']}
    return {**result, 'terminal_receipt_pin': custody['pin'], 'terminal_receipt_written': custody['written']}


class Worker:
    def __init__(self, store, authority, meter):
        self.store, self.authority, self.meter = store, authority, meter

    def run(self, manifest, job, profile, attempt_root, input_roots, attempt_id):
        permit = self.authority.permit(manifest, job)
        descriptor = manifest['producer_profiles'][job['producer_id']]
        admitted_profile = self.store.json(validate_pin(descriptor['profile_pin']), 4 * 1024 * 1024)
        require(profile == admitted_profile, 'producer-profile-mutated', job['id'])
        bound_profile = bind_profile(manifest, job, profile)
        snapshot_pin = self.authority.admission['job_snapshots'][job['id']]
        verified = verify_snapshot(self.store, manifest, job, profile, snapshot_pin, input_roots)
        if profile['worker_kind'] == 'scientific':
            from .scientific import bind_definition
            bind_definition(self.store, self.authority, manifest, job, profile, verified['request'])
        for field in ('isolation_receipt_pin', 'filesystem_quota_receipt_pin', 'io_enforcement_receipt_pin', 'environment_receipt_pin'):
            self.store.read(validate_pin(profile[field]))
        # These source-bound infrastructure receipts are independent ancestors,
        # not profile/selection back-references. No deployment is qualified here.
        identifier(attempt_id)
        require(all(c.isalnum() or c in '-_' for c in attempt_id), 'unsafe-attempt-id', attempt_id)
        caps = resource_contract(job['resources'])
        require(profile['uid'] == os.getuid() and profile['gid'] == os.getgid(),
                'output-owner-not-current-unprivileged-host', job['id'])
        path = Path(attempt_root) / attempt_id
        require(not path.exists(), 'attempt-reuse', attempt_id)
        path.mkdir(mode=0o700)
        _, targets = namespace(profile, job, verified['request'])
        writable_roots = {}
        for key in targets:
            root = path / key
            root.mkdir(mode=0o700)
            writable_roots[key] = str(root.absolute())
        name = 'k4-' + hashlib.sha256((job['id'] + ':' + attempt_id).encode()).hexdigest()[:24]
        argv = command(profile, job, writable_roots, name, verified)
        record = {'schema': 'kilosort4_worker_attempt_v2', 'attempt_id': attempt_id, 'job_id': job['id'],
                  'job_digest': job_digest(job), 'manifest_digest': manifest_digest(manifest),
                  'plan_digest': plan_digest(manifest), 'permit': permit, 'profile_digest': bound_profile,
                  'producer_profile_pin': descriptor['profile_pin'], 'producer_descriptor_digest': digest(descriptor),
                  'effective_mounts': verified, 'writable_namespaces': targets, 'argv': argv,
                  'status': 'started', 'resource_caps': caps, 'container_name': name, 'retains_failed_work': True}
        write_new(path / 'START.json', record, self.meter)
        started = time.monotonic()
        process, selector, logfile = None, None, None
        failure, total_logs, exit_code = None, 0, None
        try:
            logfile = open(path / 'combined.log', 'xb', buffering=0)
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True, env={'PATH': profile['host_path'], 'HOME': profile['docker_config_home']})
            selector = selectors.DefaultSelector()
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() - started > caps['wall_seconds']:
                    raise Rejected('wall-limit', 'worker deadline exceeded')
                for key, _ in selector.select(timeout=0.1):
                    block = os.read(key.fileobj.fileno(), 16384)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    remaining = caps['log_bytes'] - total_logs
                    accepted = block[:remaining]
                    if accepted:
                        self.meter.charge('write', len(accepted))
                        logfile.write(accepted)
                        total_logs += len(accepted)
                    if len(block) > remaining:
                        raise Rejected('log-limit', 'log prefix retained, overrun rejected')
            exit_code = process.wait(timeout=max(0.1, caps['wall_seconds'] - (time.monotonic() - started)))
            if exit_code != 0:
                failure = {'code': 'native-exit', 'detail': str(exit_code)}
        except BaseException as error:
            failure = {'code': getattr(error, 'code', type(error).__name__), 'detail': str(error)}
        finally:
            stop = None
            if process is not None and failure is not None:
                def stop():
                    result = subprocess.run([profile['docker_executable'], 'kill', name], stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
                    require(result.returncode == 0, 'owned-container-kill-failed', name)
                    return result.returncode
            result = finish_attempt(path, record, self.meter, [] if process is None else [process],
                                    [logfile] + ([] if process is None else [process.stdout, process.stderr]),
                                    selector, stop, writable_roots, profile['max_output_files'],
                                    failure, exit_code, total_logs, started)
        return result
