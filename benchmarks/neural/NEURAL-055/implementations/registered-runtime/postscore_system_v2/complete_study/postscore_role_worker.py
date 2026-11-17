"""Qualified Linux role entry. Not executed by build-only provider controls.

The role is born in its leaf before Python starts. This file bootstraps only a
fixed readonly ordinary-source capsule. No ambient n055 import or pyc is used.
"""
import hashlib
import importlib.abc
import importlib.util
import json
import os
import stat
import sys
import time
from pathlib import Path

BOOTSTRAP_READS = []
FRAME_STARTED = False
ALLOWED = ('n055/__init__.py', 'n055/common.py', 'n055/budget.py', 'n055/journal.py',
    'n055/process.py', 'n055/cgroup.py', 'n055/native.py', 'n055/native_providers.py',
    'n055/resource_policy.py', 'n055/registry.py', 'n055/seals.py',
    'n055/postscore_role_host.py', 'n055/postscore_reserved.py', 'n055/postscore_services.py',
    'postscore_role_worker.py', 'model_provider_entry.py')


def bootstrap_read(path, cap, expected):
    path = Path(path); fd = None; body = bytearray()
    record = dict(path=str(path), bytes=0, closed=False, complete=False); BOOTSTRAP_READS.append(record)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('literal source bootstrap')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > cap:
        raise ValueError('bounded single-link source bootstrap')
    try:
        fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW)
        while len(body) <= cap:
            part = os.read(fd, min(65536, cap+1-len(body))); body.extend(part)
            record['bytes'] = len(body)
            if not part: break
        after = os.fstat(fd)
        if len(body) > cap or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
            before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size,
                                  after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('changed source bootstrap')
    finally:
        if fd is not None: os.close(fd); record['closed'] = True
    raw = bytes(body)
    if hashlib.sha256(raw).hexdigest() != expected: raise ValueError('bootstrap source SHA256')
    record['complete'] = True
    return raw


class CapturedLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, bodies): self.bodies = bodies
    def find_spec(self, fullname, path=None, target=None):
        name = 'n055/__init__.py' if fullname == 'n055' else fullname.replace('.', '/')+'.py'
        if fullname == 'n055' or fullname.startswith('n055.'):
            if name not in self.bodies: raise ImportError('outside fixed captured role capsule')
            return importlib.util.spec_from_loader(fullname, self, is_package=fullname == 'n055')
        return None
    def create_module(self, spec): return None
    def exec_module(self, module):
        name = 'n055/__init__.py' if module.__name__ == 'n055' else module.__name__.replace('.', '/')+'.py'
        module.__file__ = '<captured-role>/'+name
        exec(compile(self.bodies[name], module.__file__, 'exec'), module.__dict__)


def load_boot(path, digest):
    raw = bootstrap_read(path, 8388608, digest)
    boot = json.loads(raw.decode('utf-8'))
    if boot['schema'] != 'neural055-role-worker-bootstrap-v2': raise ValueError('worker bootstrap schema')
    descriptors = boot['capsule_files']; root = Path(boot['capsule_root'])
    if len(descriptors) != len(ALLOWED) or {d['path'] for d in descriptors} != set(ALLOWED):
        raise ValueError('closed worker source allowlist')
    bodies = {}
    for desc in descriptors:
        if desc['mode'] != '0o444' or desc['role'] != 'runtime_source' or desc['bytes'] > 1048576:
            raise ValueError('ordinary captured source role')
        p = root/desc['path']
        if stat.S_IMODE(p.lstat().st_mode) != 0o444: raise ValueError('readonly captured source')
        bodies[desc['path']] = bootstrap_read(p, desc['bytes'], desc['sha256'])
    if any(name == 'n055' or name.startswith('n055.') for name in sys.modules):
        raise ValueError('fresh captured source namespace required')
    loader = CapturedLoader(bodies); sys.meta_path.insert(0, loader)
    modules = {}
    for name in ('common', 'budget', 'journal', 'process', 'cgroup', 'native_providers',
                 'native', 'resource_policy', 'registry', 'seals', 'postscore_role_host',
                 'postscore_reserved', 'postscore_services'):
        modules[name] = __import__('n055.'+name, fromlist=[name])
    return boot, modules, bodies


def claim_cache(c, budget, root, ident):
    """Exclusive one-use local cache claim, retained after both success/failure."""
    root = Path(root)
    c.require(root.is_absolute() and root.is_dir() and
              not any(p.is_symlink() for p in (root, *root.parents)), 'qualified exclusive cache root')
    path = root/'N055_ROLE_CLAIM'; body = ident.encode('ascii'); fd = None; offset = 0
    budget.admit_write(len(body))
    try:
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        budget.file_created()
        while offset < len(body):
            try: n = os.write(fd, body[offset:])
            except BaseException as error:
                n = budget.failed_write('exclusive-cache-claim', error, len(body)-offset)
                if type(n) is int and n > 0: budget.written(n); offset += n
                raise
            n = budget.write_count('exclusive-cache-claim', n, len(body)-offset)
            c.require(n is not None and n > 0, 'actual cache claim prefix')
            offset += n; budget.written(n)
        os.fsync(fd)
    finally:
        if fd is not None:
            try: os.close(fd)
            except BaseException as error:
                budget.uncertain('exclusive-cache-claim', 'managed_descriptor_closure', error); raise
    return dict(path=str(path), bytes=offset, sha256=c.sha(body), retained=True)


def cost_snapshot(budget, resources):
    """Typed actual prefixes; repeated uncertainty never erases a known prefix."""
    costs = {key: None if key == 'cpu_seconds' else getattr(budget, key) for key in resources}
    unknown = ['cpu_seconds']; lower = {}
    for row in budget.unknown:
        affected = ['write_bytes'] if row.get('quantity') == 'managed_write_extent' else list(resources[1:])
        for key in affected:
            lower[key] = getattr(budget, key)
            costs[key] = None
            if key not in unknown: unknown.append(key)
    return dict(costs=costs, unknown_quantities=unknown, known_lower_bounds=lower, costs_complete=False)


def execute(boot, runtime, bodies):
    global FRAME_STARTED
    c = runtime['common']; host = runtime['postscore_role_host']
    request = boot['request']; deadline = boot['actual_deadline']; d = boot['deployment']
    budget = runtime['budget'].Budget(request['original_origin'], boot['limits'], cpu_origin=0.)
    c.require(budget.deadline == deadline, 'same original absolute external cutoff')
    budget.bind_resource_policy(boot['resource_policy'], boot['resource_definition'])
    # Reads performed by the minimal captured-source bootstrap are admitted and
    # debited before any model/daemon activation, including refused prefixes.
    budget.read(sum(row['bytes'] for row in BOOTSTRAP_READS))
    carrier = c.FailureCarrier(); carrier.retain(BOOTSTRAP_READS)
    journal = runtime['journal'].Journal(boot['journal_root'], budget, carrier)
    runner = runtime['process'].ProcessRunner(budget, journal, carrier)
    frame = dict(schema='neural055-closed-role-worker-frame-v2',
        request_sha256=c.sha(c.encoded(request)), complete=False, costs_complete=False,
        result=None, usage=None, original_processes=[], costs={k: None for k in host.RESOURCES},
        unknown_quantities=list(host.RESOURCES), known_lower_bounds={},
        native_cumulative_io_and_physical_storage_not_measured=True)
    daemon = adapter = None; failure = None; daemon_publication = None
    try:
        budget.admit('before actual role preparation', deadline)
        c.require(tuple(d['capsule_paths']) == host.CAPSULE, 'fixed actual role capsule')
        c.require(boot['source_identity'] == request['source'], 'same source request')
        prepared = boot['prepared_payload']; c.keys(prepared,
            ('messages', 'authorized_inputs', 'response_contract', 'output_policy'))
        provider = runtime['postscore_reserved'].capture_provider(runtime, budget,
            d['operator_root'], boot['role_spec'], boot['source_identity'])
        runtime['postscore_reserved'].validate_reservation(c, request, provider['config'], prepared['messages'])
        actual_provider_root = journal.root/'provider_runtime'; actual_provider_root.mkdir(mode=0o700)
        entry = journal.write('provider_runtime/model_provider_entry.py', bodies['model_provider_entry.py'])
        os.chmod(actual_provider_root/'model_provider_entry.py', 0o444); os.chmod(actual_provider_root, 0o555)
        source = runtime['postscore_reserved'].ModelSource(c, budget, actual_provider_root,
            dict(path='model_provider_entry.py', bytes=entry['observed_bytes'], sha256=entry['sha256'],
                 mode='0o444', role='runtime_source'), boot['source_identity'])
        claim = claim_cache(c, budget, d['daemon_data_roots'][request['role']], boot['role_id'])
        journal.json('CACHE_CLAIM.json', claim)
        daemon_config = journal.json('DAEMON_CONFIG.json', {})
        cli_config = journal.root/'docker_cli'; cli_config.mkdir(mode=0o700)
        socket_path = journal.root/'docker.sock'; exec_root = journal.root/'daemon_exec'
        exec_root.mkdir(mode=0o700)
        provider_parent = str(Path(boot['provider_parent']).relative_to('/sys/fs/cgroup'))
        daemon_argv = [boot['binaries']['dockerd'], '--config-file', str(journal.root/daemon_config['path']),
            '--host', 'unix://'+str(socket_path), '--data-root', d['daemon_data_roots'][request['role']],
            '--exec-root', str(exec_root), '--pidfile', str(journal.root/'dockerd.pid'),
            '--containerd-namespace', boot['role_id'], '--containerd-plugins-namespace', boot['role_id']+'-plugins',
            '--exec-opt', 'native.cgroupdriver=cgroupfs', '--cgroup-parent', provider_parent,
            '--bridge=none', '--iptables=false', '--ip6tables=false', '--ip-forward=false',
            '--ip-masq=false', '--userland-proxy=false', '--live-restore=false']
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'N055_ROLE_WORKDIR': str(journal.root),
               'PYTHONDONTWRITEBYTECODE': '1'}
        daemon = host.GatedProcess(runtime, budget, journal, carrier, runner, 'dedicated-daemon',
            boot['binaries']['launcher'], boot['daemon_leaf'], daemon_argv, deadline,
            1048576, journal.root/'daemon-gate.sock', env)
        daemon.start()
        action_deadline = deadline-d['closure_reserve_seconds']
        c.require(budget.clock() < action_deadline, 'closure inside original role cutoff')
        # Socket appearance is a bounded readiness condition; there is no blind
        # retry of a failed Docker command or model operation.
        while not socket_path.exists():
            daemon.poll(); c.require(not daemon.original['reaped'], 'owned daemon stayed live')
            budget.check('dedicated daemon readiness', action_deadline); time.sleep(.01)
        c.require(stat.S_ISSOCK(socket_path.lstat().st_mode), 'actual owned daemon socket')
        def daemon_poll(end):
            daemon.poll(); c.require(not daemon.original['reaped'], 'owned daemon remains live')
            budget.check('dedicated daemon poll', end)
        profile = dict(d['native_profile']); profile['docker_binary'] = boot['binaries']['docker']
        profile['docker_host'] = 'unix://'+str(socket_path)
        info_obs = runner.run('dedicated-daemon-info', [profile['docker_binary'], '--config', str(cli_config), '--host',
            profile['docker_host'], 'info', '--format', '{{json .}}'], action_deadline, 131072,
            env=env, poll_service=daemon_poll)
        info = c.parse(bytes(info_obs.stdout))
        c.require(info['OSType'] == 'linux' and info['CgroupVersion'] == '2' and
                  info['CgroupDriver'] == 'cgroupfs' and info['DockerRootDir'] ==
                  d['daemon_data_roots'][request['role']] and type(info['ID']) is str and info['ID'],
                  'actual dedicated daemon and private cache identity')
        observer = host.KernelObserver(c, budget, carrier, deadline)
        c.require(observer.read(journal.root/'dockerd.pid') == str(daemon.pid),
                  'actual dedicated daemon pidfile joins gated original process')
        observer.membership(daemon.pid, boot['daemon_leaf'])
        profile['daemon_id'] = info['ID']
        scope = runtime['cgroup'].Cgroup(Path(boot['provider_parent']).parent,
            Path(boot['provider_parent']).name, budget, deadline)
        scope.initial_cpu = boot['provider_initial_cpu']
        adapter = runtime['postscore_reserved'].ReservedAdapter(runtime, budget, journal,
            carrier, runner, profile, source, provider, scope, daemon_poll)
        inventory = adapter.command(['container', 'ls', '-a', '--no-trunc', '--format', '{{.ID}}'],
                                    4096, action_deadline)
        c.require(inventory.strip() == b'', 'exclusive dedicated daemon starts without containers')
        image = runtime['native'].one(c.parse(adapter.command(['image', 'inspect', profile['image']],
                                                              end=action_deadline)))
        c.require(image['Id'] == profile['image'] and not image['Config'].get('Volumes') and
                  (not image['Config'].get('Healthcheck') or image['Config']['Healthcheck'].get('Test') == ['NONE']),
                  'qualified cached image without implicit producers')
        text, usage = adapter.generate(request, prepared['messages'], action_deadline)
        frame['usage'] = usage
        model_output = journal.write('ACTUAL_MODEL_OUTPUT.json', text)
        bound = runtime['postscore_services'].bind_result(request, text,
            prepared['authorized_inputs'], prepared['output_policy'])
        frame['result'] = host.publication_descriptor(journal.json('RESULT.json', bound),
                                                      'postscore_role_result')
        c.require(all(row['closed'] for row in adapter.observed.resources), 'all provider resources retired')
        c.require(adapter.command(['container', 'ls', '-a', '--no-trunc', '--format', '{{.ID}}'],
                                 4096).strip() == b'', 'dedicated daemon empty after role')
        daemon.wait(shutdown=True)
        daemon_publication = journal.json('DAEMON_PROCESS.json', daemon.original)
        journal.write('DAEMON_STREAM.txt', bytes(daemon.body))
        evidence = journal.json('ROLE_SOURCE_AND_PROVIDER.json', dict(source=boot['source_identity'],
            provider=boot['role_spec'], actual_daemon_id=info['ID'], cache_claim=claim,
            actual_model_output=model_output, original_adapter=adapter.original,
            legacy_role='investigator_decision', actual_role=request['role'],
            no_new_token_ledger=True, original_reservation=request['token_reservation']))
        frame['role_evidence'] = host.publication_descriptor(evidence, 'original_role_provider_receipt')
        frame['original_processes'] = [host.publication_descriptor(daemon_publication, 'original_process_receipt')]
        frame['original_processes'] += [host.publication_descriptor(x.publication,
            'original_process_receipt') for x in runner.originals]
        budget.admit('after complete role result and process publication', deadline)
        frame['complete'] = True
    except BaseException as error:
        failure = error; carrier.fail(error, 'actual-role-worker')
        if adapter is not None and adapter.original['usage'] is not None:
            frame['usage'] = adapter.original['usage']
    finally:
        if daemon is not None and not daemon.closed:
            try: daemon.abort()
            except BaseException as error: carrier.fail(error, 'daemon-abort')
        try:
            journal.terminal(dict(schema='neural055-role-worker-terminal-v2',
                request_sha256=frame['request_sha256'], complete=frame['complete'],
                usage=frame['usage'], result=frame['result'], errors=carrier.document(),
                bootstrap_reads=BOOTSTRAP_READS,
                daemon=None if daemon is None else daemon.original))
        except BaseException as error: carrier.fail(error, 'role-terminal')
        if carrier.first is not None: frame['complete'] = False
        # This snapshot follows every role-owned managed publication. The final
        # stdout frame is transport: controller stream accounting observes its
        # actual returned bytes, while final role cgroup CPU includes encoding/send.
        frame.update(cost_snapshot(budget, host.RESOURCES))
        frame['failure_types'] = [c.diagnostic_type(row[0]) if type(row) is tuple else
                                  'original_failure_retained' for row in carrier.failures]
        frame['costs_complete'] = False  # Outer observer closes the whole role CPU owner.
        raw = c.encoded(frame); c.require(len(raw) <= 1048576, 'bounded final role frame')
        offset = 0
        FRAME_STARTED = True
        while offset < len(raw):
            budget.check('final role transport', deadline)
            n = os.write(1, raw[offset:]); c.require(n > 0, 'actual final transport progress'); offset += n
    return 0 if frame['complete'] else 1


def main():
    if len(sys.argv) != 3: raise ValueError('exact original worker operands')
    boot, runtime, bodies = load_boot(sys.argv[1], sys.argv[2])
    return execute(boot, runtime, bodies)


if __name__ == '__main__':
    try: status = main()
    except BaseException:
        # Raw output/partial frame remains on the owning controller. This is not
        # a fabricated known-zero cost receipt after failed bootstrap.
        if not FRAME_STARTED: os.write(2, b'original role bootstrap/final transport failed\n')
        status = 1
    raise SystemExit(status)
