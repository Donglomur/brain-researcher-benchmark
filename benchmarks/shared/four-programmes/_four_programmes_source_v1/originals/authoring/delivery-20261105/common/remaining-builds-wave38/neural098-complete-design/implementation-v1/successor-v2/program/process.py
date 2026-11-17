"""Actual future Linux cgroup-v2 child/stream/CPU ownership.

Qualification must attest delegation and immutable executables. No process is
launched by import or by source inspection. Complete source controls never
stand in for actual Linux/native qualification.
"""
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import time
from .custody import capture, descriptor, need, parse, pin, read_pin, write_json, write_new


class ChildFailure(RuntimeError):
    def __init__(self, record):
        super().__init__('selected child did not close successfully')
        self.record = record


def require_original_completion(record):
    """Exact lifecycle values; false-like substitutes are not original closure."""
    need(type(record) is dict, 'original process record object')
    for name in ('complete_success', 'spawn_attempted', 'spawn_acknowledged',
                 'natural_exit', 'streams_eof', 'group_empty', 'group_removed',
                 'independent_outer_natural_exit_required'):
        need(record.get(name) is True, 'original process requires true ' + name)
    need(type(record.get('exit_code')) is int and record['exit_code'] == 0,
         'original natural integer zero exit')
    need(record.get('timed_out') is False and record.get('failure', 'missing') is None,
         'no original timeout or failure')
    need(type(record.get('cleanup_errors')) is list and len(record['cleanup_errors']) == 0,
         'original cleanup completed without errors')


def admit_original_process(*, root, process_pin, candidate_pin, outer, stream_cap, budget):
    """Authenticate original closure and both complete streams before collection.

    This consumes the original producer's evidence, never creates substitute
    process success. Read reservations and observed prefixes remain charged on
    refusal. Original record/stream objects are never rewritten or removed.
    """
    audit = {'schema': 'neural098-original-process-admission-v2',
             'original_process_record': process_pin, 'candidate_report': candidate_pin,
             'stage': 'original_outer_completion', 'admitted': False, 'streams': {},
             'current_collection_budget_at_entry': budget.record()}
    try:
        need(type(outer) is dict and outer.get('independent_outer_natural_exit_zero') is True
             and outer.get('original_process_record') == process_pin
             and outer.get('candidate_report') == candidate_pin,
             'external original outer completion and exact collection inputs required')
        audit['outer_completion_bound'] = True
        need(type(stream_cap) is int and stream_cap > 0, 'selected current complete stream cap')
        audit['stage'] = 'original_process_record'
        record = parse(read_pin(root, process_pin, 4_000_000, budget))
        # Keep the exact immutable original identity plus its original cost and
        # failure observations, separately from costs of this collection attempt.
        audit['original_observations'] = {k: record.get(k) for k in
            ('budget', 'cpu_usec', 'whole_cpu_usec', 'memory_peak', 'exit_code',
             'failure', 'cleanup_errors', 'stdout_bytes', 'stderr_bytes')} if type(record) is dict else None
        audit['stage'] = 'original_lifecycle'
        require_original_completion(record)
        seen = set()
        for name in ('stdout', 'stderr'):
            audit['stage'] = name
            expected = record[name]
            descriptor(expected, stream_cap)
            need(Path(expected['path']).is_absolute() and expected['path'] not in seen,
                 'distinct absolute original stream paths')
            seen.add(expected['path'])
            observed_count = record.get(name + '_bytes')
            need(type(observed_count) is int and 0 <= observed_count <= stream_cap
                 and observed_count == expected['bytes'], 'original full stream extent agrees with record')
            audit['streams'][name] = {'expected': expected, 'authenticated': False}
            # Capture the complete stable observed object within the selected
            # cap first, so altered/truncated identities survive in failure
            # evidence. Only exact original extent/hash is admitted afterwards.
            raw, actual = capture(expected['path'], stream_cap, budget)
            audit['streams'][name]['observed'] = actual
            need(actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256'],
                 'original complete ' + name + ' extent/hash/EOF required')
            need(len(raw) == observed_count, 'complete original stream byte count')
            audit['streams'][name]['authenticated'] = True
        audit['stage'] = 'complete_original_process_admission'
        audit['admitted'] = True
        audit['current_collection_budget_after_admission'] = budget.record()
        return audit
    except BaseException as error:
        audit['failure_type'] = type(error).__name__
        audit['current_collection_budget_after_refusal'] = budget.record()
        error.original_process_admission = audit
        raise


def sandbox_argv(profile, *, view, work, command, model_socket=None):
    need(type(command) is list and command and all(type(x) is str and '\0' not in x for x in command), 'exact candidate argv')
    root = Path(profile['runtime_root'])
    need(root.is_absolute() and profile['network'] == 'none' and profile['read_only_runtime'] is True,
         'qualified immutable runtime and network policy')
    result = [profile['bwrap'], '--unshare-user', '--unshare-ipc', '--unshare-pid',
              '--unshare-net', '--unshare-uts', '--unshare-cgroup', '--disable-userns',
              '--cap-drop', 'ALL', '--die-with-parent', '--new-session',
              '--ro-bind', str(root), '/', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
              '--dir', '/input', '--ro-bind', str(view), '/input', '--dir', '/work',
              '--bind', str(work), '/work', '--chdir', '/work', '--clearenv',
              '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/tmp',
              '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'PYTHONHASHSEED', '0',
              '--setenv', 'OMP_NUM_THREADS', '1', '--setenv', 'OPENBLAS_NUM_THREADS', '1',
              '--setenv', 'MKL_NUM_THREADS', '1', '--setenv', 'NUMEXPR_NUM_THREADS', '1']
    if model_socket is not None:
        result += ['--dir', '/run', '--ro-bind', str(model_socket), '/run/model.sock']
    return result + ['--'] + command


def execute(command, *, cwd, env, group_parent, group_name, limits, budget, evidence):
    need(sys.platform == 'linux', 'qualified Linux cgroup-v2 execution only')
    need(type(group_name) is str and group_name and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in group_name),
         'unique owned cgroup name')
    root = Path(group_parent)
    need(root.is_absolute() and str(root).startswith('/sys/fs/cgroup/') and not any(p.is_symlink() for p in (root, *root.parents)),
         'qualified non-symlink cgroup delegation')
    need((root / 'cgroup.controllers').is_file(), 'cgroup v2 delegation')
    budget.check()
    need(budget.deadline - time.monotonic() > 10, 'reserve whole-lifetime cleanup time before launch')
    group = root / group_name
    record = {'argv': list(command), 'cwd': str(cwd), 'group': str(group), 'spawn_attempted': False,
              'spawn_acknowledged': False, 'natural_exit': False, 'exit_code': None,
              'streams_eof': False, 'group_empty': False, 'group_removed': False,
              'timed_out': False, 'failure': None, 'cleanup_errors': [],
              'stdout_bytes': 0, 'stderr_bytes': 0, 'cpu_usec': 0, 'memory_peak': None}
    record['independent_outer_natural_exit_required'] = True
    child = None; selector = None; created = False; chunks = {'stdout': [], 'stderr': []}
    primary = None
    cpu_before = getattr(budget, 'cpu_usec', 0)
    try:
        group.mkdir(mode=0o700); created = True
        for name, value in (('memory.max', limits['memory_bytes']), ('memory.swap.max', 0), ('pids.max', limits['pids'])):
            (group / name).write_text(str(value))
        need((group / 'cgroup.kill').is_file(), 'owned aggregate kill available before launch')
        def child_setup():
            # No unrelated group/process is touched. This executes before the
            # child executable; the qualified controller is single-threaded.
            (group / 'cgroup.procs').write_text(str(os.getpid()))
            resource.setrlimit(resource.RLIMIT_FSIZE, (limits['output_bytes'], limits['output_bytes']))
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        record['spawn_attempted'] = True
        child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True, close_fds=True, preexec_fn=child_setup)
        record['spawn_acknowledged'] = True
        selector = selectors.DefaultSelector()
        for name in chunks:
            stream = getattr(child, name); os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map() or child.poll() is None:
            if time.monotonic() >= budget.deadline - 8:
                record['timed_out'] = True
                raise TimeoutError('child cutoff before whole cleanup deadline')
            for key, _ in selector.select(timeout=min(.05, max(0., budget.deadline - time.monotonic() - 8))):
                budget.charge_read(65536)
                piece = os.read(key.fileobj.fileno(), 65536)
                budget.read_completed += len(piece)
                if not piece:
                    selector.unregister(key.fileobj)
                    continue
                name = key.data
                record[name + '_bytes'] += len(piece)
                room = max(0, limits['stream_bytes'] - (record[name + '_bytes'] - len(piece)))
                chunks[name].append(piece[:room])
                need(record[name + '_bytes'] <= limits['stream_bytes'], 'complete stream bound; retained prefix is not EOF success')
            stats = dict(line.split() for line in (group / 'cpu.stat').read_text().splitlines())
            record['cpu_usec'] = int(stats['usage_usec'])
            need(cpu_before + record['cpu_usec'] <= limits['cpu_seconds'] * 1_000_000, 'aggregate campaign CPU bound')
        record['exit_code'] = child.wait(timeout=max(.001, budget.deadline - time.monotonic() - 5))
        record['natural_exit'] = True
        record['streams_eof'] = True
        # Surviving descendants make the run fail, even if the main child says0.
        events = dict(line.split() for line in (group / 'cgroup.events').read_text().splitlines())
        need(events['populated'] == '0', 'all owned descendants exited naturally')
        need(record['exit_code'] == 0, 'original child zero exit')
    except BaseException as error:
        primary = error; record['failure'] = type(error).__name__
    finally:
        if created:
            try:
                (group / 'cgroup.kill').write_text('1')
            except BaseException as error:
                record['cleanup_errors'].append('kill:' + type(error).__name__)
        if child is not None:
            try:
                child.wait(timeout=max(.001, min(3., budget.deadline - time.monotonic() - 2)))
                if record['exit_code'] is None:
                    record['exit_code'] = child.returncode
            except BaseException as error:
                record['cleanup_errors'].append('wait:' + type(error).__name__)
            for name in chunks:
                try:
                    getattr(child, name).close()
                except BaseException as error:
                    record['cleanup_errors'].append(name + ':' + type(error).__name__)
        if selector is not None:
            try:
                selector.close()
            except BaseException as error:
                record['cleanup_errors'].append('selector:' + type(error).__name__)
        if created:
            try:
                events = dict(line.split() for line in (group / 'cgroup.events').read_text().splitlines())
                record['group_empty'] = events['populated'] == '0'
                record['memory_peak'] = int((group / 'memory.peak').read_text())
                stats = dict(line.split() for line in (group / 'cpu.stat').read_text().splitlines())
                record['cpu_usec'] = int(stats['usage_usec'])
                need(record['group_empty'], 'owned group empty after cleanup')
                group.rmdir(); record['group_removed'] = True
            except BaseException as error:
                record['cleanup_errors'].append('group:' + type(error).__name__)
        budget.cpu_usec = cpu_before + record['cpu_usec']
        if budget.cpu_usec > limits['cpu_seconds'] * 1_000_000:
            record['cleanup_errors'].append('whole CPU exceeded at final capture')
        record['whole_cpu_usec'] = budget.cpu_usec
        record['budget'] = budget.record()
        record['complete_success'] = bool(primary is None and record['natural_exit'] and record['streams_eof']
                                          and record['group_empty'] and record['group_removed']
                                          and not record['cleanup_errors'] and record['exit_code'] == 0)
        try:
            # Known full prefixes are retained on failure; they are not relabeled
            # as complete EOF. Publication and cleanup share the original budget.
            for name in chunks:
                raw = b''.join(chunks[name])
                record[name] = write_new(Path(evidence) / (name.upper() + '.txt'), raw, budget, limits['stream_bytes'])
            write_json(Path(evidence) / 'PROCESS.json', record, budget)
        except BaseException as error:
            record['cleanup_errors'].append('publication:' + type(error).__name__)
            record['complete_success'] = False
            if primary is None:
                primary = error
        try:
            budget.check()
        except BaseException as error:
            record['complete_success'] = False
            if primary is None:
                primary = error
    if not record['complete_success']:
        failure = ChildFailure(record)
        if primary is not None and not isinstance(primary, Exception):
            primary.process_record = record
            raise primary
        raise failure from primary
    return record
