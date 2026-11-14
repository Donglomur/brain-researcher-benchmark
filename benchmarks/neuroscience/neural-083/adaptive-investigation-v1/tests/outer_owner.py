"""Bounded Linux owner for the fixed twenty-three NEURAL083 engineering cases.

No Docker or scientific execution. This process must be a dedicated, single
threaded child reaper. The fixed trusted harness creates at most seven tiny
children; subreaper adoption covers their separate sessions on harness failure.
"""
import argparse
import base64
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import selectors
import signal
import stat
import subprocess
import sys
import time

WORK_SECONDS = 25
CLEANUP_SECONDS = 2
STDOUT_CAP = 16384
STDERR_CAP = 65536
HARNESS_CAP = 40960
SELECTION_CAP = 8192
PROC_CAP = 131072
READ_CAP = 524288
RECEIPT_CAP = 65536
MAX_CHILDREN = 8
MAX_CENSUS = 128
MAX_ERRORS = 96
PACKAGE_ROOT = 'benchmarks/neuroscience/neural-083/adaptive-investigation-v1/package'
ROSTER = (
    'real_natural_adaptive_owner.py',
    'real_natural_inherited/process_owner.py',
    'real_natural_inherited/program/process.py',
    'real_native_owner_tiny_cli_prefix_no_Docker',
    'real_combined_cap_plus_probe',
    'real_original_timeout',
    'real_legacy_combined_cap_plus_probe',
    'inert_actual_native_late_failure_no_recapture',
    'inert_post_reap_reuse_no_signal',
    'inert_lost_wait_ownership_no_signal',
    'inert_actual_entry_metadata_callback',
    'inert_proc_adaptive_owner.py_not_found_close_failure',
    'inert_proc_adaptive_owner.py_lookup_close_failure',
    'inert_proc_adaptive_owner.py_vanished_known_closure',
    'inert_proc_inherited/process_owner.py_not_found_close_failure',
    'inert_proc_inherited/process_owner.py_lookup_close_failure',
    'inert_proc_inherited/process_owner.py_vanished_known_closure',
    'inert_proc_inherited/program/process.py_not_found_close_failure',
    'inert_proc_inherited/program/process.py_lookup_close_failure',
    'inert_proc_inherited/program/process.py_vanished_known_closure',
    'inert_proc_inherited/program/native.py_not_found_close_failure',
    'inert_proc_inherited/program/native.py_lookup_close_failure',
    'inert_proc_inherited/program/native.py_vanished_known_closure')
SOURCE_NAMES = (
    'adaptive_owner.py', 'admission.py', 'entry.py', 'inherited/integration.py',
    'inherited/process_owner.py', 'inherited/program/admission.py',
    'inherited/program/common.py', 'inherited/program/native.py',
    'inherited/program/observe.py', 'inherited/program/process.py')
BOOTSTRAP = '''import base64,hashlib,signal,sys,time
signal.pthread_sigmask(signal.SIG_SETMASK,set())
if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
 raise RuntimeError("fixed isolated captured startup")
payload,path,digest,end,*args=sys.argv[1:]
raw=base64.b64decode(payload,validate=True)
if len(raw)>40960 or hashlib.sha256(raw).hexdigest()!=digest:
 raise ValueError("captured harness bytes")
if time.monotonic()>=float(end):raise TimeoutError("original outer startup deadline")
sys.argv=[path,*args]
exec(compile(raw,path,"exec",dont_inherit=True),{"__name__":"__main__","__file__":path})
'''


def need(value, message):
    if not value:
        raise ValueError(message)


def parse(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'duplicate selected JSON key')
            value[key] = item
        return value
    def nonfinite(_):
        raise ValueError('nonfinite selected JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def exact_path(value):
    path = Path(value)
    need(type(value) is str and len(value.encode('utf-8')) <= 1024
         and value.isascii() and all(32 <= ord(c) < 127 for c in value)
         and path.is_absolute() and '..' not in path.parts and str(path) == value,
         'normalized absolute path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no path aliases')
    return path


def error_record(stage, error):
    # Bounded ASCII diagnostics; actual exception objects remain in State.
    raw = str(error).encode('utf-8','backslashreplace')[:192]
    return dict(stage=stage[:64],type=type(error).__name__[:64],
                message_prefix_base64=base64.b64encode(raw).decode('ascii'),
                message_encoding='UTF-8 prefix; original object retained')


class OuterFailure(RuntimeError):
    def __init__(self, state):
        super().__init__('NEURAL083 Linux engineering owner failed')
        self.state = state
        self.first = state.first
        self.secondary = state.secondary


class State:
    def __init__(self, origin):
        self.origin = origin
        self.work_end = origin + WORK_SECONDS
        self.final_end = self.work_end + CLEANUP_SECONDS
        self.first = None
        self.first_stage = None
        self.secondary = []
        self.errors_overflow = False
        self.read_reserved = self.proc_reserved = self.proc_actual = 0
        self.proc_census = 0
        self.children = []
        self.process = self.selector = None
        self.streams = {'stdout': bytearray(), 'stderr': bytearray()}
        self.eof = {'stdout': False, 'stderr': False}
        self.stream_closed = {'stdout': False, 'stderr': False}
        self.stream_overrun = {'stdout': False, 'stderr': False}
        self.sources = {}
        self.source_pins = {}
        self.subreaper_before = None
        self.subreaper_active = self.subreaper_restored = False
        self.libc = None
        self.no_children = False
        self.natural_code = None
        self.result = None
        self.output = None
        self.publications = []
        self.logs_complete = False
        self.signals_before = {}
        self.selector_closed = False
        self.final_signal_restore_complete = False
        self.spawn_attempted = self.spawn_returned = False
        self.startup_proof = {}
        self.final_summary = None
        self.invocation = None
        self.owner_receipt_raw = None
        self.owner_receipt_logged = False

    def fail(self, stage, error):
        if error is self.first:
            return
        if self.first is None:
            self.first, self.first_stage = error, stage
        elif len(self.secondary) < MAX_ERRORS:
            self.secondary.append((stage, error))
        else:
            # Every effectful operation is finitely capped below this bound.
            # Refuse if a future edit breaks that source-derived bound.
            self.errors_overflow = True

    def tick(self, cleanup=False):
        if time.monotonic() >= (self.final_end if cleanup else self.work_end):
            raise TimeoutError('original outer cleanup cutoff' if cleanup else 'original outer work cutoff')

    def reserve(self, amount, proc=False):
        need(type(amount) is int and amount >= 0 and self.read_reserved + amount <= READ_CAP,
             'outer managed read reservation')
        if proc:
            need(self.proc_reserved + amount <= PROC_CAP, 'outer adopted-child metadata bound')
            self.proc_reserved += amount
        else:
            need(self.read_reserved-self.proc_reserved+amount <= READ_CAP-PROC_CAP,
                 'ordinary reads preserve the original adopted-child discovery reserve')
        self.read_reserved += amount

    def source(self, path, size, digest, cap):
        need(type(size) is int and 0 < size <= cap and type(digest) is str
             and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
             'exact bounded source descriptor')
        self.tick()
        raw = bytearray()
        self.sources[str(path)] = raw
        fd = None
        first = None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
                 'ordinary exact source inode')
            while len(raw) <= size:
                self.tick()
                wanted = min(4096, size + 1 - len(raw))
                self.reserve(wanted)
                part = os.read(fd, wanted)
                if not part:
                    break
                raw.extend(part)
            after = os.fstat(fd)
            named = path.lstat()
            keys = ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
            need(all(getattr(before,k) == getattr(after,k) == getattr(named,k) for k in keys),
                 'stable selected source inode')
            need(len(raw) == size and hashlib.sha256(raw).hexdigest() == digest, 'selected source pin')
        except BaseException as error:
            first = error
            self.fail('source-capture',error)
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as error:
                    if first is None:
                        first = error
                    else:
                        self.fail('source-close-secondary', error)
        if first is not None:
            raise first
        self.source_pins[str(path)] = {'bytes': size, 'sha256': digest}
        return bytes(raw)

    def direct_children(self, cleanup=False):
        self.tick(cleanup)
        need(self.proc_census < MAX_CENSUS, 'bounded direct/adopted-child census count')
        self.proc_census += 1
        name = '/proc/self/task/' + str(os.getpid()) + '/children'
        fd = None
        raw = bytearray()
        first = None
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            need(stat.S_ISREG(os.fstat(fd).st_mode), 'ordinary direct-child proc metadata')
            while len(raw) <= 256:
                self.tick(cleanup)
                wanted = min(128, 257-len(raw))
                self.reserve(wanted, proc=True)
                part = os.read(fd, wanted)
                self.proc_actual += len(part)
                if not part:
                    break
                raw.extend(part)
            need(len(raw) <= 256, 'bounded direct-child metadata body')
            tokens = bytes(raw).split()
            need(len(tokens) <= MAX_CHILDREN and len(tokens) == len(set(tokens))
                 and all(x.isdigit() and 0 < int(x) <= 2147483647 for x in tokens),
                 'at most eight exact owned child identities')
            result = [int(x) for x in tokens]
        except BaseException as error:
            first = error
            self.fail('child-census',error)
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as error:
                    if first is None:
                        first = error
                    else:
                        self.fail('child-census-close-secondary', error)
        if first is not None:
            raise first
        return result

    def child(self, pid, role, cleanup=False):
        child = next((item for item in self.children if item['pid']==pid and not item['reaped']),None)
        if child is not None and child['admitted']:
            return child
        if child is None:
            need(len(self.children) < MAX_CHILDREN, 'fixed harness plus seven tiny children')
            child = dict(pid=pid, role=role, pidfd=None, admitted=False, reaped=False,
                         terminal=None, wait_error=False, kill_attempted=False,
                         pidfd_closed=False, admission_attempts=0, events=[])
            self.children.append(child)
        if child['admission_attempts'] >= 2:
            return child  # Original acquisition failures remain; no repeated retry.
        child['admission_attempts'] += 1
        self.tick(cleanup)
        # Exclusive parent reaping pins a direct/adopted child's numeric PID
        # during pidfd acquisition. All actual signaling uses that pidfd.
        found = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if found is not None:
            need(found.si_pid == pid, 'original direct child before pidfd capture')
        if child['pidfd'] is None:
            child['pidfd'] = os.pidfd_open(pid, 0)
        held = os.waitid(os.P_PIDFD, child['pidfd'], os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if held is not None:
            need(held.si_pid == pid, 'pidfd is same owned child')
        child['admitted'] = True
        child['events'].append('pidfd-owned-child-admitted')
        return child

    def reap(self, child, cleanup=False):
        if child['reaped'] or child['wait_error'] or not child['admitted']:
            return
        try:
            self.tick(cleanup)
            found = os.waitid(os.P_PIDFD, child['pidfd'], os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if found is None:
                return
            need(found.si_pid == child['pid'] and found.si_code in
                 (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED), 'terminal exact pidfd child')
            code = found.si_status if found.si_code == os.CLD_EXITED else -found.si_status
            child['terminal'] = {'code': code, 'si_code': found.si_code, 'si_status': found.si_status}
            returned = os.waitid(os.P_PIDFD, child['pidfd'], os.WEXITED | os.WNOHANG)
            need(returned is not None and returned.si_pid == found.si_pid
                 and returned.si_code == found.si_code and returned.si_status == found.si_status,
                 'one exact terminal pidfd reap')
            child['reaped'] = True
            child['events'].append('exact-pidfd-reaped')
            if child['role'] == 'harness':
                self.natural_code = code
                if self.process is not None:
                    self.process.returncode = code
        except BaseException as error:
            child['wait_error'] = not isinstance(error,TimeoutError)
            self.fail('owned-child-wait', error)

    def kill(self, child):
        if child['reaped'] or child['kill_attempted'] or not child['admitted']:
            return
        child['kill_attempted'] = True
        try:
            self.tick(True)
            signal.pidfd_send_signal(child['pidfd'], signal.SIGKILL, None, 0)
            child['events'].append('pidfd-SIGKILL-sent')
        except BaseException as error:
            self.fail('owned-child-pidfd-kill', error)

    def empty(self, cleanup=False):
        self.no_children=False
        pids = self.direct_children(cleanup)
        acquisition_failure=None
        for pid in pids:
            try:
                self.child(pid, 'adopted', cleanup)
            except BaseException as error:
                self.fail('owned-child-pidfd-acquisition', error)
                if acquisition_failure is None:acquisition_failure=error
        if acquisition_failure is not None:raise acquisition_failure
        if pids:
            return False
        try:
            found = os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            self.no_children = True
            return True
        # None means live children exist; a returned terminal remains unreaped.
        self.no_children = False
        if found is not None:
            try:
                self.child(found.si_pid, 'adopted', cleanup)
            except BaseException as error:
                self.fail('owned-terminal-child-acquisition', error)
        return False

    def capture_streams(self):
        # A returned Popen may precede a failed pidfd/selector acquisition.
        # Cleanup still attempts both available original read ends.
        if self.process is None:
            return
        if self.selector is None:
            self.selector=selectors.DefaultSelector()
        for name in ('stdout','stderr'):
            try:
                stream=getattr(self.process,name)
                if stream is None or self.eof[name] or self.stream_closed[name] or self.stream_overrun[name]:
                    continue
                try:
                    self.selector.get_key(stream)
                except KeyError:
                    os.set_blocking(stream.fileno(),False)
                    self.selector.register(stream,selectors.EVENT_READ,name)
            except BaseException as error:
                # One failed original pipe never suppresses the other's attempt.
                # Keep draining every successfully registered pipe in cleanup.
                self.fail('original-stream-acquisition-'+name,error)

    def drain(self, cleanup=False):
        if self.selector is None:
            return
        self.tick(cleanup)
        end = self.final_end if cleanup else self.work_end
        events = self.selector.select(min(.02, max(0, end-time.monotonic())))
        for key, _ in events:
            name = key.data
            cap = STDOUT_CAP if name == 'stdout' else STDERR_CAP
            wanted = min(4096, cap+1-len(self.streams[name]))
            need(wanted > 0, 'one consumed stream refusal probe')
            self.reserve(wanted)
            try:
                raw = os.read(key.fileobj.fileno(), wanted)
            except BlockingIOError:
                continue
            if not raw:
                self.eof[name] = True
                self.selector.unregister(key.fileobj)
                continue
            self.streams[name].extend(raw)
            if len(self.streams[name]) > cap:
                self.stream_overrun[name] = True
                self.selector.unregister(key.fileobj)
                raise ValueError('outer ' + name + ' cap plus probe')

    def cleanup(self):
        # First kill the exact harness, so separately sessioned children become
        # this subreaper's direct children. Never signal any numeric PID/PGID.
        for child in self.children:
            self.kill(child)
        discovery_failed = drain_failed = False
        try:self.capture_streams()
        except BaseException as error:
            self.fail('cleanup-original-stream-acquisition',error);drain_failed=True
        for _ in range(MAX_CENSUS-1):
            if time.monotonic() >= self.final_end:
                self.fail('cleanup-cutoff', TimeoutError('original outer cleanup cutoff'))
                break
            for child in self.children:
                self.reap(child, True)
            if not discovery_failed:
                try:
                    self.empty(True)
                except BaseException as error:
                    self.fail('cleanup-child-discovery', error)
                    discovery_failed = True
            for child in self.children:
                self.kill(child)
            if not drain_failed:
                try:
                    self.drain(True)
                except BaseException as error:
                    self.fail('cleanup-stream-drain', error)
                    drain_failed = True
            # A stream failure never skips the independent child-retirement loop.
            streams_done = self.selector is None or not self.selector.get_map() or drain_failed
            if self.no_children and streams_done:
                break
            time.sleep(min(.005, max(0, self.final_end-time.monotonic())))
        if not self.no_children:
            self.fail('cleanup-owned-children-unretired', RuntimeError('actual ECHILD not observed'))

    def close(self):
        if self.selector is not None:
            try:
                self.selector.close()
                self.selector_closed = True
            except BaseException as error:
                self.fail('selector-close', error)
        else:
            self.selector_closed = True
        if self.process is not None:
            for name in ('stdout', 'stderr'):
                stream = getattr(self.process, name)
                if stream is not None:
                    try:
                        stream.close()
                        self.stream_closed[name] = True
                    except BaseException as error:
                        self.fail(name+'-close', error)
        for child in self.children:
            if child['pidfd'] is not None and not child['pidfd_closed']:
                try:
                    os.close(child['pidfd'])
                    child['pidfd_closed'] = True
                except BaseException as error:
                    self.fail('pidfd-close', error)

    def publish(self, name, raw):
        need(name in ('stdout.bin','stderr.bin','OWNER.json'), 'fixed three-file receipt inventory')
        cap = {'stdout.bin':STDOUT_CAP+1,'stderr.bin':STDERR_CAP+1,'OWNER.json':RECEIPT_CAP}[name]
        need(len(raw) <= cap, 'bounded original receipt member')
        record = {'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                  'created':False,'written_bytes':0,'fsynced':False,'closed':False}
        self.publications.append(record)
        fd = None
        try:
            self.tick(True)
            fd = os.open(self.output/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            record['created'] = True
            value = os.fstat(fd)
            need(stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and value.st_uid == os.getuid(),
                 'exclusive ordinary original receipt')
            while record['written_bytes'] < len(raw):
                self.tick(True)
                n = os.write(fd, memoryview(raw)[record['written_bytes']:])
                need(n > 0, 'receipt write progress')
                record['written_bytes'] += n
            self.tick(True)
            os.fsync(fd)
            record['fsynced'] = True
        except BaseException as error:
            self.fail('publication-'+name, error)
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                    record['closed'] = True
                except BaseException as error:
                    self.fail('publication-close-'+name, error)

    def record(self):
        return dict(schema='neural083_linux_ci_original_owner_v1',
            status='observed_success_pending_publication' if self.first is None else 'failed',
            origin=self.origin,work_end=self.work_end,cleanup_end=self.final_end,
            observed_at=time.monotonic(),startup_proof=dict(self.startup_proof),
            actual_invocation=self.invocation,
            spawn_attempted=self.spawn_attempted,spawn_returned=self.spawn_returned,
            original_stream_availability=('captured_prefixes' if self.spawn_returned else
                'unavailable_if_spawn_created_child_but_did_not_return'),
            late_publication_or_restore_failure_evidence_may_be_unavailable_durably=True,
            first_error=None if self.first is None else error_record(self.first_stage,self.first),
            secondary_errors=[error_record(stage,exc) for stage,exc in self.secondary],
            errors_overflow=self.errors_overflow,natural_harness_exit_code=self.natural_code,
            stdout_eof=self.eof['stdout'],stderr_eof=self.eof['stderr'],
            stream_closed=dict(self.stream_closed),stream_overrun=dict(self.stream_overrun),
            stdout_bytes=len(self.streams['stdout']),stderr_bytes=len(self.streams['stderr']),
            children=[{k:v for k,v in child.items() if k != 'pidfd'} for child in self.children],
            actual_ECHILD_observed=self.no_children,selector_closed=self.selector_closed,
            subreaper_before=self.subreaper_before,subreaper_active=self.subreaper_active,
            subreaper_restored=self.subreaper_restored,managed_read_reservations=self.read_reserved,
            proc_read_reservations=self.proc_reserved,proc_actual_bytes=self.proc_actual,
            child_census_count=self.proc_census,source_pins=self.source_pins,
            harness_result=self.result,publications=list(self.publications),
            receipt_publication_and_final_exit_not_attested_by_this_file=True,
            raw_streams_are_separate_original_files=True,whole_process_RSS_enforced=False,
            descendant_scope='fixed trusted harness and at most seven tiny children; dedicated exclusive subreaper',
            Docker_model_data_science_executed=False,qualification_issued=False)


def subreaper(state, value=None):
    if state.libc is None:
        state.libc = ctypes.CDLL(None, use_errno=True)
        state.libc.prctl.argtypes = [ctypes.c_int,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong]
        state.libc.prctl.restype = ctypes.c_int
    if value is None:
        result = ctypes.c_int()
        code = state.libc.prctl(37, ctypes.addressof(result), 0, 0, 0)
        if code != 0:
            raise OSError(ctypes.get_errno(), 'PR_GET_CHILD_SUBREAPER')
        return result.value
    if state.libc.prctl(36, value, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER')
    need(subreaper(state) == value, 'actual selected subreaper state')


def platform_admit(state):
    need(sys.platform == 'linux' and platform.machine() == 'x86_64'
         and platform.python_implementation() == 'CPython' and sys.version_info >= (3,11) and ctypes.sizeof(ctypes.c_void_p) == 8,
         'selected Linux x86-64 CPython>=3.11 only')
    need(all(hasattr(os,n) for n in ('pidfd_open','P_PIDFD','waitid','WNOWAIT','WEXITED','P_ALL'))
         and hasattr(signal,'pidfd_send_signal')
         and signal.getsignal(signal.SIGCHLD) == signal.SIG_DFL,
         'pidfd/waitid support and default SIGCHLD required')
    need(not signal.pthread_sigmask(signal.SIG_BLOCK,set()),
         'dedicated supervisor starts with all signals unblocked')
    with os.scandir('/proc/self/task') as entries:
        names = []
        for entry in entries:
            need(len(names) < 2, 'dedicated single-threaded supervisor')
            names.append(entry.name)
    need(names == [str(os.getpid())], 'one original supervisor thread')
    need(state.direct_children() == [], 'dedicated supervisor starts without children')
    try:
        os.waitid(os.P_ALL,0,os.WEXITED|os.WNOHANG|os.WNOWAIT)
    except ChildProcessError:
        pass
    else:
        raise ValueError('dedicated supervisor has a waitable child')
    # Real kernel admission before Popen; feature names alone are insufficient.
    fd = os.pidfd_open(os.getpid(),0)
    first = None
    try:
        signal.pidfd_send_signal(fd,0,None,0)
        try:
            os.waitid(os.P_PIDFD,fd,os.WEXITED|os.WNOHANG|os.WNOWAIT)
        except ChildProcessError:
            pass  # Self is not our child; syscall shape/kernel support is admitted.
        else:
            raise ValueError('unexpected self pidfd wait ownership')
    except BaseException as error:
        first=error;state.fail('kernel-pidfd-admission',error)
    finally:
        try:os.close(fd)
        except BaseException as error:
            state.fail('kernel-pidfd-probe-close',error)
            if first is None:first=error
    if first is not None:raise first
    state.startup_proof=dict(single_thread_pid=os.getpid(),no_preexisting_children_ECHILD=True,
        default_SIGCHLD=True,unblocked_signal_mask=True,kernel_pidfd_signal_wait_admitted=True)
    state.no_children = True
    state.subreaper_before = subreaper(state)
    need(state.subreaper_before in (0,1), 'known original subreaper state')
    subreaper(state,1)
    state.subreaper_active = True


def admit_result(raw):
    value = parse(raw)
    fields = {'schema','status','cases','managed_reserved_bytes','elapsed_seconds',
              'real_kernel_cases','inert_logic_cases','Docker_executed','ci_proc_grant',
              'model_science_or_data_executed','qualification_issued'}
    need(type(value) is dict and set(value) == fields
         and value['schema'] == 'neural083_prospective_owner_engineering_v1'
         and value['status'] == 'passed' and value['cases'] == list(ROSTER),
         'complete exact twenty-three-case result roster')
    need(type(value['managed_reserved_bytes']) is int and 0 < value['managed_reserved_bytes'] <= 6291456
         and type(value['ci_proc_grant']) is int and value['ci_proc_grant'] == 262144
         and type(value['real_kernel_cases']) is int and value['real_kernel_cases'] == 7
         and type(value['inert_logic_cases']) is int and value['inert_logic_cases'] == 16,
         'same selected case accounting')
    elapsed = value['elapsed_seconds']
    need(type(elapsed) in (int,float) and math.isfinite(elapsed) and 0 <= elapsed < 15,
         'original harness interval')
    need(all(value[k] is False for k in ('Docker_executed','model_science_or_data_executed',
                                        'qualification_issued')), 'engineering scope only')
    return value


def execute(args, state):
    here = exact_path(str(Path(__file__).absolute()))
    tests = here.parent
    harness = exact_path(args.harness)
    selection = exact_path(args.selection)
    need(harness == tests/'owner_controls.py' and selection == tests/'source_selection.json',
         'fixed sibling harness and selector')
    selected = parse(state.source(selection,args.selection_bytes,args.selection_sha256,SELECTION_CAP))
    need(type(selected) is dict and set(selected) == {'root','files'}
         and selected['root'] == PACKAGE_ROOT and type(selected['files']) is dict
         and set(selected['files']) == set(SOURCE_NAMES), 'fixed repository-relative ten-source selector')
    package = exact_path(str((Path.cwd()/PACKAGE_ROOT).absolute()))
    need(package == tests.parent/'package', 'selected checkout root joins actual sibling package')
    for descriptor in selected['files'].values():
        need(type(descriptor) is dict and set(descriptor) == {'bytes','sha256'}, 'exact selected source pin')
    body = state.source(harness,args.harness_bytes,args.harness_sha256,HARNESS_CAP)
    temp = exact_path(os.environ.get('RUNNER_TEMP',''))
    output = exact_path(args.output)
    need(output.parent == temp and output.name.startswith('neural083-owner-')
         and len(output.name) <= 96 and all(c.isalnum() or c in '-_' for c in output.name),
         'one fresh selected RUNNER_TEMP output directory')
    t = temp.lstat()
    need(stat.S_ISDIR(t.st_mode) and t.st_uid == os.getuid(), 'owned runner temporary root')
    os.mkdir(output,0o700)
    state.output = output
    state.tick()
    python = str(exact_path(str(Path(sys.executable).resolve())))
    cwd = str(exact_path(str(Path.cwd())))
    argv = [python,'-I','-S','-B','-c',BOOTSTRAP,base64.b64encode(body).decode('ascii'),
            str(harness),args.harness_sha256,repr(state.work_end),'--selection',str(selection),
            '--selection-bytes',str(args.selection_bytes),'--selection-sha256',args.selection_sha256]
    need(sum(len(x.encode())+1 for x in argv) <= 65536, 'bounded fixed captured startup argv')
    state.invocation=dict(executable=python,version=sys.version[:1024],
        version_info=list(sys.version_info),implementation=platform.python_implementation(),
        platform=sys.platform,machine=platform.machine(),cwd=cwd,
        environment={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'},
        argv_projection=argv[:6]+[{'base64_of_captured_harness':
            {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}}]+argv[7:],
        argv_projection_kind='exact nonpayload argv; replace index6 with base64 of authenticated captured harness',
        raw_complete_argv_retained=False)
    # Do not mask the parent's deadline or the child's inherited signals.
    # If Popen is interrupted before returning, the dedicated subreaper census
    # still owns that lineage; unavailable original streams stay explicit.
    state.no_children = False
    state.spawn_attempted = True
    state.process = subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,bufsize=0,start_new_session=True,close_fds=True,
        env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
    state.spawn_returned = True
    state.child(state.process.pid,'harness')
    state.capture_streams()
    if state.first is not None:raise OuterFailure(state)
    harness_child = state.children[0]
    while True:
        state.tick()
        state.drain()
        state.reap(harness_child)
        if state.first is not None:
            raise OuterFailure(state)
        if harness_child['reaped']:
            need(state.natural_code == 0, 'harness natural exit must be zero')
            need(state.empty(), 'harness left an adopted child or unknown child state')
            if all(state.eof.values()):
                break
    state.result = admit_result(bytes(state.streams['stdout']))
    state.tick()


def emit_logs(state):
    # JSON/base64 preserves original bytes without GitHub workflow-command syntax.
    for fd,name in ((1,'stdout'),(2,'stderr')):
        value=state.streams[name]
        raw=(json.dumps(dict(original_harness_stream=name,bytes=len(value),
            sha256=hashlib.sha256(value).hexdigest(),base64=base64.b64encode(value).decode('ascii')),
            sort_keys=True)+'\n').encode()
        position = 0
        while position < len(raw):
            state.tick(True)
            n = os.write(fd,memoryview(raw)[position:])
            need(n > 0, 'original stream log progress')
            position += n
    state.logs_complete = True
    if state.owner_receipt_raw is not None:
        value=state.owner_receipt_raw
        raw=(json.dumps(dict(original_owner_receipt='OWNER.json',
            phase='exact_prepublication_snapshot',bytes=len(value),
            sha256=hashlib.sha256(value).hexdigest(),
            base64=base64.b64encode(value).decode('ascii')),sort_keys=True)+'\n').encode()
        need(len(raw)<=90112,'bounded original OWNER remote log frame')
        position=0
        while position<len(raw):
            state.tick(True)
            n=os.write(1,memoryview(raw)[position:])
            need(n>0,'original OWNER log progress')
            position+=n
        state.owner_receipt_logged=True


def main():
    state = State(time.monotonic())
    parser = argparse.ArgumentParser(allow_abbrev=False)
    for name in ('harness','harness-sha256','selection','selection-sha256','output'):
        parser.add_argument('--'+name,required=True)
    for name in ('harness-bytes','selection-bytes'):
        parser.add_argument('--'+name,required=True,type=int)
    args = parser.parse_args()
    cleanup_started = False
    def interrupted(number,*_):
        raise TimeoutError('original outer timer or interruption '+str(number))
    try:
        need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'dedicated runner has no inherited alarm')
        for number in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):
            state.signals_before[number] = signal.getsignal(number)
            signal.signal(number,interrupted)
        state.tick()
        signal.setitimer(signal.ITIMER_REAL,state.work_end-time.monotonic())
        platform_admit(state)
        execute(args,state)
    except BaseException as error:
        if not isinstance(error,OuterFailure):
            state.fail('outer-work',error)
    finally:
        # The cleanup clock is the original origin+27, never now+2.
        try:
            if state.signals_before:
                signal.setitimer(signal.ITIMER_REAL,0)
                if time.monotonic() < state.final_end:
                    signal.setitimer(signal.ITIMER_REAL,state.final_end-time.monotonic())
        except BaseException as error:
            state.fail('cleanup-timer-admission',error)
        try:
            if state.subreaper_active and (state.first is not None or not state.no_children):
                cleanup_started = True
                state.cleanup()
        except BaseException as error:
            state.fail('outer-cleanup',error)
        try:
            state.close()
        except BaseException as error:
            state.fail('outer-final-descriptor-close',error)
        if state.subreaper_active and state.no_children:
            try:
                subreaper(state,state.subreaper_before)
                state.subreaper_restored = True
                state.subreaper_active = False
            except BaseException as error:
                state.fail('subreaper-restore',error)
    if state.output is not None:
        for name in ('stdout','stderr'):
            try:
                state.publish(name+'.bin',bytes(state.streams[name]))
            except BaseException as error:
                state.fail('stream-publication-'+name,error)
        try:
            raw = (json.dumps(state.record(),sort_keys=True,allow_nan=False)+'\n').encode()
            need(len(raw)<=RECEIPT_CAP,'bounded prepublication owner receipt')
            state.owner_receipt_raw=raw
            state.publish('OWNER.json',raw)
            fd = os.open(state.output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:
                state.tick(True)
                os.fsync(fd)
            except BaseException as error:
                state.fail('receipt-directory-fsync',error)
            finally:
                try:os.close(fd)
                except BaseException as error:state.fail('receipt-directory-close',error)
        except BaseException as error:
            state.fail('owner-receipt-publication',error)
    try:
        emit_logs(state)
    except BaseException as error:
        state.fail('original-stream-log-publication',error)
    good = (state.first is None and not state.secondary and not state.errors_overflow
            and state.natural_code == 0 and all(state.eof.values()) and all(state.stream_closed.values())
            and state.no_children and all(child['reaped'] and child['pidfd_closed'] for child in state.children)
            and state.selector_closed and state.subreaper_restored and state.result is not None
            and state.logs_complete and state.owner_receipt_logged
            and len(state.publications) == 3 and all(x['fsynced'] and x['closed'] for x in state.publications)
            and time.monotonic() < state.final_end)
    summary = dict(schema='neural083_linux_ci_final_v1',status='passed' if good else 'failed',
        natural_harness_exit_code=state.natural_code,actual_ECHILD_observed=state.no_children,
        stdout_eof=state.eof['stdout'],stderr_eof=state.eof['stderr'],
        first_error=None if state.first is None else error_record(state.first_stage,state.first),
        secondary_errors=[error_record(stage,error) for stage,error in state.secondary],
        output=None if state.output is None else str(state.output),publication_records=state.publications,
        owner_receipt_remote_log_complete=state.owner_receipt_logged,
        owner_receipt_remote_is_prepublication_snapshot=True,
        cleanup_started=cleanup_started,final_exit_zero_after_signal_restore_required=True,
        late_publication_or_restore_failure_evidence_may_be_unavailable_durably=True,
        whole_tree_RSS_enforced=False,qualification_issued=False)
    raw=(json.dumps(summary,sort_keys=True,allow_nan=False)+'\n').encode()
    state.final_summary=raw
    if len(raw)>RECEIPT_CAP:
        error=ValueError('bounded final owner summary')
        state.fail('final-summary-size',error)
        raise OuterFailure(state) from error
    try:
        position=0
        while position<len(raw):
            state.tick(True)
            n=os.write(1,memoryview(raw)[position:])
            if n<=0:raise OSError('final owner summary write made no progress')
            position+=n
    except BaseException as error:
        state.fail('final-summary-publication',error)
        raise OuterFailure(state) from error
    try:
        state.tick(True)
        if state.signals_before:
            signal.setitimer(signal.ITIMER_REAL,0)
        for number,handler in state.signals_before.items():
            signal.signal(number,handler)
        state.final_signal_restore_complete=True
    except BaseException as error:
        state.fail('outer-final-signal-restore',error)
        raise OuterFailure(state) from error
    return 0 if good and state.first is None and time.monotonic()<state.final_end else 2


if __name__=='__main__':
    raise SystemExit(main())
