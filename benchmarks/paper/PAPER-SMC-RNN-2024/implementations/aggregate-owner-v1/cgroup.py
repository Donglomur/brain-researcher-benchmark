"""Task-local persistent cgroup custody; source construction is not admission.

Reuses the existing ZuCo persistent-parent/cpu.stat/cgroup.kill pattern and
Helsinki descriptor/mount checks. No cgroup or process is opened at import.
The separately pinned deployment binding must resolve before construction.
CPU polling is detection followed by closure, never a zero-overshoot claim.
"""
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import select
import stat
import sys
import time

CGROUP_MAGIC = 0x63677270
PROC_MAGIC = 0x9fa0
PHASES = ('paper_data', 'paper_data_author_code_and_weights')
CONTROLLERS = {'cpu', 'memory', 'pids'}
MAX_INTERFACE = 262144
RESOURCE_POLICY = 'measured_caps_and_oom_kill_v1'
# Same exact authenticated request.resources ABI as the selected transport.
RESOURCE_KEYS = {
    'setup_seconds', 'producer_seconds', 'capture_seconds', 'cleanup_seconds',
    'memory_bytes', 'cpu_nanos', 'cpu_seconds', 'pids', 'scratch_bytes',
    'max_files', 'max_directories', 'max_file_bytes', 'max_output_bytes',
    'manifest_bytes', 'max_cli_calls', 'max_cli_bytes', 'inventory_bytes',
    'source_read_bytes', 'host_write_bytes',
}
KERNEL_LIMIT_KEYS = ('cpu_seconds', 'memory_bytes', 'cpu_nanos', 'pids')


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= 2 * 1024**2 and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'exact metadata pin')
    return value


def decoded(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'unique metadata keys')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'finite metadata numbers'))


def directory(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute unlinked directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _magic(fd):
    need(sys.platform == 'linux' and platform.machine() in ('x86_64', 'aarch64') and
         ctypes.sizeof(ctypes.c_long) == 8, 'selected Linux LP64 cgroup ABI')
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.fstatfs
    call.argtypes, call.restype = (ctypes.c_int, ctypes.c_void_p), ctypes.c_int
    out = (ctypes.c_long * 32)()
    if call(fd, ctypes.byref(out)) != 0:
        raise OSError(ctypes.get_errno(), 'fstatfs')
    return out[0]


def _read_kernel(fd, name, cap=8192):
    need(type(name) is str and '/' not in name and name not in ('.', '..'), 'kernel basename')
    stream = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    try:
        need(stat.S_ISREG(os.fstat(stream).st_mode), 'ordinary kernel interface')
        raw = os.read(stream, cap + 1)
        need(len(raw) <= cap and not os.read(stream, 1), 'complete bounded kernel interface')
        return raw.decode('ascii')
    finally:
        os.close(stream)


def _write_kernel(fd, name, value):
    need(name in {'memory.max', 'memory.swap.max', 'pids.max', 'cpu.max', 'cgroup.kill', 'cgroup.subtree_control'}, 'fixed cgroup mutation')
    stream = os.open(name, os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
    try:
        raw = (value + '\n').encode('ascii')
        need(os.write(stream, raw) == len(raw), 'complete cgroup setting write')
    finally:
        os.close(stream)


def _file(path, expected=None):
    path = Path(path)
    parent = directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= 2 * 1024**2,
                 'bounded ordinary owner metadata')
            raw = stream.read(2 * 1024**2 + 1)
            after = os.fstat(stream.fileno())
            named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in keys),
             'stable owner metadata bytes')
        if expected is not None:
            need(pin(raw) == descriptor(expected), 'exact owner metadata pin')
        return decoded(raw)
    finally:
        os.close(parent)


def _table(text, required):
    rows = {}
    for line in text.splitlines():
        parts = line.split()
        need(len(parts) == 2 and re.fullmatch('[a-z_]+', parts[0]) and
             re.fullmatch('[0-9]{1,20}', parts[1]) and parts[0] not in rows and len(rows) < 32,
             'bounded unique kernel counters')
        rows[parts[0]] = int(parts[1])
    need(required <= set(rows), 'complete required kernel counters')
    return rows


def _number(text):
    need(type(text) is str and re.fullmatch('[0-9]{1,20}\n', text), 'literal unsigned kernel value')
    return int(text)


def _identity(fd):
    row = os.fstat(fd)
    need(stat.S_ISDIR(row.st_mode), 'retained scope directory')
    return {'st_dev': row.st_dev, 'st_ino': row.st_ino, 'uid': row.st_uid}


def _pidfd_live(fd):
    return not select.select([fd], [], [], 0)[0]


def _self_namespaces():
    return {name: os.stat('/proc/self/ns/' + name).st_ino for name in ('pid', 'mnt', 'cgroup')}


def _original_owner(folder):
    # The parent's exact selected source closure supplies this unchanged module.
    # Its expected() validates the intent/birth/controller/grant joins, including
    # the original boot and clock. No process is launched or signalled here.
    import process_owner
    return process_owner.expected(folder / 'process', require_remaining=False)[0]


def _close_original_custody(custody, deadline):
    import cli_custody
    need(type(custody) is cli_custody.CliCustody and custody.deadline == deadline,
         'actual original acknowledged CLI custody')
    return custody.close(deadline)


def _group_absent(pgid):
    need(type(pgid) is int and pgid > 1 and pgid != os.getpgrp(), 'exact non-self controller group')
    try:
        os.killpg(pgid, 0)  # Observation only, never a process signal.
    except ProcessLookupError:
        return True
    return False


def _process_birth(pid):
    fd = directory('/proc/' + str(pid))
    try:
        need(_magic(fd) == PROC_MAGIC, 'actual producer procfs')
        raw = _read_kernel(fd, 'stat', 8192)
        end = raw.rfind(')')
        need(raw.startswith(str(pid) + ' (') and end > 0, 'exact producer proc stat')
        parts = raw[end + 2:].split()
        need(len(parts) >= 20 and parts[0] not in ('Z', 'X') and parts[19].isdigit(), 'live producer start ticks')
        member = _read_kernel(fd, 'cgroup', 8192)
        rows = member.splitlines()
        need(len(rows) == 1 and rows[0].startswith('0::/'), 'one unified producer cgroup membership')
        namespaces = {name: os.stat('/proc/' + str(pid) + '/ns/' + name).st_ino for name in ('pid', 'mnt', 'cgroup')}
        return {'pid': pid, 'start_ticks': int(parts[19]), 'cgroup': rows[0][3:], 'namespaces': namespaces}
    finally:
        os.close(fd)


class ScopeViolation(RuntimeError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.evidence = evidence


class ScopeManager:
    def __init__(self, deployment, clock, invocation_pin, source, writer, folder):
        keys = {'image', 'docker_binary', 'docker_socket', 'boot_id', 'delegation', 'pid_limit', 'qualification', 'binding_pin', 'resource_policy', 'cgroup_driver'}
        need(type(deployment) is dict and set(deployment) == keys, 'resolved exact deployment binding')
        need(deployment['resource_policy'] == RESOURCE_POLICY, 'exact aggregate resource-event interpretation')
        need(deployment['cgroup_driver'] == 'cgroupfs', 'selected literal cgroupfs hierarchy driver')
        self.deployment = decoded(encoded(deployment))
        self.clock = decoded(encoded(clock))
        self.invocation_pin, self.source = descriptor(invocation_pin), descriptor(source)
        descriptor(deployment['binding_pin'])
        need(clock['clock_identity'] == 'linux:' + deployment['boot_id'] and
             all(type(clock[k]) in (int, float) and math.isfinite(clock[k]) for k in ('origin', 'controller_deadline', 'deadline')) and
             0 < clock['origin'] < clock['controller_deadline'] < clock['deadline'], 'same-boot original monotonic clock')
        d = deployment['delegation']
        need(type(d) is dict and set(d) == {'path', 'st_dev', 'st_ino', 'uid', 'mount_id', 'mount_point', 'mount_root', 'fs_type'} and
             d['fs_type'] == 'cgroup2' and d['mount_root'] == '/' and d['mount_point'] == '/sys/fs/cgroup' and
             all(type(d[k]) is int and d[k] >= 0 for k in ('st_dev', 'st_ino', 'uid', 'mount_id')) and
             d['st_ino'] > 0 and d['mount_id'] > 0 and type(deployment['pid_limit']) is int and deployment['pid_limit'] > 1,
             'exact delegated cgroup2 host binding')
        self.root = Path(d['path'])
        need(str(self.root) == d['path'] and self.root.is_absolute() and '..' not in self.root.parts and
             self.root != Path(d['mount_point']) and self.root.is_relative_to(d['mount_point']), 'nonroot exact delegation')
        self.folder = Path(folder)
        fd = directory(self.folder)
        os.close(fd)
        invocation = _file(self.folder / 'INVOCATION.json', invocation_pin)
        need(invocation['source'] == source and invocation['clock'] == clock, 'fixed original owner invocation')
        self.writer, self.scopes, self.closure_pin, self.closed = writer, {}, None, None
        self.emergency_attempted = False
        self.root_fd = None
        try:
            self._host()
        except BaseException:
            if self.root_fd is not None:
                os.close(self.root_fd)
                self.root_fd = None
            raise

    def _tick(self, closing=False):
        now = time.monotonic()
        need(self.clock['origin'] <= now < self.clock['deadline' if closing else 'controller_deadline'],
             'unchanged original cgroup deadline')
        return now

    def _host(self):
        self._tick(closing=True)
        need(sys.platform == 'linux', 'actual Linux cgroup host required')
        boot_fd = directory('/proc/sys/kernel/random')
        try:
            need(_magic(boot_fd) == PROC_MAGIC and
                 _read_kernel(boot_fd, 'boot_id', 64) == self.deployment['boot_id'] + '\n', 'same original Linux boot')
        finally:
            os.close(boot_fd)
        own = directory('/proc/' + str(os.getpid()))
        try:
            need(_magic(own) == PROC_MAGIC, 'actual host procfs')
            mounts = _read_kernel(own, 'mountinfo', MAX_INTERFACE)
            own_membership = _read_kernel(own, 'cgroup')
        finally:
            os.close(own)
        d = self.deployment['delegation']
        found = []
        for line in mounts.splitlines():
            fields = line.split()
            need(' - ' in line and len(fields) >= 10, 'complete host mountinfo')
            split = fields.index('-')
            if fields[4] == d['mount_point']:
                found.append(fields)
            elif fields[4].startswith(d['mount_point'] + '/'):
                need(False, 'no cgroup subtree overmount')
        need(len(found) == 1, 'one selected cgroup mount')
        row = found[0]
        split = row.index('-')
        need(row[0] == str(d['mount_id']) and row[2] == str(os.major(d['st_dev'])) + ':' + str(os.minor(d['st_dev'])) and
             row[3] == d['mount_root'] and row[split + 1] == d['fs_type'] and 'rw' in row[5].split(','), 'exact delegated mount identity')
        fd = directory(self.root)
        try:
            need(_magic(fd) == CGROUP_MAGIC and _identity(fd) == {k: d[k] for k in ('st_dev', 'st_ino', 'uid')} and
                 d['uid'] == os.geteuid(), 'owned unchanged delegated root')
            need(CONTROLLERS <= set(_read_kernel(fd, 'cgroup.controllers').split()) and
                 CONTROLLERS <= set(_read_kernel(fd, 'cgroup.subtree_control').split()) and
                 _read_kernel(fd, 'cgroup.type') == 'domain\n' and _read_kernel(fd, 'cgroup.procs') == '',
                 'available enabled controllers without delegation process membership')
            relative = '/' + str(self.root.relative_to(d['mount_point']))
            need(not any(line == '0::' + relative or line.startswith('0::' + relative + '/')
                         for line in own_membership.splitlines()), 'owner outside producer delegation')
            if self.root_fd is None:
                self.root_fd, fd = fd, None
            else:
                need(_identity(self.root_fd) == _identity(fd), 'retained delegation descriptor')
        finally:
            if fd is not None:
                os.close(fd)
        self._tick(closing=True)

    def _publish(self, name, body, terminal=False):
        target = self.folder / name
        result = self.writer.publish(target, body, terminal=terminal)
        need(_file(target, result) == body, 'exact durable owner publication')
        return result

    def _scope_identity(self, scope):
        need(scope['fd'] is not None and scope['identity'] is not None, 'observed scope identity before any mutation or closure')
        self._host()
        named = os.stat(scope['plan']['name'], dir_fd=self.root_fd, follow_symlinks=False)
        actual = _identity(scope['fd'])
        need(stat.S_ISDIR(named.st_mode) and not named.st_mode & 0o077 and
             actual == scope['identity'] == {'st_dev': named.st_dev, 'st_ino': named.st_ino, 'uid': named.st_uid} and
             _magic(scope['fd']) == CGROUP_MAGIC, 'same private original scope inode')

    def prepare(self, phase, plan, limits, *, intent_ref, request_pin):
        self._tick()
        need(phase in PHASES and phase not in self.scopes and self.closure_pin is None and not self.emergency_attempted,
             'one fresh admitted phase')
        descriptor(request_pin)
        need(type(plan) is dict and set(plan) == {'schema', 'phase_id', 'name', 'parent', 'path', 'cgroup_parent', 'deployment_pin', 'invocation_pin'} and
             plan['schema'] == 'smc_cgroup_plan_v1' and plan['phase_id'] == phase and
             re.fullmatch('smc-[0-9a-f]{32}-' + ('a' if phase == PHASES[0] else 'b'), plan['name']) and
             plan['parent'] == str(self.root) and plan['path'] == str(self.root / plan['name']) and
             plan['cgroup_parent'] == '/' + str(Path(plan['path']).relative_to(self.deployment['delegation']['mount_point'])) and
             plan['deployment_pin'] == self.deployment['binding_pin'] and plan['invocation_pin'] == self.invocation_pin,
             'exact original scope plan')
        need(type(limits) is dict and set(limits) == RESOURCE_KEYS and
             all(type(v) is int and v > 0 for v in limits.values()),
             'exact complete positive-integer transport resource bounds')
        kernel_limits = {key: limits[key] for key in KERNEL_LIMIT_KEYS}
        need(kernel_limits['cpu_nanos'] == 6000000000 and
             kernel_limits['pids'] == self.deployment['pid_limit'], 'exact six-CPU aggregate profile')
        need(type(intent_ref) is dict and set(intent_ref) == {'path', 'bytes', 'sha256'}, 'exact durable intent reference')
        target = Path(intent_ref['path'])
        need(target.parent == self.folder / 'events' and re.fullmatch('EVENT-[0-9]+\.json', target.name), 'fixed original owner event path')
        intent = _file(target, {k: intent_ref[k] for k in ('bytes', 'sha256')})
        need(intent['schema'] == 'smc_aggregate_owner_event_v1' and intent['owner_source'] == self.source and
             intent['invocation_pin'] == self.invocation_pin and intent['message']['event'] == 'CGROUP-INTENT', 'persisted parent cgroup intent')
        wrapper = intent['message']['value']
        record = wrapper['record']
        need(pin(encoded(record)) == descriptor(wrapper['pin']) and record['schema'] == 'smc_aggregate_transport_journal_v1' and
             record['phase_id'] == phase and record['request_sha256'] == request_pin['sha256'] and
             type(record['index']) is int and record['index'] >= 0 and record['event'] == 'CGROUP-INTENT' and
             record['value'] == {'plan': plan, 'limits': limits}, 'exact request/source/limits intent before mkdir')
        self._host()
        self._tick()
        scope = {'plan': decoded(encoded(plan)), 'limits': dict(limits), 'request_pin': dict(request_pin), 'fd': None,
                 'identity': None, 'owner_pin': None, 'producer': None, 'pidfd': None, 'last': None,
                 'finished': False, 'errors': [], 'removed': False}
        self.scopes[phase] = scope  # An incomplete create remains unknown, never an absence proof.
        os.mkdir(plan['name'], mode=0o700, dir_fd=self.root_fd)
        fd = os.open(plan['name'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.root_fd)
        scope['fd'] = fd  # Retain the descriptor even if the first identity read fails.
        scope['identity'] = _identity(fd)
        os.fchmod(fd, 0o700)
        self._scope_identity(scope)
        need(_read_kernel(fd, 'cgroup.procs') == '' and _table(_read_kernel(fd, 'cgroup.events'), {'populated'})['populated'] == 0,
             'fresh empty original scope')
        need(CONTROLLERS <= set(_read_kernel(fd, 'cgroup.controllers').split()), 'scope controllers delegated from selected parent')
        _write_kernel(fd, 'cgroup.subtree_control', '+cpu +memory +pids')
        need(CONTROLLERS <= set(_read_kernel(fd, 'cgroup.subtree_control').split()), 'scope controllers available to actual Docker child')
        settings = {'memory.max': str(kernel_limits['memory_bytes']), 'memory.swap.max': '0',
                    'pids.max': str(kernel_limits['pids']), 'cpu.max': '600000 100000'}
        for name, value in settings.items():
            self._tick()
            _write_kernel(fd, name, value)
            need(_read_kernel(fd, name) == value + '\n', 'exact original scope limit readback')
        initial = self._snapshot(scope)
        counters = initial['counters']
        need(initial['empty'] and counters['cpu_usage_usec'] == 0 and counters['memory_peak_bytes'] == 0 and
             not any(counters['memory_events'].values()) and not any(counters['pids_events'].values()) and initial['within_limits'],
             'fresh unexplained CPU/memory/PID history cannot be subtracted')
        owner = {'schema': 'smc_aggregate_scope_owner_v1', 'phase_id': phase, 'plan': plan, 'limits': limits,
                 'resource_policy': RESOURCE_POLICY,
                 'intent_ref': intent_ref, 'request_pin': request_pin, 'invocation_pin': self.invocation_pin,
                 'source': self.source, 'clock': self.clock, 'deployment_pin': self.deployment['binding_pin'],
                 'identity': scope['identity'], 'initial': initial}
        scope['owner_pin'] = self._publish('CGROUP-' + phase + '-OWNER.json', owner)
        self._tick()
        return {'phase_id': phase, 'request_pin': request_pin, 'plan': plan, 'owner_pin': scope['owner_pin']}

    def attach(self, phase, event):
        self._tick()
        scope = self.scopes[phase]
        need(scope['owner_pin'] is not None and scope['producer'] is None and self.closure_pin is None and not self.emergency_attempted,
             'one actual producer after durable ownership')
        need(type(event) is dict and set(event) == {'pid', 'container_id', 'cgroup_parent'} and
             type(event['pid']) is int and event['pid'] > 1 and
             re.fullmatch('[0-9a-f]{64}', event['container_id']) and event['cgroup_parent'] == scope['plan']['cgroup_parent'],
             'actual inspected producer and original cgroup parent')
        self._scope_identity(scope)
        fd = os.pidfd_open(event['pid'], 0)
        try:
            before = _process_birth(event['pid'])
            need(_pidfd_live(fd), 'live original producer pidfd')
            after = _process_birth(event['pid'])
            membership = scope['plan']['cgroup_parent']
            own_namespaces = _self_namespaces()
            need(before == after and before['cgroup'] == membership + '/' + event['container_id'] and
                 all(before['namespaces'][key] != own_namespaces[key] for key in ('pid', 'mnt', 'cgroup')),
                 'same producer birth inside exact private container subtree')
            evidence = {'event': event, 'birth': before, 'request_pin': scope['request_pin'], 'owner_pin': scope['owner_pin'],
                        'invocation_pin': self.invocation_pin, 'source': self.source, 'clock': self.clock}
            result = self._publish('CGROUP-' + phase + '-ATTACHED.json', evidence)
            self._tick()
            scope['producer'], scope['pidfd'] = evidence, fd
            fd = None
            return {'phase_id': phase, 'producer': evidence, 'attachment_pin': result}
        finally:
            if fd is not None:
                os.close(fd)

    def _snapshot(self, scope):
        self._scope_identity(scope)
        fd = scope['fd']
        before = _table(_read_kernel(fd, 'cgroup.events'), {'populated', 'frozen'})
        cpu = _table(_read_kernel(fd, 'cpu.stat'), {'usage_usec', 'user_usec', 'system_usec'})
        memory = _table(_read_kernel(fd, 'memory.events'), {'max', 'oom', 'oom_kill'})
        pids = _table(_read_kernel(fd, 'pids.events'), {'max'})
        events = _table(_read_kernel(fd, 'cgroup.events'), {'populated', 'frozen'})
        peak = _number(_read_kernel(fd, 'memory.peak'))
        need(before['populated'] in (0, 1) and before['frozen'] == 0 and
             events['populated'] in (0, 1) and events['frozen'] == 0 and
             cpu['user_usec'] <= cpu['usage_usec'] and cpu['system_usec'] <= cpu['usage_usec'], 'consistent kernel scope counters')
        counters = {'cpu_usage_usec': cpu['usage_usec'], 'cpu_stat': cpu, 'memory_peak_bytes': peak,
                    'memory_events': memory, 'pids_events': pids, 'cgroup_events': events,
                    'cgroup_events_before': before}
        empty = before['populated'] == events['populated'] == 0
        if empty and scope['pidfd'] is not None:
            need(not _pidfd_live(scope['pidfd']), 'original attached producer exited before empty scope acceptance')
        old = scope['last']
        if old is not None:
            need(cpu['usage_usec'] >= old['counters']['cpu_usage_usec'] and peak >= old['counters']['memory_peak_bytes'],
                 'original counters never reset')
            need(all(memory.get(k, -1) >= value for k, value in old['counters']['memory_events'].items()) and
                 all(pids.get(k, -1) >= value for k, value in old['counters']['pids_events'].items()),
                 'original memory and PID events never reset')
        failed = []
        if cpu['usage_usec'] > scope['limits']['cpu_seconds'] * 1000000:
            failed.append('aggregate_cpu_limit')
        if peak > scope['limits']['memory_bytes'] or any(memory.get(k, 0) for k in ('oom_kill', 'oom_group_kill')):
            failed.append('aggregate_memory_limit')
        result = {'observed_monotonic': time.monotonic(), 'identity': scope['identity'], 'counters': counters,
                  'empty': empty, 'within_limits': not failed, 'violations': failed,
                  'complete': True, 'measurement_scope': 'entire_original_producer_cgroup_including_descendants',
                  'zero_cpu_overshoot_claim': False}
        scope['last'] = result
        self._tick(closing=True)
        return result

    def poll(self):
        results = {}
        for phase, scope in self.scopes.items():
            if not scope['removed']:
                results[phase] = self._snapshot(scope)
        result = {'schema': 'smc_aggregate_scope_poll_v1', 'scopes': results, 'complete': True}
        failed = not all(row['within_limits'] for row in results.values()) or time.monotonic() >= self.clock['controller_deadline']
        if failed:
            failure = {'invocation_pin': self.invocation_pin, 'source': self.source, 'clock': self.clock, 'observed': result}
            if not (self.folder / 'CGROUP-VIOLATION.json').exists():
                self._publish('CGROUP-VIOLATION.json', failure, terminal=True)
            raise ScopeViolation('aggregate scope limit or original controller cutoff', result)
        return result

    def _receipt(self, phase, scope, snapshot, errors):
        return {'schema': 'smc_aggregate_scope_receipt_v1', 'phase_id': phase, 'plan': scope['plan'],
                'invocation_pin': self.invocation_pin, 'source': self.source, 'clock': self.clock,
                'resource_policy': RESOURCE_POLICY,
                'limits': scope['limits'], 'request_pin': scope['request_pin'], 'owner_pin': scope['owner_pin'],
                'producer': scope['producer'], 'counters': None if snapshot is None else snapshot['counters'],
                'empty': False if snapshot is None else snapshot['empty'],
                'within_limits': False if snapshot is None else snapshot['within_limits'],
                'complete': snapshot is not None and not errors, 'errors': errors,
                'last_known_observation': scope['last'], 'zero_cpu_overshoot_claim': False}

    def finish(self, phase):
        self._tick()
        need(not self.emergency_attempted, 'no gradeable result after emergency cleanup')
        scope = self.scopes[phase]
        need(scope['producer'] is not None and not scope['finished'], 'one finish for actual attached producer')
        observed = self._snapshot(scope)
        if not observed['empty'] and observed['counters']['cgroup_events']['populated'] == 0:
            # A live-to-empty transition cannot authenticate earlier CPU totals.
            # Read again after observed emptiness, without a fresh interval.
            self._tick()
            observed = self._snapshot(scope)
        receipt = self._receipt(phase, scope, observed, [])
        result = self._publish('CGROUP-' + phase + '-FINISHED.json', receipt)
        need(observed['empty'] and observed['within_limits'], 'closed within-limit hierarchy before phase acceptance')
        scope['finished'] = True
        return {**receipt, 'receipt_pin': result}

    def _controller_closed(self, closure_pin):
        closed = _file(self.folder / 'CONTROLLER_CLOSED.json', closure_pin)
        need(closed['schema'] == 'smc_parent_observed_controller_closure_v1' and
             closed['invocation_pin'] == self.invocation_pin and closed['source'] == self.source and closed['clock'] == self.clock and
             closed['future_controller_and_acknowledged_cli_release_closed'] is True and
             closed['controller_group']['absence_verified'] is True and closed['acknowledged_cli']['all_acknowledged_cli_absent'] is True,
             'original actual owner controller and CLI closure gate')
        owner = self._original_group_closed()
        need(owner['pgid'] == closed['controller_group']['pgid'], 'same recorded original controller group')
        return closed

    def _original_group_closed(self):
        owner = _original_owner(self.folder)
        need(owner['grant'] == {**self.clock, 'invocation_pin': self.invocation_pin} and
             owner['pid'] == owner['pgid'] and _group_absent(owner['pgid']),
             'observed original controller group remains absent before scope mutation')
        return owner

    def close(self, closure_pin):
        need(not self.emergency_attempted, 'no gradeable closure after emergency cleanup')
        descriptor(closure_pin)
        self._controller_closed(closure_pin)
        need(self.closure_pin is None or self.closure_pin == closure_pin, 'same retained controller closure')
        self.closure_pin = dict(closure_pin)
        receipts = {}
        for phase, scope in self.scopes.items():
            errors, observed = [], None
            try:
                self._tick(closing=True)
                self._scope_identity(scope)
                observed = self._snapshot(scope)
                if not observed['empty']:
                    self._controller_closed(closure_pin)
                    self._tick(closing=True)
                    _write_kernel(scope['fd'], 'cgroup.kill', '1')
                while not observed['empty']:
                    self._tick(closing=True)
                    time.sleep(min(.02, max(0, self.clock['deadline'] - time.monotonic())))
                    observed = self._snapshot(scope)
                self._tick(closing=True)
            except BaseException as exc:
                errors.append({'type': type(exc).__name__, 'message': str(exc)[:256]})
                observed = None  # Last observed values stay separately labeled, not final closure.
            receipt = self._receipt(phase, scope, observed, errors)
            if scope['identity'] is None and scope['fd'] is not None:
                # Closing our descriptor is safe; an unobserved directory is
                # still retained as unknown and must never be removed/killed.
                try:
                    os.close(scope['fd'])
                    scope['fd'] = None
                except OSError as exc:
                    receipt['errors'].append({'type': type(exc).__name__, 'message': 'unknown-scope descriptor close failed'})
            try:
                receipt['receipt_pin'] = self._publish('CGROUP-' + phase + '-CLOSED.json', receipt, terminal=True)
            except BaseException as exc:
                receipt['complete'] = False
                receipt['errors'].append({'type': type(exc).__name__, 'message': 'scope closure publication failed'})
            receipts[phase] = receipt
        complete = all(r['complete'] and r['empty'] for r in receipts.values()) and time.monotonic() < self.clock['deadline']
        self.closed = {'schema': 'smc_aggregate_scope_closure_v1', 'controller_closure_pin': closure_pin,
                       'scopes': receipts, 'all_scopes_empty': all(r['empty'] for r in receipts.values()),
                       'counters_complete': all(r['complete'] for r in receipts.values()),
                       'within_limits': all(r['within_limits'] for r in receipts.values()), 'complete': complete}
        return self.closed

    def emergency_close(self, custody):
        """Best-effort controlled exception cleanup, never a completion proof.

        No controller-closure file is trusted or required here: the actual
        unchanged process-owner metadata and acknowledged CLI custody are
        independently checked. Only previously observed directories may be
        stopped, without creation, removal, Provider calls, or a fresh clock.
        """
        need(not self.emergency_attempted, 'one retained emergency attempt')
        self.emergency_attempted = True
        rows, errors, cli, group = {}, [], None, None
        try:
            self._tick(closing=True)
            owner = self._original_group_closed()
            group = {'pgid': owner['pgid'], 'absence_verified': True}
            cli = _close_original_custody(custody, self.clock['deadline'])
            need(cli['all_acknowledged_cli_absent'] is True, 'actual acknowledged CLI absence before emergency scope stop')
            self._original_group_closed()
            for phase, scope in self.scopes.items():
                observed, failures = None, []
                try:
                    self._tick(closing=True)
                    self._scope_identity(scope)
                    observed = self._snapshot(scope)
                    if not observed['empty']:
                        self._original_group_closed()
                        self._tick(closing=True)
                        _write_kernel(scope['fd'], 'cgroup.kill', '1')
                    while not observed['empty']:
                        self._tick(closing=True)
                        time.sleep(min(.02, max(0, self.clock['deadline'] - time.monotonic())))
                        observed = self._snapshot(scope)
                    self._tick(closing=True)
                except BaseException as exc:
                    observed = None
                    failures.append({'type': type(exc).__name__, 'message': str(exc)[:256]})
                rows[phase] = {'plan': scope['plan'], 'request_pin': scope['request_pin'],
                               'final_observation': observed, 'last_known_observation': scope['last'],
                               'errors': failures}
        except BaseException as exc:
            errors.append({'type': type(exc).__name__, 'message': str(exc)[:256]})
        # Preserve unresolved/unknown phases even when a global gate failed.
        for phase, scope in self.scopes.items():
            if phase not in rows:
                rows[phase] = {'plan': scope['plan'], 'request_pin': scope['request_pin'],
                               'final_observation': None, 'last_known_observation': scope['last'],
                               'errors': [{'type': 'ClosureGateUnproven', 'message': 'scope mutation not authorized'}]}
            if scope['identity'] is None and scope['fd'] is not None:
                try:
                    os.close(scope['fd'])
                    scope['fd'] = None
                except OSError as exc:
                    rows[phase]['errors'].append({'type': type(exc).__name__, 'message': 'unknown-scope descriptor close failed'})
        result = {'schema': 'smc_aggregate_emergency_cleanup_v1', 'invocation_pin': self.invocation_pin,
                  'source': self.source, 'clock': self.clock, 'resource_policy': RESOURCE_POLICY,
                  'controller_group': group, 'acknowledged_cli': cli, 'scopes': rows, 'errors': errors,
                  'cleanup_complete': not errors and all(row['final_observation'] is not None and
                      row['final_observation']['empty'] and not row['errors'] for row in rows.values()) and
                      time.monotonic() < self.clock['deadline'],
                  'complete': False, 'gradeable': False, 'qualified': False,
                  'provider_recovery_attempted': False, 'scope_removal_attempted': False}
        try:
            result['receipt_pin'] = self._publish('CGROUP-EMERGENCY.json', result, terminal=True)
        except BaseException as exc:
            result['errors'].append({'type': type(exc).__name__, 'message': 'emergency evidence publication failed'})
            result['cleanup_complete'] = False
        return result

    def remove(self, provider_closure_pin):
        need(not self.emergency_attempted, 'no removal or gradeable proof after emergency cleanup')
        need(self.closed is not None and self.closed['complete'] and self.closure_pin is not None, 'closed counters retained before provider recovery')
        doc = _file(self.folder / 'PROVIDER_CLOSED.json', provider_closure_pin)
        need(doc['schema'] == 'smc_aggregate_provider_closure_v1' and doc['invocation_pin'] == self.invocation_pin and
             doc['source'] == self.source and doc['clock'] == self.clock and doc['controller_closure_pin'] == self.closure_pin and
             doc['recovery_cli_absent'] is True and set(doc['phases']) == set(self.scopes), 'exact post-provider closure')
        for phase, scope in self.scopes.items():
            row = doc['phases'][phase]
            need(row['request_pin'] == scope['request_pin'] and row['all_resources_closed'] is True, 'exact prepared phase recovered')
            if scope['producer'] is not None:
                need(row['producer_container_id'] == scope['producer']['event']['container_id'], 'original attached producer container identity')
            descriptor(row['ownership_pin'])
            receipt = _file(row['receipt_path'], row['receipt_pin'])
            need(receipt.get('phase_id') == phase and receipt.get('ownership_pin') == row['ownership_pin'],
                 'actual pinned provider phase ownership')
            if receipt.get('schema') == 'smc_aggregate_phase_receipt_v1':
                need(receipt.get('request_sha256') == scope['request_pin']['sha256'] and
                     receipt.get('all_native_resources_closed') is True and receipt.get('cli_reaped') is True,
                     'actual normal Provider resource closure')
            elif receipt.get('schema') == 'smc_aggregate_independent_phase_recovery_v1':
                need(receipt.get('request_pin') == scope['request_pin'] and
                     receipt.get('controller_closed_proof') == self.closure_pin and
                     receipt.get('all_resource_custody_closed') is True and receipt.get('all_namespaces_empty') is True,
                     'actual independent Provider recovery closure')
            else:
                need(False, 'known additive Provider closure schema')
        removed, errors = {}, []
        for phase, scope in self.scopes.items():
            try:
                self._tick(closing=True)
                self._controller_closed(self.closure_pin)
                observed = self._snapshot(scope)
                need(observed['empty'], 'scope still empty after provider closure')
                with os.scandir(scope['fd']) as entries:
                    need(not any(entry.is_dir(follow_symlinks=False) for entry in entries), 'provider removed every container subgroup')
                need(observed['counters'] == self.closed['scopes'][phase]['counters'], 'no late aggregate cost before removal')
                os.rmdir(scope['plan']['name'], dir_fd=self.root_fd)
                os.close(scope['fd'])
                scope['removed'] = True
                if scope['pidfd'] is not None:
                    os.close(scope['pidfd'])
                    scope['pidfd'] = None
                removed[phase] = True
            except BaseException as exc:
                removed[phase] = False
                errors.append({'phase_id': phase, 'type': type(exc).__name__, 'message': str(exc)[:256]})
        if all(removed.values()) and self.root_fd is not None:
            os.close(self.root_fd)
            self.root_fd = None
        return {'schema': 'smc_aggregate_scope_removal_v1', 'provider_closure_pin': provider_closure_pin,
                'scopes': removed, 'all_scopes_removed': all(removed.values()), 'errors': errors,
                'complete': all(removed.values()) and not errors and time.monotonic() < self.clock['deadline']}
