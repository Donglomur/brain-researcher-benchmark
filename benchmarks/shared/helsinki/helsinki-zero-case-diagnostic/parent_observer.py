"""Prospective Helsinki Linux/cgroupfs parent observer; no runtime admission.

Only a trusted, exclusively delegated cgroup-v2 subtree is supported. This
observer never migrates/kills tasks, changes the daemon, or resets counters.
Generated fixtures cannot establish kernel semantics or platform qualification.
"""
from dataclasses import dataclass
import ctypes
import hashlib
import os
from pathlib import Path
import platform
import re
import stat
import sys

from common import need, encode, write, plain
from participant_policy import (PROFILE, validate_policy, validate_kernel_evidence,
                                _counter_table)

SCHEMA = 'helsinki_persistent_parent_observer_v1'
MOUNT = '/sys/fs/cgroup'
MAGIC = 0x63677270
PROC_MAGIC = 0x9fa0
CONTROLLERS = {'cpu', 'memory', 'pids'}
CPU_KEYS = {'usage_usec', 'user_usec', 'system_usec', 'nr_periods',
            'nr_throttled', 'throttled_usec', 'nr_bursts', 'burst_usec'}
_TICKET = object()


def decimal(text):
    need(type(text) is str and re.fullmatch(r'[0-9]{1,20}\n', text) is not None,
         'literal_unsigned_kernel_counter')
    return int(text)


def table(text, required, allowed):
    rows = _counter_table(text, allowed, 'literal_kernel_table')
    need(required <= set(rows), 'complete_required_kernel_table')
    return rows


def filesystem_magic(fd):
    """Linux LP64 x86_64/aarch64 libc fstatfs, first fsword of oversized buffer.

    This restricted ABI must be included in the future actual runtime review.
    No dynamic library is loaded until an explicitly selected Linux call.
    """
    need(sys.platform == 'linux' and platform.machine() in ('x86_64', 'aarch64')
         and ctypes.sizeof(ctypes.c_long) == 8, 'selected_Linux_LP64_ABI')
    libc = ctypes.CDLL(None, use_errno=True)
    function = libc.fstatfs
    function.argtypes = (ctypes.c_int, ctypes.c_void_p)
    function.restype = ctypes.c_int
    buffer = (ctypes.c_long * 32)()
    if function(fd, ctypes.byref(buffer)) != 0:
        raise OSError(ctypes.get_errno(), 'fstatfs')
    return buffer[0]


def open_directory(path):
    """Reject symlinks in every path component, not just the final name."""
    p = Path(path)
    need(p.is_absolute() and str(p) == str(path) and '..' not in p.parts,
         'canonical_absolute_directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in p.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                          os.O_CLOEXEC, dir_fd=fd)
            old = fd
            fd = nxt
            os.close(old)
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_at(directory, name, budget, cap=8192):
    need(type(name) is str and '/' not in name and name not in ('.', '..'),
         'one_kernel_basename')
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                 os.O_CLOEXEC, dir_fd=directory)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), 'kernel_regular_interface')
        budget.charge_read(cap + 1)
        body = os.read(fd, cap + 1)
        budget.reads -= cap + 1 - len(body)
        need(len(body) <= cap, 'bounded_kernel_interface')
        # proc/kernfs reads may be short; one additional bounded read verifies EOF.
        budget.charge_read(1)
        extra = os.read(fd, 1)
        budget.reads -= 1 - len(extra)
        need(not extra, 'complete_kernel_interface')
        return body.decode('ascii')
    finally:
        os.close(fd)


def mount_record(text, expected_id, device):
    rows = []
    for line in text.splitlines():
        fields = line.split(' ')
        need(' - ' in line and len(fields) >= 10, 'mountinfo_shape')
        split = fields.index('-')
        if fields[4] == MOUNT:
            need(split >= 6 and len(fields) == split + 4, 'cgroup_mountinfo_shape')
            rows.append(fields)
        elif fields[4].startswith(MOUNT + '/'):
            need(False, 'no_overmounted_cgroup_subtree')
    need(len(rows) == 1, 'one_visible_cgroup_mount')
    f = rows[0]; split = f.index('-')
    need(f[0] == str(expected_id) and f[2] == f'{os.major(device)}:{os.minor(device)}'
         and f[3] == '/' and f[split + 1] == 'cgroup2' and
         'rw' in f[5].split(','), 'exact_full_hierarchy_mount')
    return ' '.join(f) + '\n'


def host_binding(provision, budget):
    """Observe this host only; same-host daemon truth remains a reviewed operand."""
    need(sys.platform == 'linux' and os.uname().release == provision['kernel_release'],
         'selected_Linux_kernel_release')
    proc = open_directory('/proc')
    try:
        need(filesystem_magic(proc) == PROC_MAGIC, 'actual_procfs')
        boot_dir = open_directory('/proc/sys/kernel/random')
        try:
            need(filesystem_magic(boot_dir) == PROC_MAGIC, 'actual_boot_procfs')
            boot = read_at(boot_dir, 'boot_id', budget, 64)
        finally:
            os.close(boot_dir)
        need(boot == provision['boot_id'] + '\n', 'same_selected_boot')
        # /proc/self is a kernel-generated symlink, used only at this fixed path.
        own = os.open('/proc/self', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            need(filesystem_magic(own) == PROC_MAGIC, 'actual_self_procfs')
            info = read_at(own, 'mountinfo', budget, 262144)
        finally:
            os.close(own)
        namespace = os.stat('/proc/self/ns/cgroup').st_ino
        need(namespace == provision['cgroup_namespace_inode'], 'selected_cgroup_namespace')
        return boot, info, namespace
    finally:
        os.close(proc)


def identity(fd):
    s = os.fstat(fd)
    need(stat.S_ISDIR(s.st_mode), 'owned_cgroup_directory')
    return (s.st_dev, s.st_ino)


def children(fd):
    names = []
    with os.scandir(fd) as entries:
        for index, entry in enumerate(entries):
            need(index < 128, 'finite_owned_cgroup_namespace')
            need(not entry.is_symlink(), 'no_cgroup_alias')
            if entry.is_dir(follow_symlinks=False):
                names.append(entry.name)
    return sorted(names)


@dataclass
class ParentTicket:
    name: str
    image: str
    path: str
    leaf: str
    delegation_fd: int
    parent_fd: int
    parent_identity: tuple
    token: object
    cid: object = None
    captured: object = None
    closed: bool = False


class ParentObserver:
    """Serial per-case parent lifetime; source-compatible original three hooks.

    prepare_parent is an explicit additional pre-create operation used only by
    the sibling participant_container successor. It does not change old routes.
    """
    def __init__(self, *, provision, policy, budget, evidence_root):
        validate_policy(policy)
        required = {'schema', 'boot_id', 'kernel_release', 'mount_id',
                    'cgroup_namespace_inode', 'delegation_path', 'delegation_device',
                    'delegation_inode', 'daemon_id', 'daemon_version', 'cgroup_driver',
                    'cgroup_version'}
        need(type(provision) is dict and set(provision) == required and
             provision['schema'] == SCHEMA and provision['cgroup_driver'] == 'cgroupfs'
             and provision['cgroup_version'] == '2', 'explicit_cgroupfs_v2_provision')
        need(re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',
                          provision['boot_id']) is not None, 'literal_boot_UUID')
        need(all(type(provision[k]) is int and provision[k] > 0 for k in
             ('mount_id', 'cgroup_namespace_inode', 'delegation_inode')) and
             type(provision['delegation_device']) is int and provision['delegation_device'] >= 0,
             'exact_integer_host_identities')
        need(all(type(provision[k]) is str and 0 < len(provision[k]) <= 256 and
             all(32 <= ord(c) < 127 for c in provision[k]) for k in
             ('daemon_id', 'daemon_version', 'kernel_release')), 'selected_daemon_kernel_names')
        path = provision['delegation_path']
        need(type(path) is str and path.startswith(MOUNT + '/') and
             re.fullmatch(r'/[A-Za-z0-9_./-]+', path) is not None and
             str(Path(path)) == path and '..' not in Path(path).parts,
             'explicit_nonroot_delegation')
        self.provision = dict(provision); self.policy = dict(policy)
        self.budget = budget; self.evidence_root = plain(evidence_root)
        need(self.evidence_root.is_dir() and not self.evidence_root.is_symlink(),
             'owner_evidence_directory_exists')
        self.active = None; self.failed = False

    def _persist(self, ticket, phase, value):
        return write(self.evidence_root / (ticket.name + '.' + phase + '.json'),
                     encode(value), self.budget)

    def _host(self):
        boot, info, namespace = host_binding(self.provision, self.budget)
        return {'boot_id': boot.rstrip('\n'), 'cgroup_namespace_inode': namespace,
                'mountinfo': mount_record(info, self.provision['mount_id'],
                                          self.provision['delegation_device'])}

    def _require(self, ticket):
        need(type(ticket) is ParentTicket and ticket is self.active and
             ticket.token is _TICKET and not ticket.closed, 'one_owned_parent_ticket')
        need(identity(ticket.delegation_fd) == (self.provision['delegation_device'],
             self.provision['delegation_inode']) and
             identity(ticket.parent_fd) == ticket.parent_identity,
             'retained_parent_descriptor_identity')
        current = os.stat(ticket.leaf, dir_fd=ticket.delegation_fd, follow_symlinks=False)
        need(stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) ==
             ticket.parent_identity, 'unchanged_owned_parent_name')
        need(filesystem_magic(ticket.parent_fd) == MAGIC, 'actual_cgroup2_parent')
        return self._host()

    def _snapshot(self, ticket):
        host = self._require(ticket)
        rows = {}
        for name in ('cpu.stat', 'memory.peak', 'cgroup.events', 'cgroup.procs',
                     'cgroup.type', 'cgroup.stat', 'cgroup.subtree_control'):
            rows[name] = read_at(ticket.parent_fd, name, self.budget)
        rows['children'] = children(ticket.parent_fd)
        rows['host'] = host
        return rows

    def _empty(self, snapshot, *, zero=False, no_children=False):
        cpu = table(snapshot['cpu.stat'], {'usage_usec', 'user_usec', 'system_usec'}, CPU_KEYS)
        peak = decimal(snapshot['memory.peak'])
        events = table(snapshot['cgroup.events'], {'populated', 'frozen'}, {'populated', 'frozen'})
        counts = table(snapshot['cgroup.stat'], {'nr_descendants', 'nr_dying_descendants'},
                       {'nr_descendants', 'nr_dying_descendants'})
        need(events == {'populated': 0, 'frozen': 0} and snapshot['cgroup.procs'] == ''
             and snapshot['cgroup.type'] == 'domain\n' and counts['nr_dying_descendants'] == 0,
             'empty_domain_no_pending_dying_cgroups')
        need(counts['nr_descendants'] == len(snapshot['children']), 'no_nested_unaccounted_cgroups')
        if no_children:
            need(not snapshot['children'], 'no_remaining_child_cgroups')
        if zero:
            need(all(v == 0 for v in cpu.values()) and peak == 0, 'genuinely_zero_initial_counters')
        return cpu, peak

    def prepare_parent(self, *, name, image, daemon_info):
        need(not self.failed and self.active is None and re.fullmatch(
             r'helsinki-program-[0-9a-f]{24}', name) is not None and
             image == self.policy['image'], 'fresh_exact_case_parent')
        p = self.provision
        need(type(daemon_info) is dict and all(daemon_info.get(k) == v for k, v in
             {'ID': p['daemon_id'], 'ServerVersion': p['daemon_version'],
              'KernelVersion': p['kernel_release'], 'OSType': 'linux',
              'CgroupDriver': 'cgroupfs', 'CgroupVersion': '2'}.items()),
             'selected_same_host_cgroupfs_daemon_info')
        self._host()
        delegation = None; parent = None; ticket = None; created = False
        try:
            write(self.evidence_root / (name + '.intent.json'), encode({
                'schema': SCHEMA, 'name': name, 'image': image,
                'provision': self.provision, 'operation': 'fresh_parent_mkdir',
                'existing_parent_adoption': False}), self.budget)
            delegation = open_directory(p['delegation_path'])
            need(filesystem_magic(delegation) == MAGIC and identity(delegation) ==
                 (p['delegation_device'], p['delegation_inode']), 'selected_delegation_identity')
            available = set(read_at(delegation, 'cgroup.subtree_control', self.budget).split())
            need(CONTROLLERS <= available, 'preprovisioned_parent_controllers')
            os.mkdir(name, 0o700, dir_fd=delegation); created = True
            parent = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                             os.O_CLOEXEC, dir_fd=delegation)
            ticket = ParentTicket(name, image, p['delegation_path'][len(MOUNT):] + '/' + name,
                                  name, delegation, parent, identity(parent), _TICKET)
            self.active = ticket
            initial = self._snapshot(ticket)
            self._empty(initial, zero=True, no_children=True)
            need(initial['cgroup.subtree_control'] == '\n' or
                 initial['cgroup.subtree_control'] == '', 'new_parent_no_enabled_children')
            controllers = set(read_at(parent, 'cgroup.controllers', self.budget).split())
            need(CONTROLLERS <= controllers, 'required_delegated_controllers')
            fd = os.open('cgroup.subtree_control', os.O_WRONLY | os.O_NOFOLLOW |
                         os.O_CLOEXEC, dir_fd=parent)
            try:
                body = b'+cpu +memory +pids\n'
                self.budget.reserve_write(len(body))
                need(os.write(fd, body) == len(body), 'complete_owned_controller_write')
            finally:
                os.close(fd)
            configured = self._snapshot(ticket)
            self._empty(configured, zero=True, no_children=True)
            need(set(configured['cgroup.subtree_control'].split()) == CONTROLLERS,
                 'exact_owned_controller_configuration')
            self._persist(ticket, 'prepared', {'schema': SCHEMA, 'parent': ticket.path,
                'parent_identity': list(ticket.parent_identity), 'name': name, 'image': image,
                'daemon_info': {k:daemon_info[k] for k in ('ID', 'ServerVersion', 'KernelVersion',
                    'OSType', 'CgroupDriver', 'CgroupVersion')},
                'initial': initial, 'configured': configured,
                'runtime_qualified': False})
            return ticket
        except BaseException as primary:
            self.failed = True
            try:
                write(self.evidence_root / (name + '.prepare_failure.json'), encode({
                    'schema': SCHEMA, 'created': created, 'name': name,
                    'class': type(primary).__name__, 'message': str(primary),
                    'parent_identity': list(ticket.parent_identity) if ticket else None}), self.budget)
            except BaseException as preservation:
                primary.add_note('failure preservation: ' + type(preservation).__name__)
            try:
                if ticket is not None:
                    self.close(ticket)
                else:
                    # No captured inode means no deletion authority by name.
                    for fd in (parent, delegation):
                        if fd is not None:
                            try:
                                os.close(fd)
                            except BaseException as cleanup:
                                primary.add_note('descriptor cleanup attempt: ' + type(cleanup).__name__)
            except BaseException as cleanup:
                primary.add_note('observer cleanup: ' + type(cleanup).__name__)
            raise primary

    def creation_parent(self, ticket):
        self._require(ticket)
        return ticket.path

    def before_start(self, *, cid, image, name):
        ticket = self.active
        self._require(ticket)
        need(re.fullmatch(r'[0-9a-f]{64}', cid) is not None and ticket.cid is None and
             image == ticket.image and name == ticket.name, 'exact_before_start_identity')
        snapshot = self._snapshot(ticket)
        self._empty(snapshot, zero=True, no_children=True)
        ticket.cid = cid
        self._persist(ticket, 'bound', {'cid': cid, 'name': name, 'image': image,
                                      'parent': ticket.path, 'snapshot': snapshot})
        return ticket

    def after_exit(self, ticket, *, cid, image, name):
        self._require(ticket)
        need(cid == ticket.cid and image == ticket.image and name == ticket.name and
             ticket.captured is None, 'exact_after_exit_identity')
        snapshot = self._snapshot(ticket)
        self._empty(snapshot)
        need(snapshot['children'] in ([], [cid]), 'only_exact_selected_container_child')
        original = self._persist(ticket, 'capture', {'schema': SCHEMA, 'cid': cid,
            'name': name, 'image': image, 'parent': ticket.path,
            'parent_identity': list(ticket.parent_identity), 'snapshot': snapshot,
            'tracked_object': 'owner_parent_persists_until_close',
            'counter_reset_or_baseline_subtraction': False})
        result = {'schema': PROFILE + '.KERNEL', 'cid': cid, 'name': name, 'image': image,
            'observer_source_sha256': self.policy['observer_source_sha256'],
            'source': 'linux_cgroup_v2',
            'lifetime': 'entire_fresh_container_including_all_descendants',
            'capture_stage': 'all_tasks_exited_before_cgroup_release',
            'cgroup_device': ticket.parent_identity[0], 'cgroup_inode': ticket.parent_identity[1],
            'cgroup_path': ticket.path, 'cpu_stat': snapshot['cpu.stat'],
            'memory_peak': snapshot['memory.peak'], 'cgroup_events': snapshot['cgroup.events'],
            'original_capture_sha256': original['sha256']}
        validate_kernel_evidence(result, self.policy, cid=cid, name=name)
        ticket.captured = snapshot
        return result

    def close(self, ticket):
        need(type(ticket) is ParentTicket and ticket is self.active and
             ticket.token is _TICKET and not ticket.closed, 'owned_parent_close_once')
        errors = []; snapshot = None; removed = False
        try:
            snapshot = self._snapshot(ticket)
            cpu, peak = self._empty(snapshot, no_children=True)
            if ticket.captured is not None:
                old = table(ticket.captured['cpu.stat'], {'usage_usec', 'user_usec', 'system_usec'}, CPU_KEYS)
                need(all(cpu[k] == old[k] for k in ('usage_usec', 'user_usec', 'system_usec')) and
                     peak == decimal(ticket.captured['memory.peak']), 'no_late_counter_loss')
            self._require(ticket)
            os.rmdir(ticket.leaf, dir_fd=ticket.delegation_fd); removed = True
        except BaseException as error:
            errors.append({'phase': 'owned_parent_removal', 'class': type(error).__name__,
                           'message': str(error)})
        finally:
            for fd in (ticket.parent_fd, ticket.delegation_fd):
                try: os.close(fd)
                except BaseException as error:
                    errors.append({'phase': 'descriptor_close', 'class': type(error).__name__})
            ticket.closed = True; self.active = None
        if errors: self.failed = True
        try:
            original = self._persist(ticket, 'close', {'schema': SCHEMA,
                'parent': ticket.path, 'parent_identity': list(ticket.parent_identity),
                'cid': ticket.cid, 'snapshot': snapshot, 'parent_removed': removed,
                'errors': errors, 'observer_processes_created': 0})
        except BaseException:
            self.failed = True
            raise
        need(not errors and removed, 'owned_observer_close_incomplete')
        return {'schema': PROFILE + '.OBSERVER_CLOSED',
                'observer_source_sha256': self.policy['observer_source_sha256'],
                'close_status': 'all_owned_descriptors_closed_no_children_created',
                'original_close_sha256': original['sha256']}
