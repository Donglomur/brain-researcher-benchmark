"""Concrete bounded Docker Engine transport; dormant until operator qualification.

The daemon socket is a privileged host dependency and is never mounted inside a
candidate. No Docker command, URL, mount, image or resource value comes from model
actions. Engine protocol/telemetry support must be qualified on the exact daemon.
"""
import http.client
import io
import json
import math
import os
from pathlib import Path
import socket
import stat
import tarfile
import threading
import time
from urllib.parse import quote, urlencode

from core import capture, descriptor, encoded, finite, fresh, integer, need, parse, pin, publish, seal_output


class LocalConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


class Engine:
    def __init__(self, selection, budget, record):
        # selection was admitted by the protected root gate, not by a model.
        self.selection, self.budget, self.record = selection, budget, record
        self.socket_path = selection['socket']
        st = os.lstat(self.socket_path)
        need(stat.S_ISSOCK(st.st_mode) and st.st_uid == selection['socket_uid'],
             'qualified ordinary Docker daemon socket')
        self.socket_stamp = (st.st_dev, st.st_ino, st.st_uid)
        self.api = selection['api_version']
        need(type(self.api) is str and self.api.startswith('v')
             and all(x in '0123456789.' for x in self.api[1:]), 'selected Engine API version')

    def call(self, method, route, cutoff, payload=None, cap=1048576, accepted=(200,)):
        need(method in ('GET', 'POST', 'DELETE') and route.startswith('/'), 'fixed Engine method/route')
        now = self.budget.tick(cutoff)
        st = os.lstat(self.socket_path)
        need((st.st_dev, st.st_ino, st.st_uid) == self.socket_stamp and stat.S_ISSOCK(st.st_mode),
             'daemon socket custody changed')
        body = None if payload is None else encoded(payload)
        cap = integer(cap, 1)
        # Response cap reservation is conservative; EOF/headers do not become
        # purported measured daemon or physical filesystem usage.
        self.budget.reserve_read(cap)
        if body is not None:
            self.budget.reserve_write(len(body))
        conn = LocalConnection(self.socket_path, min(30., cutoff-now))
        try:
            conn.request(method, '/' + self.api + route, body=body,
                         headers={'Content-Type': 'application/json', 'Connection': 'close'})
            response = conn.getresponse()
            length = response.getheader('Content-Length')
            if length is not None:
                need(length.isdigit() and int(length) <= cap, 'Engine response length exceeds cap')
            parts, size = [], 0
            while True:
                self.budget.tick(cutoff)
                chunk = response.read(min(65536, cap+1-size))
                if not chunk:
                    break
                parts.append(chunk); size += len(chunk)
                need(size <= cap, 'Engine response exceeds cap')
            raw = b''.join(parts)
            self.record({'kind': 'transport_observed', 'transport': 'docker_engine', 'method': method, 'route': route,
                         'request': None if body is None else pin(body), 'response': pin(raw),
                         'status': response.status, 'observed_end': self.budget.tick(cutoff)})
            need(response.status in accepted, 'unexpected Engine status:' + str(response.status))
            return response.status, raw
        finally:
            conn.close()

    def inspect(self, ident, cutoff, absent=False):
        status, raw = self.call('GET', '/containers/' + quote(ident, safe='') + '/json', cutoff,
                                accepted=(200, 404) if absent else (200,))
        return None if status == 404 else parse(raw)

    def owned(self, run_id, cutoff):
        query = urlencode({'all': '1', 'filters': json.dumps({'label': ['neural060.run=' + run_id]})})
        _, raw = self.call('GET', '/containers/json?' + query, cutoff)
        rows = parse(raw)
        need(type(rows) is list and all(type(x) is dict and type(x.get('Id')) is str for x in rows),
             'Engine owned-container inventory')
        return rows


def read_logs(raw, cap):
    """Decode the non-TTY Docker multiplex framing, preserving both streams."""
    need(len(raw) <= cap, 'bounded raw tool log')
    cursor = 0
    streams = {1: bytearray(), 2: bytearray()}
    while cursor < len(raw):
        need(len(raw)-cursor >= 8, 'short Engine log header')
        header = raw[cursor:cursor+8]; cursor += 8
        stream = header[0]
        need(stream in streams and header[1:4] == b'\0\0\0', 'non-TTY log stream header')
        length = int.from_bytes(header[4:], 'big')
        need(length <= len(raw)-cursor, 'short Engine log payload')
        streams[stream].extend(raw[cursor:cursor+length]); cursor += length
    return {('stdout' if k == 1 else 'stderr'): bytes(v) for k, v in streams.items()}


def one_tar(raw, filename, cap):
    """Never extract an untrusted archive; admit exactly one ordinary file."""
    need(type(filename) is str and '/' not in filename and filename not in ('', '.', '..'),
         'fixed output basename')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        members = archive.getmembers()
        need(len(members) == 1, 'one requested output artifact only')
        member = members[0]
        need(member.name == filename and member.isfile() and not member.issym()
             and not member.islnk() and not member.sparse and member.size <= cap,
             'bounded ordinary output file; no links or sparse archive')
        stream = archive.extractfile(member)
        need(stream is not None, 'missing archive body')
        body = stream.read(cap+1)
        need(len(body) == member.size, 'exact captured archive member')
        return body


def admit_configuration(observed, wanted, resolved_image):
    need(observed['Image'] == resolved_image, 'qualified resolved image identity')
    actual, host = observed['Config'], observed['HostConfig']
    for name in ('Cmd', 'User', 'WorkingDir', 'Tty', 'Labels'):
        need(actual[name] == wanted[name] and type(actual[name]) is type(wanted[name]),
             'exact native configuration:' + name)
    need(all(x in actual['Env'] for x in wanted['Env']), 'fixed native environment overrides')
    for name in ('NetworkMode', 'ReadonlyRootfs', 'CapDrop', 'SecurityOpt', 'Memory',
                 'MemorySwap', 'NanoCpus', 'CpuPeriod', 'CpuQuota', 'PidsLimit', 'Binds',
                 'AutoRemove', 'RestartPolicy', 'Tmpfs', 'LogConfig'):
        need(host[name] == wanted['HostConfig'][name] and type(host[name]) is type(wanted['HostConfig'][name]),
             'exact native host isolation:' + name)
    limits = {r['Name']: (r['Soft'], r['Hard']) for r in host['Ulimits']}
    expected = {r['Name']: (r['Soft'], r['Hard']) for r in wanted['HostConfig']['Ulimits']}
    need(limits == expected, 'fixed file/core limits')
    need(host.get('Privileged') is False and host.get('PidMode', '') == ''
         and host.get('Devices', []) in ([], None) and host.get('DeviceRequests', []) in ([], None),
         'no privilege, host PID or accelerator device grants')


def cpu_reservation(limits, start, requested_cutoff):
    """Prospective quota×wall bound, including selected stop latency and bursts.

    Kernel CFS quota/period semantics and stop-latency support remain required
    environment qualifications. If a stop fails, usage stays uncertain and the
    run cannot pass; an after-exit measurement never retroactively grants budget.
    """
    period_us = 100000
    nanos = integer(limits['cpu_nanos'], 1)
    quota_us = nanos*period_us//1000000000
    need(quota_us > 0, 'positive representable aggregate cgroup CPU quota')
    cleanup_s = integer(limits['cleanup_seconds'], 1)
    limit_ns = integer(limits['cpu_seconds'], 1)*1000000000
    buffer_ns = cleanup_s*1000000000+2*period_us*1000
    maximum_wall_ns = limit_ns*period_us//quota_us-buffer_ns
    available_ns = math.floor((requested_cutoff-start)*1000000000)
    run_ns = min(maximum_wall_ns, available_ns)
    need(run_ns > 0, 'insufficient CPU/elapsed allowance including bounded stop reserve')
    reserved_ns = ((run_ns+buffer_ns)*quota_us+period_us-1)//period_us
    need(reserved_ns <= limit_ns, 'prospective aggregate native CPU reservation')
    return {'cpu_period_us': period_us, 'cpu_quota_us': quota_us,
            'cpu_reserved_nanoseconds': reserved_ns, 'cpu_limit_nanoseconds': limit_ns,
            'execution_cutoff': min(requested_cutoff, start+run_ns/1000000000),
            'cleanup_seconds': cleanup_s, 'quota_burst_allowance_nanoseconds': 2*period_us*1000}


def stop_owned(engine, ident, run_id, phase_id, cutoff, record):
    """Bounded SIGKILL for precisely this invocation; retain its files/container."""
    if ident is None:
        return {'attempted': False, 'closed': False, 'unknown_create_outcome': True}
    record({'kind': 'native_stop_attempted', 'phase': phase_id, 'container': ident})
    observed = engine.inspect(ident, cutoff, absent=True)
    if observed is None:
        return {'attempted': True, 'closed': True, 'already_absent': True}
    need(observed['Config']['Labels'] == {'neural060.run': run_id, 'neural060.phase': phase_id},
         'refuse stopping any resource outside this exact owned invocation')
    need(type(observed['State'].get('Running')) is bool, 'typed owned running state')
    if observed['State']['Running']:
        engine.call('POST', '/containers/'+ident+'/kill?signal=SIGKILL', cutoff, accepted=(204, 409))
    while True:
        engine.budget.tick(cutoff)
        observed = engine.inspect(ident, cutoff, absent=True)
        # A freshly created container can still have an in-flight /start. Never
        # call that stopped: wait for running→kill→exited, natural exited, or
        # absence. Pending creation/start at the deadline remains uncertain.
        if observed is None or (observed['State'].get('Status') == 'exited'
                               and observed['State']['Running'] is False
                               and type(observed['State']['Pid']) is int and observed['State']['Pid'] == 0):
            result = {'attempted': True, 'closed': True, 'retained_for_inspection': observed is not None}
            record({'kind': 'native_stop_observed', 'phase': phase_id, 'container': ident, 'result': result})
            return result
        need(type(observed['State'].get('Running')) is bool, 'typed owned running state while stopping')
        if observed['State']['Running']:
            engine.call('POST', '/containers/'+ident+'/kill?signal=SIGKILL', cutoff, accepted=(204, 409))
        time.sleep(min(0.05, max(0., cutoff-time.monotonic())))


class PhaseStop:
    """Independent host thread enforces one selected phase cutoff.

    It never writes the producer journal concurrently. Its separate ledger was
    reserved before effects. Scheduling/daemon kill latency remains an explicit
    environment qualification; failure to observe stop is unknown, never free.
    """
    def __init__(self, selection, budget, ident, run_id, phase_id, cutoff):
        self.selection, self.budget = selection, budget
        self.ident, self.run_id, self.phase_id, self.cutoff = ident, run_id, phase_id, cutoff
        self.wake = threading.Event(); self.cancelled = False
        self.events = []; self.result = None; self.fired = False
        self.thread = threading.Thread(target=self._run, name='neural060-phase-stop', daemon=True)

    def _run(self):
        self.wake.wait(max(0., self.cutoff-time.monotonic()))
        if self.cancelled:
            self.result = {'attempted': False, 'cancelled_after_natural_retirement': True}
            return
        self.fired = True
        try:
            engine = Engine(self.selection, self.budget, self.events.append)
            self.result = stop_owned(engine, self.ident, self.run_id, self.phase_id,
                                     self.budget.deadline, self.events.append)
        except BaseException as error:
            self.result = {'attempted': True, 'closed': False, 'error_type': type(error).__name__,
                           'usage_and_resource_state_unknown': True}

    def start(self):
        self.thread.start()

    def finish(self, natural=False):
        # Natural cancellation occurs only after observed zero exit and removal.
        self.cancelled = natural
        self.wake.set()
        self.thread.join(max(0., self.budget.deadline-time.monotonic()))
        return {'timer_or_failure_stop_triggered': self.fired,
                'watchdog_joined': not self.thread.is_alive(), 'stop': self.result,
                'events': self.events, 'ledger': {
                    'origin': self.budget.origin, 'deadline': self.budget.deadline,
                    'observed': time.monotonic(), 'read_reserved_bytes': self.budget.read_bytes,
                    'write_reserved_bytes': self.budget.write_bytes,
                    'logical_reservations_not_measured_physical_usage': True,
                    'passive_closeout_snapshot_may_be_after_deadline': True}}


def native(engine, *, run_id, phase_id, image, command, inputs, output_caps,
           limits, cutoff, output_root, budget, record):
    """One actual offline container, natural closure, capture and retirement.

    Input rows are operator-frozen {source,target,pin,cap}; model actions supply
    only script bytes already published to a fixed input descriptor. Phase state
    records are written before effects. Failure retains uncertain resources.
    """
    need(type(run_id) is str and type(phase_id) is str, 'owned phase identities')
    need(type(image) is str and '@sha256:' in image, 'digest-pinned qualified image')
    need(type(command) is list and command and all(type(x) is str for x in command),
         'operator command argv only')
    plan = cpu_reservation(limits, budget.tick(cutoff), cutoff)
    requested_cutoff, cutoff = cutoff, plan['execution_cutoff']
    cleanup_read = integer(limits['cleanup_read_bytes'], 1)
    cleanup_write = integer(limits['cleanup_write_bytes'], 1)
    budget.reserve_read(cleanup_read); budget.reserve_write(cleanup_write)
    # Pre-reserved emergency ledger can stop this exact container even after the
    # production cutoff. It cannot authorize another producer or late success.
    from core import Budget
    cleanup_budget = Budget(budget.origin, cutoff+plan['cleanup_seconds'], cleanup_read, cleanup_write)
    before_inputs = {}
    binds = []
    seen = set()
    for row in inputs:
        need(set(row) == {'source', 'target', 'pin', 'cap'}, 'exact native input descriptor')
        target = row['target']
        need(type(target) is str and (target.startswith('/input/') or target.startswith('/trusted/')
             or target == '/model/model.pkl')
             and '..' not in target.split('/') and target not in seen, 'unique fixed readonly target')
        seen.add(target)
        _, st = capture(row['source'], row['pin'], row['cap'], budget, retain=False, readonly=True)
        before_inputs[row['source']] = st
        need(':' not in str(row['source']), 'unambiguous Engine bind path')
        binds.append(str(Path(row['source']).absolute()) + ':' + target + ':ro')
    memory = integer(limits['memory_bytes'], 1)
    scratch = integer(limits['scratch_bytes'], 1)
    output_limit = integer(limits['output_bytes'], 1)
    cpus = integer(limits['cpu_nanos'], 1)
    integer(limits['pids'], 1)
    need(type(output_caps) is dict and output_caps, 'fixed nonempty output inode inventory')
    max_file = max(integer(x, 1) for x in output_caps.values())
    # RLIMIT_FSIZE is per file. Candidate can write the largest allowance into
    # any mounted output inode, so reserve that upper bound for EVERY inode.
    # Directory is readonly and only these precreated files are writable.
    need(len(output_caps)*max_file <= output_limit, 'all fixed output inode upper bounds reserved')
    budget.reserve_write(len(output_caps)*max_file)
    fresh(output_root, budget)
    output_inodes = {}
    for name in output_caps:
        need(type(name) is str and name not in ('', '.', '..') and '/' not in name,
             'fixed output basenames')
        path = Path(output_root)/name
        publish(path, b'', budget)
        os.chmod(path, 0o666)
        st = os.lstat(path)
        output_inodes[name] = (st.st_dev, st.st_ino)
    binds.append(str(Path(output_root).absolute()) + ':/output:ro')
    for name in output_caps:
        binds.append(str((Path(output_root)/name).absolute()) + ':/output/' + name + ':rw')
    config = {'Image': image, 'Cmd': command, 'User': '65534:65534', 'WorkingDir': '/work',
              'Env': ['PYTHONHASHSEED=0', 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=1',
                      'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', 'HOME=/work'],
              'Tty': False, 'AttachStdout': True, 'AttachStderr': True,
              'Labels': {'neural060.run': run_id, 'neural060.phase': phase_id},
              'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'CapDrop': ['ALL'],
                             'SecurityOpt': ['no-new-privileges'], 'Memory': memory,
                             'MemorySwap': memory, 'NanoCpus': 0, 'CpuPeriod': plan['cpu_period_us'],
                             'CpuQuota': plan['cpu_quota_us'], 'PidsLimit': limits['pids'],
                             'Binds': binds, 'AutoRemove': False,
                             'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0},
                             'Tmpfs': {'/work': 'rw,noexec,nosuid,nodev,mode=1777,size=' + str(scratch),
                                       '/tmp': 'rw,noexec,nosuid,nodev,mode=1777,size=67108864'},
                             'Ulimits': [{'Name': 'fsize', 'Soft': max_file, 'Hard': max_file},
                                         {'Name': 'core', 'Soft': 0, 'Hard': 0}],
                             'LogConfig': {'Type': 'none', 'Config': {}}}}
    record({'kind': 'native_intent', 'phase': phase_id, 'config': config,
            'original_origin': budget.origin, 'cutoff': cutoff, 'requested_cutoff': requested_cutoff,
            'cpu_reservation': plan})
    ident = None; watchdog = None
    try:
        _, raw = engine.call('POST', '/containers/create', cutoff, config, accepted=(201,))
        created = parse(raw); ident = created['Id']
        need(type(ident) is str and len(ident) == 64 and all(c in '0123456789abcdef' for c in ident),
             'exact created container identity')
        record({'kind': 'native_created', 'phase': phase_id, 'container': ident})
        admit_configuration(engine.inspect(ident, cutoff), config, engine.selection['image_ids'][image])
        watchdog = PhaseStop(engine.selection, cleanup_budget, ident, run_id, phase_id, cutoff)
        watchdog.start()
        engine.call('POST', '/containers/' + ident + '/start', cutoff, accepted=(204,))
        record({'kind': 'native_started', 'phase': phase_id, 'container': ident})
        while True:
            budget.tick(cutoff)
            inspected = engine.inspect(ident, cutoff)
            state = inspected['State']
            admit_configuration(inspected, config, engine.selection['image_ids'][image])
            need(type(state.get('Running')) is bool, 'native running state')
            if not state['Running']:
                break
            time.sleep(min(0.1, max(0., cutoff-time.monotonic())))
        natural_end = budget.tick(cutoff)
        need(state.get('Status') == 'exited' and type(state.get('ExitCode')) is int
             and state['ExitCode'] == 0 and state.get('OOMKilled') is False
             and state.get('Error') == '' and type(state.get('Pid')) is int and state['Pid'] == 0,
             'natural successful native closure before capture')
        # Exact daemon support is an activation qualification. Missing cumulative
        # CPU or peak memory is unknown, never zero or inferred from reservations.
        _, raw_stats = engine.call('GET', '/containers/' + ident + '/stats?stream=false', cutoff)
        stats = parse(raw_stats)
        cpu_ns = integer(stats['cpu_stats']['cpu_usage']['total_usage'], 1)
        peak = integer(stats['memory_stats']['max_usage'], 1)
        need(cpu_ns <= plan['cpu_reserved_nanoseconds'] <= integer(limits['cpu_seconds'], 1)*1000000000
             and peak <= memory,
             'native measured resource ceiling')
        artifacts = {}
        # Trusted sandbox launcher redirects stdout/stderr to their fixed bounded
        # output files. These are untrusted final tool-result bytes, not a claim
        # of an append-only transcript of every candidate internal operation.
        for name, cap in output_caps.items():
            artifacts[name] = seal_output(Path(output_root)/name, cap, output_inodes[name], budget)
        engine.call('DELETE', '/containers/' + ident + '?force=0&v=1', cutoff, accepted=(204,))
        need(engine.inspect(ident, cutoff, absent=True) is None, 'owned container retirement independently queried')
        for row in inputs:
            _, st = capture(row['source'], row['pin'], row['cap'], budget, retain=False, readonly=True)
            need(st == before_inputs[row['source']], 'native readonly input custody changed')
        stop_status = watchdog.finish(natural=True)
        need(stop_status['watchdog_joined'] is True and stop_status['timer_or_failure_stop_triggered'] is False,
             'independent phase watchdog did not need to stop production')
        result = {'schema': 'neural060_native_v1', 'phase': phase_id, 'container': ident,
                  'natural_end': natural_end, 'closed_and_removed': True, 'exit_code': 0,
                  'cpu_nanoseconds': cpu_ns, 'peak_memory_bytes': peak,
                  'config': pin(encoded(config)), 'stats': pin(raw_stats), 'artifacts': artifacts,
                  'source_inputs': inputs, 'cutoff': cutoff, 'requested_cutoff': requested_cutoff,
                  'original_origin': budget.origin,
                  'cpu_reservation': plan, 'cleanup_reserved_read_bytes': cleanup_read,
                  'cleanup_reserved_write_bytes': cleanup_write, 'watchdog': stop_status}
        record({'kind': 'native_completed', 'result': result})
        return result
    except BaseException as error:
        # Stopping precisely owned computation is distinct from retrying or
        # deleting its evidence. Journal attempts may be unavailable at cutoff;
        # the independent outer observer also stops any still-running owned IDs.
        local_events = []
        stopped = {'attempted': False, 'closed': False}
        try:
            if watchdog is not None:
                stopped = watchdog.finish(natural=False)
            else:
                emergency = Engine(engine.selection, cleanup_budget, local_events.append)
                stopped = stop_owned(emergency, ident, run_id, phase_id, cleanup_budget.deadline, local_events.append)
        except BaseException as stop_error:
            stopped = {'attempted': ident is not None, 'closed': False,
                       'error_type': type(stop_error).__name__, 'usage_and_resource_state_unknown': True}
        failure = {'kind': 'native_failed', 'phase': phase_id, 'container': ident,
                   'error_type': type(error).__name__, 'error': str(error),
                   'partial_output_directory': str(output_root), 'output_inodes': output_inodes,
                   'stop': stopped, 'stop_events': local_events, 'cpu_reservation': plan,
                   'resource_state_requires_independent_inspection': True}
        try:
            record(failure)
        except BaseException:
            # Persist only through the pre-reserved closeout ledger; this record
            # is explicitly a failed/late closeout, never a production success.
            try:
                publish(Path(output_root).parent/'NATIVE_FAILURE.json', encoded(failure), cleanup_budget, readonly=True)
            except BaseException:
                pass
        raise
