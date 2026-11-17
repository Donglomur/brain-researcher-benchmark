"""Owned SMC execution successor; candidate/model use needs separate admission.

Only the trusted source controller runs on the host. Its synchronous callback
cannot release a Provider command before this parent has durable custody.
"""
from pathlib import Path
import argparse
import fcntl
import os
import selectors
import select
import signal
import socket
import subprocess
import sys
import time
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (CONDITIONS, FRAME_CAP, JOURNAL_CAP, OwnerWriter, PAIR_SECONDS, RECOVERY_SECONDS,
                    body, encoded, extract, frame, need, ordinary, pin, publish, read)
from cli_custody import CliCustody, production_host
from journal import ParentJournal
import legacy
import process_owner

CONTROLLER = 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/long-owner-v1/controller.py'


def engine_for(L):
    L.provider_class()
    return sys.modules['_smc_existing_transport.engine']


def recovery_budget(read_bytes, write_bytes):
    need(type(read_bytes) is type(write_bytes) is int
         and 131072 <= read_bytes <= 256 * 1024**2
         and 131072 <= write_bytes <= 64 * 1024**2, 'Explicit finite additional recovery I/O allocation')
    return {'source_read_bytes': read_bytes, 'host_write_bytes': write_bytes,
            'per_phase_cli_calls': 64, 'per_phase_cli_bytes': 2 * 1024**2,
            'max_records': 2048, 'max_record_bytes': FRAME_CAP, 'max_metadata_bytes': 16 * 1024**2}


def make_invocation(protocol_path, expected, output, owner_folder, recovery_reads, recovery_writes):
    L = legacy.load()
    source = legacy.source_identity()
    protocol_path, output, owner_folder = map(ordinary, (protocol_path, output, owner_folder))
    protocol, runtime = L.admit_protocol(protocol_path, expected)
    # Actual provider platform/profile/image evidence is separate from this source.
    L.qualify(runtime, protocol['source'])
    production_host()
    need(not owner_folder.exists() and owner_folder.parent.is_dir() and not output.exists()
         and output.parent.is_dir(), 'Fresh owner and execution roots, no execution resume')
    roots = (owner_folder, output, protocol_path.parent, Path(protocol['pair_path']).parent)
    need(all(not a.is_relative_to(b) and not b.is_relative_to(a)
             for i, a in enumerate(roots) for b in roots[i + 1:]), 'Disjoint private/public/protocol roots')
    recovery = recovery_budget(recovery_reads, recovery_writes)
    owner_folder.mkdir(mode=0o700)
    (owner_folder / 'process').mkdir(mode=0o700)
    (owner_folder / 'events').mkdir(mode=0o700)
    clock = {'outcome': protocol['outcome'], 'origin': time.monotonic(),
             'clock_identity': process_owner.clock_identity()}
    clock['deadline'] = clock['origin'] + PAIR_SECONDS[clock['outcome']]
    clock['controller_deadline'] = clock['deadline'] - RECOVERY_SECONDS
    invocation = {'schema': 'smc_long_owner_invocation_v1', 'source': source,
        'legacy_source': legacy.LEGACY_SOURCE, 'protocol_path': str(protocol_path),
        'protocol_pin': pin(body(protocol_path)), 'output': str(output), 'owner': str(owner_folder),
        'clock': clock, 'recovery': recovery,
        'transport_cost_allocation': {'original_child_read_ceiling': runtime['source_read_bytes'],
            'original_child_write_ceiling': runtime['host_write_bytes'],
            'additional_recovery_read_ceiling': recovery_reads,
            'additional_recovery_write_ceiling': recovery_writes,
            'owner_journal_write_ceiling': JOURNAL_CAP,
            'unknown_child_failure_cost_charged_at_original_ceiling': True},
        'source_construction_is_not_run_authorization': True,
        'restricted_single_process_not_generic_primary': True,
        'external_parent_death_watchdog_qualified': False}
    invocation_pin = publish(owner_folder / 'INVOCATION.json', invocation, cap=16384)
    return invocation, invocation_pin, L, runtime


def check_controller(value, folder, source, invocation, owner, handles):
    need(set(value) == {'pid', 'parent_pid', 'pgid', 'owner_token', 'clock_identity', 'source'}
         and value['parent_pid'] == value['pgid'] == owner['pid'] and value['owner_token'] == owner['token']
         and value['source'] == source and value['clock_identity'] == invocation['clock']['clock_identity'],
         'Current active controller identity')
    until = min(invocation['clock']['controller_deadline'], time.monotonic() + 1)
    launch_path = Path(folder) / 'process_child.json'
    while not launch_path.exists() and time.monotonic() < until:
        time.sleep(.005)
    child = process_owner.read(launch_path)
    need(child['child_pid'] == value['pid'] and child['token'] == owner['token'],
         'Parent observes exact child from owned bootstrap')
    need(not handles, 'One controller identity handle')
    fd = os.pidfd_open(value['pid'], 0)
    try:
        observed = process_owner.inspect_leader(value['pid'], until)
        need(observed is not None and observed['pgid'] == owner['pid']
             and observed['command'].endswith(' ' + ' '.join(owner['child_argv'][1:])),
             'Observed initialized trusted controller command/group')
        p = subprocess.run(['/bin/ps', '-p', str(value['pid']), '-o', 'ppid='],
                           capture_output=True, timeout=max(.001, min(1, until - time.monotonic())))
        need(p.returncode == 0 and len(p.stdout) <= 128 and not p.stderr
             and int(p.stdout.strip()) == owner['pid'] and not select.select([fd], [], [], 0)[0],
             'Observed live actual bootstrap child before any release')
        handles.update(fd=fd, pid=value['pid'], observed=observed)
        return observed
    except BaseException:
        os.close(fd)
        raise


def reap_controller(handles):
    if handles:
        try:
            os.waitid(os.P_PIDFD, handles['fd'], os.WEXITED | os.WNOHANG)
        except ChildProcessError:
            pass  # The live bootstrap may already have reaped its exact child.


def pump(proc, sock, journal, invocation, owner, controller_handles, cancelled=None):
    selector = selectors.DefaultSelector()
    buffer = bytearray()
    logs = {'stdout': bytearray(), 'stderr': bytearray()}
    cutoff = invocation['clock']['controller_deadline']
    terminal_end = cutoff
    observations = 0
    def save_absence(row):
        nonlocal observations
        journal.writer.publish(Path(invocation['owner']) / ('CLI-ABSENT-' + str(observations).zfill(6) + '.json'),
                {'schema': 'smc_observed_cli_absence_v1', 'invocation_pin': journal.invocation_pin,
                 'source': journal.source, 'observation': row})
        observations += 1
    try:
        for name, stream in (('socket', sock), ('stdout', proc.stdout), ('stderr', proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while time.monotonic() < terminal_end:
            need(not cancelled or cancelled[0] is None, 'Owned supervisor termination requested')
            for key, _ in selector.select(min(.1, max(0, terminal_end - time.monotonic()))):
                name = key.data
                if name == 'socket':
                    chunk = sock.recv(min(65536, FRAME_CAP + 4 - len(buffer)))
                    if not chunk:
                        selector.unregister(sock)
                        need(not buffer, 'No truncated terminal owner frame')
                        need(journal.done is not None, 'Controller channel ended before complete paired result')
                        terminal_end = min(cutoff, time.monotonic() + 1)
                        continue
                    buffer.extend(chunk)
                    message = extract(buffer)
                    if message is not None:
                        need(not buffer, 'One synchronous owner request in flight')
                        answer = journal.accept(message, controller_check=lambda value:
                            check_controller(value, Path(invocation['owner']) / 'process', journal.source,
                                             invocation, owner, controller_handles))
                        # A failed/partial ACK is a failure; the parent keeps every prior custody record.
                        need(time.monotonic() < cutoff, 'Parent ACK before original cutoff')
                        need(not cancelled or cancelled[0] is None, 'Owner stop precedes native release acknowledgement')
                        sock.settimeout(min(1, max(.001, cutoff - time.monotonic())))
                        sock.sendall(frame(answer))
                        sock.setblocking(False)
                else:
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    need(len(logs[name]) + len(chunk) <= 65536, 'Bounded trusted-controller diagnostics')
                    logs[name].extend(chunk)
            journal.custody.retire_exited(save_absence)
            completion = Path(invocation['owner']) / 'process' / 'process_completion.json'
            if completion.exists():
                result = process_owner.read(completion)
                need(result['token'] == owner['token'] and result['returncode'] == 0
                     and result['child_pid'] == controller_handles['pid']
                     and journal.done is not None and not buffer and time.monotonic() < cutoff,
                     'Natural complete controller and paired result before original cutoff')
                return {'natural_exit': True, 'completion': result,
                        'logs': {k: bytes(v).decode(errors='replace') for k, v in logs.items()}}
        raise TimeoutError('Original controller cutoff reached; reserved recovery interval starts')
    finally:
        selector.close()


def recover_phases(invocation, invocation_pin, L, runtime, journal, closure_pin, custody):
    """No target access or producer retry. Unknown child costs consume their full grants."""
    remaining = [phase for phase in CONDITIONS if phase in journal.ownership and phase not in journal.closed]
    if not remaining:
        return []
    root = Path(invocation['output'])
    exposures = {}
    for phase in CONDITIONS:
        p = root / 'jobs' / phase / 'EXPOSURE.json'
        exposures[pin(body(p))['sha256']] = str(p)
    extra = invocation['recovery']
    cls = L.provider_class()
    provider = cls(root / 'control', root / 'quarantine', runtime['docker_binary'], runtime['docker_socket'],
        pin(body(L.TRANSPORT / 'SOURCE_MANIFEST.json')), exposures,
        runtime['source_read_bytes'] + extra['source_read_bytes'],
        runtime['host_write_bytes'] + extra['host_write_bytes'])
    # This does not refund hidden or failed child activity from retained file size.
    provider.read_used = runtime['source_read_bytes']
    provider.write_used = runtime['host_write_bytes']
    results, count = [], 0
    def recovery_event(name, value):
        nonlocal count
        need(count < 2048 and value['record']['controller_closed_proof'] == closure_pin,
             'Recovery tied to actual parent-observed controller closure')
        row = value['record']
        need(pin(encoded(row)) == value['pin'], 'Exact unchanged Provider recovery record')
        if name == 'CLI-CHILD':
            custody.capture(row['value'], invocation['clock']['deadline'])
        journal.writer.publish(Path(invocation['owner']) / ('RECOVERY-EVENT-' + str(count).zfill(6) + '.json'),
                {'invocation_pin': invocation_pin, 'value': value})
        count += 1
    for phase in remaining:
        own = journal.ownership[phase]
        limits = {key: extra[key] for key in ('max_records', 'max_record_bytes', 'max_metadata_bytes')}
        limits.update(max_cli_calls=extra['per_phase_cli_calls'], max_cli_bytes=extra['per_phase_cli_bytes'],
                      source_read_bytes=extra['source_read_bytes'] // 2,
                      host_write_bytes=extra['host_write_bytes'] // 2)
        result = provider.recover(phase, own['ownership']['request_pin'], own['ownership_pin'],
            invocation['clock']['deadline'], recovery_event, limits, closure_pin)
        receipt = result['receipt']
        results.append({'phase_id': phase, 'receipt_pin': result['receipt_pin'],
            'all_resource_custody_closed': receipt['all_resource_custody_closed'],
            'all_namespaces_empty': receipt['all_namespaces_empty'],
            'final_transport_counters': result['final_transport_counters']})
    return results


def execute(protocol, expected, output, owner_folder, recovery_reads, recovery_writes):
    invocation, invocation_pin, L, runtime = make_invocation(protocol, expected, output, owner_folder,
                                                            recovery_reads, recovery_writes)
    folder = Path(invocation['owner'])
    writer = OwnerWriter(invocation_pin['bytes'])
    parent = child = custody = journal = proc = None
    controller_handles = {}
    previous_signals = {}
    stop_requested = [None]
    error = None
    recovery_error = None
    cleanup_errors = []
    execution = None
    recoveries = []
    group = {'absence_verified': False}
    cli = {'all_acknowledged_cli_absent': False}
    result = None
    result_pin = None
    closure_pin = None
    with (folder / 'OWNER.lock').open('xb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            def interrupted(sig, *_):
                # Defer interruption to a safe pump boundary. Raising during a
                # pidfd authority transfer could abandon a partially retired fd.
                stop_requested[0] = sig
                for owned_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                    signal.signal(owned_signal, signal.SIG_IGN)
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                previous_signals[sig] = signal.signal(sig, interrupted)
            try:
                parent, child = socket.socketpair()
                custody = CliCustody(engine_for(L), invocation['clock']['deadline'])
                journal = ParentJournal(folder / 'events', invocation, invocation_pin, invocation['source'],
                                        L, custody, writer)
                controller = {'path': CONTROLLER, **pin(body(HERE / 'controller.py'))}
                argv = [sys.executable, '-I', '-B', str(HERE / 'controller.py'), '--invocation', str(folder / 'INVOCATION.json'),
                        '--invocation-sha256', invocation_pin['sha256'], '--channel-fd', str(child.fileno())]
                grant = {**invocation['clock'], 'invocation_pin': invocation_pin}
                proc = process_owner.launch(argv, folder / 'process', grant, controller, child.fileno())
                child.close()
                owned, _ = process_owner.expected(folder / 'process', require_remaining=True)
                execution = pump(proc, parent, journal, invocation, owned, controller_handles, stop_requested)
            except BaseException as exc:
                error = {'type': type(exc).__name__, 'automatic_retry': False}
            finally:
                for stream in (parent, child):
                    if stream is not None:
                        try:
                            stream.close()
                        except BaseException as exc:
                            cleanup_errors.append({'scope': 'channel', 'type': type(exc).__name__})
                try:
                    group = process_owner.stop(folder / 'process', invocation['clock']['deadline'], proc,
                        reap_owned_children=lambda end: reap_controller(controller_handles))
                except BaseException as exc:
                    group = {'absence_verified': False, 'error': type(exc).__name__}
                if custody is not None:
                    cli = custody.close(invocation['clock']['deadline'])
                if controller_handles:
                    try:
                        os.close(controller_handles['fd'])
                    except BaseException as exc:
                        cleanup_errors.append({'scope': 'controller_pidfd', 'type': type(exc).__name__})
                    controller_handles.clear()
            closure = {'schema': 'smc_parent_observed_controller_closure_v1', 'invocation_pin': invocation_pin,
                'source': invocation['source'], 'clock': invocation['clock'], 'controller_group': group,
                'acknowledged_cli': cli, 'unacknowledged_cli_host_absence_verified': False,
                'unacknowledged_bootstrap_cannot_exec_without_parent_ack': True,
                'future_controller_and_acknowledged_cli_release_closed':
                    group.get('absence_verified') is True and cli['all_acknowledged_cli_absent'] and not cleanup_errors,
                'outer_parent_death_watchdog_qualified': False}
            closure_pin = writer.publish(folder / 'CONTROLLER_CLOSED.json', closure, terminal=True)
            last_cli = {'all_acknowledged_cli_absent': True, 'records': []}
            try:
                need(closure['future_controller_and_acknowledged_cli_release_closed'],
                     'Actual controller and acknowledged CLI custody before recovery')
                if error is not None and journal is not None:
                    recoveries = recover_phases(invocation, invocation_pin, L, runtime, journal, closure_pin, custody)
            except BaseException as exc:
                recovery_error = {'type': type(exc).__name__, 'automatic_retry': False}
            finally:
                if custody is not None:
                    last_cli = custody.close(invocation['clock']['deadline'])
            complete = (error is None and recovery_error is None and not cleanup_errors
                        and execution is not None and journal is not None and journal.done is not None
                        and closure['future_controller_and_acknowledged_cli_release_closed']
                        and last_cli['all_acknowledged_cli_absent'])
            result = {'schema': 'smc_long_owner_result_v1', 'status': 'closed_pair' if complete else 'failed',
                'invocation_pin': invocation_pin, 'source': invocation['source'], 'controller_closure_pin': closure_pin,
                'controller_execution': execution, 'pair_closed_pin': journal.done if complete else None,
                'error': error, 'recovery_error': recovery_error, 'cleanup_errors': cleanup_errors,
                'recovery': recoveries, 'recovery_cli': last_cli,
                'original_child_transport_cost_conservative_charge': invocation['transport_cost_allocation'],
                'owner_event_bytes': 0 if journal is None else journal.bytes,
                'owner_event_count': 0 if journal is None else journal.sequence,
                'owner_metadata_charged_bytes_before_terminal_result': writer.used,
                'scientific_success': None, 'AI_performance_verified': False,
                'actual_linux_docker_runtime_qualification_inherited': False,
                'forced_parent_stop_independent_host_and_daemon_qualification': False}
            result_pin = writer.publish(folder / 'RESULT.json', result, terminal=True)
        except BaseException as exc:
            # Do not replace a prior failure or pretend a partial receipt is success.
            if not (folder / 'RESULT.json').exists():
                try:
                    writer.publish(folder / 'TERMINAL_FAILURE.json', {
                        'schema': 'smc_owner_terminal_failure_v1', 'invocation_pin': invocation_pin,
                        'source': invocation['source'], 'original_error': error,
                        'recovery_error': recovery_error, 'terminal_error': type(exc).__name__,
                        'cleanup_errors': cleanup_errors, 'controller_closure_pin': closure_pin,
                        'owner_metadata_conservative_charge': JOURNAL_CAP,
                        'automatic_retry': False, 'scientific_success': None}, terminal=True)
                except BaseException:
                    pass  # Full reserved ceiling remains charged; retain partial evidence.
            raise
        finally:
            # Every cleanup is attempted independently, even after evidence-write failure.
            for stream in (parent, child):
                if stream is not None:
                    try:
                        stream.close()
                    except BaseException:
                        pass
            if custody is not None and custody.children:
                final_cli = custody.close(invocation['clock']['deadline'])
                try:
                    writer.publish(folder / 'RECOVERY_CLI_FINAL.json', final_cli, terminal=True)
                except BaseException:
                    pass
            if controller_handles:
                try:
                    os.close(controller_handles['fd'])
                except BaseException:
                    pass
            for sig, handler in previous_signals.items():
                signal.signal(sig, handler)
    need(result is not None and result['status'] == 'closed_pair',
         'Preserved terminal owned-episode failure; no partial success')
    return {'result': result, 'result_pin': result_pin}


def grade(owner_folder, result_sha256, target, evaluator, output, scratch_bytes):
    """Public successor grade requires parent closure, never the child draft alone."""
    folder = ordinary(owner_folder)
    result_raw = body(folder / 'RESULT.json')
    need(pin(result_raw)['sha256'] == result_sha256, 'Exact parent result selected for grading')
    result = read(folder / 'RESULT.json')
    invocation = read(folder / 'INVOCATION.json', result['invocation_pin'])
    need(result['status'] == 'closed_pair' and result['error'] is None
         and result['recovery_error'] is None and result['cleanup_errors'] == []
         and result['recovery_cli']['all_acknowledged_cli_absent'] is True
         and result['controller_execution']['natural_exit'] is True
         and result['source'] == invocation['source'] == legacy.source_identity(), 'Closed exact successor invocation')
    closed = read(folder / 'CONTROLLER_CLOSED.json', result['controller_closure_pin'])
    need(closed['invocation_pin'] == result['invocation_pin']
         and closed['source'] == result['source'] and closed['clock'] == invocation['clock']
         and closed['future_controller_and_acknowledged_cli_release_closed'] is True
         and closed['controller_group']['absence_verified'] is True
         and closed['acknowledged_cli']['all_acknowledged_cli_absent'] is True,
         'Actual parent closure before private target access')
    pair_path = Path(invocation['output']) / 'PAIR_CLOSED.json'
    pair = read(pair_path, result['pair_closed_pin'])
    need(pair['owner_invocation_pin'] == result['invocation_pin'] and pair['owner_source'] == result['source']
         and pair['protocol_path'] == invocation['protocol_path']
         and pair['protocol_sha256'] == invocation['protocol_pin']['sha256']
         and pair['outcome'] == invocation['clock']['outcome'],
         'Child output joins exact parent invocation')
    return legacy.load().grade(pair_path, result['pair_closed_pin']['sha256'], target, evaluator, output, scratch_bytes)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    run = sub.add_parser('execute')
    for name in ('protocol', 'output', 'owner'):
        run.add_argument('--' + name, type=Path, required=True)
    run.add_argument('--protocol-sha256', required=True)
    run.add_argument('--recovery-read-bytes', type=int, required=True)
    run.add_argument('--recovery-write-bytes', type=int, required=True)
    score = sub.add_parser('grade')
    for name in ('owner', 'target', 'evaluator', 'output'):
        score.add_argument('--' + name, type=Path, required=True)
    score.add_argument('--result-sha256', required=True)
    score.add_argument('--scratch-bytes', type=int, required=True)
    args = p.parse_args()
    if args.action == 'execute':
        result = execute(args.protocol, args.protocol_sha256, args.output, args.owner,
                         args.recovery_read_bytes, args.recovery_write_bytes)
    else:
        result = grade(args.owner, args.result_sha256, args.target, args.evaluator, args.output, args.scratch_bytes)
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    main()
