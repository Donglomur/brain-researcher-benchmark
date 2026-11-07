"""Complete NEURAL035 single-program plus independent operator collection.

Source component. Requires the exact pinned parent program and separate runtime
qualification; it never authorizes private grading or scientific claims.
"""
import time
ORIGIN = time.monotonic()
import signal
INITIAL_HANDLERS = {}
FINAL_END = ORIGIN + 120


def expired(*_):
    raise TimeoutError('original NEURAL035 adapter deadline')


def restore_handlers():
    failed = False
    try:
        signal.setitimer(signal.ITIMER_REAL, 0)
    except BaseException:
        failed = True
    for number, handler in INITIAL_HANDLERS.items():
        try:
            signal.signal(number, handler)
        except BaseException:
            failed = True
    return not failed


def startup_owned():
    before = time.monotonic()
    timer = signal.getitimer(signal.ITIMER_REAL)
    after = time.monotonic()
    if not (INITIAL_HANDLERS and signal.getsignal(signal.SIGALRM) is expired
            and timer[1] == 0.0 and 0.0 < timer[0] <= ORIGIN + 120 - before + 0.001
            and after < ORIGIN + 120):
        raise ValueError('live nonperiodic original120s adapter startup ownership')


def enter_startup():
    global INITIAL_HANDLERS
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError('fresh standalone adapter has no inherited timer')
    INITIAL_HANDLERS = {n: signal.getsignal(n) for n in
                        (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    try:
        signal.signal(signal.SIGALRM, expired)
        remaining = ORIGIN + 120 - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('original startup expired before timer installation')
        signal.setitimer(signal.ITIMER_REAL, remaining)
        startup_owned()
    except BaseException as error:
        if not restore_handlers():
            error.add_note('Independent timer/handler restoration uncertainty')
        raise


if __name__ == '__main__':
    enter_startup()

try:
    import argparse
    import ast
    import hashlib
    import json
    import math
    import os
    from pathlib import Path
    import stat
    import sys
except BaseException:
    if INITIAL_HANDLERS:
        restore_handlers()
    raise SystemExit(2)

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[5]
TASK = 'NEURAL-035'
READ_CAP = 4000000
PROGRAM_CAP = 131072
PREDICTION_CAP = 2000000
SCOPE = {'sessions': 14, 'mice': 7, 'session_local_cells': 1012,
         'query_blocks': 28, 'calibration_blocks_per_session': 4,
         'validation_blocks_per_session': 1, 'samples_per_block': 300,
         'window_seconds': 30, 'query_starts_seconds': [210, 270],
         'candidate_programs': 1, 'isolated_producer_phases': 2,
         'roles': ['candidate', 'operator'], 'query_records_per_role': 28,
         'public_export_members': 21, 'whole_paper_reproduction': False}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def equal(left, right):
    return encode(left) == encode(right)


def parse(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value, maximum, allow_empty=False):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact bounded descriptor')
    need(type(value['bytes']) is int and (0 if allow_empty else 1) <= value['bytes'] <= maximum,
         'bounded nonboolean extent')
    digest = value['sha256']
    need(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
         'exact lowercase SHA256')
    return value


def literal(value):
    need(type(value) is str and value and not any(c in value for c in '\x00\r\n,'), 'literal path')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value, 'canonical absolute path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'unlinked path components')
    return path


def relative(value):
    need(type(value) is str and value and '\\' not in value and not value.startswith('/')
         and all(p not in ('', '.', '..') for p in value.split('/')), 'confined repository relative path')
    return literal(str(ROOT / value))


def operand(value, maximum):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact selected descriptor')
    return literal(value['path']), descriptor({k: value[k] for k in ('bytes', 'sha256')}, maximum)


class Captures:
    def __init__(self, end):
        self.end = end
        self.reserved = 0

    def tick(self):
        need(time.monotonic() < self.end, 'original adapter deadline')

    def read(self, path, maximum, expected=None, allow_empty=False):
        self.tick()
        path = literal(str(path))
        if expected is not None:
            descriptor(expected, maximum, allow_empty)
        self.tick()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        primary = None
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                 and (0 if allow_empty else 1) <= before.st_size <= maximum, 'ordinary bounded captured file')
            need(expected is None or before.st_size == expected['bytes'], 'pinned extent before read')
            charge = before.st_size + 1
            need(self.reserved + charge <= READ_CAP, 'whole additional adapter metadata cap')
            self.reserved += charge
            self.tick()
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(charge)
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns')
            signature = lambda q: tuple(getattr(q, k) for k in fields)
            need(len(raw) == before.st_size and signature(before) == signature(os.fstat(fd)) == signature(path.lstat()),
                 'stable fd and named capture')
            need(expected is None or pin(raw) == expected, 'exact captured content')
            self.tick()
            return raw
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                os.close(fd)
            except BaseException as error:
                if primary is None:
                    raise
                primary.add_note('Capture descriptor close uncertainty: ' + type(error).__name__)


def metadata(captures, value, cap=32768):
    path, identity = operand(value, cap)
    return parse(captures.read(path, cap, identity)), (path, identity, cap)


def whole_seconds(candidate_seconds):
    need(type(candidate_seconds) is int and 1 <= candidate_seconds <= 7200, 'prospective candidate seconds')
    return candidate_seconds + 900


def memory_limit(value):
    need(type(value) is int and 536870912 <= value <= 4294967296 and value % 1048576 == 0,
         'prospective512MiB to4GiB memory profile')
    return value


def runtime_review(value, source, binding):
    keys = {'schema', 'task_id', 'qualified', 'adapter_source', 'controller_source',
            'controller_runtime', 'host_python', 'candidate_seconds', 'memory_bytes',
            'scope', 'resources', 'metadata_read_cap', 'adapter_persistent_writes',
            'complete_observer_route_qualified', 'original_clock_handoff_qualified',
            'scientific_qualification', 'private_grading_authorized', 'evidence'}
    need(type(value) is dict and set(value) == keys
         and value['schema'] == 'neural035_full14_registration_runtime_v1'
         and value['task_id'] == TASK and value['qualified'] is True,
         'independent complete NEURAL035 adapter runtime prerequisite')
    need(value['adapter_source'] == source
         and value['controller_source'] == binding['controller_source']
         and value['host_python'] == str(Path(sys.executable).resolve())
         and equal(value['scope'], SCOPE) and equal(value['resources'], binding['resources']),
         'exact independently qualified source/interpreter/scope/resources')
    whole_seconds(value['candidate_seconds']); memory_limit(value['memory_bytes'])
    need(type(value['metadata_read_cap']) is int and value['metadata_read_cap'] == READ_CAP
         and type(value['adapter_persistent_writes']) is int and value['adapter_persistent_writes'] == 0
         and value['complete_observer_route_qualified'] is True and value['original_clock_handoff_qualified'] is True
         and value['scientific_qualification'] is False and value['private_grading_authorized'] is False,
         'complete route qualification does not qualify science or grading')
    operand(value['controller_runtime'], 32768)
    operand(value['evidence'], 1048576)
    return value


class Terminal:
    def __init__(self, end):
        self.end = end
        self.parts = []
        self.size = 0

    def write(self, value):
        need(type(value) is str and time.monotonic() < self.end, 'original-clock bounded observer terminal')
        size = len(value.encode())
        need(self.size + size <= 8192, 'observer terminal cap')
        self.parts.append(value); self.size += size
        return len(value)

    def flush(self):
        need(time.monotonic() < self.end, 'observer terminal deadline')


def own_sources(captures, expected):
    manifest = parse(captures.read(HERE / 'SOURCE_MANIFEST.json', 32768, expected))
    need(type(manifest) is dict and set(manifest) == {'schema', 'task_id', 'files'}
         and manifest['schema'] == 'neural035_full14_registration_source_v1'
         and manifest['task_id'] == TASK
         and set(manifest['files']) == {'adapter.py', 'BINDINGS.json', 'README.md'},
         'exact complete adapter source closure')
    bodies = {n: captures.read(HERE / n, 131072, descriptor(d, 131072))
              for n, d in manifest['files'].items()}
    binding = parse(bodies['BINDINGS.json'])
    need(binding['schema'] == 'neural035_full14_registration_bindings_v1'
         and binding['task_id'] == TASK and equal(binding['scope'], SCOPE)
         and binding['private_grading_authorized'] is False
         and type(binding['adapter_read_cap']) is int and binding['adapter_read_cap'] == READ_CAP,
         'complete source-only NEURAL035 adapter binding')
    descriptor(binding['controller_source'], 32768)
    return binding


def adapter_startup_guard(origin):
    need(type(origin) in (int, float) and math.isfinite(origin) and origin == ORIGIN,
         'same exact original adapter origin')
    startup_owned()


def original_observer(raw, filename):
    """Validate the native owner interface, compile the original bytes unchanged."""
    tree = ast.parse(raw, filename)
    origins = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
               and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'ORIGIN']
    expected = ast.parse("globals().get('ADAPTER_ORIGIN',time.monotonic())", mode='eval').body
    need(len(origins) == 1 and ast.dump(origins[0].value) == ast.dump(expected),
         'one exact native original-origin interface')
    owner = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'enter_startup'), None)
    clause = ast.parse("if 'ADAPTER_ORIGIN' in globals():\n    guard=globals().get('ADAPTER_STARTUP_GUARD')\n    if not callable(guard):raise ValueError('explicit original adapter owner')\n    guard(ORIGIN)").body[0]
    need(owner is not None and isinstance(owner.body[0], ast.If)
         and ast.dump(owner.body[0].test) == ast.dump(clause.test)
         and [ast.dump(n) for n in owner.body[0].body] == [ast.dump(n) for n in clause.body],
         'exact native startup owner callback before observer handler changes')
    final = ast.parse("if __name__=='__main__':\n    result=entry()\n    if time.monotonic()>=FINAL_END:result=2\n    raise SystemExit(result)").body[0]
    need(ast.dump(tree.body[-1]) == ast.dump(final), 'original entry and post-cleanup deadline guard')
    return compile(raw, filename, 'exec')


def target(captures, binding):
    manifest = parse(captures.read(relative(binding['controller_manifest_path']), 32768,
                                  binding['controller_source']))
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'neural035_full14_program_source_v1'
         and equal(manifest['files'], binding['controller_members'])
         and len(manifest['files']) == 16, 'exact complete16-member program source')
    directory = relative(binding['controller_directory'])
    need(sum(descriptor(d, 262144, True)['bytes'] for d in manifest['files'].values()) <= 1500000,
         'bounded whole program source closure')
    bodies = {}
    for name, identity in manifest['files'].items():
        need(type(name) is str and name and '/' not in name and '\\' not in name and name not in ('.', '..'),
             'flat source member name')
        bodies[name] = captures.read(directory / name, 262144, identity, True)
    selected = parse(bodies['BINDINGS.json'])
    need(selected['schema'] == 'neural035_full14_bindings_v1' and selected['task_id'] == TASK
         and selected['private_grading_authorized'] is False and selected['runtime_qualified'] is False
         and selected['scope'] == {'cells': 1012, 'mice': 7, 'query_blocks': 28, 'sessions': 14}
         and selected['package'] == binding['package'] and selected['image'] == binding['image']
         and equal(selected['original_source'], binding['original_source'])
         and equal(selected['metadata_dependencies'], binding['metadata_dependencies'])
         and equal(selected['public_files'], binding['public_files'])
         and type(selected['public_bytes']) is int and selected['public_bytes'] == 11648181,
         'same complete public scope/source/image/metadata bindings')
    need(len(selected['public_files']) == 21
         and sum(d['bytes'] for d in selected['public_files']) == selected['public_bytes'],
         'complete21-member public projection identities; bodies remain unopened')
    for row in binding['original_source'] + binding['metadata_dependencies']:
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'exact source dependency descriptor')
        captures.read(relative(row['path']), 262144,
                      descriptor({k: row[k] for k in ('bytes', 'sha256')}, 262144))
    row = binding['resource_descriptor']
    resource = parse(captures.read(relative(row['path']), 32768,
                                  descriptor({k: row[k] for k in ('bytes', 'sha256')}, 32768)))
    need(equal(resource, binding['resources']['original_program_resources']), 'same prospective program resource plan')
    filename = directory / 'observe.py'
    return original_observer(bodies['observe.py'], str(filename)), filename, bodies


def selection_metadata(value, source, binding, certificate, captures):
    keys = {'schema', 'execution_selected', 'task_id', 'repository', 'output', 'program', 'source',
            'docker_binary', 'docker_socket', 'candidate_seconds', 'operator_seconds', 'memory_bytes',
            'other_future_bytes', 'contexts', 'retained_bytes', 'managed_reads', 'managed_writes',
            'whole_seconds', 'method_review', 'runtime_review', 'private_grading_authorized'}
    need(type(value) is dict and set(value) == keys
         and value['schema'] == 'neural035_full14_program_selection_v1'
         and value['execution_selected'] is True and value['task_id'] == TASK
         and value['source'] == source and value['private_grading_authorized'] is False,
         'exact original selected complete two-producer authority')
    need(value['contexts'] == [0, 1] and all(type(n) is int for n in value['contexts'])
         and type(value['operator_seconds']) is int and value['operator_seconds'] == 300,
         'complete candidate/operator phases with fixed operator cap')
    seconds = whole_seconds(value['candidate_seconds']); memory_limit(value['memory_bytes'])
    need(value['candidate_seconds'] == certificate['candidate_seconds']
         and value['memory_bytes'] == certificate['memory_bytes']
         and value['runtime_review'] == certificate['controller_runtime'], 'same qualified original runtime profile')
    expected = {'retained_bytes': 67108864, 'managed_reads': 285212672,
                'managed_writes': 67125248, 'whole_seconds': seconds}
    need(all(type(value[k]) is int and value[k] == v for k, v in expected.items())
         and type(value['other_future_bytes']) is int and value['other_future_bytes'] >= 0,
         'same complete prospective resource envelope')
    for key in ('repository', 'output', 'docker_binary', 'docker_socket'):
        need(type(value[key]) is str and len(value[key].encode()) <= 512, 'bounded selected absolute path')
        literal(value[key])
    need(literal(value['repository']) == ROOT, 'same exact source repository')
    operand(value['program'], PROGRAM_CAP)
    method, mp = metadata(captures, value['method_review'])
    runtime, rp = metadata(captures, value['runtime_review'])
    for review in (method, runtime):
        need(type(review) is dict and review.get('task_id') == TASK and review.get('approved') is True
             and review.get('source') == source
             and review.get('program') == {k: value['program'][k] for k in ('bytes', 'sha256')},
             'original root source/program review')
    need(method.get('schema') == 'neural035_chronological_method_review_v1', 'original method review schema')
    for key in ('one_frozen_method_all14_sessions', 'calibration_development_validation_selection',
                'final_refit_at_most_five_public_blocks', 'no_query_trace_target_or_related_fulltrace_access',
                'no_private_feedback', 'prior_exposure_audited'):
        need(method.get(key) is True, 'complete original method attestation: ' + key)
    need(method.get('artifact_hashes_alone_prove_chronology') is False
         and method.get('new_animal_or_event_specific_claim') is False, 'no unsupported history or frontier claim')
    need(runtime.get('schema') == 'neural035_runtime_review_v1' and runtime.get('image') == binding['image']
         and runtime.get('candidate_seconds') == value['candidate_seconds']
         and runtime.get('operator_seconds') == 300 and runtime.get('memory_bytes') == value['memory_bytes']
         and runtime.get('full14_two_phase_isolation_cleanup_qualified') is True
         and runtime.get('numpy_version') == '2.2.6'
         and runtime.get('native_scientific_method_parity_claimed') is False,
         'separate qualified original native environment; no current scientific parity')
    return [mp, rp]


def bind(args, captures, source, binding):
    review_path = literal(args.review)
    raw = captures.read(review_path, 32768)
    review = parse(raw)
    fields = {'schema', 'task_id', 'approved', 'adapter_source', 'controller_source', 'selection',
              'program', 'adapter_runtime', 'typed_result', 'private_grading_authorized'}
    need(type(review) is dict and set(review) == fields
         and review['schema'] == 'neural035_full14_registration_review_v1'
         and review['task_id'] == TASK and review['approved'] is True
         and review['adapter_source'] == source and review['controller_source'] == binding['controller_source']
         and review['typed_result'] == 'neural035_full14_unscored_result_v1'
         and review['private_grading_authorized'] is False, 'root complete NEURAL035 adapter authority')
    qualified, qp = metadata(captures, review['adapter_runtime'])
    certificate = runtime_review(qualified, source, binding)
    # No selection, candidate or output operand is converted or read above this gate.
    selected, sp = metadata(captures, review['selection'])
    pins = [(review_path, pin(raw), 32768), qp, sp]
    pins += selection_metadata(selected, binding['controller_source'], binding, certificate, captures)
    need(selected['program'] == review['program']
         and literal(args.program) == literal(selected['program']['path']), 'same selected single program; body unopened')
    need(type(args.other_reserve_bytes) is int and args.other_reserve_bytes >= 0
         and args.other_reserve_bytes == selected['other_future_bytes'], 'same fresh OTHER reservation')
    output = literal(args.output); external = literal(str(output) + '.observer')
    need(output == literal(selected['output']) and not os.path.lexists(output) and not os.path.lexists(external),
         'fresh complete attempt and external observer slot')
    need(not output.is_relative_to(ROOT) and not external.is_relative_to(ROOT), 'attempt outside immutable source tree')
    for path, _, _ in pins:
        need(not path.is_relative_to(output) and path != external, 'authority outside mutable attempt')
    return selected, sp, pins


def invoke(code, path, selected_operand, controller, whole, outer, output):
    startup_owned()
    old_argv, old_stdout = sys.argv, sys.stdout
    terminal = Terminal(outer)
    selected = selected_operand[0]
    external = str(output) + '.observer'
    sys_args = [str(path), '--source-pin', encode(controller).decode(), '--selection', str(selected),
                '--selection-pin', encode(selected_operand[1]).decode(), '--external-output', external]
    success = False
    primary = None
    try:
        sys.argv = sys_args; sys.stdout = terminal
        namespace = {'__name__': '__main__', '__file__': str(path),
                     'ADAPTER_ORIGIN': ORIGIN, 'ADAPTER_STARTUP_GUARD': adapter_startup_guard}
        try:
            exec(code, namespace)
        except SystemExit as error:
            need(type(error.code) is int and error.code == 0, 'original observer natural integer zero')
            success = True
        need(success and time.monotonic() < whole and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
             and signal.getsignal(signal.SIGALRM) is expired
             and all(signal.getsignal(n) is INITIAL_HANDLERS[n] for n in (signal.SIGTERM, signal.SIGINT))
             and ''.join(terminal.parts) == '', 'silent original complete observer and cleanup before original whole deadline')
    except BaseException as error:
        primary = error; success = False
        raise
    finally:
        failures = []
        for name, value in (('argv', old_argv), ('stdout', old_stdout)):
            try:
                setattr(sys, name, value)
            except BaseException as error:
                failures.append(error)
        try:
            signal.signal(signal.SIGALRM, expired)
            left = (whole if success and not failures else outer) - time.monotonic()
            need(left > 0, 'positive original postflight or failure-cleanup remainder')
            signal.setitimer(signal.ITIMER_REAL, left)
        except BaseException as error:
            failures.append(error)
        if failures:
            if primary is not None:
                primary.add_note('Independent invoke restoration uncertainty: ' + ','.join(type(e).__name__ for e in failures))
            else:
                raise ValueError('Independent invoke restoration failed') from failures[0]


def outcome(captures, selected, binding, bodies, output, whole, outer, selection):
    source = binding['controller_source']
    raw = captures.read(literal(str(output) + '.observer'), 8192)
    need(len(raw) == 8192, 'fixed durable external observer slot')
    observed = parse(raw)
    need(observed.get('schema') == 'neural035_full14_external_v1'
         and observed.get('status') == 'complete_unqualified' and observed.get('source') == source
         and observed.get('selection') == selected[1] and observed.get('attempt') == str(output)
         and observed.get('error_type') is None, 'exact complete original observer identity')
    for key, expected in (('origin_monotonic', ORIGIN), ('whole_deadline', whole), ('outer_deadline', outer)):
        need(type(observed.get(key)) in (int, float) and math.isfinite(observed[key])
             and observed[key] == expected, 'unchanged original clock endpoint')
    need(observed.get('full14_source_scope') is True
         and all(observed.get(k) is False for k in ('scientific_qualified', 'runtime_qualified', 'grading_performed',
                  'nested_native_recovery_may_be_required', 'automatic_retry')), 'complete unqualified custody only')
    child = observed['child']
    need(type(child) is dict and type(child.get('exit_code')) is int and child['exit_code'] == 0
         and all(child.get(k) is True for k in ('natural_exit', 'process_reaped', 'process_group_absent', 'streams_closed'))
         and all(child.get(k) is False for k in ('timed_out', 'kill_sent'))
         and all(child.get(k) is None for k in ('error_type', 'timer_disable_error', 'timer_restore_error')),
         'original unforced error-free worker closure')
    outputs = observed['outputs']
    need(type(outputs) is dict and set(outputs) == {'candidate', 'operator'}, 'both complete output identities')
    for value in outputs.values(): descriptor(value, PREDICTION_CAP)
    complete_pin = descriptor(observed['complete'], 32768)
    complete = parse(captures.read(output / 'COMPLETE.json', 32768, complete_pin))
    need(complete.get('schema') == 'neural035_full14_complete_v1'
         and complete.get('status') == 'complete_unqualified' and complete.get('source') == source
         and all(type(complete.get(k)) is int and complete[k] == v for k, v in
                 (('outputs', 2), ('query_blocks_per_output', 28), ('sessions', 14), ('biological_mice', 7), ('cells', 1012)))
         and complete.get('all_views_retired') is True and complete.get('external_natural_zero_required') is True
         and all(complete.get(k) is False for k in ('private_grading_performed', 'target_bodies_opened',
                  'runtime_qualified', 'scientific_qualified')), 'same complete14/7/1012/28 result without grading')
    expected_programs = {'candidate': {k: selection['program'][k] for k in ('bytes', 'sha256')},
                         'operator': pin(bodies['baseline_program.py'])}
    need(equal(complete.get('programs'), expected_programs), 'selected candidate and exact separately fixed operator')
    rows = complete['contexts']
    need(type(rows) is list and len(rows) == 2, 'two complete original contexts')
    for index, role in enumerate(('candidate', 'operator')):
        row = rows[index]
        need(type(row) is dict and type(row.get('case')) is int and row['case'] == index
             and row.get('role') == role and row.get('native_closed') is True
             and row.get('prediction') == outputs[role], 'same complete original role/output metadata')
        descriptor(row['native_receipt'], 262144)
    commitment_pin = descriptor(complete['commitment'], 8192)
    commitment = parse(captures.read(output / 'commitment/COMMITMENT.json', 8192, commitment_pin))
    need(commitment.get('schema') == 'neural035_program_commitment_v1' and commitment.get('source') == source
         and equal(commitment.get('programs'), expected_programs) and commitment.get('before_any_public_view') is True
         and commitment.get('method_review') == {k: selection['method_review'][k] for k in ('bytes', 'sha256')}, 'same original pre-public commitment and method authority')
    descriptor(complete['public_manifest'], 2000000); descriptor(complete['retirement'], 16384)
    return {'external': pin(raw), 'complete': complete_pin, 'outputs': outputs, 'commitment': commitment_pin,
            'scope': SCOPE, 'original_observer_full_body_validation_required': True,
            'adapter_replays_prediction_or_target_bodies': False}


def main(argv=None):
    global FINAL_END
    end = ORIGIN + 120; result = 2
    if not INITIAL_HANDLERS:
        return 2
    try:
        startup_owned()
        parser = argparse.ArgumentParser(description=__doc__)
        for name in ('program', 'output', 'review', 'source-sha256'):
            parser.add_argument('--' + name, required=True)
        for name in ('source-bytes', 'other-reserve-bytes'):
            parser.add_argument('--' + name, required=True, type=int)
        args = parser.parse_args(argv)
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
             'isolated nonwriting adapter entry')
        cache = literal(sys.pycache_prefix)
        need(not os.path.lexists(cache), 'fresh absent disabled bytecode prefix')
        captures = Captures(end)
        expected = descriptor({'bytes': args.source_bytes, 'sha256': args.source_sha256}, 32768)
        binding = own_sources(captures, expected)
        compiled, path, bodies = target(captures, binding)
        selected, operand_row, metadata_pins = bind(args, captures, expected, binding)
        whole = ORIGIN + selected['whole_seconds']; outer = whole + 60
        end = outer; FINAL_END = outer
        output = literal(args.output)
        invoke(compiled, path, operand_row, binding['controller_source'], whole, outer, output)
        # Success retains the original whole deadline; outer60 is failure cleanup only.
        end = whole; FINAL_END = whole; captures.end = whole
        completed = outcome(captures, operand_row, binding, bodies, output, whole, outer, selected)
        for source_path, identity, cap in metadata_pins:
            captures.read(source_path, cap, identity)
        need(equal(own_sources(captures, expected), binding), 'same adapter source after complete observation')
        target(captures, binding)
        need(sys.pycache_prefix == str(cache) and not os.path.lexists(cache), 'same absent bytecode prefix')
        captures.tick()
        value = {'schema': 'neural035_full14_unscored_result_v1', 'task_id': TASK, 'status': 'complete_unscored',
                 'context_count': 2, 'query_records_per_output': 28, 'controller_result': completed,
                 'adapter_source': expected, 'controller_source': binding['controller_source'],
                 'private_grading_authorized': False, 'private_grading_performed': False,
                 'runtime_qualified': False, 'scientific_qualified': False,
                 'adapter_metadata_read_reserved_bytes': captures.reserved,
                 'requires_observed_adapter_exit_zero': True}
        raw = encode(value)
        need(len(raw) + 1 <= 8192, 'bounded unscored adapter terminal')
        print(raw.decode(), flush=True); captures.tick(); result = 0
    except BaseException:
        result = 2
    finally:
        if not restore_handlers():
            result = 2
        if time.monotonic() >= end:
            result = 2
    return result


if __name__ == '__main__':
    result = main()
    if time.monotonic() >= FINAL_END:
        result = 2
    raise SystemExit(result)
