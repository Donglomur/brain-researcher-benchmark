"""Closed external roles; original campaign controller remains the finalizer.

No ledger is created here. Linux deployment and executable qualification are
external prerequisites; invented controls do not establish either one.
"""
import os
import signal
import socket
import stat
import struct
import time
import uuid
from pathlib import Path

CAPSULE = (
    'postscore_role_worker.py', 'model_provider_entry.py', 'n055/__init__.py',
    'n055/common.py', 'n055/budget.py', 'n055/journal.py', 'n055/process.py',
    'n055/cgroup.py', 'n055/native.py', 'n055/native_providers.py',
    'n055/resource_policy.py', 'n055/registry.py', 'n055/seals.py',
    'n055/postscore_role_host.py', 'n055/postscore_reserved.py',
    'n055/postscore_services.py',
)
RESOURCES = ('cpu_seconds', 'read_bytes', 'write_bytes', 'files',
             'stream_bytes', 'model_calls')


class RoleFailure(Exception):
    def __init__(self, original):
        self.original = original
        super().__init__('original postscore role unavailable; custody retained')


def publication_descriptor(publication, role):
    if not (publication['status'] == 'complete' and publication['closed'] and
            publication['expected_bytes'] == publication['observed_bytes']):
        raise ValueError('complete original publication required')
    return dict(path=publication['path'], bytes=publication['observed_bytes'],
                sha256=publication['sha256'], mode='0o600', role=role)


class KernelObserver:
    """Finite actual /proc and cgroup reads on the supplied original ledger."""
    def __init__(self, common, budget, carrier, deadline):
        self.common = common; self.budget = budget; self.carrier = carrier
        self.deadline = deadline; self.events = []; carrier.retain(self)

    def read(self, path):
        c = self.common; path = Path(path); body = bytearray(); fd = None
        event = dict(path=str(path), body_hex=None, returned_bytes=0, closed=False)
        self.events.append(event)
        try:
            self.budget.check('before kernel observation', self.deadline)
            self.budget.admit_read(16385)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            while len(body) <= 16384:
                part = os.read(fd, min(4096, 16385-len(body)))
                body.extend(part); event['body_hex'] = body.hex()
                event['returned_bytes'] = len(body); self.budget.read(len(part))
                if not part: break
            c.require(len(body) <= 16384, 'finite kernel record')
        except BaseException as error:
            self.carrier.fail(error, 'kernel-read'); raise
        finally:
            if fd is not None:
                try: os.close(fd); event['closed'] = True
                except BaseException as error:
                    self.budget.uncertain(str(path), 'managed_descriptor_closure', error)
                    self.carrier.fail(error, 'kernel-close'); raise
        self.budget.check('after kernel observation', self.deadline)
        return bytes(body).decode('ascii').strip()

    def membership(self, pid, leaf):
        c = self.common
        rows = self.read('/proc/%d/cgroup' % pid).splitlines()
        expected = '0::/' + str(Path(leaf).relative_to('/sys/fs/cgroup'))
        c.require(rows == [expected], 'actual PID belongs to exact unified leaf')
        members = self.read(Path(leaf)/'cgroup.procs').splitlines()
        c.require(str(pid) in members, 'actual PID present in selected leaf')
        return dict(pid=pid, cgroup=expected, members=members)


def literal_directory(c, path):
    p = Path(path)
    c.require(p.is_absolute() and p.is_dir() and
              not any(x.is_symlink() for x in (p, *p.parents)),
              'literal existing qualified directory')
    return p


def memory_components(c, controller_cap, role_cap, whole_cap, controller_peak, role_peak):
    for x in (controller_cap, role_cap, whole_cap): c.integer(x, 1)
    for x in (controller_peak, role_peak): c.integer(x)
    c.require(controller_cap + role_cap <= whole_cap, 'disjoint enforced cap sum')
    c.require(controller_peak <= controller_cap and role_peak <= role_cap,
              'observed component peaks obey enforced caps')
    return {
        'schema': 'neural055-disjoint-component-memory-v2',
        'controller_peak_bytes': controller_peak, 'controller_peak_kind': 'checkpoint',
        'role_peak_bytes': role_peak, 'role_peak_kind': 'closed_subtree_final',
        'component_peak_sum_upper_bound_bytes': controller_peak + role_peak,
        'component_peak_sum_scope': 'through_controller_checkpoint',
        'simultaneous_peak_bytes': None,
        'controller_cap_bytes': controller_cap, 'role_cap_bytes': role_cap,
        'enforced_lifetime_cap_sum_bytes': controller_cap + role_cap,
        'whole_limit_bytes': whole_cap,
        'later_controller_work_is_not_in_closed_role_measurement': True,
    }


class ControllerAdmission:
    def __init__(self, runtime, budget, journal, carrier, deployment):
        self.runtime = runtime; self.budget = budget; self.journal = journal
        self.carrier = carrier; self.deployment = deployment; self.c = runtime['common']
        c = self.c; carrier.retain(self); self.original = {}
        c.require(os.uname().sysname == 'Linux', 'actual Linux unified deployment')
        c.require(type(budget) is runtime['budget'].Budget and
                  type(journal) is runtime['journal'].Journal and type(carrier) is c.FailureCarrier and
                  journal.budget is budget and journal.carrier is carrier,
                  'same original controller owners')
        c.keys(deployment, ('schema', 'controller_leaf', 'delegated_parent',
            'controller_memory_bytes', 'role_memory_bytes', 'whole_memory_bytes',
            'controller_pids', 'role_pids', 'launcher', 'python', 'docker', 'dockerd',
            'daemon_data_roots', 'native_profile', 'operator_root', 'closure_reserve_seconds',
            'capsule_paths', 'controller_reserve'))
        c.require(deployment['schema'] == 'neural055-role-host-deployment-v2',
                  'explicit prospective role deployment')
        c.keys(deployment['controller_reserve'], (*RESOURCES, 'live_bytes'))
        for key, value in deployment['controller_reserve'].items():
            if key == 'cpu_seconds': c.finite(value, True)
            else: c.integer(value, 1)
        for key in ('controller_pids', 'role_pids'): c.integer(deployment[key], 1)
        c.finite(deployment['closure_reserve_seconds'], True)
        self.leaf = literal_directory(c, deployment['controller_leaf'])
        self.parent = literal_directory(c, deployment['delegated_parent'])
        c.require(self.leaf.parent == self.parent and
                  self.parent.is_relative_to('/sys/fs/cgroup'),
                  'literal controller leaf and delegated sibling parent')
        self.identity = c.stamp(self.leaf.lstat())[:2]
        self.parent_identity = c.stamp(self.parent.lstat())[:2]
        self.pid = os.getpid(); self.observer = KernelObserver(c, budget, carrier, budget.deadline)
        self.original['membership'] = self.observer.membership(self.pid, self.leaf)
        c.require(self.observer.read(self.leaf/'cgroup.procs').splitlines() == [str(self.pid)],
                  'controller admitted before descendants or campaign work')
        c.require(self.observer.read(self.parent/'cgroup.procs') == '', 'delegated parent empty')
        c.require({'cpu', 'memory', 'pids'} <= set(self.observer.read(
                  self.parent/'cgroup.subtree_control').split()), 'actual delegated controllers')
        self.checkpoint()
        self.original['admission'] = journal.json('POSTSCORE_CONTROLLER_ADMISSION.json', {
            'schema': 'neural055-controller-admission-v2', 'pid': self.pid,
            'leaf': str(self.leaf), 'leaf_identity': self.identity,
            'parent': str(self.parent), 'parent_identity': self.parent_identity,
            'actual_membership': self.original['membership'],
            'memory': self.original['latest_checkpoint'],
            'historical_preactivation_launch_requires_independent_qualification': True,
        })

    def checkpoint(self):
        c = self.c; d = self.deployment; o = self.observer
        c.require(os.getpid() == self.pid and c.stamp(self.leaf.lstat())[:2] == self.identity
                  and c.stamp(self.parent.lstat())[:2] == self.parent_identity,
                  'same current controller and group identities')
        o.membership(self.pid, self.leaf)
        limits = {'memory.max': str(d['controller_memory_bytes']), 'memory.swap.max': '0',
                  'pids.max': str(d['controller_pids']), 'cpu.max': '100000 100000'}
        observed = {k: o.read(self.leaf/k) for k in limits}
        c.require(observed == limits, 'actual selected controller enforced limits')
        c.require(o.read(self.leaf/'cgroup.subtree_control') == '', 'controller is process leaf')
        peak = o.read(self.leaf/'memory.peak'); c.require(peak.isdigit(), 'actual controller peak')
        value = memory_components(c, d['controller_memory_bytes'], d['role_memory_bytes'],
                                  d['whole_memory_bytes'], int(peak), 0)
        # Zero is an observed-role placeholder only here, before a role exists.
        value.pop('role_peak_bytes'); value.pop('component_peak_sum_upper_bound_bytes')
        value['role_peak_kind'] = 'not_yet_observed'
        self.original['latest_checkpoint'] = value
        self.original['latest_checkpoint_at'] = self.budget.clock()
        return int(peak)


def admit_controller(runtime, budget, journal, carrier, deployment):
    return ControllerAdmission(runtime, budget, journal, carrier, deployment)


def create_leaf(runtime, root, name, budget, deadline, memory, pids, owners):
    """Same accepted Cgroup controls; deliberately no subtree controllers here."""
    c = runtime['common']; group = runtime['cgroup'].Cgroup(root, name, budget, deadline)
    owners.append(group)  # Own it before mkdir or the first fallible kernel write.
    c.require(not group.path.exists(), 'fresh original process leaf')
    group.path.mkdir(); group.created = True
    s = group.path.lstat(); group.identity = (s.st_dev, s.st_ino)
    c.require(group.read('cgroup.procs') == '', 'new leaf empty')
    for key, value in (('memory.max', str(memory)), ('memory.swap.max', '0'),
                       ('pids.max', str(pids)), ('cpu.max', '100000 100000')):
        group.write(key, value)
    group.initial_cpu = group.cpu(); c.require(group.initial_cpu == 0, 'fresh leaf CPU')
    return group


class GatedProcess:
    """A direct owned child born in its leaf, released only after kernel joins.

    Child wait4 is evidence, not an additive Budget.physical charge: encompassing
    role cgroup CPU is the sole external CPU owner. Launcher helper CPU is charged
    normally by ProcessRunner, outside this child subtree.
    """
    def __init__(self, runtime, budget, journal, carrier, runner, ident,
                 launcher, leaf, argv, deadline, stream_cap, socket_path, env):
        self.runtime = runtime; self.c = runtime['common']; self.budget = budget
        self.journal = journal; self.carrier = carrier; self.runner = runner
        self.ident = ident; self.deadline = deadline; self.stream_cap = stream_cap
        self.leaf = Path(leaf); self.argv = list(argv); self.launcher = launcher
        self.socket_path = Path(socket_path); self.env = env
        self.server = self.conn = None; self.pid = None; self.body = bytearray()
        self.original = dict(id=ident, pid=None, origin=budget.clock(), end=None,
            argv=list(argv), natural=False, reaped=False, group_absent=False,
            returncode=None, cpu_seconds=None, activated=False, stream_eof=False,
            listener_closed=False, stream_closed=False, socket_removed=False,
            forced=False, failure_types=[], membership=None,
            cpu_is_nonadditive_breakdown=True)
        self.closed = False; carrier.retain(self)

    def start(self):
        c = self.c
        c.require(not self.socket_path.exists() and len(str(self.socket_path).encode()) < 108,
                  'fresh bounded Linux Unix gate path')
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.socket_path)); self.server.listen(1)
        self.server.settimeout(max(.001, self.deadline-self.budget.clock()))
        observer = KernelObserver(c, self.budget, self.carrier, self.deadline)
        children_path = '/proc/self/task/%d/children' % os.getpid()
        before_children = set(observer.read(children_path).split())
        launch_error = None; result = None
        try:
            result = self.runner.run(self.ident+'-launcher', [self.launcher, str(self.leaf),
                 str(self.socket_path), *self.argv], self.deadline, 4096, env=self.env)
        except BaseException as error:
            launch_error = error
            result = getattr(error, 'observation', None)
        # Recover the actual direct child even if helper stdout publication failed.
        # The helper has already been reaped by ProcessRunner; preexisting children
        # cannot be adopted or killed through this difference.
        added = set(observer.read(children_path).split())-before_children
        c.require(len(added) <= 1, 'one source-owned clone child')
        if added:
            self.pid = int(next(iter(added))); self.original['pid'] = self.pid
            self.original['membership'] = observer.membership(self.pid, self.leaf)
        if launch_error is not None: raise launch_error
        raw = bytes(result.stdout).strip()
        c.require(raw.isdigit() and int(raw) > 1 and int(raw) == self.pid,
                  'actual launcher and direct-child PID agree')
        self.conn, _ = self.server.accept()
        pid, uid, gid = struct.unpack('3i', self.conn.getsockopt(socket.SOL_SOCKET,
                                                               socket.SO_PEERCRED, 12))
        c.require(pid == self.pid and uid == os.getuid() and gid == os.getgid(),
                  'actual gated child socket peer')
        self.original['membership'] = observer.membership(self.pid, self.leaf)
        c.require(os.getpgid(self.pid) == self.pid, 'original owned process group')
        self.conn.setblocking(False)
        self.budget.check('before gated activation', self.deadline)
        c.require(self.conn.send(b'G') == 1, 'exact one-byte activation')
        self.original['activated'] = True
        self.server.close(); self.server = None; self.original['listener_closed'] = True
        return self

    def poll(self):
        if self.conn is not None and not self.original['stream_eof']:
            while True:
                try: part = self.conn.recv(65536)
                except BlockingIOError: break
                if not part: self.original['stream_eof'] = True; break
                self.body.extend(part); self.budget.stream(len(part))
                self.c.require(len(self.body) <= self.stream_cap, 'bounded original role stream')
        if self.pid is not None and not self.original['reaped']:
            pid, status, ru = os.wait4(self.pid, os.WNOHANG)
            if pid:
                self.original.update(reaped=True, returncode=os.waitstatus_to_exitcode(status),
                    cpu_seconds=ru.ru_utime+ru.ru_stime,
                    natural=not self.original['forced'])
        return self.original['reaped'] and self.original['stream_eof']

    def wait(self, poll_service=None, shutdown=False):
        if shutdown and self.pid is not None and not self.original['reaped']:
            # Graceful owned service shutdown is protocol retirement, not a kill fallback.
            os.kill(self.pid, signal.SIGTERM); self.original['requested_shutdown'] = 'SIGTERM'
        while not self.poll():
            self.budget.check('owned child wait', self.deadline)
            if poll_service is not None: poll_service(self.deadline)
            time.sleep(.005)
        self.original['group_absent'] = self.runtime['process'].absent(self.pid)
        self.c.require(self.original['returncode'] == 0 and self.original['natural'] and
                       self.original['group_absent'], 'natural zero and original group absent')
        self.close_streams(); self.original['end'] = self.budget.clock()
        self.closed = True
        return self.original

    def abort(self):
        self.original['forced'] = True
        first = None
        def retain(error, stage, quantity):
            nonlocal first
            if first is None: first = error
            self.carrier.fail(error, stage)
            self.budget.uncertain(self.ident, quantity, error)
        if self.pid is not None and not self.original['reaped']:
            try: os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            except BaseException as error: retain(error, 'gated-abort-kill', 'owned_group_termination')
            try:
                while self.budget.clock() < self.deadline and not self.poll(): time.sleep(.005)
            except BaseException as error: retain(error, 'gated-abort-poll', 'owned_child_retirement')
            # A failed stream read must not skip an independent reap observation.
            if not self.original['reaped']:
                try:
                    pid, status, ru = os.wait4(self.pid, os.WNOHANG)
                    if pid:
                        self.original.update(reaped=True, returncode=os.waitstatus_to_exitcode(status),
                            cpu_seconds=ru.ru_utime+ru.ru_stime, natural=False)
                except BaseException as error: retain(error, 'gated-abort-reap', 'owned_child_reap')
        try: self.close_streams()
        except BaseException as error:
            if first is None: first = error
        if self.pid is not None:
            try: self.original['group_absent'] = self.runtime['process'].absent(self.pid)
            except BaseException as error: retain(error, 'gated-abort-group', 'owned_group_absence')
            if not self.original['reaped']:
                self.budget.uncertain(self.ident, 'owned_child_reap')
            if not self.original['group_absent']:
                self.budget.uncertain(self.ident, 'owned_group_absence')
        try: self.original['end'] = self.budget.clock()
        except BaseException as error: retain(error, 'gated-abort-clock', 'owned_retirement_clock')
        if first is not None: raise first

    def close_streams(self):
        first = None
        for attr, flag in (('server', 'listener_closed'), ('conn', 'stream_closed')):
            obj = getattr(self, attr)
            if obj is not None:
                try: obj.close(); self.original[flag] = True; setattr(self, attr, None)
                except BaseException as error:
                    if first is None: first = error
                    self.budget.uncertain(self.ident+':'+attr, 'managed_descriptor_closure', error)
                    self.carrier.fail(error, 'gated-stream-close')
        # Every owned cleanup is attempted even if an earlier handle failed.
        try:
            try: current = self.socket_path.lstat()
            except FileNotFoundError: current = None
            if current is not None:
                self.c.require(stat.S_ISSOCK(current.st_mode), 'only owned gate socket')
                self.socket_path.unlink()
            self.original['socket_removed'] = True
        except BaseException as error:
            if first is None: first = error
            self.budget.uncertain(self.ident+':gate', 'owned_socket_retirement', error)
            self.carrier.fail(error, 'gated-socket-retirement')
        if first is not None: raise first


class RoleHost:
    def __init__(self, runtime, budget, journal, carrier, source, controller,
                 deployment, *, authority):
        self.runtime = dict(runtime); self.c = runtime['common']; self.budget = budget
        self.journal = journal; self.carrier = carrier; self.source = source
        self.controller = controller; self.deployment = self.c.parse(self.c.encoded(deployment))
        self.authority = authority; self.originals = []; self.used = set()
        self.c.require(type(controller) is ControllerAdmission and controller.budget is budget
            and controller.journal is journal and controller.carrier is carrier
            and source.budget is budget and authority.budget is budget,
            'one actual campaign controller, source and authority lifetime')
        self.c.require(type(source) is runtime['source'].Sources and
                       type(authority) is runtime['authority'].Authority,
                       'actual captured source and original external authority types')
        self.c.require(self.deployment == controller.deployment, 'same admitted deployment')
        self.runner = runtime['process'].ProcessRunner(budget, journal, carrier)
        carrier.retain(self)

    def _binary(self, key):
        c = self.c; d = self.deployment[key]
        c.keys(d, ('path', 'bytes', 'sha256'))
        p = Path(d['path']); c.require(p.is_absolute(), 'explicit executable')
        c.require(self.runtime['seals'].file_identity(p, self.budget, d['bytes']) ==
                  {'bytes': d['bytes'], 'sha256': d['sha256']}, 'exact qualified executable')
        c.require(os.access(p, os.X_OK), 'selected executable permission')
        return str(p)

    def _capsule(self, ident):
        c = self.c; base = self.journal.root/ident/'capsule'; base.mkdir(mode=0o700)
        (base/'n055').mkdir(mode=0o700); descriptors = []
        c.require(tuple(self.deployment['capsule_paths']) == CAPSULE, 'fixed worker allowlist')
        for name in CAPSULE:
            body = self.source.bodies[name]
            rec = self.journal.write(str((base/name).relative_to(self.journal.root)), body)
            os.chmod(base/name, 0o444)
            descriptors.append(dict(path=name, bytes=rec['observed_bytes'], sha256=rec['sha256'],
                                    mode='0o444', role='runtime_source'))
        os.chmod(base/'n055', 0o555); os.chmod(base, 0o555)
        return base, descriptors

    def _events(self, ident, label, events):
        """All events, finite individually bounded chunks; no scope truncation."""
        chunks = []; current = []; index = 0
        for event in events:
            self.c.require(len(self.c.encoded(event)) <= 65536, 'single finite kernel event')
            if current and len(self.c.encoded(current+[event])) > 65536:
                record = self.journal.json(ident+'/'+label+'-'+str(index)+'.json', current)
                chunks.append(publication_descriptor(record, 'original_kernel_observation'))
                current = []; index += 1
            current.append(event)
        if current:
            record = self.journal.json(ident+'/'+label+'-'+str(index)+'.json', current)
            chunks.append(publication_descriptor(record, 'original_kernel_observation'))
        return chunks

    def run(self, request, role_spec, prepared_payload):
        c = self.c; b = self.budget; d = self.deployment
        ident = 'postscore-role-'+uuid.uuid4().hex
        original = dict(id=ident, request=request, origin=b.clock(), end=None,
            complete=False, costs={k: None for k in RESOURCES}, groups=[], child=None,
            frame=None, result=None, failures=[], memory=None, costs_complete=False,
            unknown_quantities=list(RESOURCES), known_lower_bounds={}, usage=None)
        self.originals.append(original); self.carrier.retain(original)
        group = worker = daemon = providers = child = None; first = None
        first_controller_process = len(self.runner.originals)
        deadline = min(b.deadline, request['postscore_deadline'])
        try:
            b.admit('before original postscore role', deadline)
            c.require(request['schema'] == 'neural055-postscore-operation-request-v2' and
                      request['source'] == self.source.identity and
                      request['original_origin'] == b.origin and
                      request['original_deadline'] == b.deadline,
                      'same original request/source/lifetime')
            request_pin = c.sha(c.encoded(request)); c.require(request_pin not in self.used,
                                                            'one attempt per reserved request')
            self.used.add(request_pin)
            self.controller.checkpoint()
            c.require(request['memory_limit_bytes'] == d['whole_memory_bytes'],
                      'explicit role/control memory partition of request whole bound')
            c.require(role_spec['kind'] == 'local_transformers_text_v1', 'explicit local role model')
            subject = dict(source=self.source.identity, provider=role_spec['id'], kind=role_spec['kind'],
                config=role_spec['config'], model_manifest=role_spec['model_manifest'],
                native_profile=d['native_profile']['deployment_identity'],
                resource_policy=b.resource_policy, same_original_cgroup=True)
            qualification = self.authority.verify(role_spec['qualification'],
                                                  'trusted_provider_source_and_runtime', subject)
            binaries = {key: self._binary(key) for key in ('launcher', 'python', 'docker', 'dockerd')}
            base = self.journal.root/ident; base.mkdir(mode=0o700)
            capsule, capsule_files = self._capsule(ident)
            group = self.runtime['cgroup'].Cgroup(d['delegated_parent'], ident, b, deadline)
            original['groups'].append(group); original['role_scope_origin'] = b.clock()
            group.create(d['role_memory_bytes'], d['role_pids'])
            original['role_scope_created_observed_at'] = b.clock()
            worker = create_leaf(self.runtime, group.path, 'worker', b, deadline,
                                 d['role_memory_bytes'], d['role_pids'], original['groups'])
            daemon = create_leaf(self.runtime, group.path, 'daemon', b, deadline,
                                 d['role_memory_bytes'], d['role_pids'], original['groups'])
            providers = self.runtime['cgroup'].Cgroup(group.path, 'providers', b, deadline)
            original['groups'].append(providers); providers.create(d['role_memory_bytes'], d['role_pids'])
            reserved_bytes, reserved_files = b.reserved(); capacity_bytes, capacity_files = b.capacity()
            reserve = d['controller_reserve']
            limits = {}
            for key in RESOURCES:
                used = b.cpu+b.own_cpu() if key == 'cpu_seconds' else getattr(b, key)
                headroom = b.limits[key]-used-reserve[key]
                if key == 'write_bytes': headroom -= reserved_bytes
                if key == 'files': headroom -= reserved_files+capacity_files
                limits[key] = min(request['maximum_original_operation_resources'][key], headroom)
            limits.update(wall_seconds=deadline-b.origin,
                live_bytes=b.limits['live_bytes']-b.live_bytes-reserved_bytes-capacity_bytes-reserve['live_bytes'])
            # No reset: the worker envelope is an external component capped by the
            # original request's remaining allowance, with the same absolute origin.
            boot = dict(schema='neural055-role-worker-bootstrap-v2', request=request,
                role_spec=role_spec, prepared_payload=prepared_payload, limits=limits,
                deployment=d, binaries=binaries, capsule_root=str(capsule),
                capsule_files=capsule_files, source_identity=self.source.identity,
                resource_policy=b.resource_policy, resource_definition=b.resource_definition,
                journal_root=str(base/'work'), role_parent=str(group.path),
                daemon_leaf=str(daemon.path), provider_parent=str(providers.path),
                provider_initial_cpu=providers.initial_cpu, provider_qualification=qualification,
                role_id=ident, actual_deadline=deadline)
            # Bootstrap itself is controller publication. A monotone finite size
            # bound is computed before writing; no nominal 8 MiB cost is charged.
            allocation = dict(controller_point=b.cost_point(), existing_reserved_bytes=reserved_bytes,
                existing_reserved_files=reserved_files, existing_capacity_bytes=capacity_bytes,
                existing_capacity_files=capacity_files, controller_reserve=dict(reserve),
                bootstrap_publication_upper_bound=0)
            boot['component_allocation'] = allocation; original['component_allocation'] = allocation
            base_write, base_live = limits['write_bytes'], limits['live_bytes']; limits['files'] -= 1
            for _ in range(16):
                upper = allocation['bootstrap_publication_upper_bound']
                limits['write_bytes'] = base_write-upper; limits['live_bytes'] = base_live-upper
                size = len(c.encoded(boot))
                if size <= upper: break
                allocation['bootstrap_publication_upper_bound'] = size
            else: c.require(False, 'finite bootstrap size bound converged before dispatch')
            for key, value in limits.items():
                if key in ('cpu_seconds', 'wall_seconds'): c.finite(value, True)
                else: c.integer(value, 1)
            c.require(len(c.encoded(boot)) <= 8388608, 'complete bootstrap transport bound')
            boot_record = self.journal.json(ident+'/BOOT.json', boot)
            # Work directory is deliberately absent: its Journal creates it.
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
                   'PYTHONHASHSEED': '0', 'N055_ROLE_WORKDIR': str(base)}
            child = GatedProcess(self.runtime, b, self.journal, self.carrier, self.runner,
                ident, binaries['launcher'], worker.path,
                [binaries['python'], '-I', '-B', str(capsule/'postscore_role_worker.py'),
                 str(self.journal.root/boot_record['path']), boot_record['sha256']],
                deadline, 1048576, base/'worker.sock', env)
            original['child'] = child; child.start()
            def observe(end):
                b.check('whole original role observer', end)
                cpu = group.sample()
                c.require(b.cpu+b.own_cpu()+cpu <= b.limits['cpu_seconds'],
                          'controller plus whole role CPU inside original budget')
            child.wait(observe)
            # Stream is sent only after result, native retirement, and role records.
            frame = c.parse(bytes(child.body)); original['frame'] = frame
            c.require(frame['schema'] == 'neural055-closed-role-worker-frame-v2' and
                      frame['request_sha256'] == request_pin and frame['complete'],
                      'exact complete original worker frame')
            # Every owned subgroup is empty and removed before the enclosing final sample.
            for item in (providers, daemon, worker): item.finish()
            closed = group.finish(); c.require(closed['complete'], 'closed whole role subtree')
            original['role_scope_closed_at'] = b.clock()
            original['costs'] = dict(frame['costs']); original['costs']['cpu_seconds'] = closed['cpu_seconds']
            c.require(set(original['costs']) == set(RESOURCES), 'exact external cost vector')
            for key, value in original['costs'].items():
                c.finite(value); c.require(value >= 0, 'known external resource')
                if key != 'cpu_seconds': c.integer(value)
            original.update(costs_complete=True, unknown_quantities=[], usage=frame['usage'])
            peak = self.controller.checkpoint()
            original['memory'] = memory_components(c, d['controller_memory_bytes'],
                d['role_memory_bytes'], d['whole_memory_bytes'], peak, closed['memory_peak_bytes'])
            result = dict(frame['result']); result['path'] = ident+'/work/'+result['path']
            body = c.capture(self.journal.root, result, b, 16777216)
            original['result'] = result
            process_descriptor = publication_descriptor(self.journal.json(
                ident+'/WORKER_PROCESS.json', child.original), 'original_process_receipt')
            process_descriptors = [process_descriptor]
            for desc in frame['original_processes']:
                translated = dict(desc); translated['path'] = ident+'/work/'+translated['path']
                # Actual bytes captured on controller ledger, not charged again as role work.
                receipt = c.parse(c.capture(self.journal.root, translated, b, 4194304))
                c.require(receipt['natural'] and receipt['reaped'] and receipt['group_absent'],
                          'all original role processes naturally closed')
                process_descriptors.append(translated)
            evidence = dict(frame['role_evidence']); evidence['path'] = ident+'/work/'+evidence['path']
            c.capture(self.journal.root, evidence, b, 4194304)
            census = []
            for index, item in enumerate(original['groups']):
                census.append(dict(path=str(item.path), identity=item.identity, created=item.created,
                    closed=item.closed, final={k: v for k, v in item.final.items() if k != 'original_events'},
                    kernel_events=self._events(ident, 'GROUP-'+str(index), item.events)))
            original['end'] = original['role_scope_closed_at']; original['complete'] = True
            controller_processes = [publication_descriptor(item.publication, 'original_process_receipt')
                                    for item in self.runner.originals[first_controller_process:]]
            role_observation = publication_descriptor(self.journal.json(ident+'/ROLE_OBSERVATION.json', {
                'schema': 'neural055-closed-role-observation-v2', 'request_sha256': request_pin,
                'source': self.source.identity, 'role_owner': ident, 'origin': original['origin'],
                'role_child_end': child.original['end'], 'closed_groups': census,
                'original_processes': process_descriptors, 'provider_evidence': evidence,
                'controller_processes_nonadditive_to_role': controller_processes,
                'usage': frame['usage'], 'costs': original['costs'], 'memory': original['memory'],
                'component_allocation': original['component_allocation'],
                'controller_leaf': str(self.controller.leaf),
                'memory_observation': {
                    'role_scope_origin': original['role_scope_origin'],
                    'role_scope_created_observed_at': original['role_scope_created_observed_at'],
                    'role_scope_closed_at': original['role_scope_closed_at'],
                    'controller_checkpoint_at': self.controller.original['latest_checkpoint_at'],
                    'controller_peak_scope': 'preexisting_partition_lifetime_through_checkpoint',
                    'controller_partition_created_at': None,
                    'controller_peak_is_conservative_for_current_operation': True,
                },
                'controller_kernel_events': self._events(ident, 'CONTROLLER', self.controller.observer.events),
                'closed_role_end': original['end'], 'closure_observation_end': b.clock(),
                'own_publication_is_continuing_original_controller_work': True,
                'qualification_not_created_here': True,
            }), 'original_role_observation')
            original['role_observation'] = role_observation
            return dict(schema='neural055-closed-role-result-v2', request_sha256=request_pin,
                result=result, result_bytes=body, usage=frame['usage'],
                original_processes=process_descriptors, costs=original['costs'],
                memory=original['memory'], origin=original['role_scope_origin'], end=original['end'],
                complete=True, costs_complete=True, unknown_quantities=[], known_lower_bounds={},
                role_observation=role_observation, original=original)
        except BaseException as error:
            first = error; original['failures'].append(error); self.carrier.fail(error, 'role-host')
        finally:
            if first is not None:
                # Containment never manufactures natural/complete outcomes.
                for item in (group,):
                    if item is not None and item.created and not item.closed:
                        try: item.emergency_kill()
                        except BaseException as error: original['failures'].append(error); self.carrier.fail(error, 'role-kill')
                if child is not None:
                    try: child.abort()
                    except BaseException as error: original['failures'].append(error); self.carrier.fail(error, 'role-abort')
                for item in reversed(original['groups']):
                    if item is not None and item.created and not item.closed:
                        try: item.finish()
                        except BaseException as error: original['failures'].append(error); self.carrier.fail(error, 'role-final-observation')
                if child is not None and child.body:
                    try:
                        frame = c.parse(bytes(child.body))
                        c.require(frame['schema'] == 'neural055-closed-role-worker-frame-v2' and
                            frame['request_sha256'] == c.sha(c.encoded(request)), 'same partial original frame')
                        original['frame'] = frame; original['usage'] = frame.get('usage')
                        for key in RESOURCES:
                            value = frame['costs'][key]
                            if value is not None:
                                c.finite(value); c.require(value >= 0, 'actual nonnegative partial cost')
                                if key != 'cpu_seconds': c.integer(value)
                                original['costs'][key] = value
                        original['known_lower_bounds'].update(frame.get('known_lower_bounds', {}))
                    except BaseException as error:
                        original['failures'].append(error); self.carrier.fail(error, 'partial-frame-capture')
                if group is not None:
                    if group.final is not None and group.final.get('cpu_complete'):
                        original['costs']['cpu_seconds'] = group.final['cpu_seconds']
                    elif group.max_cpu is not None and group.initial_cpu is not None:
                        original['known_lower_bounds']['cpu_seconds'] = group.max_cpu-group.initial_cpu
                original['unknown_quantities'] = [k for k in RESOURCES if original['costs'][k] is None]
                original['costs_complete'] = not original['unknown_quantities']
                original['end'] = original.get('role_scope_closed_at', b.clock())
        raise RoleFailure(original) from first
