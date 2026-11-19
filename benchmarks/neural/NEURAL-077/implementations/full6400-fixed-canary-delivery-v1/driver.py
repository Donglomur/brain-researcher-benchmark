"""Versioned full-roster fixed-canary delivery verification, never model scoring."""
from __future__ import annotations

import argparse
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
import types

HERE = Path(__file__).resolve().parent
RELATIVE = 'benchmarks/neural/NEURAL-077/implementations/full6400-fixed-canary-delivery-v1'
PREDECESSOR = 'benchmarks/neural/NEURAL-077/implementations/full32-paired-runtime-v1'
COUNT = 6400
CONDITIONS = ('numeric_direct_four_demo', 'numeric_program_four_demo')
LIMITS = {'work_seconds': 3600, 'whole_seconds': 4200, 'episode_seconds': 30,
          'cleanup_seconds': 5, 'owner_settlement_seconds': 120,
          'read_bytes': 6 * 1024**3, 'write_bytes': 6 * 1024**3 - 2 * 1024**2}
BASE_PACKET_READ = 1048576 + 4194304 + 129921 + 1703 + 480 + 5
QUERY_READ = 2 * 60000
PIPE_READ = 65536 + 4096 + 4 + 1
EPISODE_WRITE = 524288
DIRECT_WRITE = 196608
COMMITMENT_WRITE = 4096
CENSUS_RESERVE = 16 * 1024**2
CLIENT_CAP = 65536


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


class Budget:
    """One cumulative operation account; case reservation is atomic."""
    def __init__(self, read_limit=LIMITS['read_bytes'], write_limit=LIMITS['write_bytes']):
        need(type(read_limit) is int and read_limit > 0 and type(write_limit) is int and write_limit > 0,
             'Positive whole-operation byte ceilings')
        self.read_limit, self.write_limit = read_limit, write_limit
        self.read_charged = self.write_reserved = self.cases_reserved = 0

    def input(self, amount):
        self.reserve(amount, 0)

    def output(self, amount):
        self.reserve(0, amount)

    def reserve(self, read_bytes, write_bytes):
        need(type(read_bytes) is int and read_bytes >= 0 and type(write_bytes) is int and write_bytes >= 0,
             'Integer byte charges')
        need(self.read_charged + read_bytes <= self.read_limit and
             self.write_reserved + write_bytes <= self.write_limit, 'Whole-operation byte budget exhausted')
        self.read_charged += read_bytes
        self.write_reserved += write_bytes

    def reserve_case(self, continuity_bytes):
        need(type(continuity_bytes) is int and continuity_bytes >= 0, 'Nonnegative exact continuity bytes')
        self.reserve(QUERY_READ + PIPE_READ + continuity_bytes,
                     EPISODE_WRITE + DIRECT_WRITE + COMMITMENT_WRITE)
        self.cases_reserved += 1


def prepare_census(trial_ids, expected_count=COUNT):
    need(type(expected_count) is int and expected_count > 0 and
         type(trial_ids) in (list, tuple) and len(trial_ids) == expected_count and
         all(type(x) is str and re.fullmatch('q-[0-9a-f]{32}', x) for x in trial_ids) and
         list(trial_ids) == sorted(set(trial_ids)), 'Complete sorted unique opaque roster required')
    return [{'ordinal': i, 'trial_id': identifier, 'status': 'unattempted', 'pid': None,
             'closure_complete': True, 'case_receipt': None, 'error_code': None}
            for i, identifier in enumerate(trial_ids)]


def drive_roster(trial_ids, context_for, episode_call, projection_sink, status_sink,
                 budget, no_tools, program_tools, *, adapter, now, work_deadline,
                 continuity_bytes, expected_count=COUNT, census=None):
    """Pure sequential join; callbacks own durable writes and actual episodes.

    projection_sink(ordinal, direct, commitment) saves the complete direct prompt.
    episode_call(ordinal, program) returns (envelope, END, case_receipt_pin).
    status_sink(row) durably records dispatching and terminal states. No callback
    can authorize a retry. Tiny expected_count is for generated controls only;
    production run always passes COUNT after authenticating PacketSession.
    """
    rows = prepare_census(trial_ids, expected_count)
    if census is not None:
        need(type(census) is list and census == rows, 'Fresh shared complete census')
        rows = census
    need(budget.cases_reserved == 0, 'One fresh case census per operation budget')
    result = {'census': rows, 'complete': False, 'stop_reason': None,
              'direct_projection_count': 0, 'process_dispatch_count': 0}
    for ordinal, identifier in enumerate(trial_ids):
        row = rows[ordinal]
        entered = False
        try:
            need(now() + 35 <= work_deadline, 'Absolute work deadline cannot fit next episode')
            budget.reserve_case(continuity_bytes)
            direct, program = [context_for(identifier, condition) for condition in CONDITIONS]
            matched = adapter.matched_commitment(direct, program, no_tools, program_tools)
            projection_sink(ordinal, direct, matched)
            result['direct_projection_count'] += 1
            # A durable started state precedes any possible native dispatch.
            row.update(status='dispatching', closure_complete=False)
            status_sink(dict(row))
            entered = True
            envelope, end, receipt_pin = episode_call(ordinal, program)
            row.update(pid=end.get('pid'), closure_complete=adapter.end_closed(end), case_receipt=receipt_pin)
            result['process_dispatch_count'] += int(end.get('pid') is not None)
            row['status'] = 'failed_closed' if row['closure_complete'] else 'failed_unresolved'
            adapter.accept_episode(envelope, end, identifier, program['context_sha256'])
            # The pinned episode creates a new Popen and fully reaps it before
            # returning. Integer PIDs can legitimately recycle in a long run.
            row['status'] = 'closed_pass'
            status_sink(dict(row))
        except BaseException as error:
            result['stop_reason'] = {'ordinal': ordinal, 'type': type(error).__name__,
                                     'message': str(error)[:256]}
            row['error_code'] = type(error).__name__[:64]
            if row['status'] == 'dispatching':
                row['status'] = 'failed_unresolved' if entered else 'failed_closed'
                row['closure_complete'] = not entered
            elif row['status'] == 'unattempted' and budget.cases_reserved > ordinal:
                row['status'] = 'failed_closed'
            if row['status'] != 'unattempted':
                try:
                    status_sink(dict(row))
                except BaseException as sink_error:
                    result['status_sink_error'] = type(sink_error).__name__
            break
    result['counts'] = {name: sum(row['status'] == name for row in rows)
                        for name in ('closed_pass', 'failed_closed', 'failed_unresolved', 'unattempted')}
    result['complete'] = result['counts']['closed_pass'] == expected_count and result['stop_reason'] is None
    result['all_exercised_children_closed'] = all(row['closure_complete'] for row in rows)
    result['read_bytes_conservatively_charged'] = budget.read_charged
    result['artifact_bytes_conservatively_reserved'] = budget.write_reserved
    return result


# Bootstrapping uses the same bounded ordinary-file capture contract as the
# pinned runtime; no dependency is imported before its complete bytes match.
def capture(path, maximum, budget, expected=None):
    path = Path(path)
    need(path.is_absolute() and all(not p.is_symlink() for p in (path, *path.parents)), 'Direct source paths')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum,
             'Bounded ordinary single-link source')
        budget.input(before.st_size)
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(before.st_size)
        fields = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns)
        need(len(body) == before.st_size and fields(before) == fields(os.fstat(fd)) == fields(path.lstat()),
             'Source changed during capture')
    finally:
        os.close(fd)
    need(expected is None or pin(body) == {k: expected[k] for k in ('bytes', 'sha256')}, 'Source pin mismatch')
    return body


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= 1048576 and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Exact source descriptor')


def absolute(value):
    need(type(value) is str and Path(value).is_absolute() and '..' not in Path(value).parts, 'Absolute operator path')
    return Path(value)


def in_runtime(path):
    return any(path.is_relative_to(root) for root in ('/System', '/usr', '/Library/Frameworks'))


def validate_config(value, here=HERE):
    need(type(value) is dict and set(value) == {
        'schema', 'selected', 'repository_root', 'public_root', 'public_manifest', 'output_root',
        'interpreter', 'sandbox', 'operator_source', 'source_bindings', 'query_count', 'limits'}, 'Exact full-roster config')
    need(value['schema'] == 'erp-full6400-fixed-canary-delivery-v1' and value['selected'] is True,
         'Separately selected full-roster activation required')
    root, packet, output = [absolute(value[key]) for key in ('repository_root', 'public_root', 'output_root')]
    need(root / RELATIVE == Path(here), 'Exact versioned sibling location')
    need(not in_runtime(packet) and not in_runtime(output), 'Packet/output outside runtime data scopes')
    need(not output.is_relative_to(packet) and not packet.is_relative_to(output) and
         not output.is_relative_to(root) and not root.is_relative_to(output), 'Disjoint output, packet and repository')
    for key in ('public_manifest', 'operator_source', 'source_bindings'):
        descriptor(value[key])
    for key in ('interpreter', 'sandbox'):
        row = value[key]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Exact executable descriptor')
        need(in_runtime(absolute(row['path'])), 'Supported runtime executable location')
        descriptor({k: row[k] for k in ('bytes', 'sha256')})
    need(value['sandbox']['path'] == '/usr/bin/sandbox-exec', 'Maintained macOS sandbox only')
    need(type(value['query_count']) is int and value['query_count'] == COUNT, 'All 6400 queries; no subset selector')
    need(value['limits'] == LIMITS and all(type(v) is int for v in value['limits'].values()), 'Frozen global limits')
    return value


class ReservedWriter:
    """A bounded partition of an already charged write reservation."""
    def __init__(self, adapter, limit):
        self.adapter, self.limit, self.written = adapter, limit, 0

    def write(self, path, body):
        need(self.written + len(body) <= self.limit, 'Reserved output partition exhausted')
        self.written += len(body)  # Charge failed/partial writes too.
        return self.adapter.write_new(path, body, None, reserved=True)


class Journal:
    def __init__(self, path, writer):
        self.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        self.writer, self.lines = writer, 0

    def append(self, row):
        body = encode(row)
        need(len(body) <= 512 and self.lines < 2 * COUNT + 1, 'Bounded append-only state journal')
        need(self.writer.written + len(body) <= self.writer.limit, 'Journal partition exhausted')
        self.writer.written += len(body); self.lines += 1
        view = memoryview(body)
        while view:
            count = os.write(self.fd, view)
            need(count > 0, 'Journal write progress')
            view = view[count:]
        os.fsync(self.fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd); self.fd = None


def _run(config, operation_started, operation_deadline):
    budget = Budget()
    # Charge in-memory selected configuration conservatively; outer admission
    # reads/ledger work remain separately included by the resource owner.
    budget.input(65536)
    operator = capture(HERE / 'driver.py', 65536, budget, config['operator_source'])
    binding_body = capture(HERE / 'SOURCE_BINDINGS.json', 16384, budget, config['source_bindings'])
    bindings = decode(binding_body)
    need(type(bindings) is dict and set(bindings) == {'schema', 'members'} and
         bindings['schema'] == 'erp-full6400-fixed-canary-sources-v1', 'Versioned dependency closure')
    members = bindings['members']; root = Path(config['repository_root'])
    need(type(members) is dict and set(members) == {'public_runtime', 'public_runtime_bindings'}, 'Two immutable roots')
    expected = {'public_runtime': PREDECESSOR + '/runtime.py',
                'public_runtime_bindings': PREDECESSOR + '/SOURCE_BINDINGS.json'}
    for name, row in members.items():
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and row['path'] == expected[name],
             'Exact predecessor source path')
        descriptor({k: row[k] for k in ('bytes', 'sha256')})
    bodies = {name: capture(root / row['path'], 65536, budget, row) for name, row in members.items()}
    adapter = types.ModuleType('erp_full6400_runtime'); adapter.__file__ = str(root / members['public_runtime']['path'])
    exec(compile(bodies['public_runtime'], adapter.__file__, 'exec'), adapter.__dict__)
    old_bindings = adapter.validate_bindings(decode(bodies['public_runtime_bindings']))
    sources = {name: capture(root / row['path'], 65536, budget, row) for name, row in old_bindings['members'].items()}
    need(decode(sources['evaluator_bindings']) == {
        'schema': 'erp-full32-portable-evaluator-sources-v1',
        'members': {name: {'path': name + '.py', **pin(sources[name])} for name in ('bundle', 'consumer')}},
        'Pinned evaluator dependency join')
    for name in ('interpreter', 'sandbox'):
        capture(config[name]['path'], 1048576, budget, config[name])
        need(os.access(config[name]['path'], os.X_OK), 'Executable permission required')
    need(sys.platform == 'darwin', 'Maintained macOS sandbox; no host fallback')
    output = Path(config['output_root'])
    need(all(not p.is_symlink() for p in (output, *output.parents)) and not output.exists(), 'Fresh direct output root')
    output.mkdir(mode=0o700)
    budget.output(CENSUS_RESERVE)
    metadata = ReservedWriter(adapter, CENSUS_RESERVE)
    result = {'schema': 'erp-full6400-fixed-canary-result-v1', 'status': 'failed', 'operation_complete': False,
              'model_calls': 0, 'direct_model_calls': 0, 'scores_computed': False, 'private_inputs_opened': False,
              'query_count': COUNT, 'inventory_admitted': False, 'all_exercised_children_closed': True,
              'operator_source': pin(operator), 'source_bindings': pin(binding_body),
              'public_manifest': config['public_manifest'], 'canonical_configuration': pin(encode(config)),
              'operation_started_monotonic': operation_started,
              'operation_deadline_monotonic': operation_deadline + LIMITS['owner_settlement_seconds'],
              'public_finalization_deadline_monotonic': operation_deadline,
              'qualification_scope': 'Non-AI fixed-canary delivery only; no direct prediction or paired study arm'}
    session = journal = None; rows = None
    try:
        modules = {name: adapter.loaded('erp_full6400_' + name, root / old_bindings['members'][name]['path'], sources[name])
                   for name in ('evaluator', 'bundle', 'consumer', 'wire', 'owned', 'profile', 'episode')}
        modules['wire'] = modules['profile'].wrap_wire(modules['wire'])
        witness_root = output / 'witnesses'; witness_root.mkdir(mode=0o700)
        names = ('prior_episode', 'answer', 'person', 'manifest')
        witnesses = {name: str(witness_root / (name + '.bin')) for name in names}
        for name, path in witnesses.items():
            adapter.write_new(Path(path), ('GENERATED NON-NEURAL ' + name + '\n').encode(), budget)
        candidate_config = {'witnesses': witnesses, 'witnesses_are_generated_non_neural': True,
                            'actual_private_paths_provided': False}
        staging = output / 'bundle-input'; staging.mkdir(mode=0o700)
        adapter.write_new(staging / 'canary.py', sources['canary'], budget)
        candidate_body = encode(candidate_config)
        adapter.write_new(staging / 'config.json', candidate_body, budget)
        budget.input(modules['bundle'].MODULE_CAP + modules['bundle'].CONFIG_CAP + 2)
        frozen = modules['bundle'].capture(staging, {'schema': 'neural077_python_bundle_v1',
                  'entry_module': 'canary', 'modules': ['canary.py'], 'config': 'config.json'})
        client_body = modules['bundle'].verify(frozen)
        need(len(client_body) <= CLIENT_CAP, 'Fixed client envelope')
        client_root = output / 'client'; client_root.mkdir(mode=0o700)
        frozen_pin = adapter.write_new(client_root / 'FROZEN.json', encode(frozen), budget)
        client = client_root / 'CLIENT.py'; client_pin = adapter.write_new(client, client_body, budget)
        result.update(client=client_pin, frozen=frozen_pin, bundle_identity=frozen['bundle_identity'])
        result['effective_profile'] = adapter.write_new(output / 'SELECTED_PROFILE.sb',
                                                      modules['wire'].sandbox_profile(client).encode(), budget)
        continuity_rows = [(HERE / 'driver.py', config['operator_source']),
                           (HERE / 'SOURCE_BINDINGS.json', config['source_bindings'])]
        continuity_rows += [(root / row['path'], row) for row in members.values()]
        continuity_rows += [(root / row['path'], row) for row in old_bindings['members'].values()]
        continuity_rows += [(Path(config[name]['path']), config[name]) for name in ('interpreter', 'sandbox')]
        continuity_rows += [(client, client_pin)]
        continuity_bytes = sum(row['bytes'] for path, row in continuity_rows)
        result['per_case_continuity_read_bytes'] = continuity_bytes
        # This is a feasibility ceiling, not a promise to finish within time.
        need(budget.read_charged + BASE_PACKET_READ + COUNT * (QUERY_READ + PIPE_READ + continuity_bytes) +
             continuity_bytes + frozen_pin['bytes'] <= budget.read_limit, 'Full-roster read ceiling before packet admission')
        need(budget.write_reserved + COUNT * (EPISODE_WRITE + DIRECT_WRITE + COMMITMENT_WRITE) <= budget.write_limit,
             'Full-roster write ceiling before packet admission')
        budget.input(BASE_PACKET_READ)
        session = modules['consumer'].PacketSession(config['public_root'], config['public_manifest'])
        rows = prepare_census(session.trial_ids)
        initial = b''.join(encode({key: row[key] for key in ('ordinal', 'trial_id', 'status')}) for row in rows)
        need(len(initial) <= COUNT * 128, 'Initial census envelope')
        result['initial_census'] = metadata.write(output / 'INITIAL_CENSUS.jsonl', initial)
        result['inventory_admitted'] = True
        journal = Journal(output / 'STATUS.jsonl', metadata)
        cases = output / 'cases'; cases.mkdir(mode=0o700)

        def continuity(account):
            for path, descriptor_row in continuity_rows:
                capture(path, 1048576, account, descriptor_row)

        def project(ordinal, direct, commitment):
            case = cases / ('%04d' % ordinal); case.mkdir(mode=0o700)
            body = direct['prompt'].encode()
            need(len(body) <= DIRECT_WRITE, 'Complete direct prompt bound')
            adapter.write_new(case / 'DIRECT_PROMPT.utf8', body, None, reserved=True)
            projection = encode({'schema': 'erp-full6400-complete-direct-projection-v1', **commitment,
                                 'direct_prompt': pin(body), 'condition': CONDITIONS[0], 'ordinal': ordinal})
            need(len(projection) <= COMMITMENT_WRITE // 2, 'Projection metadata bound')
            adapter.write_new(case / 'PROJECTION.json', projection, None, reserved=True)

        def invoke(ordinal, program):
            account = Budget(read_limit=continuity_bytes, write_limit=1)
            continuity(account)  # Already charged atomically by reserve_case.
            need(account.read_charged == continuity_bytes, 'Exact reserved continuity')
            need(time.monotonic() + 35 <= operation_started + LIMITS['work_seconds'], 'Absolute work deadline before dispatch')
            local = {'written': 0}; case = cases / ('%04d' % ordinal)
            evaluator = types.SimpleNamespace(**vars(modules['evaluator']))
            def bounded_write(path, body, account=None):
                need(account is local and local['written'] + len(body) <= EPISODE_WRITE,
                     'Pre-write episode capture reservation')
                return modules['evaluator'].write(path, body, account)
            evaluator.write = bounded_write
            envelope, end = modules['episode'].episode(
                evaluator, program, CONDITIONS[1], case / 'episode', client, config['interpreter']['path'],
                {'episode_work_seconds': 30, 'episode_cleanup_seconds': 5},
                operation_started + LIMITS['work_seconds'], modules, local, generated_protocol_only=False)
            need(local['written'] <= EPISODE_WRITE, 'Per-episode reserved capture envelope')
            receipt = encode({'schema': 'erp-full6400-case-receipt-v1', 'ordinal': ordinal,
                              'trial_id': program['trial_id'], 'context_sha256': program['context_sha256'],
                              'pid': end['pid'], 'closure_complete': adapter.end_closed(end),
                              'end': pin(modules['evaluator'].encode(end)),
                              'attempt': pin(modules['evaluator'].encode(envelope)),
                              'input': end['input'], 'output': end['output'],
                              'stderr': (end.get('stderr_capture') or {}).get('file')})
            need(len(receipt) <= COMMITMENT_WRITE // 2, 'Case metadata bound')
            receipt_pin = adapter.write_new(case / 'CASE.json', receipt, None, reserved=True)
            return envelope, end, receipt_pin

        joined = drive_roster(session.trial_ids, session.context, invoke, project, journal.append,
                              budget, modules['consumer'].NO_TOOLS, modules['consumer'].PROGRAMME_TOOLS,
                              adapter=adapter, now=time.monotonic, work_deadline=operation_started + LIMITS['work_seconds'],
                              continuity_bytes=continuity_bytes, census=rows)
        rows = joined.pop('census'); result.update(joined)
        need(time.monotonic() < operation_deadline, 'Absolute finalization deadline')
        continuity(budget)
        capture(client_root / 'FROZEN.json', 1048576, budget, frozen_pin)
        if joined['complete']:
            result.update(status='full_roster_fixed_canary_delivery_passed', operation_complete=True)
    except BaseException as error:
        result.update(status='failed', operation_complete=False,
                      error={'type': type(error).__name__, 'message': str(error)[:512]})
    finally:
        if journal is not None:
            try:
                journal.close()
            except BaseException as error:
                result.update(status='failed', operation_complete=False, journal_close_error=type(error).__name__)
        if session is not None:
            try:
                session.close()
            except BaseException as error:
                result.update(status='failed', operation_complete=False, session_close_error=type(error).__name__)
        # Closure is derived from the shared live inventory even if joining or
        # aggregation was interrupted before drive_roster returned.
        if rows is not None:
            for row in rows:
                if row['status'] == 'dispatching':
                    row.update(status='failed_unresolved', closure_complete=False, error_code='InterruptedJoin')
            result['all_exercised_children_closed'] = all(row['closure_complete'] for row in rows)
            result['counts'] = {name: sum(row['status'] == name for row in rows) for name in
                                ('closed_pass', 'failed_closed', 'failed_unresolved', 'unattempted')}
        # A consumed one-shot alarm does not grant a new finalization window.
        need(time.monotonic() < operation_deadline, 'Absolute deadline before final evidence')
        if rows is not None:
            lines = [encode(row) for row in rows]
            need(all(len(line) <= 1024 for line in lines), 'Final census row envelope')
            result['final_census'] = metadata.write(output / 'FINAL_CENSUS.jsonl', b''.join(lines))
        result['read_bytes_conservatively_charged'] = budget.read_charged
        result['artifact_bytes_conservatively_reserved'] = budget.write_reserved
        result['accounting'] = 'Reservations include consumer sentinels/spans, continuity, pipe reads and complete captures; not measured I/O'
        result['elapsed_seconds'] = time.monotonic() - operation_started
        body = encode(result); need(len(body) <= 262144, 'Final result envelope')
        need(time.monotonic() < operation_deadline, 'Absolute deadline before result evidence')
        metadata.write(output / 'RESULT.json', body)
    return result


def run(config, *, operation_started, operation_deadline):
    """Owner directly calls this in its main thread while retaining its lease.

    Both monotonic values belong to the owner's original admission window;
    this API cannot start a fresh nested 4200-second allocation. The last 120
    seconds belong to owner settlement, leaving 480 seconds for driver closure. An owner must
    cancel only its own timer before entry and rearm its remaining absolute
    deadline afterwards. No active caller timer is silently overwritten.
    """
    validate_config(config)
    need(all(type(v) in (int, float) and math.isfinite(v) for v in (operation_started, operation_deadline)) and
         abs(operation_deadline - operation_started - LIMITS['whole_seconds']) < 0.001,
         'Original absolute 4200-second operation envelope required')
    now = time.monotonic()
    need(operation_started <= now and now + 35 <= operation_started + LIMITS['work_seconds'],
         'Admission consumes the same absolute work window')
    need(threading.current_thread() is threading.main_thread(), 'Main-thread owner required')
    need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'Existing caller timer must not be replaced')
    handlers = {}
    def interrupted(signum, frame):
        raise TimeoutError('Absolute operation deadline') if signum == signal.SIGALRM else InterruptedError('Owner interrupted')
    try:
        for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            handlers[sig] = signal.signal(sig, interrupted)
        public_deadline = operation_deadline - LIMITS['owner_settlement_seconds']
        need(time.monotonic() < public_deadline, 'Owner settlement reserve remains intact')
        signal.setitimer(signal.ITIMER_REAL, max(0.001, public_deadline - time.monotonic()))
        return _run(config, operation_started, public_deadline)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main(argv=None):
    # The admitting owner supplies its original clock; the CLI cannot silently
    # create a fresh allocation after admission. This is not a controller.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--operation-started', type=float, required=True)
    parser.add_argument('--operation-deadline', type=float, required=True)
    args = parser.parse_args(argv)
    path = args.config.absolute(); need(not in_runtime(path), 'Operator config outside child runtime scopes')
    body = capture(path, 65536, Budget())
    need(pin(body)['sha256'] == args.config_sha256, 'Selected config digest')
    result = run(decode(body), operation_started=args.operation_started, operation_deadline=args.operation_deadline)
    print(json.dumps({k: result[k] for k in ('status', 'operation_complete', 'all_exercised_children_closed')}))
    return 0 if result['operation_complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
