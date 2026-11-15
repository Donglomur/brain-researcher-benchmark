"""Complete one-shot DMFC operation using the reviewed V4 group lifecycle.

This composes existing ownership, numerical recovery and shared actor recovery.
No candidate code is executed on the host and no private subset is scored.
"""
import ast
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import sys
import threading
import time

PROFILE_PATH = Path(__file__).absolute().parent / 'OPERATION_PROFILE.json'
CELL_KEYS = ('frozen_program__cue_only', 'frozen_program__neural',
             'case_adaptive__cue_only', 'case_adaptive__neural')
MARKERS = ('process_intent.json', 'process_ready.json', 'process_owner.json',
           'process_gate.json', 'process_completion.json')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate metadata key'); value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite metadata')))


def read(path, cap=262144):
    p = Path(path).absolute()
    need(all(not x.is_symlink() for x in (p, *p.parents)), 'unlinked private metadata')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd); need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and 0 < a.st_size <= cap,
                               'ordinary bounded private metadata')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        b = os.fstat(fd)
        need(len(body) == a.st_size and all(getattr(a, k) == getattr(b, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'stable complete metadata')
        return body
    finally:
        os.close(fd)


def pinned(root, pin, cap=262144):
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'exact metadata descriptor')
    p = Path(pin['path']); p = p if p.is_absolute() else Path(root) / p
    body = read(p, cap)
    need(type(pin['bytes']) is int and len(body) == pin['bytes'] and
         hashlib.sha256(body).hexdigest() == pin['sha256'], 'exact selected metadata bytes')
    return body


def durable(path, value, budget):
    body = encode(value); need(len(body) <= 1048576, 'bounded whole-operation receipt')
    budget.write(path, body, receipt=True, mode=0o444)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class ManagedReads:
    """Precharge managed regular-file opens in a shared append-only ledger.

    The ledger's own bounded accounting I/O is excluded, not called scientific
    bytes. Native candidate I/O stays inside numerical cgroups; this is host I/O.
    """
    def __init__(self, root, output, limit, reserve=268435456):
        self.roots = (Path(root).absolute(), Path(output).absolute())
        self.path = self.roots[1] / 'managed_read_charges.jsonl'
        need(type(limit) is int and limit > reserve > 0, 'declared work/recovery read allocation')
        self.limit, self.reserve, self.recovery = limit, reserve, False
        self.local = threading.local()

    def charge(self, amount):
        need(type(amount) is int and amount >= 0, 'typed complete host read charge')
        self.local.active = True
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                s = os.fstat(fd); need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= 2097152,
                                       'bounded shared read ledger')
                previous = {'total_bytes': 0, 'sequence': 0}
                if s.st_size:
                    os.lseek(fd, max(0, s.st_size - 512), os.SEEK_SET)
                    tail = os.read(fd, 512)
                    need(tail.endswith(b'\n'), 'complete previous read charge')
                    previous = decode(tail.splitlines()[-1])
                need(set(previous) == {'total_bytes', 'sequence'} and all(type(x) is int and x >= 0 for x in previous.values()),
                     'exact previous read accounting')
                total = previous['total_bytes'] + amount
                need(total <= self.limit - (0 if self.recovery else self.reserve), 'managed read allocation exhausted')
                body = encode({'total_bytes': total, 'sequence': previous['sequence'] + 1}) + b'\n'
                need(os.write(fd, body) == len(body), 'complete durable read charge'); os.fsync(fd)
                result = {'total_bytes': total, 'sequence': previous['sequence'] + 1}
            finally:
                os.close(fd)
        finally:
            self.local.active = False
        return result

    def report(self):
        return dict(self.charge(0), limit_bytes=self.limit, recovery_reserve_bytes=self.reserve,
                    accounting_ledger_io_excluded=True, method='precharged-full-file-open-upper-bound')

    def audit(self, event, args):
        if event != 'open' or getattr(self.local, 'active', False):
            return
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)) or (flags & os.O_ACCMODE) == os.O_WRONLY:
            return
        p = Path(os.fsdecode(path)).absolute()
        if p == self.path or not any(p.is_relative_to(root) for root in self.roots):
            return
        try:
            s = p.lstat()
        except FileNotFoundError:
            if flags & os.O_CREAT:
                return  # A newly created empty file has no existing bytes to read.
            raise
        if stat.S_ISDIR(s.st_mode):
            return
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and not p.is_symlink(), 'ordinary managed read')
        self.charge(s.st_size)

    def install(self, bootstrap_bytes):
        self.charge(bootstrap_bytes)
        sys.addaudithook(self.audit)
        return self


def install_managed_reads(config, bootstrap_bytes):
    v = config.value
    return ManagedReads(v['repository_root'], v['output_root'], v['host_budget']['read_bytes']).install(bootstrap_bytes)


def admit(config, *, now=None):
    """Bind the exact selected request, profile and current root capacity witness."""
    v = config.value; root = Path(v['repository_root']); output = Path(v['output_root'])
    now = time.time() if now is None else now
    need(output.is_absolute() and not output.exists() and not output.is_symlink() and output.parent.is_dir() and
         all(not p.is_symlink() for p in (output.parent, *output.parents)), 'fresh short unlinked operation namespace')
    need(set(v['actor']['arms']) == set(CELL_KEYS) and all(len(os.fsencode(output / 'arms' / key / 'arm.sock')) <= 99
         for key in CELL_KEYS), 'all four private actor sockets fit the platform')
    body = pinned(root, v['request']); need(hashlib.sha256(body).hexdigest() == config.request_sha256,
                                          'configuration request identity')
    request = decode(body)
    fields = {'schema', 'decision', 'candidate_id', 'configuration_payload_sha256', 'source_freeze', 'profile',
              'output_root', 'actor_contexts', 'runtime_identity', 'capacity', 'issued_at_unix', 'expires_at_unix',
              'prior_known_seconds', 'family_ceiling_seconds'}
    need(type(request) is dict and set(request) == fields and request['schema'] == 'dmfc-complete-four-cell-root-request/v1'
         and request['decision'] == 'admit_one_complete_dmfc_four_cell_operation' and request['candidate_id'] == 'NEURAL-095',
         'current exact root-selected complete operation')
    payload = {k: x for k, x in v.items() if k != 'request'}
    need(request['configuration_payload_sha256'] == hashlib.sha256(encode(payload)).hexdigest() and
         request['source_freeze'] == v['successor_freeze'] and request['output_root'] == str(output) and
         request['actor_contexts'] == list(CELL_KEYS) and request['runtime_identity'] == v['runtime_identity'],
         'request binds all source/config/actors/runtime and output values')
    for key in ('issued_at_unix', 'expires_at_unix', 'prior_known_seconds', 'family_ceiling_seconds'):
        need(type(request[key]) in (int, float) and math.isfinite(request[key]) and request[key] >= 0, 'finite root accounting')
    need(request['issued_at_unix'] <= now <= request['expires_at_unix'] and
         request['expires_at_unix'] - request['issued_at_unix'] <= 3600,
         'fresh one-hour initial admission window; no operation-clock reset')
    profile_body = pinned(root, request['profile']); need(profile_body == read(PROFILE_PATH), 'exact reviewed operation profile')
    profile = decode(profile_body)
    need(request['prior_known_seconds'] + profile['whole_seconds'] <= request['family_ceiling_seconds'], 'complete prospective family charge')
    limits = v['limits']; host = v['host_budget']
    need(limits['wall_us'] == profile['cell_seconds'] * 1000000 and
         limits['preparation_wall_us'] == profile['preparation_seconds'] * 1000000 and
         limits['max_memory_bytes'] == profile['memory_upper_bound_bytes'], 'same complete mode/view resource limits')
    for field, pkey in (('artifact_bytes', 'minimum_artifact_bytes'), ('receipt_bytes', 'minimum_receipt_reserve_bytes'),
                       ('read_bytes', 'minimum_managed_read_bytes')):
        need(type(host[field]) is int and host[field] >= profile[pkey], 'whole host allocation includes ' + field)
    need(host['artifact_bytes'] > host['receipt_bytes'] + 4 * 1024**2, 'receipt and concurrent-write margins reserved')
    capacity = decode(pinned(root, request['capacity']))
    fields = {'schema', 'observed_at_unix', 'repository_root', 'output_parent', 'available_memory_bytes',
              'other_disk_reserve_bytes', 'memory_pressure', 'swap_growth_bytes', 'pageout_growth_bytes'}
    need(type(capacity) is dict and set(capacity) == fields and capacity['schema'] == 'dmfc-complete-four-cell-capacity/v1'
         and capacity['repository_root'] == str(root) and capacity['output_parent'] == str(output.parent), 'exact selected capacity namespace')
    need(type(capacity['observed_at_unix']) in (int, float) and 0 <= now - capacity['observed_at_unix'] <= 120,
         'capacity observations are current at admission')
    for field in ('available_memory_bytes', 'other_disk_reserve_bytes', 'swap_growth_bytes', 'pageout_growth_bytes'):
        need(type(capacity[field]) is int and capacity[field] >= 0, 'typed capacity observation')
    need(capacity['available_memory_bytes'] >= profile['minimum_available_memory_bytes'] and
         capacity['other_disk_reserve_bytes'] >= profile['minimum_other_disk_reserve_bytes'] and
         capacity['memory_pressure'] == 'NORMAL' and capacity['swap_growth_bytes'] == capacity['pageout_growth_bytes'] == 0,
         'root-observed complete memory and other-work reserves')
    fs = os.statvfs(output.parent); free = fs.f_bavail * fs.f_frsize
    need(free >= host['artifact_bytes'] + capacity['other_disk_reserve_bytes'], 'actual current disk covers whole reservation')
    return profile, request, {'root_witness': request['capacity'], 'actual_free_bytes': free}


def completed_unit(folder, index, live, engines, seen_names, seen_ids):
    """Reuse only a complete trusted absent receipt, never an actor assertion."""
    intent_body = read(folder / 'UNIT_INTENT.json'); intent = decode(intent_body)
    need(intent['unit']['unit_id'] == 'dmfc-four-cell/unit-%04d' % index and intent['dispatches'] == 1 and
         intent['runner'] == {'path': str(live.UNIT), 'bytes': live.UNIT_PIN[0], 'sha256': live.UNIT_PIN[1]}, 'exact original numerical intent')
    program = intent['program']; need(Path(program['path']) == folder / 'program.py', 'one exact committed unit source')
    pinned(folder, program, 65536)
    attempt = folder / 'attempt'
    journal = decode(read(attempt / 'resource_ownership.json', 65536))
    owned = journal['owned']; need(type(owned) is list and len(owned) == 3, 'complete original resource family')
    names = [x['name'] for x in owned]
    need(len(set(names)) == 3 and not seen_names.intersection(names), 'resources never reused across units')
    prefixes = ('dmfc-prog-volume-', 'dmfc-prog-holder-', 'dmfc-prog-worker-')
    need(all(type(name) is str and re.fullmatch(prefix + '[0-9a-f]{32}', name)
             for name, prefix in zip(names, prefixes)) and len({name[len(prefix):] for name, prefix in zip(names, prefixes)}) == 1,
         'one original ordered unit resource namespace')
    unit = intent['unit']; profile = {'public_destinations': tuple(x['mount_destination'] for x in unit['public_inputs']),
        'output_name': unit['output_filename'], 'max_output_bytes': unit['max_output_bytes']}
    for position, row in enumerate(owned):
        kind = 'volume' if position == 0 else 'container'
        need(row['kind'] == kind and row.get('attempted_before_dispatch') is True, 'original durable attempted role')
        if position == 0:
            expected = engines.volume_expected(names[0])
        else:
            mounts = ({'/trusted/holder.py': {'type': 'bind', 'source': str(live.ROOT / 'authoring/shared-large-npz-runner-v1/holder_profile.py'), 'rw': False},
                       '/capture': {'type': 'volume', 'source': names[0], 'rw': False}} if position == 1 else
                      {'/program/program.py': {'type': 'bind', 'source': str(folder / 'program.py'), 'rw': False},
                       '/output': {'type': 'volume', 'source': names[0], 'rw': True}})
            if position == 2:
                mounts.update({x['mount_destination']: {'type': 'bind', 'source': str(live.ROOT / x['path']), 'rw': False}
                               for x in unit['public_inputs']})
            expected = engines.container_expected(names[position], 'holder' if position == 1 else 'candidate', mounts, profile)
        need(row['canonical_create_argv'] == expected['argv'], 'closed receipt retains independently regenerated constructor')
    execution_body = read(attempt / 'execution.json'); execution = decode(execution_body)
    commit_body = read(attempt / 'commit.json'); commit = decode(commit_body)
    need(execution.get('status') == 'unit_committed' and execution.get('all_owned_absent') is True and
         execution.get('candidate_id') == commit.get('candidate_id') == 'NEURAL-095' and
         execution.get('unit_id') == commit.get('unit_id') == intent['unit']['unit_id'] and
         execution.get('program_sha256') == commit.get('program_sha256') == program['sha256'] and
         execution.get('commit_sha256') == hashlib.sha256(commit_body).hexdigest(), 'immutable source-bound completed unit')
    need(commit.get('status') == 'removed_producer_output_committed' and
         commit.get('producer_removed_before_capture') is True and commit.get('all_candidate_holder_volume_absent') is True and
         commit.get('public_inputs') == intent['unit']['public_inputs'] and commit.get('output') == execution.get('output'),
         'same full captured output and removal-before-capture proof')
    pin = commit['output']; need(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and type(pin['bytes']) is int,
                                 'exact complete opaque output pin')
    pinned(folder, {'path': str(attempt / intent['unit']['output_filename']), **pin}, 1048576)
    cleanup = execution.get('cleanup')
    need(type(cleanup) is list and len(cleanup) == 3 and {x.get('name') for x in cleanup} == set(names) and
         all(x.get('absence_verified') is True for x in cleanup), 'all original resources already absent')
    ids = [x.get('verified_identity') for x in cleanup if x.get('kind') == 'container']
    need(len(ids) == 2 and all(type(x) is str and re.fullmatch('[0-9a-f]{64}', x) for x in ids) and
         len(set(ids)) == 2 and not seen_ids.intersection(ids), 'captured container IDs never reused')
    need(commit.get('producer', {}).get('container_id') in ids and commit['producer'].get('name') == names[2],
         'captured producer belongs to original unit')
    seen_names.update(names); seen_ids.update(ids)
    return {'index': index, 'all_absent': True, 'reused_closed_receipt': True,
            'intent_sha256': hashlib.sha256(intent_body).hexdigest(),
            'execution_sha256': hashlib.sha256(execution_body).hexdigest(),
            'commit_sha256': hashlib.sha256(commit_body).hexdigest()}


def recover_numerical(root, live, runtime, budget, until):
    """Reuse the exact accepted inner recovery function for every nonclosed unit."""
    root = Path(root)
    if not root.exists():
        return {'all_owned_absent': True, 'units': [], 'never_initialized': True}
    folders = sorted(root.iterdir())
    need(len(folders) <= 46 and all(p.is_dir() and not p.is_symlink() and p.name == 'unit-%04d' % i
         for i, p in enumerate(folders)), 'complete finite contiguous numerical family')
    source = runtime.sources[Path(live.__file__).relative_to(runtime.root).as_posix()]
    outer = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == 'recover_units')
    helper = next(x for x in outer.body if isinstance(x, ast.FunctionDef) and x.name == 'recover_one')
    ns = dict(vars(live), engines=runtime.engines, budget=budget, until=until)
    exec(compile(ast.Module(body=[helper], type_ignores=[]), live.__file__, 'exec'), ns)
    seen_names, seen_ids, rows, pending = set(), set(), [], []
    all_names, all_ids, reuse_forbidden = [], [], False
    # Establish the no-later-reuse invariant over the whole durable family
    # before trusting an earlier closed receipt. Unknown provenance fails safe.
    for folder in folders:
        journal = folder / 'attempt/resource_ownership.json'
        execution = folder / 'attempt/execution.json'
        try:
            if journal.exists():
                owned = decode(read(journal, 65536))['owned']
                need(type(owned) is list and len(owned) <= 3, 'bounded original resource family')
                all_names.extend(x['name'] for x in owned)
            if execution.exists():
                cleanup = decode(read(execution)).get('cleanup', [])
                all_ids.extend(x['verified_identity'] for x in cleanup
                               if x.get('kind') == 'container' and x.get('verified_identity'))
        except BaseException:
            reuse_forbidden = True
    reuse_forbidden = (reuse_forbidden or len(set(all_names)) != len(all_names) or
                       len(set(all_ids)) != len(all_ids))
    # A malformed proof is never enough to skip actual recovery.
    for index, folder in enumerate(folders):
        try:
            need(not reuse_forbidden, 'whole-family no-reuse proof before receipt reuse')
            rows.append(completed_unit(folder, index, live, runtime.engines, seen_names, seen_ids))
        except BaseException:
            pending.append((index, folder))
    for index, folder in pending:
        try:
            rows.append(ns['recover_one'](index, folder))
        except BaseException as error:
            rows.append({'index': index, 'all_absent': False, 'error_type': type(error).__name__})
    rows.sort(key=lambda x: x['index'])
    return {'all_owned_absent': all(x['all_absent'] for x in rows), 'units': rows,
            'closed_receipt_reuse_disabled': reuse_forbidden,
            'unit_family_identity_valid': not reuse_forbidden,
            'all_unit_commits_verified': len(pending) == 0, 'unit_count': len(folders),
            'reused_closed_receipts': len(folders) - len(pending), 'pending_units_recovered': len(pending)}


def run_operation(config, stack, runtime):
    """Called once by the actual root-selected entrypoint, never by an actor."""
    start = config.started_monotonic
    need(type(start) in (float, int) and math.isfinite(start) and 0 < start <= time.monotonic(), 'original pre-bootstrap operation clock')
    profile, request, capacity = admit(config)
    work_end, whole_end = start + profile['work_seconds'], start + profile['whole_seconds']
    need(time.monotonic() < work_end, 'admission fits original work horizon')
    root = Path(config.value['output_root']); root.mkdir(mode=0o700)
    for name in ('owner', 'units', 'actors', 'identity', 'invitations', 'arms', 'cells'):
        (root / name).mkdir(mode=0o700)
    host = config.value['host_budget']; budget = runtime.HostBudget(root, host['artifact_bytes'], host['receipt_bytes'])
    guard = install_managed_reads(config, config.bootstrap_read_bytes)
    result = {'schema': 'dmfc-complete-four-cell-outer-result/v1', 'status': 'failed_preserved',
              'config_sha256': config.sha256, 'request_sha256': config.request_sha256,
              'original_start': start, 'work_deadline': work_end, 'whole_deadline': whole_end,
              'profile': request['profile'], 'capacity': capacity, 'all_owned_absent': False,
              'automatic_retry': False, 'candidate_id': 'NEURAL-095', 'research_qualified': False}
    proc = None; old = {}; timer = None
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'no competing whole-operation alarm')
    def hard(*unused):
        # All recovery is already scheduled before this deadline. This terminal
        # alarm cannot report success or invent a final receipt.
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        os._exit(124)
    def interrupt(signum, frame):
        result['interrupted_signal'] = signum
        raise InterruptedError('whole operation interrupted')
    try:
        old[signal.SIGALRM] = signal.signal(signal.SIGALRM, hard)
        signal.setitimer(signal.ITIMER_REAL, max(.001, whole_end - time.monotonic()))
        for sig in (signal.SIGINT, signal.SIGTERM):
            old[sig] = signal.signal(sig, interrupt)
        durable(root / 'OPERATION_INTENT.json', result, budget)
        result['actual_runtime'] = runtime.verify_identity(min(work_end, time.monotonic() + 10), root / 'identity', budget)
        desc = stack.entrypoint.captured_descriptor(stack, 'controller', runtime.root)
        argv = [sys.executable, str(runtime.root / desc['path']), '--config', str(config.source_path),
                '--config-sha256', config.sha256, '--owner-directory', str(root / 'owner'),
                '--work-deadline', str(work_end), '--whole-deadline', str(whole_end)]
        proc = runtime.owner.launch(argv, root / 'owner', work_end - time.monotonic(), desc)
        while not (root / 'owner/process_completion.json').exists():
            need(time.monotonic() < work_end and proc.poll() is None, 'original whole controller work deadline')
            time.sleep(.05)
        completion = runtime.owner.read(root / 'owner/process_completion.json')
        owner = runtime.owner.read(root / 'owner/process_owner.json')
        need(completion['token'] == owner['token'] and completion.get('group_leader_waits_for_owner_stop') is True,
             'actual owned controller completion')
        result['controller_returncode'] = completion['returncode']
    except BaseException as error:
        result['error_type'] = type(error).__name__
    finally:
        guard.recovery = True
        try:
            try:
                group = runtime.owner.stop(root / 'owner', min(whole_end - 20, time.monotonic() + 10), proc)
            except BaseException as error:
                group = {'absence_verified': False, 'error_type': type(error).__name__}
            result['group_cleanup'] = group
            creator_groups = {}
            # These are separate V4 groups. Main-group failure must not prevent
            # independent attempts to stop every already known actor creator.
            for key in CELL_KEYS:
                try:
                    creator_groups[key] = stack.entrypoint.group_stop(runtime.owner,
                        root / 'actors' / key / 'owner', min(whole_end - 20, time.monotonic() + 10))
                except BaseException as error:
                    creator_groups[key] = {'absence_verified': False, 'error_type': type(error).__name__}
            result['actor_creator_group_cleanup'] = creator_groups
            need(group.get('absence_verified') is True and all(x.get('absence_verified') is True for x in creator_groups.values()),
                 'all exact creating groups absent before Docker recovery')
            actors = {}
            for key in CELL_KEYS:
                try:
                    actors[key] = stack.actor_runtime.recover_mode(config, stack, runtime, key, budget,
                        min(whole_end - 20, time.monotonic() + 60))
                except BaseException as error:
                    actors[key] = {'absence_verified': False, 'error_type': type(error).__name__}
            result['actor_cleanup'] = actors
            units = recover_numerical(root / 'units', stack.live, runtime, budget, whole_end - 20)
            result['numerical_cleanup'] = units
            result['all_owned_absent'] = units['all_owned_absent'] and all(x.get('absence_verified') is True for x in actors.values())
            path = root / 'controller_result.json'
            if path.exists():
                body = read(path, 1048576); inner = decode(body)
                result['controller_result'] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
                need(inner.get('schema') == 'dmfc-complete-four-cell-controller-result/v1' and
                     inner.get('config_sha256') == config.sha256 and inner.get('request_sha256') == config.request_sha256,
                     'exact selected complete controller result')
                if (result.get('controller_returncode') == 0 and result['all_owned_absent'] and
                    units.get('unit_family_identity_valid') is True and
                    units.get('all_unit_commits_verified') is True and 14 <= units.get('unit_count', 0) <= 46 and
                    'error_type' not in result and 'interrupted_signal' not in result and
                    inner.get('status') == 'four_cell_outputs_scored' and inner.get('study_result', {}).get('status') == 'four_cell_outputs_scored'):
                    result['status'] = 'complete_four_cell_operation'
        except BaseException as error:
            result['recovery_error_type'] = type(error).__name__
        elapsed = time.monotonic() - start
        result.update(elapsed_before_receipt_seconds=elapsed, charged_seconds=max(profile['whole_seconds'], elapsed),
                      prior_known_seconds=request['prior_known_seconds'])
        result['known_after_seconds'] = request['prior_known_seconds'] + result['charged_seconds']
        try:
            result['managed_reads_before_final_receipt'] = guard.report()
        except BaseException as error:
            result['status'] = 'failed_preserved'
            result['read_accounting_error_type'] = type(error).__name__
        if time.monotonic() >= whole_end or result['known_after_seconds'] > request['family_ceiling_seconds']:
            result['status'] = 'failed_preserved'
        try:
            durable(root / 'OUTER_RESULT.json', result, budget)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            for sig, handler in old.items():
                signal.signal(sig, handler)
    return result
