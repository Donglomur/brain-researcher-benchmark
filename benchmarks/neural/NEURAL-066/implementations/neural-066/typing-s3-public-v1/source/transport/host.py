"""Independent gated controller observer, adapted from exact reviewed H watch.

Complete programme authentication is the owner's responsibility before calling.
This observer never claims to observe its own caller or unknown daemon children.
"""
import failures
import math, os, selectors, signal, subprocess, time
from .io import need, pin, failure
from .vendor.engine import BOOTSTRAP, process_identity, cleanup_all

def absent(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False

def observe_controller(argv, root, clock, work_deadline, budget, grace, log_cap, host_memory):
    import resource
    origin, end = (clock['origin'], clock['deadline'])
    need(all((type(v) in (int, float) and math.isfinite(v) for v in (origin, end, work_deadline))) and 0 <= origin < work_deadline < end, 'Original work/outer terminal clocks')
    need(type(argv) is list and len(argv) >= 2 and argv[0].startswith('/') and all((type(v) is str and '\x00' not in v for v in argv)), 'Exact authenticated host argv')
    need(all((type(v) is int and v > 0 for v in (grace, log_cap, host_memory))) and work_deadline + grace <= end, 'Prospective complete observer limits')
    need(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'Separately qualified Linux pidfd primitives')

    def limits():
        os.umask(63)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_AS, (host_memory, host_memory))
    env = {'PATH': '/usr/bin:/bin', 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'TZ': 'UTC', 'LC_ALL': 'C'}
    process = None
    selector = None
    pidfd = None
    token = None
    code = None
    primary = None
    cleanup = []
    forced = False
    reaped = False
    group_absent = False
    identity_actual = 0
    identity_reserved = 0
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    started = budget.tick()
    need(origin <= started < work_deadline, 'Original cutoff immediately before observer launch')

    def reserve_identity(n):
        nonlocal identity_reserved
        budget.read(n)
        identity_reserved += n

    def account_identity(n):
        nonlocal identity_actual
        identity_actual += n
    try:
        process = subprocess.Popen([argv[0], '-I', '-S', '-B', '-c', BOOTSTRAP, *argv], cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, close_fds=True, preexec_fn=limits)
        pidfd = os.pidfd_open(process.pid, 0)
        token = process_identity(process.pid, work_deadline, account_identity, reserve_identity)
        budget.event({'event': 'N065-CONTROLLER-CHILD', 'process_identity': token, 'exec_still_gated': True, 'argv': argv, 'original_origin': origin, 'original_end': end})
        need(budget.tick() < work_deadline and os.write(process.stdin.fileno(), b'G') == 1, 'Durable ownership before one release byte')
        closing_stdin, process.stdin = process.stdin, None
        closing_stdin.close()
        selector = selectors.DefaultSelector()
        for name, stream in (('stdout', process.stdout), ('stderr', process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map() or process.poll() is None:
            need(budget.tick() < work_deadline, 'Original controller work deadline')
            for key, _ in selector.select(min(0.05, max(0, work_deadline - time.monotonic()))):
                remaining = log_cap - sum(map(len, buffers.values()))
                need(remaining >= 0, 'Complete controller logs')
                wanted = min(65536, remaining + 1)
                budget.read(wanted)
                data = os.read(key.fileobj.fileno(), wanted)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.data].extend(data)
                need(len(data) <= remaining, 'Log overflow retained as unadmitted evidence')
        code = process.wait(timeout=max(0, min(grace, end - budget.tick())))
        reaped = True
        group_absent = absent(process.pid)
        need(group_absent, 'Surviving/reused group is unknown, never numerically signaled')
        need(budget.tick() < work_deadline, 'Natural controller close inside original work cutoff')
    except BaseException as error:
        failures.hold(error, 'caught')
        primary = error
        forced = True
        actions = []
        if pidfd is not None:

            def kill():
                try:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL, None, 0)
                except ProcessLookupError:
                    pass
            actions.append(('controller.pidfd_kill', kill))
        if process is not None and process.stdin is not None:
            actions.append(('controller.stdin.close', process.stdin.close))
        if process is not None:

            def reap():
                nonlocal code, reaped
                code = process.wait(timeout=max(0, min(grace, end - time.monotonic())))
                reaped = True
            actions.append(('controller.reap', reap))
        for name, action in actions:
            try:
                action()
            except BaseException as secondary:
                failures.hold(secondary, 'caught')
                cleanup.append({'action': name, **failure(secondary)})
    finally:
        actions = []
        if selector is not None:
            actions.append(('selector.close', selector.close))
        if process is not None:
            actions.extend(((name + '.close', stream.close) for name, stream in (('stdin', process.stdin), ('stdout', process.stdout), ('stderr', process.stderr)) if stream is not None))
        if pidfd is not None:
            actions.append(('pidfd.close', lambda: os.close(pidfd)))
        for name, action in actions:
            try:
                action()
            except BaseException as secondary:
                failures.hold(secondary, 'caught')
                cleanup.append({'action': name, **failure(secondary)})
    try:
        group_absent = process is None or absent(process.pid)
    except BaseException as secondary:
        failures.hold(secondary, 'caught')
        cleanup.append({'action': 'group.absence', **failure(secondary)})
        group_absent = False
    try:
        finished = budget.tick()
        need(finished < end, 'Final original observer cutoff')
    except BaseException as secondary:
        failures.hold(secondary, 'caught')
        cleanup.append({'action': 'final_clock', **failure(secondary)})
        finished = time.monotonic()
    complete = primary is None and (not cleanup) and (not forced) and (code == 0) and reaped and group_absent and (origin <= started <= finished < work_deadline)
    result = {'schema': 'neural066_independent_controller_close_v1', 'argv': argv, 'process_identity': token, 'started': started, 'finished': finished, 'origin': origin, 'work_deadline': work_deadline, 'global_deadline': end, 'exit_code': code, 'natural_exit': complete, 'forced': forced, 'reaped': reaped, 'process_group_absent': group_absent, 'error': None if primary is None else failure(primary), 'cleanup_errors': cleanup, 'logs': {k: pin(bytes(v)) for k, v in buffers.items()}, 'logs_data': {k: bytes(v) for k, v in buffers.items()}, 'transitive_daemon_custody': 'requires_separate_resource_join', 'caller_custody_claim': False, 'identity_metadata_actual_bytes': identity_actual, 'identity_metadata_precharged_bytes': identity_reserved, 'log_accounting': 'Prospective requested-read bytes charged before reads, not actual physical I/O', 'enforced_host_address_space_bytes': host_memory, 'exact_RSS': None}
    return result
