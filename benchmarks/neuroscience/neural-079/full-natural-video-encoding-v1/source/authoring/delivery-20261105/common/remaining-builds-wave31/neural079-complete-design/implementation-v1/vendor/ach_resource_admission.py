"""Concrete source and live identity admission, enabled only by external custody.

Hashes and Linux credentials identify selected bytes/processes. Authentic issuer
custody, the read-only source environment, view policy and absence of foreign
writers remain independent deployment facts; this code does not infer them.
"""
import os
import stat
from ach_resource_common import (require, fields, integer, check_pin, body_pin,
    bounded_decode, read_body, read_fd, close_all, token)
from ach_resource_model import profile, profile_pin
from ach_resource_readers import absolute


def source_admission(selection, selected, clock):
    require(type(selection) is dict and selection.get('execution_enabled') is True,
            'typed source deployment disabled before any source/host reads')
    fields(selection, ('schema', 'execution_enabled', 'issuer_receipt', 'source_environment_receipt',
        'custody_receipt', 'history_receipt', 'sources', 'source_manifest_pin', 'profile_pin',
        'role', 'role_identity', 'peers', 'scope_membership', 'boot_id', 'environment'),
        'complete independently installed source admission')
    require(selection['schema'] == 'ach_typed_source_admission_v1', 'source admission version')
    profile(selected); require(selection['profile_pin'] == profile_pin(selected), 'exact selected typed profile')
    token(selection['role']); check_pin(selection['source_manifest_pin'])
    receipts = {}
    for name, expected in (('issuer_receipt', None),
            ('source_environment_receipt', selected['source_environment_pin']),
            ('custody_receipt', selected['custody_admission_pin']),
            ('history_receipt', selected['authoring_history_pin'])):
        descriptor = selection[name]
        fields(descriptor, ('path', 'pin'), 'independently issued receipt descriptor')
        if expected is not None: require(descriptor['pin'] == expected, 'same external admission receipt')
        receipts[name] = bounded_decode(read_body(absolute(descriptor['path']), descriptor['pin'],
            selected['reader_limits']['file_bytes'], clock, 'scientific'), selected['encoding_limits'])
    issuer = receipts['issuer_receipt']
    fields(issuer, ('schema', 'source_manifest_pin', 'profile_pin', 'environment_pin', 'custody_pin',
                   'history_pin', 'origin_ns', 'scientific_ns', 'closeout_ns', 'outer_ns', 'roles'),
           'exact independent deployment issuer receipt')
    require(issuer['schema'] == 'ach_typed_deployment_issuer_v1' and
        issuer['source_manifest_pin'] == selection['source_manifest_pin'] and
        issuer['profile_pin'] == selection['profile_pin'] and
        issuer['environment_pin'] == selected['source_environment_pin'] and
        issuer['custody_pin'] == selected['custody_admission_pin'] and
        issuer['history_pin'] == selected['authoring_history_pin'], 'joined issuer resource/source custody')
    for name in ('origin', 'scientific', 'closeout', 'outer'):
        require(issuer[name + '_ns'] == getattr(clock, name), 'same original operation interval')
    require(issuer['roles'][selection['role']] == selection['role_identity'], 'source-owned selected role identity')
    require(type(selection['sources']) is list and selection['sources'] and
        len(selection['sources']) <= selected['reader_limits']['source_files'], 'bounded complete runtime source roster')
    paths = set(); captured = []
    for item in selection['sources']:
        fields(item, ('path', 'pin'), 'exact selected runtime body')
        require(item['path'] not in paths, 'no duplicate selected source'); paths.add(item['path'])
        read_body(absolute(item['path']), item['pin'], selected['reader_limits']['file_bytes'], clock, 'scientific')
        captured.append(item)
    from ach_resource_common import bounded_encode
    require(body_pin(bounded_encode(captured, selected['encoding_limits'])) == selection['source_manifest_pin'],
            'full independently selected runtime source closure')
    require(type(selection['environment']) is dict and dict(os.environ) == selection['environment'],
            'exact admitted process environment, including interpreter/module configuration')
    own = live_identity(os.getpid(), selected, clock)
    require(own == selection['role_identity'], 'actual selected boot/start/executable/cgroup/namespace process')
    require(own['boot_id'] == selection['boot_id'] and own['cgroup'] == selection['scope_membership'],
            'actual common-scope membership')
    return {'selection': selection, 'receipts': receipts, 'observed_identity': own,
            'source_pin': selection['source_manifest_pin']}


def proc_read(path, selected, clock, phase):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW); primary = None
    try: return read_fd(fd, selected['reader_limits']['file_bytes'], clock, phase)
    except BaseException as error: primary = error; raise
    finally: close_all([('proc identity descriptor', lambda: os.close(fd))], primary)


def live_identity(pid, selected, clock, phase='scientific'):
    integer(pid, 1); clock.tick(phase)
    raw = proc_read('/proc/%d/stat' % pid, selected, clock, phase)
    # comm may contain spaces or parentheses; the last ')' delimits field two.
    tail = raw[raw.rfind(b')') + 2:].split()
    require(len(tail) >= 20 and tail[19].isdigit(), 'actual proc start ticks')
    start = int(tail[19])
    status = proc_read('/proc/%d/status' % pid, selected, clock, phase).decode('ascii')
    rows = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    uid = [int(v) for v in rows['Uid'].split()]; gid = [int(v) for v in rows['Gid'].split()]
    require(len(uid) == len(gid) == 4, 'actual proc credentials')
    executable = os.stat('/proc/%d/exe' % pid)
    namespaces = {}
    for name in ('mnt', 'pid', 'user', 'net', 'ipc', 'uts', 'cgroup'):
        node = os.stat('/proc/%d/ns/%s' % (pid, name)); namespaces[name] = [node.st_dev, node.st_ino]
    result = {'pid': pid, 'uid': uid[1], 'gid': gid[1], 'start_ticks': start,
        'boot_id': proc_read('/proc/sys/kernel/random/boot_id', selected, clock, phase).decode('ascii').strip(),
        'executable': {'device': executable.st_dev, 'inode': executable.st_ino}, 'namespaces': namespaces,
        'cgroup': proc_read('/proc/%d/cgroup' % pid, selected, clock, phase).decode('ascii')}
    again = proc_read('/proc/%d/stat' % pid, selected, clock, phase)
    require(int(again[again.rfind(b')') + 2:].split()[19]) == start, 'PID identity changed during admission')
    return result


def verify_peer(actual, expected, selected, clock, phase):
    for key in ('pid', 'uid', 'gid'): require(actual[key] == expected[key], 'exact selected Unix peer credentials')
    require(live_identity(actual['pid'], selected, clock, phase) == expected, 'same admitted live peer identity')
    return expected
