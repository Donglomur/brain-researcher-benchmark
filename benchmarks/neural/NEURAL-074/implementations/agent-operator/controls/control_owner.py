"""N074 eleven operator checks; source-only finite execution proposal.

The original exclusive-child ownership mechanisms are retained; Linux admission is explicit.
The old N059 regression suites are not selected or executed by this launcher.
Only admission, fixed caller/paths, composite reservations and child source
handoff are adapted. No scientific/native-owner qualification follows.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import sys
import time
import threading
import sysconfig


CAP = 65536
MIB = 1048576


def need(value, reason):
    if not value:
        raise ValueError(reason)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def capture(path, row):
    need(type(row['bytes']) is int and 0 < row['bytes'] <= MIB, 'bounded selected body')
    path = Path(path)
    need(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary source ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    first = None; body = None; errors = []
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == row['bytes'], 'exact source extent')
        parts = []; left = row['bytes'] + 1
        while left:
            piece = os.read(fd, min(left, 65536))
            if not piece:
                break
            parts.append(piece); left -= len(piece)
        body = b''.join(parts); after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(before, k) == getattr(after, k) for k in fields) and
             pin(body) == {k: row[k] for k in ('bytes', 'sha256')}, 'selected source identity/body')
    except BaseException as exc:
        first = exc
    try:
        os.close(fd)
    except BaseException as exc:
        errors.append(exc)
    if first is not None:
        first.supervisor_cleanup_errors = tuple(errors)
        raise first
    if errors:
        raise errors[0]
    return body


def write_new(root, name, body, *, deadline):
    need('/' not in name and len(body) <= 131072, 'finite supervisor record')
    deadline()
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    first = None; extra = []
    try:
        offset = 0
        while offset < len(body):
            deadline()
            n = os.write(fd, memoryview(body)[offset:])
            need(type(n) is int and 0 < n <= len(body) - offset, 'observed complete record write')
            offset += n
        deadline()
        os.fsync(fd)
    except BaseException as exc:
        first = exc
    try:
        os.close(fd)
    except BaseException as exc:
        if first is None:
            first = exc
        else:
            extra.append(exc)
    try:
        deadline()
    except BaseException as exc:
        if first is None:
            first = exc
        else:
            extra.append(exc)
    if first is not None:
        first.supervisor_cleanup_errors = tuple(extra)
        raise first
    if extra:
        raise extra[0]
    return dict(path=name, **pin(body))


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def error_row(stage, exc):
    # Only this closed, source-reviewed stdlib control graph supplies errors.
    return {'stage': stage, 'type': type(exc).__name__, 'message': str(exc)[:4096]}



# Exactly eleven accepted N074 operator tests; no native owner child.
HARNESS_PIN = {'bytes': 6198, 'sha256': 'e1e1746c236a32418e20febe5368f6885de859b65aec7be4ad2adef23f8ff4f5'}
INTERPRETER = str(Path(sys.executable).resolve(strict=True))


class ChildOwner:
    """The sole waiter. Injected ops are used only by the separately pinned inert checks."""
    def __init__(self, guard, ops=os):
        self.guard = guard
        self.ops = ops
        self.pid = None
        self.state = 'not_spawned'
        self.signal_authority = False
        self.stop_attempted = False
        self.wait_calls = 0
        self.zero_results = 0
        self.raw_status = None
        self.returncode = None
        self.group_probe = 'not_observed'
        self.signal_operations = []

    def adopt(self, pid):
        need(self.state == 'not_spawned' and type(pid) is int and pid > 0, 'one exact child adoption')
        self.pid = pid
        self.state = 'owned_unreaped'
        self.signal_authority = True

    def wait_once(self):
        need(self.state == 'owned_unreaped', 'wait requires original unreaped child')
        # Retire BEFORE guard or wait. Any exception/ambiguous result loses ownership.
        self.signal_authority = False
        self.state = 'wait_in_progress'
        self.wait_calls += 1
        try:
            self.guard()
            got, status = self.ops.waitpid(self.pid, os.WNOHANG)
            need(type(got) is int and type(status) is int, 'exact builtin wait result')
            if got == 0:
                need(status == 0, 'zero wait status')
                self.guard()
                self.zero_results += 1
                self.state = 'owned_unreaped'
                self.signal_authority = not self.stop_attempted
                return False
            need(got == self.pid, 'wait returned another child')
            need(os.WIFEXITED(status) or os.WIFSIGNALED(status), 'terminal original wait status')
            # No operation after this point can reacquire destructive authority.
            self.raw_status = status
            self.returncode = os.waitstatus_to_exitcode(status)
            self.state = 'reaped'
            return True
        except BaseException:
            self.state = 'ownership_lost'
            self.signal_authority = False
            raise

    def stop_unreaped(self):
        # A terminal/lost owner never performs even an attempted destructive signal.
        if self.state != 'owned_unreaped' or not self.signal_authority:
            return False
        self.signal_authority = False
        self.stop_attempted = True
        try:
            self.guard()
        except BaseException:
            self.state = 'ownership_lost'
            raise
        # Exclusive wait ownership plus a default/reinstalled SIGCHLD retains the
        # original PID even if it has already become a zombie. The PID therefore
        # cannot name a different process group before this owner reaps.
        self.signal_operations.append('unreaped_group_SIGKILL')
        try:
            self.ops.killpg(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            # Child may not yet have executed setsid. Its still-unreaped exact PID
            # remains ours. No wait occurs between these two bounded operations.
            self.signal_operations.append('unreaped_pre_setsid_PID_SIGKILL')
            try:
                self.ops.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return True

    def observe_absence(self):
        need(self.pid is not None, 'group probe needs original child identity')
        # Numeric PGID after reaping is only a read-only observation. A reused
        # group can cause a conservative refusal, never cleanup of that group.
        try:
            self.ops.killpg(self.pid, 0)
        except ProcessLookupError:
            self.group_probe = 'absent'
            return True
        except BaseException:
            self.group_probe = 'unestablished'
            raise
        self.group_probe = 'present_or_reused'
        return False

    def evidence(self):
        return {'pid': self.pid, 'state': self.state, 'signal_authority': self.signal_authority,
                'stop_attempted': self.stop_attempted, 'wait_calls': self.wait_calls,
                'zero_wait_results': self.zero_results, 'raw_wait_status': self.raw_status,
                'returncode': self.returncode, 'group_probe': self.group_probe,
                'signal_operations': list(self.signal_operations)}


def capture_configurable_handlers(signal_api=signal):
    """Capture only signals that can carry a configurable child-reaping handler.

    Mac CPython may report None for SIGKILL/SIGSTOP. They cannot be caught,
    ignored or blocked, so neither can execute a competing waiter. None remains
    forbidden for every catchable signal; no signal disposition is reset here.
    """
    handlers = {}
    for number in sorted(signal_api.valid_signals()):
        if number in (signal_api.SIGKILL, signal_api.SIGSTOP):
            continue
        handler = signal_api.getsignal(number)
        allowed = handler in (signal_api.SIG_DFL, signal_api.SIG_IGN) or (
            number == signal_api.SIGINT and handler is signal_api.default_int_handler)
        need(allowed, 'no unknown or arbitrary child-reaping signal handler')
        handlers[number] = handler
    need(handlers[signal_api.SIGCHLD] == signal_api.SIG_DFL,
         'inherited SIGCHLD must be default')
    return handlers


def guard_configurable_handlers(handlers, signal_api=signal):
    need(all(signal_api.getsignal(n) is h or signal_api.getsignal(n) == h
             for n, h in handlers.items()), 'wait-owner signal dispositions unchanged')


def exclusive_admission():
    need(sys.platform == 'linux' and sys.implementation.name == 'cpython' and
         sys.version_info[:3] == (3, 11, 18), 'selected Linux CPython 3.11.18 only')
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and not sys.flags.optimize,
         'fresh isolated -I -S -B supervisor')
    need(sys.gettrace() is None and sys.getprofile() is None, 'no external trace/profile hooks')
    need(sysconfig.get_config_var('HAVE_SIGACTION') == 1, 'selected sigaction implementation required')
    main = threading.main_thread()
    def threads():
        need(threading.current_thread() is main and threading.enumerate() == [main],
             'exclusive single main thread wait ownership')
    threads()
    handlers = capture_configurable_handlers()
    # CPython v3.11.18 PyOS_setsig installs SA_ONSTACK, replacing flags, so this
    # also removes inherited SA_NOCLDWAIT. Do not infer flags from getsignal.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    def guard():
        threads()
        need(sys.gettrace() is None and sys.getprofile() is None, 'wait-owner hooks unchanged')
        guard_configurable_handlers(handlers)
    guard()
    return guard, handlers


METHODS = ["test_actual_submission_commit_and_separate_evaluation","test_late_candidate_disposition_rejected_before_target","test_changed_native_prediction_cannot_be_recommitted","test_failed_candidate_keeps_complete_roster_and_no_targets","test_unclosed_owner_preserves_exact_failure_evidence","test_wrong_training_selection_refused_before_workspace_creation","test_changed_budget_cannot_keep_the_same_policy_identity","test_overlapping_workspace_refused_before_mutation","test_changed_target_pin_rejected_at_owner_admission","test_reused_context_is_not_a_new_fold","test_late_reference_file_tamper_has_zero_target_calls"]

def validate_fixed(config, group, config_bytes, deadline):
    base=Path(__file__).absolute().parent.parent
    selected=config['groups'][group]
    need(config['schema']=='n074_public_operator_supervisor_v1' and
         list(config['groups'])==['all11'] and group=='all11','one fixed all11 group')
    need(selected['seconds']==180 and selected['transfer_bytes']==1024*MIB and
         selected['retained_bytes']==32*MIB,'original finite reservation')
    need(config['working_directory']==str(base) and
         config['interpreter']==INTERPRETER,'actual selected interpreter/origin')
    stage=Path(config['stage'])
    need(stage.is_absolute() and stage.name=='neural074-operator-ci-v1' and
         not any(x.is_symlink() for x in (stage,*stage.parents)) and
         base not in stage.parents and stage not in base.parents,'ordinary disjoint runner output')
    selection_path=base/'controls/ENGINEERING_SELECTION.json'
    expected=[INTERPRETER,'-I','-S','-B',str(base/'controls/run_controls.py'),
              '--selection',str(selection_path),'--selection-bytes',str(HARNESS_PIN['bytes']),
              '--selection-sha256',HARNESS_PIN['sha256'],'--source-root',str(base),
              '--output',str(stage/'child')]
    need(selected['argv']==expected and selected['output_root']==str(stage/'outer'),
         'exact captured child and destinations')
    deadline()
    selection=json.loads(capture(selection_path,HARNESS_PIN))
    need(selection['schema']=='n074_public_operator_controls_v1' and
         selection['methods']==METHODS and selection['attempts']==1 and
         selection['native_scientific_execution'] is False,'exact unchanged eleven controls')
    self_row=config['operative_supervisor']
    need(self_row['path']==str(Path(__file__).absolute()),'operative outer source')
    need(selection['launcher']['path']=='controls/run_controls.py','public child path')
    rows=[self_row,dict(selection['launcher'],path=str(base/selection['launcher']['path'])),
          *[dict(r,path=str(base/r['path'])) for r in selection['modules']],
          dict(path=str(selection_path),**HARNESS_PIN)]
    need(selected['source_files']==rows and len(selection['modules'])==20,'complete source selection')
    charge=config_bytes+1+HARNESS_PIN['bytes']+1+sum(r['bytes']+1 for r in rows)
    need(charge<=2*MIB,'finite complete source admission')
    child_body=None
    for row in rows:
        deadline();body=capture(row['path'],row)
        if row['path']==expected[4]:child_body=body
    need(child_body is not None,'authenticated child body')
    deadline()
    return charge,child_body


CHILD_BOOTSTRAP = ("import sys; p=sys.argv[2]; b=bytes.fromhex(sys.argv[1]); "
                   "sys.argv=[p]+sys.argv[3:]; "
                   "exec(compile(b,p,'exec',dont_inherit=True),"
                   "{'__name__':'__main__','__file__':p})")

def supervise(config, group, original_start, config_bytes):
    selected = config['groups'][group]
    out = Path(selected['output_root'])
    need(out.is_absolute() and not out.exists() and not any(p.is_symlink() for p in out.parents),
         'fresh ordinary outer record root')
    out.mkdir(mode=0o700)
    os.chmod(out, 0o700)
    end = original_start + 180
    actor_end = end - 1.0
    receipt = {'schema': 'n074_public_operator_actual_engineering_supervisor_v1', 'group': group,
        'argv': selected['argv'], 'maximum_attempts': 1, 'automatic_retry': False,
        'attempt_transfer_charge': 1024 * MIB, 'retained_envelope': 32 * MIB,
        'original_monotonic_start': original_start, 'original_monotonic_end': end,
        'actor_deadline': actor_end, 'errors': [], 'prefix_files': {},
        'source_read_bytes': config_bytes + 1, 'child_started': False,
        'natural_exit_observed': False, 'returncode': None, 'group_absent': False,
        'forced_kill_attempted': False, 'combined_stream_cap': CAP,
        'streams_eof': {'stdout': False, 'stderr': False},
        'observed_stream_bytes': {'stdout': 0, 'stderr': 0},
        'retained_stream_bytes': {'stdout': 0, 'stderr': 0},
        'native_or_scientific_execution': False}
    first = None
    selector = None
    owner = None
    fds = {}
    chunks = {'stdout': [], 'stderr': []}
    combined = 0
    mask_restore = None
    handlers = None

    def fail(stage, exc):
        nonlocal first
        if first is None:
            first = exc
        receipt['errors'].append(error_row(stage, exc))
        for extra in getattr(exc, 'supervisor_cleanup_errors', ()):
            receipt['errors'].append(error_row(stage + '.close', extra))

    def whole_time():
        need(time.monotonic() < end, 'original whole-child and publication horizon exhausted')

    def original_time():
        need(time.monotonic() < actor_end, 'original child deadline; cleanup reserve retained')

    def close_fd(name):
        fd = fds.pop(name, None)  # Retire before close; an ambiguous close is not retried.
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                fail(name + '.close', exc)

    try:
        receipt['source_read_bytes'], child_body = validate_fixed(
            config, group, config_bytes, original_time)
        guard, handlers = exclusive_admission()
        owner = ChildOwner(guard)
        receipt['admission'] = {'fresh_single_main_thread': True, 'sigchld_default_reinstalled': True,
                                'sigaction_flags_basis': 'CPython v3.11.18 SA_ONSTACK replacement',
                                'no_Popen_or_external_waiter': True,
                                'uncatchable_signals_excluded': [int(signal.SIGKILL), int(signal.SIGSTOP)],
                                'catchable_unknown_handlers_allowed': False}
        initial = encoded(receipt)
        need(len(initial) <= 16384, 'finite initial attempt metadata')
        write_new(out, 'ATTEMPT.json', initial, deadline=original_time)
        # Historical N059 regressions remain genuine evidence; none is rerun.
        receipt['selected_test_count'] = 11
        receipt['historical_owner_regressions_rerun'] = False
        effective_argv = [INTERPRETER, '-I', '-S', '-B', '-c', CHILD_BOOTSTRAP,
                          child_body.hex(), selected['argv'][4], *selected['argv'][5:],
                          '--origin', repr(original_start),
                          '--deadline', repr(original_start + 175.0)]
        receipt['actual_exec_argv_identity'] = pin(encoded(effective_argv))
        receipt['captured_child_body'] = pin(child_body)
        receipt['child_original_deadline'] = original_start + 175.0
        original_time()
        # Save the original mask before blocking. No child exists if this call
        # itself is interrupted. PID/FD adoption occurs with callable signals blocked.
        mask_restore = signal.pthread_sigmask(signal.SIG_BLOCK, [])
        blockable = signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP}
        signal.pthread_sigmask(signal.SIG_BLOCK, blockable)
        guard()
        for standard in (0, 1, 2):
            os.fstat(standard)  # Do not allow pipes to alias a missing standard FD.
        fds['stdin'] = os.open('/dev/null', os.O_RDONLY | os.O_NOFOLLOW)
        fds['stdout_read'], fds['stdout_write'] = os.pipe()
        fds['stderr_read'], fds['stderr_write'] = os.pipe()
        original_time()
        pid = os.fork()
        if pid == 0:
            try:
                os.setsid()
                os.chdir(config['working_directory'])
                os.dup2(fds['stdin'], 0)
                os.dup2(fds['stdout_write'], 1)
                os.dup2(fds['stderr_write'], 2)
                for fd in fds.values():
                    os.close(fd)
                signal.pthread_sigmask(signal.SIG_SETMASK, mask_restore)
                os.execve(INTERPRETER, effective_argv, {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                    'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                    'VECLIB_MAXIMUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'})
            except BaseException:
                try:
                    os.write(2, b'n074 operator supervisor child exec setup failed\n')
                finally:
                    os._exit(127)
        owner.adopt(pid)  # No pending Python signal can discard the returned PID first.
        receipt['child_started'] = True
        receipt['pid'] = pid
        signal.pthread_sigmask(signal.SIG_SETMASK, mask_restore)
        mask_restore = None
        for name in ('stdin', 'stdout_write', 'stderr_write'):
            close_fd(name)
        need(first is None, 'spawn descriptor closure failed')
        selector = selectors.DefaultSelector()
        for role in ('stdout', 'stderr'):
            fd = fds[role + '_read']
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ, role)
        while selector.get_map():
            original_time()
            for key, _ in selector.select(min(.025, max(0, actor_end - time.monotonic()))):
                original_time()
                piece = os.read(key.fd, min(8192, CAP - combined + 1))
                if not piece:
                    receipt['streams_eof'][key.data] = True
                    selector.unregister(key.fd)
                    continue
                receipt['observed_stream_bytes'][key.data] += len(piece)
                keep = min(len(piece), CAP - combined)
                if keep:
                    chunks[key.data].append(piece[:keep])
                    receipt['retained_stream_bytes'][key.data] += keep
                combined += len(piece)
                need(combined <= CAP, 'original combined64KiB stream cap')
        while owner.state == 'owned_unreaped':
            original_time()
            if owner.wait_once():
                break
            time.sleep(min(.005, max(0, actor_end - time.monotonic())))
        original_time()
        receipt['natural_exit_observed'] = owner.state == 'reaped' and not owner.stop_attempted
        receipt['returncode'] = owner.returncode
        need(receipt['natural_exit_observed'] and owner.returncode == 0,
             'authentic natural engineering child returned nonzero')
    except BaseException as exc:
        fail('body', exc)
    finally:
        if owner is not None and owner.pid is not None:
            # This method is an explicit no-op after terminal/ambiguous wait.
            try:
                whole_time()
                owner.stop_unreaped()
            except BaseException as exc:
                fail('cleanup.signal_unreaped', exc)
            if owner.state == 'owned_unreaped':
                try:
                    while owner.state == 'owned_unreaped':
                        whole_time()
                        if owner.wait_once():
                            break
                        time.sleep(min(.005, max(0, end - time.monotonic())))
                except BaseException as exc:
                    fail('cleanup.exact_wait', exc)
            try:
                whole_time()
                need(owner.observe_absence(), 'post-wait group absence unestablished; no signal permitted')
            except BaseException as exc:
                fail('cleanup.readonly_group_probe', exc)
            receipt['child_owner'] = owner.evidence()
            receipt['group_absent'] = owner.group_probe == 'absent'
            receipt['forced_kill_attempted'] = owner.stop_attempted
            receipt['returncode'] = owner.returncode
            if owner.state != 'reaped':
                fail('cleanup.wait_ownership', ValueError('original child reap unestablished'))
        if selector is not None:
            try:
                selector.close()
            except BaseException as exc:
                fail('selector.close', exc)
        for name in tuple(fds):
            close_fd(name)
        if mask_restore is not None:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask_restore)
            except BaseException as exc:
                fail('signal_mask.restore', exc)
        # SIGCHLD was admitted default and remains default. Reinstalling it again
        # preserves that disposition; no prior nondefault semantics are overwritten.
        if handlers is not None:
            try:
                signal.signal(signal.SIGCHLD, handlers[signal.SIGCHLD])
            except BaseException as exc:
                fail('sigchld.restore', exc)
    receipt['closure_observed_elapsed_seconds'] = time.monotonic() - original_start
    receipt['combined_observed_stream_bytes'] = combined
    receipt['snapshot_before_own_publication'] = True
    receipt['requires_outer_natural_exit_zero_after_final_deadline_check'] = True
    try:
        whole_time()
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['child_usage'] = {'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime,
                                 'maxrss_raw': usage.ru_maxrss, 'maxrss_unit': 'KiB on selected Linux',
                                 'known_live_is_not_a_hard_RSS_limit': True}
        whole_time()
    except BaseException as exc:
        fail('usage_or_deadline', exc)
    for role in ('stdout', 'stderr'):
        try:
            receipt['prefix_files'][role] = write_new(out, role + '.prefix', b''.join(chunks[role]), deadline=whole_time)
        except BaseException as exc:
            fail(role + '.publication', exc)
    receipt['first_error_type'] = None if first is None else type(first).__name__
    receipt['prepublication_success'] = (first is None and receipt['natural_exit_observed'] and
        receipt['returncode'] == 0 and receipt['group_absent'] and not receipt['forced_kill_attempted'] and
        all(receipt['streams_eof'].values()))
    final_success = False
    published_error_count = 0
    try:
        whole_time()
        body = encoded(receipt)
        row = write_new(out, 'SUPERVISOR.json', body, deadline=whole_time)
        published_error_count = len(receipt['errors'])
        whole_time()
        final_success = first is None and receipt['prepublication_success']
        print(json.dumps({'group': group, 'receipt': str(out / 'SUPERVISOR.json'), **row,
              'success': final_success, 'elapsed_after_record_close': time.monotonic() - original_start},
              sort_keys=True), flush=True)
        whole_time()
    except BaseException as exc:
        fail('receipt_or_final_deadline', exc)
        final_success = False
        # One bounded fallback; last-transport failure remains incomplete evidence.
        try:
            body = encoded({'group': group, 'success': False, 'complete_durable_record_unavailable': True,
                'first_error_type': type(first).__name__, 'known_unpublished_errors': receipt['errors'][published_error_count:],
                'scope': 'single fallback; failed final transport is incomplete, never success'})
            need(len(body) <= 24576, 'finite supervisor fallback')
            sys.stderr.write(body.decode())
            sys.stderr.flush()
            whole_time()
        except BaseException:
            pass
    return 0 if first is None and final_success else 1


def main():
    original_start=time.monotonic()
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--owner-bytes',required=True,type=int)
    parser.add_argument('--owner-sha256',required=True)
    args=parser.parse_args()
    base=Path(__file__).absolute().parent.parent
    stage=Path(args.output)
    need(stage.is_absolute() and len(str(stage))<=384 and
         stage.name=='neural074-operator-ci-v1' and not stage.exists() and
         stage.parent.is_dir() and
         not any(x.is_symlink() for x in (stage,*stage.parents)) and
         base not in stage.parents and stage not in base.parents,'fresh ordinary runner output')
    selection_path=base/'controls/ENGINEERING_SELECTION.json'
    raw=capture(selection_path,HARNESS_PIN);selection=json.loads(raw)
    need(time.monotonic()<original_start+175.,'original capture horizon')
    owner=dict(path=str(Path(__file__).absolute()),bytes=args.owner_bytes,sha256=args.owner_sha256)
    rows=[owner,dict(selection['launcher'],path=str(base/selection['launcher']['path'])),
          *[dict(r,path=str(base/r['path'])) for r in selection['modules']],
          dict(path=str(selection_path),**HARNESS_PIN)]
    argv=[INTERPRETER,'-I','-S','-B',str(base/'controls/run_controls.py'),
          '--selection',str(selection_path),'--selection-bytes',str(HARNESS_PIN['bytes']),
          '--selection-sha256',HARNESS_PIN['sha256'],'--source-root',str(base),
          '--output',str(stage/'child')]
    config={'schema':'n074_public_operator_supervisor_v1','stage':str(stage),
            'working_directory':str(base),'interpreter':INTERPRETER,'operative_supervisor':owner,
            'groups':{'all11':{'seconds':180,'transfer_bytes':1024*MIB,'retained_bytes':32*MIB,
                              'source_files':rows,'argv':argv,'output_root':str(stage/'outer')}}}
    stage.mkdir(mode=0o700);os.chmod(stage,0o700)
    return supervise(config,'all11',original_start,len(raw))


if __name__ == '__main__':
    try:
        code = main()
    except BaseException as exc:
        code = 1
        try:
            sys.stderr.write(json.dumps({'success': False, 'unmanaged_admission_failure': True,
                'type': type(exc).__name__, 'message': str(exc)[:2048]}) + '\n')
            sys.stderr.flush()
        except BaseException:
            pass
    raise SystemExit(code)
