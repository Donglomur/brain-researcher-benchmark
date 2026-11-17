"""Parent-held pidfds for the unchanged Provider's gated Linux CLI children."""
import ctypes
import errno
import os
import resource
import select
import signal
import sys
import time
from common import need

MAX_CHILDREN = 640  # 2 x 256 phase commands plus 2 x 64 recovery commands.


def production_host():
    need(sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(os, 'P_PIDFD')
         and hasattr(signal, 'pidfd_send_signal'), 'Linux pidfd/waitid operator required')
    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    need(soft == resource.RLIM_INFINITY or soft >= 1024,
         'Explicit capacity for 640 retained CLI pidfds and owner descriptors')
    libc = ctypes.CDLL(None, use_errno=True)
    need(libc.prctl(36, 1, 0, 0, 0) == 0, 'Dedicated owner becomes child subreaper')
    observed = ctypes.c_int()
    need(libc.prctl(37, ctypes.byref(observed), 0, 0, 0) == 0 and observed.value == 1,
         'Observed Linux child-subreaper state')


def reap_pidfd(fd):
    try:
        os.waitid(os.P_PIDFD, fd, os.WEXITED | os.WNOHANG)
    except ChildProcessError:
        pass  # Its original controller may already have reaped the exact birth.


class CliCustody:
    def __init__(self, engine, deadline):
        self.engine, self.deadline = engine, deadline
        self.children = []
        self.retired = []
        self.read_bytes = 0
        self.read_cap = MAX_CHILDREN * 3 * 8192

    def account(self, count):
        need(type(count) is int and count >= 0 and self.read_bytes + count <= self.read_cap,
             'Bounded owner process-identity reads')
        self.read_bytes += count

    def reserve(self, count):
        need(self.read_bytes + count <= self.read_cap, 'Remaining identity-read capacity')

    def capture(self, value, cutoff):
        need(len(self.children) + len(self.retired) < MAX_CHILDREN and value['docker_exec_still_gated'] is True
             and value['independent_group'] is True, 'Bounded pre-release CLI custody')
        token = value['process_identity']
        pid = value['pid']
        need(type(pid) is int and pid > 1 and value['pgid'] == pid
             and token['pid'] == token['pgid'] == token['session_id'] == pid,
             'Exact independent CLI session')
        need(time.monotonic() < value['original_end'] <= cutoff <= self.deadline,
             'CLI retains original invocation deadline')
        fd = os.pidfd_open(pid, 0)
        try:
            observed = self.engine.process_identity(pid, value['original_end'], self.account, self.reserve)
            need(observed == token and not select.select([fd], [], [], 0)[0],
                 'Parent binds same live gated birth before acknowledgement')
            self.children.append({'fd': fd, 'token': token, 'original_end': value['original_end']})
        except BaseException:
            os.close(fd)
            raise

    def restore(self, token, cutoff):
        """Recovery only: never signal by a numeric PID or refresh its clock."""
        need(time.monotonic() < cutoff <= self.deadline, 'Recovery before retained cutoff')
        pid = token['pid']
        try:
            fd = os.pidfd_open(pid, 0)
        except ProcessLookupError:
            try:
                os.killpg(token['pgid'], 0)
            except ProcessLookupError:
                return {'process_identity': token, 'already_absent': True}
            raise ValueError('Lost leader with surviving or reused group remains unknown')
        try:
            observed = self.engine.process_identity(pid, cutoff, self.account, self.reserve)
            need(observed == token, 'Same-boot same-birth recovery authority only')
            need(len(self.children) + len(self.retired) < MAX_CHILDREN, 'Bounded recovered CLI set')
            self.children.append({'fd': fd, 'token': token, 'original_end': cutoff})
            return {'process_identity': token, 'already_absent': False}
        except BaseException:
            os.close(fd)
            raise

    def retire_exited(self, durable_observer):
        """Persist actual absence promptly, before a long run can reuse its PGID."""
        for child in tuple(self.children):
            fd, pid = child['fd'], child['token']['pid']
            absent = False
            if select.select([fd], [], [], 0)[0]:
                reap_pidfd(fd)
                try:
                    os.killpg(child['token']['pgid'], 0)
                except ProcessLookupError:
                    absent = True
            if absent:
                row = {'process_identity': child['token'], 'leader_exited': True,
                       'group_absent': True, 'error': None, 'wait_status': None}
                durable_observer(row)  # fsync before releasing the identity handle.
                # Transfer authority one child at a time. A later publication
                # failure must never leave a closed/reused fd in the live set.
                self.children.remove(child)
                self.retired.append(row)
                try:
                    os.close(fd)
                except OSError as exc:
                    row['error'] = type(exc).__name__
                    raise  # A close error is unknown; never signal/close that fd again.

    def close(self, end):
        """Stop every exact child first; one unknown group cannot starve another."""
        end = min(end, self.deadline)
        rows = list(self.retired)
        children = list(self.children)
        new_rows = [{'process_identity': child['token'], 'leader_exited': False,
                     'group_absent': False, 'error': None, 'wait_status': None} for child in children]
        rows.extend(new_rows)
        pending = list(zip(children, new_rows))
        self.retired.clear()
        self.children.clear()
        try:
            for child, row in pending:
                try:
                    # A missed cutoff still allows one exact-handle stop, never
                    # a renewed wait interval or successful late-closure claim.
                    signal.pidfd_send_signal(child['fd'], signal.SIGKILL, None, 0)
                except ProcessLookupError:
                    pass
                except BaseException as exc:
                    row['error'] = type(exc).__name__
            while pending and time.monotonic() < end:
                remaining = []
                for child, row in pending:
                    try:
                        exited = bool(select.select([child['fd']], [], [], 0)[0])
                        if exited:
                            reap_pidfd(child['fd'])
                        try:
                            os.killpg(child['token']['pgid'], 0)
                            absent = False
                        except ProcessLookupError:
                            absent = True
                        if exited and absent:
                            row.update(leader_exited=True, group_absent=True)
                        else:
                            remaining.append((child, row))
                    except BaseException as exc:
                        row['error'] = type(exc).__name__
                pending = remaining
                if pending:
                    time.sleep(min(.01, max(0, end - time.monotonic())))
            for child, row in pending:
                row['error'] = row['error'] or 'OriginalDeadlineOrUnknownGroup'
        except BaseException as exc:
            for child, row in pending:
                row['error'] = row['error'] or type(exc).__name__
                # Independently attempt stop even if an earlier observation
                # raised unexpectedly; numeric PID/group signals are never used.
                try:
                    signal.pidfd_send_signal(child['fd'], signal.SIGKILL, None, 0)
                except BaseException:
                    pass
        finally:
            for child, row in zip(children, new_rows):
                try:
                    os.close(child['fd'])
                except OSError as exc:
                    row['error'] = type(exc).__name__
        return {'all_acknowledged_cli_absent': all(x['leader_exited'] and x['group_absent']
                and x['error'] is None for x in rows), 'records': rows,
                'identity_read_bytes': self.read_bytes,
                'unacknowledged_cli_birth_window_claimed_closed': False}
